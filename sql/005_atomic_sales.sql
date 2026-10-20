-- UNIQUEMENT SUR UNE BASE SUPABASE DE TEST.
-- Prérequis : migration 002_atomic_stock_movement.sql ; clé serveur réservée.
-- Aucun mouvement de stock lors de la validation/annulation d'une facture.
-- Les marchandises sont décrémentées UNIQUEMENT à l'expédition d'un BL.
BEGIN;

CREATE TABLE IF NOT EXISTS public.erp_sales_operations (
    operation_id text PRIMARY KEY,
    action text NOT NULL CHECK (action IN ('DRAFT','VALIDATE','CANCEL','SHIP')),
    request_payload jsonb NOT NULL,
    result_payload jsonb,
    created_at timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE IF NOT EXISTS public.erp_sales_outbox (
    operation_id text PRIMARY KEY REFERENCES public.erp_sales_operations(operation_id),
    payload jsonb NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    synced_at timestamptz
);

CREATE OR REPLACE FUNCTION public.erp_sale_transaction(
    p_action text, p_operation_id text, p_payload jsonb
) RETURNS jsonb
LANGUAGE plpgsql
SECURITY INVOKER
SET search_path = pg_catalog, public
AS $body$
DECLARE
    v_previous record;
    v_invoice record;
    v_original record;
    v_order record;
    v_counter record;
    v_line record;
    v_sku record;
    v_lot jsonb;
    v_allocation jsonb;
    v_item jsonb;
    v_result jsonb;
    v_invoice_id text;
    v_bl_id text;
    v_now text := to_char(now() AT TIME ZONE 'UTC', 'YYYY-MM-DD');
    v_gross numeric;
    v_net_lines numeric := 0;
    v_net_ht numeric;
    v_tax numeric;
    v_stamp numeric;
    v_ttc numeric;
    v_discount numeric;
    v_expected_ht numeric;
    v_expected_tva numeric;
    v_expected_stamp numeric;
    v_expected_ttc numeric;
    v_total_credit numeric;
    v_ordered numeric;
    v_delivered numeric;
    v_allocated numeric;
    v_count integer := 0;
BEGIN
    IF p_action IS NULL OR p_action NOT IN ('DRAFT','VALIDATE','CANCEL','SHIP')
       OR p_operation_id IS NULL OR length(btrim(p_operation_id))=0 OR length(p_operation_id)>128
       OR p_payload IS NULL OR jsonb_typeof(p_payload) <> 'object' THEN
        RAISE EXCEPTION 'Transaction Ventes invalide' USING ERRCODE='22023';
    END IF;

    -- Reprise idempotente après timeout réseau : aucune double écriture.
    INSERT INTO public.erp_sales_operations(operation_id,action,request_payload)
      VALUES(p_operation_id,p_action,p_payload)
      ON CONFLICT (operation_id) DO NOTHING;
    SELECT action,request_payload,result_payload INTO v_previous
      FROM public.erp_sales_operations WHERE operation_id=p_operation_id FOR UPDATE;
    IF v_previous.action IS DISTINCT FROM p_action
       OR v_previous.request_payload IS DISTINCT FROM p_payload THEN
        RAISE EXCEPTION 'operation_id déjà utilisé avec un autre contenu' USING ERRCODE='23505';
    END IF;
    IF v_previous.result_payload IS NOT NULL THEN RETURN v_previous.result_payload; END IF;

    IF p_action = 'DRAFT' THEN
        IF nullif(btrim(p_payload->>'client_id'),'') IS NULL
           OR length(p_payload->>'client_id')>200
           OR p_payload->>'type_facture' IS NULL
           OR p_payload->>'type_facture' NOT IN ('FactureClient','FactureAvoir')
           OR length(coalesce(p_payload->>'date_echeance',''))>10
           OR length(coalesce(p_payload->>'facture_origine_id',''))>200
           OR p_payload->>'paiement_especes' IS NULL
           OR p_payload->>'paiement_especes' NOT IN ('true','false')
           OR jsonb_typeof(p_payload->'lignes') IS DISTINCT FROM 'array'
           OR jsonb_array_length(p_payload->'lignes') NOT BETWEEN 1 AND 500 THEN
            RAISE EXCEPTION 'Entête de facture incorrect' USING ERRCODE='22023';
        END IF;
        PERFORM 1 FROM public.clients WHERE client_id=p_payload->>'client_id';
        IF NOT FOUND THEN RAISE EXCEPTION 'Client inexistant' USING ERRCODE='23503'; END IF;
        IF p_payload->>'type_facture'='FactureAvoir' THEN
            IF nullif(btrim(p_payload->>'facture_origine_id'),'') IS NULL
               OR p_payload->>'paiement_especes'='true' THEN
                RAISE EXCEPTION 'Avoir sans origine ou avec timbre espèces' USING ERRCODE='23514';
            END IF;
        ELSIF coalesce(p_payload->>'facture_origine_id','')<>'' THEN
            RAISE EXCEPTION 'Facture normale avec origine d avoir' USING ERRCODE='23514';
        END IF;

        v_net_lines := 0;
        FOR v_line IN SELECT * FROM jsonb_to_recordset(p_payload->'lignes')
          AS x(sku_id text,quantite numeric,prix_unitaire numeric,remise_ligne numeric,total_ligne_ht numeric)
        LOOP
            IF nullif(btrim(v_line.sku_id),'') IS NULL OR length(v_line.sku_id)>200
               OR v_line.quantite IS NULL OR v_line.quantite<=0 OR v_line.quantite>=1000000000000000
               OR v_line.quantite::text IN ('NaN','Infinity','-Infinity')
               OR v_line.prix_unitaire IS NULL OR v_line.prix_unitaire<0 OR v_line.prix_unitaire>=1000000000000000
               OR v_line.prix_unitaire::text IN ('NaN','Infinity','-Infinity')
               OR v_line.remise_ligne IS NULL OR v_line.remise_ligne<0 OR v_line.remise_ligne>=1000000000000000
               OR v_line.remise_ligne::text IN ('NaN','Infinity','-Infinity')
               OR v_line.total_ligne_ht IS NULL OR v_line.total_ligne_ht::text IN ('NaN','Infinity','-Infinity') THEN
                RAISE EXCEPTION 'Ligne de facture invalide' USING ERRCODE='22023';
            END IF;
            IF v_line.remise_ligne > v_line.quantite * v_line.prix_unitaire
               OR v_line.total_ligne_ht IS DISTINCT FROM round(v_line.quantite*v_line.prix_unitaire-v_line.remise_ligne,2) THEN
                RAISE EXCEPTION 'Montant ligne incohérent' USING ERRCODE='23514';
            END IF;
            PERFORM 1 FROM public.sku_conditionnement WHERE sku_id=v_line.sku_id;
            IF NOT FOUND THEN RAISE EXCEPTION 'SKU facture inconnu' USING ERRCODE='23503'; END IF;
            v_net_lines := v_net_lines + v_line.total_ligne_ht;
            v_count := v_count + 1;
        END LOOP;
        v_discount := (p_payload->>'remise_globale')::numeric;
        IF v_discount IS NULL OR v_discount::text IN ('NaN','Infinity','-Infinity')
           OR v_discount<0 OR v_discount>v_net_lines THEN
            RAISE EXCEPTION 'Remise globale incohérente' USING ERRCODE='23514';
        END IF;
        v_net_ht := round(v_net_lines-v_discount,2);
        v_tax := round(v_net_ht * 0.19,2);
        v_stamp := CASE WHEN p_payload->>'paiement_especes'='true'
                   THEN least(round((v_net_ht+v_tax)*0.01,2),2500) ELSE 0 END;
        v_ttc := v_net_ht+v_tax+v_stamp;
        IF v_ttc>=1000000000000000 THEN
            RAISE EXCEPTION 'Montant facture trop élevé' USING ERRCODE='22023';
        END IF;
        IF p_payload->>'type_facture'='FactureAvoir' THEN
            v_net_ht:=-v_net_ht; v_tax:=-v_tax; v_ttc:=-v_ttc;
        END IF;
        v_expected_ht := (p_payload->>'montant_ht')::numeric;
        v_expected_tva := (p_payload->>'montant_tva')::numeric;
        v_expected_stamp := (p_payload->>'montant_timbre')::numeric;
        v_expected_ttc := (p_payload->>'montant_ttc')::numeric;
        IF v_expected_ht IS DISTINCT FROM v_net_ht OR v_expected_tva IS DISTINCT FROM v_tax
           OR v_expected_stamp IS DISTINCT FROM v_stamp OR v_expected_ttc IS DISTINCT FROM v_ttc THEN
            RAISE EXCEPTION 'Totaux facture non concordants avec les lignes' USING ERRCODE='23514';
        END IF;

        -- Numérotation légale et création documentaire dans la MÊME transaction.
        SELECT prefixe,annee,dernier_numero INTO v_counter FROM public.compteurs
          WHERE type_document=p_payload->>'type_facture' FOR UPDATE;
        IF NOT FOUND OR nullif(btrim(v_counter.prefixe),'') IS NULL
           OR nullif(btrim(v_counter.annee),'') IS NULL
           OR coalesce(v_counter.dernier_numero,0)<0 OR coalesce(v_counter.dernier_numero,0)>=999999999 THEN
            RAISE EXCEPTION 'Compteur légal manquant ou invalide' USING ERRCODE='23514';
        END IF;
        UPDATE public.compteurs SET dernier_numero=coalesce(dernier_numero,0)+1
          WHERE type_document=p_payload->>'type_facture' RETURNING dernier_numero INTO v_count;
        v_invoice_id := v_counter.prefixe || '-' || v_counter.annee || '-' || lpad(v_count::text,6,'0');
        INSERT INTO public.factures(facture_id,commande_vente_id,client_id,date,montant_ht,taux_tva,
          montant_tva,montant_ttc,montant_paye,statut,date_echeance,montant_timbre,
          type_facture,facture_origine_id,remise_globale)
        VALUES(v_invoice_id,'',p_payload->>'client_id',v_now,v_net_ht,0.19,
          v_tax,v_ttc,0,'BROUILLON',p_payload->>'date_echeance',v_stamp,
          p_payload->>'type_facture',p_payload->>'facture_origine_id',v_discount);
        FOR v_line IN SELECT * FROM jsonb_to_recordset(p_payload->'lignes') AS x(
          sku_id text,quantite numeric,prix_unitaire numeric,remise_ligne numeric,total_ligne_ht numeric)
        LOOP
            INSERT INTO public.lignes_facture(ligne_facture_id,facture_id,sku_id,quantite,
                                              prix_unitaire,remise_ligne,total_ligne_ht)
            VALUES('LFA-'||gen_random_uuid()::text,v_invoice_id,v_line.sku_id,v_line.quantite,
                   v_line.prix_unitaire,v_line.remise_ligne,v_line.total_ligne_ht);
        END LOOP;
        v_result := jsonb_build_object('operation_id',p_operation_id,'action',p_action,
                                        'facture_id',v_invoice_id,'statut','BROUILLON');

    ELSIF p_action IN ('VALIDATE','CANCEL') THEN
        IF nullif(btrim(p_payload->>'facture_id'),'') IS NULL
           OR length(p_payload->>'facture_id')>200 THEN
            RAISE EXCEPTION 'Numéro de facture obligatoire' USING ERRCODE='22023';
        END IF;
        SELECT * INTO v_invoice FROM public.factures
          WHERE facture_id=p_payload->>'facture_id' FOR UPDATE;
        IF NOT FOUND THEN RAISE EXCEPTION 'Facture inexistante' USING ERRCODE='23503'; END IF;
        IF v_invoice.statut IS DISTINCT FROM 'BROUILLON' THEN
            RAISE EXCEPTION 'Seuls les brouillons peuvent être validés ou annulés' USING ERRCODE='23514';
        END IF;
        IF coalesce(v_invoice.montant_paye,0) <> 0 THEN
            RAISE EXCEPTION 'Facture ayant des paiements : modification interdite' USING ERRCODE='23514';
        END IF;
        IF p_action='VALIDATE' THEN
            PERFORM 1 FROM public.lignes_facture WHERE facture_id=v_invoice.facture_id;
            IF NOT FOUND THEN RAISE EXCEPTION 'Facture sans lignes' USING ERRCODE='23514'; END IF;
            IF v_invoice.type_facture='FactureAvoir' THEN
                SELECT * INTO v_original FROM public.factures
                  WHERE facture_id=v_invoice.facture_origine_id FOR UPDATE;
                IF NOT FOUND OR v_original.statut IS DISTINCT FROM 'VALIDE'
                   OR v_original.type_facture IS DISTINCT FROM 'FactureClient'
                   OR v_original.client_id IS DISTINCT FROM v_invoice.client_id THEN
                    RAISE EXCEPTION 'Avoir : facture origine non valide ou client différent' USING ERRCODE='23514';
                END IF;
                SELECT coalesce(sum(-montant_ttc),0) INTO v_total_credit FROM public.factures
                  WHERE facture_origine_id=v_original.facture_id
                    AND type_facture='FactureAvoir' AND statut='VALIDE';
                IF v_invoice.montant_ttc IS NULL OR v_invoice.montant_ttc >= 0
                   OR v_original.montant_ttc IS NULL OR v_original.montant_ttc <= 0
                   OR v_total_credit + (-v_invoice.montant_ttc) > v_original.montant_ttc THEN
                    RAISE EXCEPTION 'Avoir dépassant le montant de la facture d origine' USING ERRCODE='23514';
                END IF;
            END IF;
        END IF;
        UPDATE public.factures SET statut=CASE WHEN p_action='VALIDATE' THEN 'VALIDE' ELSE 'ANNULE' END
          WHERE facture_id=v_invoice.facture_id;
        -- Aucune entrée en stock, même lors de l'annulation.
        v_result := jsonb_build_object('operation_id',p_operation_id,'action',p_action,
          'facture_id',v_invoice.facture_id,
          'statut',CASE WHEN p_action='VALIDATE' THEN 'VALIDE' ELSE 'ANNULE' END);

    ELSIF p_action='SHIP' THEN
        IF nullif(btrim(p_payload->>'commande_vente_id'),'') IS NULL
           OR length(p_payload->>'commande_vente_id')>200
           OR length(coalesce(p_payload->>'transporteur',''))>200
           OR length(coalesce(p_payload->>'zone',''))>200
           OR jsonb_typeof(p_payload->'lignes') IS DISTINCT FROM 'array'
           OR jsonb_array_length(p_payload->'lignes') NOT BETWEEN 1 AND 500 THEN
            RAISE EXCEPTION 'Bon de livraison invalide' USING ERRCODE='22023';
        END IF;
        -- Verrou du parent pour interdire le cumul d'expéditions supérieures à la commande.
        SELECT * INTO v_order FROM public.commandes_ventes
          WHERE commande_vente_id=p_payload->>'commande_vente_id' FOR UPDATE;
        IF NOT FOUND OR v_order.statut='ANNULE' THEN
            RAISE EXCEPTION 'Commande client absente ou annulée' USING ERRCODE='23503';
        END IF;
        FOR v_line IN SELECT * FROM jsonb_to_recordset(p_payload->'lignes')
          AS x(sku_id text,quantite_livree numeric)
        LOOP
            IF nullif(btrim(v_line.sku_id),'') IS NULL OR length(v_line.sku_id)>200
               OR v_line.quantite_livree IS NULL OR v_line.quantite_livree<=0
               OR v_line.quantite_livree>=1000000000000000
               OR v_line.quantite_livree::text IN ('NaN','Infinity','-Infinity') THEN
                RAISE EXCEPTION 'Ligne de livraison invalide' USING ERRCODE='22023';
            END IF;
        END LOOP;
        -- Valider les cumul avant tout débit de stock.
        FOR v_sku IN SELECT x.sku_id,sum(x.quantite_livree) qty FROM
          jsonb_to_recordset(p_payload->'lignes') AS x(sku_id text,quantite_livree numeric)
          GROUP BY x.sku_id ORDER BY x.sku_id
        LOOP
            SELECT coalesce(sum(quantite),0) INTO v_ordered
              FROM public.lignes_commande_ventes WHERE commande_vente_id=v_order.commande_vente_id
                AND sku_id=v_sku.sku_id;
            SELECT coalesce(sum(l.quantite_livree),0) INTO v_delivered
              FROM public.lignes_bons_livraison l JOIN public.bons_livraison b ON l.bl_id=b.bl_id
              WHERE b.commande_vente_id=v_order.commande_vente_id
                AND b.statut='EXPEDIE' AND l.sku_id=v_sku.sku_id;
            IF v_ordered<=0 OR v_delivered+v_sku.qty>v_ordered THEN
                RAISE EXCEPTION 'Quantité expédiée supérieure à la commande pour %',v_sku.sku_id
                  USING ERRCODE='23514';
            END IF;
        END LOOP;
        v_bl_id := 'BL-' || gen_random_uuid()::text;
        INSERT INTO public.bons_livraison(bl_id,commande_vente_id,date,transporteur,zone,statut)
          VALUES(v_bl_id,v_order.commande_vente_id,v_now,
                 coalesce(p_payload->>'transporteur',''),coalesce(p_payload->>'zone',''),'EXPEDIE');
        FOR v_sku IN SELECT x.sku_id,sum(x.quantite_livree) qty FROM
          jsonb_to_recordset(p_payload->'lignes') AS x(sku_id text,quantite_livree numeric)
          GROUP BY x.sku_id ORDER BY x.sku_id
        LOOP
            v_lot := public.erp_apply_stock_movement(
              'BL-PF-'||md5(p_operation_id||':'||v_sku.sku_id),
              'PF','SORTIE',v_sku.sku_id,v_sku.qty,NULL,'BL '||v_bl_id,NULL);
            IF v_lot IS NULL OR jsonb_typeof(v_lot->'lot_allocations') IS DISTINCT FROM 'array' THEN
                RAISE EXCEPTION 'Sortie FIFO sans allocations de lots' USING ERRCODE='23514';
            END IF;
            v_allocated := 0;
            FOR v_allocation IN SELECT value FROM jsonb_array_elements(v_lot->'lot_allocations')
            LOOP
                v_allocated := v_allocated + (v_allocation->>'taken')::numeric;
                INSERT INTO public.lignes_bons_livraison(ligne_bl_id,bl_id,sku_id,quantite_livree,lot_id)
                VALUES('LBL-'||gen_random_uuid()::text,v_bl_id,v_sku.sku_id,
                       (v_allocation->>'taken')::numeric,v_allocation->>'lot_id');
                v_count := v_count+1;
            END LOOP;
            IF v_allocated IS DISTINCT FROM v_sku.qty THEN
                RAISE EXCEPTION 'Répartition FIFO non égale à la livraison' USING ERRCODE='23514';
            END IF;
        END LOOP;
        v_result := jsonb_build_object('operation_id',p_operation_id,'action',p_action,
                        'bl_id',v_bl_id,'nombre_lignes_lots',v_count,'statut','EXPEDIE');
    END IF;

    UPDATE public.erp_sales_operations SET result_payload=v_result WHERE operation_id=p_operation_id;
    INSERT INTO public.erp_sales_outbox(operation_id,payload)
      VALUES(p_operation_id,jsonb_build_object('action',p_action,'result',v_result));
    RETURN v_result;
END;
$body$;

REVOKE ALL ON FUNCTION public.erp_sale_transaction(text,text,jsonb) FROM PUBLIC, anon, authenticated;
GRANT EXECUTE ON FUNCTION public.erp_sale_transaction(text,text,jsonb) TO service_role;
REVOKE ALL ON public.erp_sales_operations,public.erp_sales_outbox FROM PUBLIC,anon,authenticated;
GRANT SELECT,INSERT,UPDATE ON public.erp_sales_operations,public.erp_sales_outbox TO service_role;
COMMIT;
