-- MIGRATION 006 FINANCE : installation contrôlée après sauvegarde, tests obligatoires.
-- Ne pas activer de règlements/lettrages réels dans Streamlit avant validation SQL.
-- Ce module ne constitue pas une comptabilité générale complète.
-- Fonctions appelées via la clé service_role dédiée côté Streamlit.
-- Les privilèges sur la clé de service et la couche applicative sont critiques.
BEGIN;

CREATE TABLE IF NOT EXISTS public.erp_finance_operations (
    operation_id text PRIMARY KEY,
    action text NOT NULL CHECK (action IN ('ACCOUNT','PAYMENT','ALLOCATE')),
    request_payload jsonb NOT NULL,
    result_payload jsonb,
    created_at timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE IF NOT EXISTS public.erp_finance_outbox (
    operation_id text PRIMARY KEY REFERENCES public.erp_finance_operations(operation_id),
    payload jsonb NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    synced_at timestamptz
);

-- Ne pas exposer la journalisation des opérations financières aux sessions clientes.
ALTER TABLE public.erp_finance_operations ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.erp_finance_outbox ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS erp_finance_operations_service_only ON public.erp_finance_operations;
CREATE POLICY erp_finance_operations_service_only
    ON public.erp_finance_operations FOR ALL TO service_role USING (true) WITH CHECK (true);
DROP POLICY IF EXISTS erp_finance_outbox_service_only ON public.erp_finance_outbox;
CREATE POLICY erp_finance_outbox_service_only
    ON public.erp_finance_outbox FOR ALL TO service_role USING (true) WITH CHECK (true);

CREATE OR REPLACE FUNCTION public.erp_finance_transaction(
    p_action text, p_operation_id text, p_payload jsonb
) RETURNS jsonb
LANGUAGE plpgsql
SECURITY INVOKER
SET search_path = pg_catalog, public
AS $body$
DECLARE
    v_previous record;
    v_account record;
    v_payment record;
    v_invoice record;
    v_result jsonb;
    v_account_id text;
    v_reg_id text;
    v_letter_id text;
    v_cash_id text;
    v_counter_id text;
    v_cash_type text;
    v_counter_type text;
    v_amount numeric;
    v_balance numeric;
    v_applied numeric;
    v_invoice_applied numeric;
    v_montant_ttc numeric;
    v_doc_type text;
    v_doc_id text;
    v_direction text;
    v_date text;
    v_count integer;
BEGIN
    IF p_action IS NULL OR p_action NOT IN ('ACCOUNT','PAYMENT','ALLOCATE')
       OR p_operation_id IS NULL OR length(btrim(p_operation_id))=0 OR length(p_operation_id)>128
       OR p_payload IS NULL OR jsonb_typeof(p_payload) IS DISTINCT FROM 'object' THEN
        RAISE EXCEPTION 'Transaction Finance invalide' USING ERRCODE='22023';
    END IF;
    INSERT INTO public.erp_finance_operations(operation_id,action,request_payload)
      VALUES(p_operation_id,p_action,p_payload) ON CONFLICT(operation_id) DO NOTHING;
    SELECT action,request_payload,result_payload INTO v_previous
      FROM public.erp_finance_operations WHERE operation_id=p_operation_id FOR UPDATE;
    IF v_previous.action IS DISTINCT FROM p_action
       OR v_previous.request_payload IS DISTINCT FROM p_payload THEN
        RAISE EXCEPTION 'operation_id déjà utilisé avec un autre contenu' USING ERRCODE='23505';
    END IF;
    IF v_previous.result_payload IS NOT NULL THEN RETURN v_previous.result_payload; END IF;

    IF p_action='ACCOUNT' THEN
        IF nullif(btrim(p_payload->>'nom_compte'),'') IS NULL
           OR length(p_payload->>'nom_compte')>200
           OR nullif(btrim(p_payload->>'type_compte'),'') IS NULL
           OR length(p_payload->>'type_compte')>200
           OR nullif(btrim(p_payload->>'numero_compte'),'') IS NULL
           OR length(p_payload->>'numero_compte')>200
           OR lower(btrim(p_payload->>'type_compte')) NOT IN
              ('banque', 'caisse', 'tiers client', 'tiers fournisseur') THEN
            RAISE EXCEPTION 'Informations ou type de compte invalides' USING ERRCODE='22023';
        END IF;
        v_amount := (p_payload->>'solde_initial')::numeric;
        IF v_amount IS NULL OR v_amount::text IN ('NaN','Infinity','-Infinity')
           OR abs(v_amount)>=1000000000000000 OR v_amount<>round(v_amount,2) THEN
            RAISE EXCEPTION 'Solde initial invalide' USING ERRCODE='22023';
        END IF;
        -- Empêche les doublons de numéro en sérialisant les créations.
        PERFORM pg_advisory_xact_lock(hashtextextended('erp:finance:account_number',0));
        PERFORM 1 FROM public.comptes WHERE numero_compte=p_payload->>'numero_compte';
        IF FOUND THEN RAISE EXCEPTION 'Numéro de compte existant' USING ERRCODE='23505'; END IF;
        v_account_id := 'CPT-' || gen_random_uuid()::text;
        INSERT INTO public.comptes(compte_id,nom_compte,type_compte,numero_compte,solde_initial,statut)
        VALUES(v_account_id,p_payload->>'nom_compte',p_payload->>'type_compte',
               p_payload->>'numero_compte',v_amount,'OUI');
        v_result := jsonb_build_object('operation_id',p_operation_id,'action',p_action,
                                       'compte_id',v_account_id);

    ELSIF p_action='PAYMENT' THEN
        v_amount := (p_payload->>'montant_total')::numeric;
        v_date := p_payload->>'date_reglement';
        v_direction := p_payload->>'type_flux';
        v_cash_id := p_payload->>'compte_id';
        v_counter_id := p_payload->>'contrepartie_compte_id';
        IF v_direction IS NULL OR v_direction NOT IN ('ENCAISSEMENT','DECAISSEMENT')
           OR v_amount IS NULL OR v_amount::text IN ('NaN','Infinity','-Infinity')
           OR v_amount<=0 OR v_amount>=1000000000000000 OR v_amount<>round(v_amount,2)
           OR v_date IS NULL OR v_date !~ '^\d{4}-\d{2}-\d{2}$'
           OR to_char(to_date(v_date,'YYYY-MM-DD'),'YYYY-MM-DD') IS DISTINCT FROM v_date
           OR nullif(btrim(v_cash_id),'') IS NULL OR length(v_cash_id)>200
           OR nullif(btrim(v_counter_id),'') IS NULL OR length(v_counter_id)>200
           OR v_cash_id=v_counter_id
           OR nullif(btrim(p_payload->>'partenaire_id'),'') IS NULL
           OR length(p_payload->>'partenaire_id')>200
           OR nullif(btrim(p_payload->>'mode_paiement'),'') IS NULL
           OR length(p_payload->>'mode_paiement')>200
           OR nullif(btrim(p_payload->>'reference_trace'),'') IS NULL
           OR length(p_payload->>'reference_trace')>200 THEN
            RAISE EXCEPTION 'Règlement invalide' USING ERRCODE='22023';
        END IF;
        -- Verrouillage dans un ordre déterministe pour éviter les interblocages.
        SELECT count(*) INTO v_count FROM (
            SELECT compte_id FROM public.comptes
            WHERE compte_id IN (v_cash_id,v_counter_id) AND statut='OUI'
            ORDER BY compte_id FOR UPDATE
        ) locked_accounts;
        IF v_count<>2 THEN RAISE EXCEPTION 'Un compte est inexistant ou inactif' USING ERRCODE='23503'; END IF;
        SELECT lower(btrim(type_compte)) INTO v_cash_type FROM public.comptes WHERE compte_id=v_cash_id;
        SELECT lower(btrim(type_compte)) INTO v_counter_type FROM public.comptes WHERE compte_id=v_counter_id;
        IF v_cash_type IS NULL OR v_cash_type NOT IN ('banque', 'caisse') THEN
             RAISE EXCEPTION 'Le compte de trésorerie doit être une Banque ou Caisse' USING ERRCODE='23514';
         END IF;
        IF v_counter_type IS NULL OR
            (v_direction='ENCAISSEMENT' AND v_counter_type NOT IN ('tiers client','client','clients')) OR
            (v_direction='DECAISSEMENT' AND v_counter_type NOT IN ('tiers fournisseur','fournisseur','fournisseurs')) THEN
             RAISE EXCEPTION 'Type de compte de contrepartie incompatible avec le flux' USING ERRCODE='23514';
         END IF;
        -- Le partenaire doit exister et être actif, indépendamment des contrôles Streamlit.
        IF v_direction='ENCAISSEMENT' THEN
             PERFORM 1 FROM public.clients
               WHERE client_id=p_payload->>'partenaire_id' AND actif='OUI';
         ELSE
             PERFORM 1 FROM public.fournisseurs
               WHERE fournisseur_id=p_payload->>'partenaire_id' AND actif='OUI';
         END IF;
        IF NOT FOUND THEN RAISE EXCEPTION 'Partenaire inexistant ou inactif' USING ERRCODE='23503'; END IF;
        -- Empêche un deuxième règlement portant la même référence bancaire
        -- sur un même compte, même si une interface recrée un operation_id.
        -- Les paiements par espèces doivent eux aussi recevoir une référence unique.
        PERFORM pg_advisory_xact_lock(hashtextextended(
            'erp:finance:payment:' || v_cash_id || ':' || (p_payload->>'reference_trace'), 0));
        PERFORM 1 FROM public.reglements
          WHERE compte_id=v_cash_id AND reference_trace=p_payload->>'reference_trace';
        IF FOUND THEN
            RAISE EXCEPTION 'Référence de règlement déjà enregistrée sur ce compte'
              USING ERRCODE='23505';
        END IF;
        v_reg_id := 'REGF-'||gen_random_uuid()::text;
        INSERT INTO public.reglements(reglement_id,date_reglement,type_flux,partenaire_id,
           compte_id,mode_paiement,reference_trace,montant_total,montant_alloue,statut)
        VALUES(v_reg_id,v_date,v_direction,p_payload->>'partenaire_id',v_cash_id,
           p_payload->>'mode_paiement',p_payload->>'reference_trace',v_amount,0,'VALIDE');
        INSERT INTO public.ecritures_comptables(ecriture_id,date_ecriture,compte_id,
                  document_source_id,libelle,debit,credit,lettrage_id)
        VALUES('ECR-'||gen_random_uuid()::text,v_date,v_cash_id,v_reg_id,
               v_direction||' '||p_payload->>'reference_trace',
               CASE WHEN v_direction='ENCAISSEMENT' THEN v_amount ELSE 0 END,
               CASE WHEN v_direction='DECAISSEMENT' THEN v_amount ELSE 0 END,'');
        INSERT INTO public.ecritures_comptables(ecriture_id,date_ecriture,compte_id,
                  document_source_id,libelle,debit,credit,lettrage_id)
        VALUES('ECR-'||gen_random_uuid()::text,v_date,v_counter_id,v_reg_id,
               'Contrepartie '||p_payload->>'reference_trace',
               CASE WHEN v_direction='DECAISSEMENT' THEN v_amount ELSE 0 END,
               CASE WHEN v_direction='ENCAISSEMENT' THEN v_amount ELSE 0 END,'');
        v_result := jsonb_build_object('operation_id',p_operation_id,'action',p_action,
                      'reglement_id',v_reg_id,'montant_total',v_amount,'nombre_ecritures',2);

    ELSIF p_action='ALLOCATE' THEN
        v_amount := (p_payload->>'montant_applique')::numeric;
        v_doc_type := p_payload->>'type_document';
        v_doc_id := p_payload->>'document_id';
        IF v_amount IS NULL OR v_amount::text IN ('NaN','Infinity','-Infinity')
           OR v_amount<=0 OR v_amount>=1000000000000000 OR v_amount<>round(v_amount,2)
           OR v_doc_type NOT IN ('FactureClient','FactureFournisseur') OR v_doc_type IS NULL
           OR nullif(btrim(v_doc_id),'') IS NULL OR length(v_doc_id)>200
           OR nullif(btrim(p_payload->>'reglement_id'),'') IS NULL
           OR length(p_payload->>'reglement_id')>200 THEN
            RAISE EXCEPTION 'Lettrage invalide' USING ERRCODE='22023';
        END IF;
        SELECT * INTO v_payment FROM public.reglements
          WHERE reglement_id=p_payload->>'reglement_id' FOR UPDATE;
        IF NOT FOUND OR v_payment.statut IS DISTINCT FROM 'VALIDE' THEN
            RAISE EXCEPTION 'Règlement inexistant ou invalide' USING ERRCODE='23503';
        END IF;
        IF (v_doc_type='FactureClient' AND v_payment.type_flux IS DISTINCT FROM 'ENCAISSEMENT')
           OR (v_doc_type='FactureFournisseur' AND v_payment.type_flux IS DISTINCT FROM 'DECAISSEMENT') THEN
            RAISE EXCEPTION 'Sens du règlement incompatible avec le document' USING ERRCODE='23514';
        END IF;
        SELECT coalesce(sum(montant_applique),0) INTO v_applied
          FROM public.lettrage WHERE reglement_id=v_payment.reglement_id;
        IF v_applied IS DISTINCT FROM coalesce(v_payment.montant_alloue,0)
           OR v_payment.montant_total IS NULL OR v_payment.montant_total<=0
           OR v_payment.montant_total<>round(v_payment.montant_total,2)
           OR v_applied<0 OR v_applied+v_amount>v_payment.montant_total THEN
            RAISE EXCEPTION 'Solde règlement incohérent ou insuffisant' USING ERRCODE='23514';
        END IF;
        IF v_doc_type='FactureClient' THEN
            SELECT * INTO v_invoice FROM public.factures WHERE facture_id=v_doc_id FOR UPDATE;
            IF NOT FOUND OR v_invoice.statut IS DISTINCT FROM 'VALIDE'
               OR v_invoice.type_facture IS DISTINCT FROM 'FactureClient'
               OR v_invoice.client_id IS DISTINCT FROM v_payment.partenaire_id THEN
                RAISE EXCEPTION 'Facture client non payable ou client différent' USING ERRCODE='23514';
            END IF;
        ELSE
            SELECT * INTO v_invoice FROM public.factures_fournisseurs
              WHERE facture_fournisseur_id=v_doc_id FOR UPDATE;
            IF NOT FOUND OR v_invoice.fournisseur_id IS DISTINCT FROM v_payment.partenaire_id
               OR upper(btrim(coalesce(v_invoice.statut_paiement,''))) IN ('','ANNULE','REJETE','PAYEE') THEN
                RAISE EXCEPTION 'Facture fournisseur non payable ou fournisseur différent' USING ERRCODE='23514';
            END IF;
        END IF;
        v_montant_ttc := v_invoice.montant_ttc;
        SELECT coalesce(sum(montant_applique),0) INTO v_invoice_applied FROM public.lettrage
          WHERE type_document=v_doc_type AND document_id=v_doc_id;
        IF v_montant_ttc IS NULL OR v_montant_ttc<=0 OR v_montant_ttc>=1000000000000000
           OR v_montant_ttc<>round(v_montant_ttc,2)
           OR v_invoice_applied<0 OR v_invoice_applied+v_amount>v_montant_ttc THEN
            RAISE EXCEPTION 'Facture déjà réglée ou montant de règlement supérieur' USING ERRCODE='23514';
        END IF;
        IF v_doc_type='FactureClient' AND
           v_invoice_applied IS DISTINCT FROM coalesce(v_invoice.montant_paye,0) THEN
            RAISE EXCEPTION 'Facture client : montant payé incohérent avec les lettrages' USING ERRCODE='23514';
        END IF;
        v_letter_id := 'LET-'||gen_random_uuid()::text;
        INSERT INTO public.lettrage(lettrage_id,date,reglement_id,document_id,type_document,montant_applique)
        VALUES(v_letter_id,to_char(now() AT TIME ZONE 'UTC','YYYY-MM-DD'),
               v_payment.reglement_id,v_doc_id,v_doc_type,v_amount);
        UPDATE public.reglements SET montant_alloue=v_applied+v_amount
         WHERE reglement_id=v_payment.reglement_id;
        IF v_doc_type='FactureClient' THEN
            -- NE PAS passer la facture à PAYEE / PARTIELLE : le cycle Ventes dépend
            -- du statut commercial VALIDE pour les avoirs et les annulations.
            UPDATE public.factures SET montant_paye=v_invoice_applied+v_amount
             WHERE facture_id=v_doc_id;
        ELSE
            UPDATE public.factures_fournisseurs
               SET statut_paiement=CASE WHEN v_invoice_applied+v_amount=v_montant_ttc
                                      THEN 'PAYEE' ELSE 'PARTIELLE' END
             WHERE facture_fournisseur_id=v_doc_id;
        END IF;
        v_result := jsonb_build_object('operation_id',p_operation_id,'action',p_action,
             'lettrage_id',v_letter_id,'reglement_id',v_payment.reglement_id,
             'document_id',v_doc_id,'montant_alloue',v_amount);
    END IF;

    UPDATE public.erp_finance_operations SET result_payload=v_result WHERE operation_id=p_operation_id;
    INSERT INTO public.erp_finance_outbox(operation_id,payload)
      VALUES(p_operation_id,jsonb_build_object('action',p_action,'result',v_result));
    RETURN v_result;
END;
$body$;

REVOKE ALL ON FUNCTION public.erp_finance_transaction(text,text,jsonb) FROM PUBLIC, anon, authenticated;
GRANT EXECUTE ON FUNCTION public.erp_finance_transaction(text,text,jsonb) TO service_role;
REVOKE ALL ON public.erp_finance_operations,public.erp_finance_outbox FROM PUBLIC,anon,authenticated;
GRANT SELECT,INSERT,UPDATE ON public.erp_finance_operations,public.erp_finance_outbox TO service_role;
COMMIT;
