-- Migration 009 : création atomique de commandes clients et de leurs lignes.
-- À examiner et tester dans une transaction ROLLBACK avant toute application.
-- Prérequis : tables clients, produits, sku_conditionnement, commandes_ventes,
-- lignes_commande_ventes ; migration 005 pour les futures livraisons.
-- N'altère ni factures ni stocks. Ne rattache aucune facture existante.
BEGIN;

CREATE TABLE IF NOT EXISTS public.erp_sales_order_creations (
    operation_id text PRIMARY KEY,
    request_payload jsonb NOT NULL,
    result_payload jsonb NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT erp_sales_order_operation_id_valid
      CHECK (length(btrim(operation_id)) BETWEEN 1 AND 128)
);

-- Les identifiants d'opération ne doivent pas être exposés aux clients publics.
ALTER TABLE public.erp_sales_order_creations ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON TABLE public.erp_sales_order_creations FROM PUBLIC, anon, authenticated;
GRANT SELECT, INSERT ON TABLE public.erp_sales_order_creations TO service_role;

CREATE OR REPLACE FUNCTION public.erp_create_sales_order(
    p_operation_id text,
    p_client_id text,
    p_date text,
    p_lignes jsonb
) RETURNS jsonb
LANGUAGE plpgsql SECURITY INVOKER
SET search_path = pg_catalog, public
AS $order$
DECLARE
    v_request jsonb;
    v_saved record;
    v_client_actif text;
    v_sku record;
    v_produit_actif text;
    v_line jsonb;
    v_sku_id text;
    v_qty_raw text;
    v_price_raw text;
    v_qty numeric;
    v_price numeric;
    v_seen text[] := ARRAY[]::text[];
    v_next bigint;
    v_id text;
    v_result jsonb;
BEGIN
    -- Refuser les paramètres absents ou excessifs avant toute écriture.
    IF p_operation_id IS NULL OR length(btrim(p_operation_id)) NOT BETWEEN 1 AND 128
       OR p_client_id IS NULL OR length(btrim(p_client_id)) NOT BETWEEN 1 AND 200
       OR p_date IS NULL OR p_date !~ '^[0-9]{4}-[0-9]{2}-[0-9]{2}$' THEN
        RAISE EXCEPTION 'Entête de commande invalide' USING ERRCODE = '22023';
    END IF;
    PERFORM p_date::date;
    IF jsonb_typeof(p_lignes) IS DISTINCT FROM 'array' THEN
        RAISE EXCEPTION 'Lignes de commande invalides' USING ERRCODE = '22023';
    END IF;
    IF jsonb_array_length(p_lignes) NOT BETWEEN 1 AND 500 THEN
        RAISE EXCEPTION 'La commande exige 1 à 500 lignes' USING ERRCODE = '22023';
    END IF;

    v_request := jsonb_build_object(
        'client_id', btrim(p_client_id), 'date', p_date, 'lignes', p_lignes
    );
    -- Sérialiser les tentatives portant le même operation_id.
    PERFORM pg_advisory_xact_lock(hashtextextended('erp_sales_order_op_' || p_operation_id, 0));
    SELECT request_payload, result_payload INTO v_saved
      FROM public.erp_sales_order_creations
     WHERE operation_id = p_operation_id;
    IF FOUND THEN
        IF v_saved.request_payload IS DISTINCT FROM v_request THEN
            RAISE EXCEPTION 'operation_id réutilisé avec données différentes'
                USING ERRCODE = '23505';
        END IF;
        RETURN v_saved.result_payload;
    END IF;

    SELECT actif INTO v_client_actif
      FROM public.clients WHERE client_id = btrim(p_client_id) FOR SHARE;
    IF NOT FOUND OR upper(btrim(coalesce(v_client_actif, ''))) <> 'OUI' THEN
        RAISE EXCEPTION 'Client absent ou inactif' USING ERRCODE = '23503';
    END IF;

    -- Les lignes sont traitées dans un ordre stable pour limiter les interblocages.
    FOR v_line IN
        SELECT value FROM jsonb_array_elements(p_lignes)
         ORDER BY value->>'sku_id'
    LOOP
        IF jsonb_typeof(v_line) IS DISTINCT FROM 'object' THEN
            RAISE EXCEPTION 'Ligne de commande invalide' USING ERRCODE = '22023';
        END IF;
        v_sku_id := v_line->>'sku_id';
        v_qty_raw := v_line->>'quantite';
        v_price_raw := v_line->>'prix_unitaire';
        IF v_sku_id IS NULL OR length(btrim(v_sku_id)) NOT BETWEEN 1 AND 200
           OR v_qty_raw IS NULL
           OR v_qty_raw !~ '^[0-9]{1,15}(\.[0-9]{1,12})?$'
           OR v_price_raw IS NULL
           OR v_price_raw !~ '^[0-9]{1,15}(\.[0-9]{1,2})?$' THEN
            RAISE EXCEPTION 'SKU, quantité ou prix invalide' USING ERRCODE = '22023';
        END IF;
        v_sku_id := btrim(v_sku_id);
        v_qty := v_qty_raw::numeric;
        v_price := v_price_raw::numeric;
        IF v_qty <= 0 OR v_qty >= 1000000000000000
           OR v_qty <> trunc(v_qty)
           OR v_price < 0 OR v_price >= 1000000000000000 THEN
            RAISE EXCEPTION 'Quantité entière positive et prix valide requis'
                USING ERRCODE = '22023';
        END IF;
        IF v_sku_id = ANY(v_seen) THEN
            RAISE EXCEPTION 'SKU dupliqué dans la commande : %', v_sku_id
                USING ERRCODE = '23505';
        END IF;
        v_seen := array_append(v_seen, v_sku_id);

        SELECT pf_id, actif INTO v_sku
          FROM public.sku_conditionnement WHERE sku_id = v_sku_id FOR SHARE;
        IF NOT FOUND OR upper(btrim(coalesce(v_sku.actif, ''))) <> 'OUI'
           OR v_sku.pf_id IS NULL THEN
            RAISE EXCEPTION 'SKU absent ou inactif : %', v_sku_id USING ERRCODE = '23503';
        END IF;
        SELECT actif INTO v_produit_actif
          FROM public.produits WHERE pf_id = v_sku.pf_id FOR SHARE;
        IF NOT FOUND OR upper(btrim(coalesce(v_produit_actif, ''))) <> 'OUI' THEN
            RAISE EXCEPTION 'Produit fini absent ou inactif pour %', v_sku_id
                USING ERRCODE = '23503';
        END IF;
        -- Blocage conservateur tant que le conditionnement n'est pas validé.
        IF v_sku_id = 'SKU-007' THEN
            RAISE EXCEPTION 'SKU-007 : conditionnement physique non validé'
                USING ERRCODE = '23514';
        END IF;
    END LOOP;

    -- Numérotation unique sous verrou ; aucun compteur consommé après un échec.
    PERFORM pg_advisory_xact_lock(hashtextextended('erp_sales_order_counter_CDV', 0));
    SELECT coalesce(max(substring(commande_vente_id FROM '^CDV-([0-9]+)$')::bigint), 0) + 1
      INTO v_next FROM public.commandes_ventes
     WHERE commande_vente_id ~ '^CDV-[0-9]{1,15}$';
    v_id := 'CDV-' || lpad(v_next::text, greatest(4, length(v_next::text)), '0');
    INSERT INTO public.commandes_ventes(
        commande_vente_id, devis_id, client_id, date, statut
    ) VALUES (
        v_id, NULL, btrim(p_client_id), p_date, 'EN_ATTENTE'
    );

    FOR v_line IN SELECT value FROM jsonb_array_elements(p_lignes)
    LOOP
        INSERT INTO public.lignes_commande_ventes(
            ligne_commande_vente_id, commande_vente_id, sku_id, quantite, prix_unitaire
        ) VALUES (
            'LCV-' || gen_random_uuid()::text,
            v_id, btrim(v_line->>'sku_id'),
            (v_line->>'quantite')::numeric,
            (v_line->>'prix_unitaire')::numeric
        );
    END LOOP;

    v_result := jsonb_build_object(
        'operation_id', p_operation_id,
        'commande_vente_id', v_id,
        'statut', 'EN_ATTENTE',
        'nombre_lignes', jsonb_array_length(p_lignes)
    );
    INSERT INTO public.erp_sales_order_creations(operation_id, request_payload, result_payload)
    VALUES(p_operation_id, v_request, v_result);
    RETURN v_result;
END;
$order$;

-- Nouvelle fonction : interdiction d'exécution pour PUBLIC, anon et authenticated.
REVOKE ALL ON FUNCTION public.erp_create_sales_order(text,text,text,jsonb)
  FROM PUBLIC, anon, authenticated;
GRANT EXECUTE ON FUNCTION public.erp_create_sales_order(text,text,text,jsonb)
  TO service_role;

COMMIT;
