-- INSTALLATION CONTROLEE : apres sql/002_atomic_stock_movement_supabase_securise.sql.
-- Ne pas appliquer avant audit et sauvegarde ; tester avec ROLLBACK avant toute utilisation reelle.
-- Montants de commande dans leur devise ; stock valorise en DZD via taux_change (DZD/devise).
-- Pour une meme MP commandee sur plusieurs lignes, prix d'entree = moyenne ponderee de la commande.
-- Conditionnements non convertis : unite_cond = unite_stock et qte_cond = qte_totale.
-- RPC SECURITY INVOKER, tables techniques RLS, execution service_role seulement.
BEGIN;

CREATE TABLE IF NOT EXISTS public.erp_purchase_operations (
    operation_id text PRIMARY KEY,
    operation_type text NOT NULL CHECK (operation_type IN ('ORDER', 'RECEIPT')),
    request_payload jsonb NOT NULL,
    result_payload jsonb,
    created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS public.erp_purchase_outbox (
    operation_id text PRIMARY KEY REFERENCES public.erp_purchase_operations(operation_id),
    payload jsonb NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    synced_at timestamptz
);

ALTER TABLE public.erp_purchase_operations ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.erp_purchase_outbox ENABLE ROW LEVEL SECURITY;

CREATE OR REPLACE FUNCTION public.erp_create_purchase_order(
    p_operation_id text,
    p_order_id text,
    p_fournisseur_id text,
    p_type_achat text,
    p_devise text,
    p_taux_change numeric,
    p_mode_paiement text,
    p_delai_paiement text,
    p_date_voulue text,
    p_lines jsonb
) RETURNS jsonb
LANGUAGE plpgsql
SECURITY INVOKER
SET search_path = pg_catalog, public
AS $body$
DECLARE
    v_line record;
    v_mp_unit text;
    v_request jsonb;
    v_saved_request jsonb;
    v_saved_result jsonb;
    v_saved_type text;
    v_total numeric := 0;
    v_count integer := 0;
    v_result jsonb;
    v_now text := to_char(now() AT TIME ZONE 'UTC', 'YYYY-MM-DD');
BEGIN
    IF p_operation_id IS NULL OR length(btrim(p_operation_id)) = 0 OR length(p_operation_id) > 128
       OR p_order_id IS NULL OR length(btrim(p_order_id)) = 0 OR length(p_order_id) > 200
       OR p_fournisseur_id IS NULL OR length(btrim(p_fournisseur_id)) = 0 OR length(p_fournisseur_id) > 200
       OR p_type_achat IS NULL OR length(btrim(p_type_achat)) = 0 OR length(p_type_achat) > 200
       OR p_devise IS NULL OR length(btrim(p_devise)) = 0 OR length(p_devise) > 30
       OR p_mode_paiement IS NULL OR length(p_mode_paiement) > 200
       OR p_delai_paiement IS NULL OR length(p_delai_paiement) > 200
       OR p_date_voulue IS NULL OR length(p_date_voulue) > 40 THEN
        RAISE EXCEPTION 'Champs obligatoires commande incorrects' USING ERRCODE='22023';
    END IF;
    IF p_taux_change IS NULL OR p_taux_change::text IN ('NaN','Infinity','-Infinity')
       OR p_taux_change <= 0 OR p_taux_change >= 1000000000000000 THEN
        RAISE EXCEPTION 'Taux de change incorrect' USING ERRCODE='22023';
    END IF;
    -- Le stock est valorise en DZD : 1 DZD doit toujours donner 1 DZD.
    IF upper(btrim(p_devise)) = 'DZD' AND p_taux_change <> 1 THEN
        RAISE EXCEPTION 'Pour la devise DZD, taux_change doit etre egal a 1' USING ERRCODE='22023';
    END IF;
    IF p_lines IS NULL OR jsonb_typeof(p_lines) <> 'array'
       OR jsonb_array_length(p_lines) < 1 OR jsonb_array_length(p_lines) > 500 THEN
        RAISE EXCEPTION 'La commande requiert entre 1 et 500 lignes' USING ERRCODE='22023';
    END IF;

    -- request_payload exclut l'ID documentaire généré en Python : une répétition
    -- avec le même operation_id reste idempotente après un timeout réseau.
    v_request := jsonb_build_object('fournisseur',p_fournisseur_id,
        'type',p_type_achat,'devise',p_devise,'change',p_taux_change,
        'mode_paiement',p_mode_paiement,'delai_paiement',p_delai_paiement,
        'date_voulue',p_date_voulue,'lignes',
        (SELECT jsonb_agg(e.item - 'ligne_achat_id' ORDER BY e.ord)
         FROM jsonb_array_elements(p_lines) WITH ORDINALITY AS e(item,ord)));
    INSERT INTO public.erp_purchase_operations(operation_id, operation_type, request_payload)
    VALUES (p_operation_id,'ORDER',v_request)
    ON CONFLICT (operation_id) DO NOTHING;
    SELECT operation_type,request_payload,result_payload
      INTO v_saved_type,v_saved_request,v_saved_result
      FROM public.erp_purchase_operations WHERE operation_id=p_operation_id FOR UPDATE;
    IF v_saved_type <> 'ORDER' OR v_saved_request IS DISTINCT FROM v_request THEN
        RAISE EXCEPTION 'operation_id réutilisé avec un autre contenu' USING ERRCODE='23505';
    END IF;
    IF v_saved_result IS NOT NULL THEN RETURN v_saved_result; END IF;

    PERFORM 1 FROM public.fournisseurs WHERE fournisseur_id=p_fournisseur_id;
    IF NOT FOUND THEN RAISE EXCEPTION 'Fournisseur introuvable' USING ERRCODE='23503'; END IF;

    FOR v_line IN SELECT * FROM jsonb_to_recordset(p_lines) AS x(
       ligne_achat_id text, mp_id text, unite_cond text, qte_cond numeric,
       qte_totale numeric, prix_unitaire numeric, total_devise numeric)
    LOOP
        IF v_line.ligne_achat_id IS NULL OR length(btrim(v_line.ligne_achat_id))=0
           OR length(v_line.ligne_achat_id)>200
           OR v_line.mp_id IS NULL OR length(btrim(v_line.mp_id))=0 OR length(v_line.mp_id)>200
           OR v_line.unite_cond IS NULL OR length(btrim(v_line.unite_cond))=0 OR length(v_line.unite_cond)>200
           OR v_line.qte_cond IS NULL OR v_line.qte_cond::text IN ('NaN','Infinity','-Infinity')
           OR v_line.qte_cond <= 0 OR v_line.qte_cond >= 1000000000000000
           OR v_line.qte_totale IS NULL OR v_line.qte_totale::text IN ('NaN','Infinity','-Infinity')
           OR v_line.qte_totale <= 0 OR v_line.qte_totale >= 1000000000000000
           OR v_line.prix_unitaire IS NULL OR v_line.prix_unitaire::text IN ('NaN','Infinity','-Infinity')
           OR v_line.prix_unitaire < 0 OR v_line.prix_unitaire >= 1000000000000000
           OR v_line.total_devise IS NULL OR v_line.total_devise::text IN ('NaN','Infinity','-Infinity')
           OR v_line.total_devise < 0 OR v_line.total_devise >= 1000000000000000 THEN
            RAISE EXCEPTION 'Ligne de commande invalide' USING ERRCODE='22023';
        END IF;
        -- L'ecran actuel achete en unites de STOCK, pas en cartons/sacs a convertir.
        -- Tant qu'un vrai facteur de conditionnement n'est pas modele : fail closed.
        IF v_line.qte_cond IS DISTINCT FROM v_line.qte_totale THEN
            RAISE EXCEPTION 'Conversion de conditionnement Achats non prise en charge' USING ERRCODE='22023';
        END IF;
        SELECT unite_stock INTO v_mp_unit FROM public.matieres_premieres WHERE mp_id=v_line.mp_id;
        IF NOT FOUND THEN RAISE EXCEPTION 'MP commande inexistante' USING ERRCODE='23503'; END IF;
        IF v_mp_unit IS NULL OR btrim(v_mp_unit) = ''
           OR upper(btrim(v_line.unite_cond)) <> upper(btrim(v_mp_unit)) THEN
            RAISE EXCEPTION 'Unite de commande differente de unite_stock pour %',v_line.mp_id USING ERRCODE='22023';
        END IF;
        -- total_devise est un montant, pas une valeur libre. Tolerance = 1 centime
        -- pour les arrondis d'affichage en devises (flottants depuis Streamlit).
        IF abs(v_line.total_devise - v_line.qte_totale * v_line.prix_unitaire) > 0.01 THEN
            RAISE EXCEPTION 'Total ligne incompatible avec prix * quantite pour %',v_line.mp_id USING ERRCODE='22023';
        END IF;
        v_total := v_total + v_line.total_devise;
        v_count := v_count + 1;
    END LOOP;
    IF v_count <> jsonb_array_length(p_lines) OR v_total >= 1000000000000000
       OR v_total * p_taux_change >= 1000000000000000 THEN
        RAISE EXCEPTION 'Total commande incorrect ou hors limites' USING ERRCODE='22023';
    END IF;

    INSERT INTO public.commandes_achats(
      commande_achat_id,date_commande,fournisseur_id,type_achat,devise,taux_change,
      montant_total_devise,montant_total_local,mode_paiement,delai_paiement,date_voulue,statut)
    VALUES(p_order_id,v_now,p_fournisseur_id,p_type_achat,p_devise,p_taux_change,
      v_total,v_total*p_taux_change,p_mode_paiement,p_delai_paiement,p_date_voulue,'EN_ATTENTE');

    INSERT INTO public.lignes_achats(
      ligne_achat_id,commande_achat_id,mp_id,unite_cond,qte_cond,qte_totale,prix_unitaire,total_devise)
    SELECT x.ligne_achat_id,p_order_id,x.mp_id,x.unite_cond,x.qte_cond,
      x.qte_totale,x.prix_unitaire,x.total_devise
      FROM jsonb_to_recordset(p_lines) AS x(
        ligne_achat_id text, mp_id text, unite_cond text, qte_cond numeric,
        qte_totale numeric, prix_unitaire numeric, total_devise numeric);

    v_result := jsonb_build_object('operation_id',p_operation_id,
      'commande_achat_id',p_order_id,'nombre_lignes',v_count,'montant_total_devise',v_total);
    UPDATE public.erp_purchase_operations SET result_payload=v_result WHERE operation_id=p_operation_id;
    INSERT INTO public.erp_purchase_outbox(operation_id,payload)
      VALUES(p_operation_id,jsonb_build_object('type','ORDER','result',v_result));
    RETURN v_result;
END;
$body$;

CREATE OR REPLACE FUNCTION public.erp_receive_purchase_order(
    p_operation_id text,
    p_br_id text,
    p_commande_achat_id text,
    p_date_reception text,
    p_controle_conformite text,
    p_remarques text,
    p_date_peremption text,
    p_lines jsonb
) RETURNS jsonb
LANGUAGE plpgsql
SECURITY INVOKER
SET search_path = pg_catalog, public
AS $body$
DECLARE
    v_line record;
    v_order record;
    v_request jsonb;
    v_saved_request jsonb;
    v_saved_result jsonb;
    v_saved_type text;
    v_ordered numeric;
    v_received numeric;
    v_qty numeric;
    v_price numeric;
    v_order_price_total numeric;
    v_lot jsonb;
    v_complete boolean;
    v_count integer := 0;
    v_result jsonb;
BEGIN
    IF p_operation_id IS NULL OR length(btrim(p_operation_id))=0 OR length(p_operation_id)>128
       OR p_br_id IS NULL OR length(btrim(p_br_id))=0 OR length(p_br_id)>200
       OR p_commande_achat_id IS NULL OR length(btrim(p_commande_achat_id))=0
       OR length(p_commande_achat_id)>200
       OR p_date_reception IS NULL OR length(btrim(p_date_reception))=0 OR length(p_date_reception)>40
       OR p_controle_conformite IS DISTINCT FROM 'OUI'
       OR p_remarques IS NULL OR length(p_remarques)>5000
       OR p_date_peremption IS NULL OR length(p_date_peremption)>40 THEN
        RAISE EXCEPTION 'Champs de réception incorrects ou non conformes' USING ERRCODE='22023';
    END IF;
    IF p_lines IS NULL OR jsonb_typeof(p_lines)<>'array'
       OR jsonb_array_length(p_lines)<1 OR jsonb_array_length(p_lines)>500 THEN
        RAISE EXCEPTION 'La réception requiert entre 1 et 500 lignes' USING ERRCODE='22023';
    END IF;

    -- Lock order FIRST: concurrent receipts for one BC are serialized.
    SELECT commande_achat_id, statut, devise, taux_change INTO v_order FROM public.commandes_achats
      WHERE commande_achat_id=p_commande_achat_id FOR UPDATE;
    IF NOT FOUND THEN RAISE EXCEPTION 'Commande achat inexistante' USING ERRCODE='23503'; END IF;
    IF v_order.taux_change IS NULL OR v_order.taux_change::text IN ('NaN','Infinity','-Infinity')
       OR v_order.taux_change<=0 OR v_order.taux_change>=1000000000000000
       OR v_order.devise IS NULL OR btrim(v_order.devise)=''
       OR (upper(btrim(v_order.devise))='DZD' AND v_order.taux_change<>1) THEN
        RAISE EXCEPTION 'Devise ou taux de change de la commande invalide' USING ERRCODE='22023';
    END IF;

    v_request := jsonb_build_object('commande_achat_id',p_commande_achat_id,
      'date',p_date_reception,'conformite',p_controle_conformite,
      'remarques',p_remarques,'date_peremption',p_date_peremption,'lignes',
      (SELECT jsonb_agg(e.item - 'ligne_br_id' ORDER BY e.ord)
       FROM jsonb_array_elements(p_lines) WITH ORDINALITY AS e(item,ord)));
    INSERT INTO public.erp_purchase_operations(operation_id,operation_type,request_payload)
      VALUES(p_operation_id,'RECEIPT',v_request)
      ON CONFLICT (operation_id) DO NOTHING;
    SELECT operation_type,request_payload,result_payload
      INTO v_saved_type,v_saved_request,v_saved_result
      FROM public.erp_purchase_operations WHERE operation_id=p_operation_id FOR UPDATE;
    IF v_saved_type <> 'RECEIPT' OR v_saved_request IS DISTINCT FROM v_request THEN
        RAISE EXCEPTION 'operation_id réutilisé avec un autre contenu' USING ERRCODE='23505';
    END IF;
    IF v_saved_result IS NOT NULL THEN RETURN v_saved_result; END IF;
    IF v_order.statut IS NULL OR v_order.statut NOT IN ('EN_ATTENTE','PARTIELLEMENT_RECEPTIONNE') THEN
        RAISE EXCEPTION 'Statut de commande non réceptionnable' USING ERRCODE='23514';
    END IF;
    PERFORM 1 FROM public.lignes_achats WHERE commande_achat_id=p_commande_achat_id;
    IF NOT FOUND THEN RAISE EXCEPTION 'Commande sans lignes' USING ERRCODE='23514'; END IF;

    -- Validate EACH line before any stock movement (and aggregate same-MP rows).
    FOR v_line IN SELECT * FROM jsonb_to_recordset(p_lines)
      AS x(ligne_br_id text, mp_id text, quantite_recue numeric, prix_unitaire numeric)
    LOOP
        IF v_line.ligne_br_id IS NULL OR length(btrim(v_line.ligne_br_id))=0 OR length(v_line.ligne_br_id)>200
           OR v_line.mp_id IS NULL OR length(btrim(v_line.mp_id))=0 OR length(v_line.mp_id)>200
           OR v_line.quantite_recue IS NULL OR v_line.quantite_recue::text IN ('NaN','Infinity','-Infinity')
           OR v_line.quantite_recue<=0 OR v_line.quantite_recue>=1000000000000000
           OR v_line.prix_unitaire IS NULL OR v_line.prix_unitaire::text IN ('NaN','Infinity','-Infinity')
           OR v_line.prix_unitaire<0 OR v_line.prix_unitaire>=1000000000000000 THEN
            RAISE EXCEPTION 'Ligne de réception invalide' USING ERRCODE='22023';
        END IF;
    END LOOP;

    -- Check quantities against ordered and ALREADY received quantities.
    -- Le prix transmis dans p_lines n'est JAMAIS utilise pour valoriser le stock.
    FOR v_line IN
        SELECT x.mp_id, sum(x.quantite_recue) AS qty,
               min(x.ligne_br_id) AS line_id
        FROM jsonb_to_recordset(p_lines) AS x(
          ligne_br_id text, mp_id text, quantite_recue numeric, prix_unitaire numeric)
        GROUP BY x.mp_id ORDER BY x.mp_id
    LOOP
        v_qty := v_line.qty;
        IF v_qty<=0 OR v_qty>=1000000000000000 THEN
            RAISE EXCEPTION 'Quantité réception agrégée invalide' USING ERRCODE='22023';
        END IF;
        SELECT coalesce(sum(qte_totale),0) INTO v_ordered
          FROM public.lignes_achats
          WHERE commande_achat_id=p_commande_achat_id AND mp_id=v_line.mp_id;
        SELECT coalesce(sum(r.quantite_recue),0) INTO v_received
          FROM public.lignes_bons_reception r
          JOIN public.bons_reception b ON b.bon_reception_id=r.bon_reception_id
          WHERE b.commande_achat_id=p_commande_achat_id AND r.mp_id=v_line.mp_id;
        IF v_ordered <= 0 OR v_received + v_qty > v_ordered THEN
            RAISE EXCEPTION 'Réception supérieure aux quantités commandées pour %',v_line.mp_id
              USING ERRCODE='23514';
        END IF;
    END LOOP;

    INSERT INTO public.bons_reception(
      bon_reception_id,commande_achat_id,date_reception,controle_conformite,remarques)
    VALUES(p_br_id,p_commande_achat_id,p_date_reception,p_controle_conformite,p_remarques);

    -- Nested stock RPC calls execute inside the SAME transaction.
    FOR v_line IN
        SELECT x.mp_id, sum(x.quantite_recue) AS qty,
               min(x.ligne_br_id) AS line_id
        FROM jsonb_to_recordset(p_lines) AS x(
          ligne_br_id text, mp_id text, quantite_recue numeric, prix_unitaire numeric)
        GROUP BY x.mp_id ORDER BY x.mp_id
    LOOP
        -- Prix d'achat dans la DEVISE de la commande, moyenne ponderee des
        -- lignes pour cette MP, converti en DZD avec le taux de la commande.
        SELECT coalesce(sum(qte_totale),0), coalesce(sum(qte_totale*prix_unitaire),0)
          INTO v_ordered, v_order_price_total
          FROM public.lignes_achats
          WHERE commande_achat_id=p_commande_achat_id AND mp_id=v_line.mp_id;
        IF v_ordered<=0 THEN
            RAISE EXCEPTION 'Aucune ligne de commande pour la MP %',v_line.mp_id USING ERRCODE='23514';
        END IF;
        v_price := (v_order_price_total/v_ordered) * v_order.taux_change;
        IF v_price::text IN ('NaN','Infinity','-Infinity') OR v_price<0
           OR v_price>=1000000000000000 OR v_price*v_line.qty>=1000000000000000 THEN
            RAISE EXCEPTION 'Valorisation locale hors limites pour %',v_line.mp_id USING ERRCODE='22023';
        END IF;
        v_lot := public.erp_apply_stock_movement(
          'BR-MP-' || encode(sha256(convert_to(p_operation_id || ':' || v_line.mp_id,'UTF8')),'hex'),
          'MP','ENTREE',v_line.mp_id,v_line.qty,v_price,
          'BR ' || p_br_id || ' (Cmd ' || p_commande_achat_id || ')',NULLIF(p_date_peremption,''));
        IF v_lot IS NULL OR v_lot->>'lot_id' IS NULL THEN
            RAISE EXCEPTION 'Entrée MP sans lot attribué' USING ERRCODE='23514';
        END IF;
        INSERT INTO public.lignes_bons_reception(
          ligne_br_id,bon_reception_id,mp_id,quantite_recue,lot_attribue_id)
        VALUES(v_line.line_id,p_br_id,v_line.mp_id,v_line.qty,v_lot->>'lot_id');
        v_count := v_count + 1;
    END LOOP;

    SELECT NOT EXISTS (
      SELECT 1 FROM (
        SELECT mp_id,sum(qte_totale) AS ordered FROM public.lignes_achats
        WHERE commande_achat_id=p_commande_achat_id GROUP BY mp_id
      ) o LEFT JOIN (
        SELECT r.mp_id,sum(r.quantite_recue) AS received
        FROM public.lignes_bons_reception r
        JOIN public.bons_reception b ON b.bon_reception_id=r.bon_reception_id
        WHERE b.commande_achat_id=p_commande_achat_id GROUP BY r.mp_id
      ) r ON r.mp_id=o.mp_id
      WHERE coalesce(r.received,0) < o.ordered
    ) INTO v_complete;
    UPDATE public.commandes_achats SET statut =
      CASE WHEN v_complete THEN 'RECEPTIONNE' ELSE 'PARTIELLEMENT_RECEPTIONNE' END
    WHERE commande_achat_id=p_commande_achat_id;

    v_result := jsonb_build_object('operation_id',p_operation_id,
      'bon_reception_id',p_br_id,'commande_achat_id',p_commande_achat_id,
      'nombre_lignes',v_count,
      'statut_commande',CASE WHEN v_complete THEN 'RECEPTIONNE' ELSE 'PARTIELLEMENT_RECEPTIONNE' END);
    UPDATE public.erp_purchase_operations SET result_payload=v_result WHERE operation_id=p_operation_id;
    INSERT INTO public.erp_purchase_outbox(operation_id,payload)
      VALUES(p_operation_id,jsonb_build_object('type','RECEIPT','result',v_result));
    RETURN v_result;
END;
$body$;

REVOKE ALL ON FUNCTION public.erp_create_purchase_order(
  text,text,text,text,text,numeric,text,text,text,jsonb) FROM PUBLIC,anon,authenticated;
GRANT EXECUTE ON FUNCTION public.erp_create_purchase_order(
  text,text,text,text,text,numeric,text,text,text,jsonb) TO service_role;
REVOKE ALL ON FUNCTION public.erp_receive_purchase_order(
  text,text,text,text,text,text,text,jsonb) FROM PUBLIC,anon,authenticated;
GRANT EXECUTE ON FUNCTION public.erp_receive_purchase_order(
  text,text,text,text,text,text,text,jsonb) TO service_role;
REVOKE ALL ON public.erp_purchase_operations,public.erp_purchase_outbox FROM PUBLIC,anon,authenticated;
GRANT SELECT,INSERT,UPDATE ON public.erp_purchase_operations,public.erp_purchase_outbox TO service_role;
COMMIT;
