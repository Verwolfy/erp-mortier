-- Migration 008 : créations atomiques de recettes et d'OF planifiés.
-- Exécuter après 002 et 003, tester d'abord sur un environnement de TEST.
-- N'efface ni ne transforme aucun enregistrement métier existant.
-- Un appel RPC = une transaction PostgreSQL. RLS + service_role uniquement.
BEGIN;

CREATE TABLE IF NOT EXISTS public.erp_production_creations (
    operation_id text PRIMARY KEY,
    action text NOT NULL CHECK (action IN ('RECIPE', 'OF')),
    request_payload jsonb NOT NULL,
    result_payload jsonb NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now()
);
ALTER TABLE public.erp_production_creations ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON public.erp_production_creations FROM PUBLIC, anon, authenticated;
GRANT SELECT, INSERT ON public.erp_production_creations TO service_role;

CREATE OR REPLACE FUNCTION public.erp_create_recipe(
    p_operation_id text, p_pf_id text, p_version text,
    p_rendement_unite numeric, p_instructions text,
    p_date_effet text, p_lignes jsonb
) RETURNS jsonb
LANGUAGE plpgsql SECURITY INVOKER
SET search_path = pg_catalog, public
AS $recipe$
DECLARE
    v_request jsonb;
    v_saved record;
    v_product record;
    v_material record;
    v_line jsonb;
    v_mp_id text;
    v_qty numeric;
    v_seen text[] := ARRAY[]::text[];
    v_id text;
    v_next bigint;
    v_result jsonb;
BEGIN
    IF p_operation_id IS NULL OR btrim(p_operation_id) = '' OR length(p_operation_id) > 128
       OR p_pf_id IS NULL OR btrim(p_pf_id) = '' OR length(p_pf_id) > 200
       OR p_version IS NULL OR btrim(p_version) = '' OR length(p_version) > 200
       OR p_instructions IS NULL OR length(p_instructions) > 5000
       OR p_date_effet IS NULL OR p_date_effet !~ '^[0-9]{4}-[0-9]{2}-[0-9]{2}$'
       OR p_rendement_unite IS NULL OR p_rendement_unite::text IN ('NaN', 'Infinity', '-Infinity')
       OR p_rendement_unite <= 0 OR p_rendement_unite >= 1000000000000000
       OR p_lignes IS NULL OR jsonb_typeof(p_lignes) IS DISTINCT FROM 'array'
       OR jsonb_array_length(p_lignes) NOT BETWEEN 1 AND 200 THEN
        RAISE EXCEPTION 'Données de recette invalides' USING ERRCODE = '22023';
    END IF;
    -- Écarter les dates impossibles avant toute écriture.
    PERFORM p_date_effet::date;

    v_request := jsonb_build_object('pf_id', p_pf_id, 'version', p_version,
         'rendement_unite', p_rendement_unite, 'instructions', p_instructions,
         'date_effet', p_date_effet, 'lignes', p_lignes);
    -- La même clé d'opération ne peut être traitée que par une transaction à la fois.
    PERFORM pg_advisory_xact_lock(hashtextextended('erp_prod_op_' || p_operation_id, 0));
    SELECT action, request_payload, result_payload INTO v_saved
    FROM public.erp_production_creations WHERE operation_id = p_operation_id;
    IF FOUND THEN
        IF v_saved.action IS DISTINCT FROM 'RECIPE'
           OR v_saved.request_payload IS DISTINCT FROM v_request THEN
            RAISE EXCEPTION 'operation_id réutilisé avec données différentes' USING ERRCODE = '23505';
        END IF;
        RETURN v_saved.result_payload;
    END IF;


    -- Validation des composants avant verrou et écriture.
    SELECT pf_id, actif INTO v_product FROM public.produits
    WHERE pf_id = p_pf_id FOR SHARE;
    IF NOT FOUND OR upper(btrim(coalesce(v_product.actif, ''))) <> 'OUI' THEN
        RAISE EXCEPTION 'Produit fini inexistant ou inactif' USING ERRCODE = '23503';
    END IF;
    FOR v_line IN SELECT value FROM jsonb_array_elements(p_lignes) AS x(value)
    LOOP
        IF jsonb_typeof(v_line) IS DISTINCT FROM 'object'
           OR jsonb_typeof(v_line -> 'mp_id') IS DISTINCT FROM 'string'
           OR jsonb_typeof(v_line -> 'quantite_par_unite') NOT IN ('number', 'string') THEN
            RAISE EXCEPTION 'Ligne de recette mal formée' USING ERRCODE = '22023';
        END IF;
        v_mp_id := v_line ->> 'mp_id';
        IF v_mp_id IS NULL OR btrim(v_mp_id) = '' OR length(v_mp_id) > 200
           OR v_mp_id = ANY(v_seen) THEN
            RAISE EXCEPTION 'Matière absente, invalide ou en double' USING ERRCODE = '22023';
        END IF;
        v_seen := array_append(v_seen, v_mp_id);
        v_qty := (v_line ->> 'quantite_par_unite')::numeric;
        IF v_qty IS NULL OR v_qty::text IN ('NaN', 'Infinity', '-Infinity')
           OR v_qty <= 0 OR v_qty >= 1000000000000000 OR v_qty < 0.000000000001 THEN
            RAISE EXCEPTION 'Quantité matière invalide' USING ERRCODE = '22023';
        END IF;
        SELECT mp_id, actif, categorie_mp INTO v_material FROM public.matieres_premieres
        WHERE mp_id = v_mp_id FOR SHARE;
        IF NOT FOUND OR upper(btrim(coalesce(v_material.actif, ''))) <> 'OUI'
           OR upper(btrim(coalesce(v_material.categorie_mp, ''))) IN ('EMBALLAGE', 'EMBALLAGE_CONSOMMABLE') THEN
            RAISE EXCEPTION 'Matière absente, inactive ou emballage' USING ERRCODE = '23503';
        END IF;
    END LOOP;

    -- Verrou transactionnel pour produire des numéros REC-0001, REC-0002, ...
    -- compatibles avec les identifiants historiques, même sous concurrence.
    PERFORM pg_advisory_xact_lock(hashtextextended('erp_prod_counter_REC', 0));
    SELECT coalesce(max(substring(recette_id FROM '^REC-([0-9]+)$')::bigint), 0) + 1
      INTO v_next FROM public.recettes WHERE recette_id ~ '^REC-[0-9]{1,15}$';
    v_id := 'REC-' || lpad(v_next::text, greatest(4, length(v_next::text)), '0');
    INSERT INTO public.recettes(recette_id, pf_id, version, rendement_unite,
                                instructions, date_effet, actif)
    VALUES(v_id, p_pf_id, p_version, p_rendement_unite,
           p_instructions, p_date_effet, 'OUI');
    FOR v_line IN SELECT value FROM jsonb_array_elements(p_lignes) AS x(value)
    LOOP
        INSERT INTO public.lignes_recette(ligne_recette_id, recette_id, mp_id, quantite_par_unite)
        VALUES('LRC-' || replace(gen_random_uuid()::text, '-', ''),
               v_id, v_line ->> 'mp_id', (v_line ->> 'quantite_par_unite')::numeric);
    END LOOP;
    v_result := jsonb_build_object('operation_id', p_operation_id,
                                   'recette_id', v_id, 'nb_lignes', jsonb_array_length(p_lignes));
    INSERT INTO public.erp_production_creations(operation_id, action, request_payload, result_payload)
    VALUES(p_operation_id, 'RECIPE', v_request, v_result);
    RETURN v_result;
END;
$recipe$;

CREATE OR REPLACE FUNCTION public.erp_create_manufacturing_order(
    p_operation_id text, p_pf_id text, p_recette_id text, p_sku_id text,
    p_quantite_prevue numeric, p_date_planification text, p_notes text
) RETURNS jsonb
LANGUAGE plpgsql SECURITY INVOKER
SET search_path = pg_catalog, public
AS $order$
DECLARE
    v_request jsonb;
    v_saved record;
    v_recipe record;
    v_sku record;
    v_product record;
    v_next bigint;
    v_id text;
    v_result jsonb;
BEGIN
    IF p_operation_id IS NULL OR btrim(p_operation_id) = '' OR length(p_operation_id) > 128
       OR p_pf_id IS NULL OR btrim(p_pf_id) = '' OR length(p_pf_id) > 200
       OR p_recette_id IS NULL OR btrim(p_recette_id) = '' OR length(p_recette_id) > 200
       OR p_sku_id IS NULL OR btrim(p_sku_id) = '' OR length(p_sku_id) > 200
       OR p_notes IS NULL OR length(p_notes) > 5000
       OR p_date_planification IS NULL OR p_date_planification !~ '^[0-9]{4}-[0-9]{2}-[0-9]{2}$'
       OR p_quantite_prevue IS NULL OR p_quantite_prevue::text IN ('NaN', 'Infinity', '-Infinity')
       OR p_quantite_prevue <= 0 OR p_quantite_prevue >= 1000000000000000
       OR p_quantite_prevue <> trunc(p_quantite_prevue) THEN
        RAISE EXCEPTION 'Données d''OF invalides' USING ERRCODE = '22023';
    END IF;
    PERFORM p_date_planification::date;
    v_request := jsonb_build_object('pf_id', p_pf_id, 'recette_id', p_recette_id,
         'sku_id', p_sku_id, 'quantite_prevue', p_quantite_prevue,
         'date_planification', p_date_planification, 'notes', p_notes);
    PERFORM pg_advisory_xact_lock(hashtextextended('erp_prod_op_' || p_operation_id, 0));
    SELECT action, request_payload, result_payload INTO v_saved
    FROM public.erp_production_creations WHERE operation_id = p_operation_id;
    IF FOUND THEN
        IF v_saved.action IS DISTINCT FROM 'OF'
           OR v_saved.request_payload IS DISTINCT FROM v_request THEN
            RAISE EXCEPTION 'operation_id réutilisé avec données différentes' USING ERRCODE = '23505';
        END IF;
        RETURN v_saved.result_payload;
    END IF;


    SELECT pf_id, actif INTO v_product FROM public.produits WHERE pf_id = p_pf_id FOR SHARE;
    IF NOT FOUND OR upper(btrim(coalesce(v_product.actif, ''))) <> 'OUI' THEN
        RAISE EXCEPTION 'Produit fini absent ou inactif' USING ERRCODE = '23503';
    END IF;
    SELECT pf_id, actif INTO v_recipe FROM public.recettes WHERE recette_id = p_recette_id FOR SHARE;
    IF NOT FOUND OR v_recipe.pf_id IS DISTINCT FROM p_pf_id
       OR upper(btrim(coalesce(v_recipe.actif, ''))) <> 'OUI' THEN
        RAISE EXCEPTION 'Recette absente, inactive ou d''un autre produit' USING ERRCODE = '23503';
    END IF;
    SELECT pf_id, actif INTO v_sku FROM public.sku_conditionnement WHERE sku_id = p_sku_id FOR SHARE;
    IF NOT FOUND OR v_sku.pf_id IS DISTINCT FROM p_pf_id
       OR upper(btrim(coalesce(v_sku.actif, ''))) <> 'OUI' THEN
        RAISE EXCEPTION 'SKU absent, inactif ou d''un autre produit' USING ERRCODE = '23503';
    END IF;
    -- La validation physique de ce SKU n'est pas achevée.
    IF p_sku_id = 'SKU-007' THEN
        RAISE EXCEPTION 'SKU-007 bloqué : conditionnement physique non validé' USING ERRCODE = '23514';
    END IF;

    PERFORM pg_advisory_xact_lock(hashtextextended('erp_prod_counter_OF', 0));
    SELECT coalesce(max(substring(of_id FROM '^OF-([0-9]+)$')::bigint), 0) + 1
      INTO v_next FROM public.ordres_fabrication WHERE of_id ~ '^OF-[0-9]{1,15}$';
    v_id := 'OF-' || lpad(v_next::text, greatest(4, length(v_next::text)), '0');
    INSERT INTO public.ordres_fabrication(
        of_id, pf_id, recette_id, sku_id, quantite_prevue, quantite_produite,
        date_planification, date_debut, date_fin, statut, cout_total, notes
    ) VALUES (
        v_id, p_pf_id, p_recette_id, p_sku_id, p_quantite_prevue, 0,
        p_date_planification, '', '', 'PLANIFIE', 0, p_notes
    );
    v_result := jsonb_build_object('operation_id', p_operation_id,
                                   'of_id', v_id, 'statut', 'PLANIFIE');
    INSERT INTO public.erp_production_creations(operation_id, action, request_payload, result_payload)
    VALUES(p_operation_id, 'OF', v_request, v_result);
    RETURN v_result;
END;
$order$;

REVOKE ALL ON FUNCTION public.erp_create_recipe(text,text,text,numeric,text,text,jsonb)
    FROM PUBLIC, anon, authenticated;
GRANT EXECUTE ON FUNCTION public.erp_create_recipe(text,text,text,numeric,text,text,jsonb)
    TO service_role;
REVOKE ALL ON FUNCTION public.erp_create_manufacturing_order(text,text,text,text,numeric,text,text)
    FROM PUBLIC, anon, authenticated;
GRANT EXECUTE ON FUNCTION public.erp_create_manufacturing_order(text,text,text,text,numeric,text,text)
    TO service_role;

COMMIT;
