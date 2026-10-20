-- TEST ONLY: requires sql/002_atomic_stock_movement.sql applied first.
-- One PostgreSQL RPC call = one SQL transaction (MP FIFO, CNOF, PF, QC, OF).
-- NEVER execute on a production project before RLS, concurrency, audit, and
-- reconciliation tests; business tables and identifiers remain unchanged.
BEGIN;

CREATE TABLE IF NOT EXISTS public.erp_of_closures (
    of_id text PRIMARY KEY REFERENCES public.ordres_fabrication(of_id),
    request_payload jsonb NOT NULL,
    result_payload jsonb,
    created_at timestamptz NOT NULL DEFAULT now()
);

-- TECHNICAL outbox, not a second master ERP table. No worker is provided.
CREATE TABLE IF NOT EXISTS public.erp_of_outbox (
    of_id text PRIMARY KEY REFERENCES public.erp_of_closures(of_id),
    payload jsonb NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    synced_at timestamptz
);

CREATE OR REPLACE FUNCTION public.erp_close_manufacturing_order(
    p_of_id text,
    p_conforme text,
    p_remarques text,
    p_controleur text,
    p_quantite_produite numeric,
    p_emballage_mp_id text,
    p_emballage_consomme numeric
) RETURNS jsonb
LANGUAGE plpgsql
SECURITY INVOKER
SET search_path = pg_catalog, public
AS $body$
DECLARE
    v_of record;
    v_recipe record;
    v_sku_pf_id text;
    v_line record;
    v_mp_id text;
    v_lot record;
    v_needs jsonb := '{}'::jsonb;
    v_required numeric;
    v_line_qty numeric;
    v_movement jsonb;
    v_pf_movement jsonb;
    v_request jsonb;
    v_saved_request jsonb;
    v_saved_result jsonb;
    v_result jsonb;
    v_cost_total numeric := 0;
    v_consumed_rows integer := 0;
    v_item_count integer := 0;
    v_now text := to_char(now() AT TIME ZONE 'UTC', 'YYYY-MM-DD HH24:MI:SS');
    v_today text := to_char(now() AT TIME ZONE 'UTC', 'YYYY-MM-DD');
BEGIN
    IF p_of_id IS NULL OR length(btrim(p_of_id)) = 0 OR length(p_of_id) > 200
       OR p_controleur IS NULL OR length(btrim(p_controleur)) = 0 OR length(p_controleur) > 200
       OR p_remarques IS NULL OR length(p_remarques) > 5000 THEN
        RAISE EXCEPTION 'Identifiant, contrôleur ou remarques invalides' USING ERRCODE = '22023';
    END IF;
    IF p_conforme IS NULL OR p_conforme NOT IN ('OUI', 'NON') THEN
        RAISE EXCEPTION 'Conformité invalide' USING ERRCODE = '22023';
    END IF;
    IF p_quantite_produite IS NULL OR p_quantite_produite::text IN ('NaN', 'Infinity', '-Infinity')
       OR p_quantite_produite < 0 OR p_quantite_produite >= 1000000000000000
       OR (p_conforme = 'OUI' AND p_quantite_produite = 0) THEN
        RAISE EXCEPTION 'Quantité produite invalide' USING ERRCODE = '22023';
    END IF;
    IF p_emballage_consomme IS NULL OR p_emballage_consomme::text IN ('NaN', 'Infinity', '-Infinity')
       OR p_emballage_consomme < 0 OR p_emballage_consomme >= 1000000000000000 THEN
        RAISE EXCEPTION 'Quantité emballage invalide' USING ERRCODE = '22023';
    END IF;
    IF p_emballage_mp_id IS NOT NULL AND
       (length(btrim(p_emballage_mp_id)) = 0 OR length(p_emballage_mp_id) > 200) THEN
        RAISE EXCEPTION 'Identifiant emballage invalide' USING ERRCODE = '22023';
    END IF;
    IF (p_emballage_mp_id IS NULL) <> (p_emballage_consomme = 0)
       OR (p_conforme = 'NON' AND (p_quantite_produite <> 0 OR p_emballage_mp_id IS NOT NULL)) THEN
        RAISE EXCEPTION 'Combinaison conformité/emballage/quantité invalide' USING ERRCODE = '22023';
    END IF;

    -- This row lock serializes duplicate attempts for a given OF.
    SELECT of_id, pf_id, recette_id, sku_id, statut, quantite_prevue
      INTO v_of FROM public.ordres_fabrication
     WHERE of_id = p_of_id FOR UPDATE;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'OF inexistant' USING ERRCODE = '23503';
    END IF;

    v_request := jsonb_build_object('conforme', p_conforme,
                                    'remarques', p_remarques,
                                    'controleur', p_controleur,
                                    'quantite_produite', p_quantite_produite,
                                    'emballage_mp_id', p_emballage_mp_id,
                                    'emballage_consomme', p_emballage_consomme);
    SELECT request_payload, result_payload INTO v_saved_request, v_saved_result
      FROM public.erp_of_closures WHERE of_id = p_of_id FOR UPDATE;
    IF FOUND THEN
        IF v_saved_request IS DISTINCT FROM v_request THEN
            RAISE EXCEPTION 'OF déjà clôturé avec paramètres différents' USING ERRCODE = '23505';
        END IF;
        IF v_saved_result IS NOT NULL THEN
            RETURN v_saved_result;
        END IF;
        -- A NULL result would indicate a damaged/incomplete journal.
        RAISE EXCEPTION 'Clôture incomplète : journal à examiner' USING ERRCODE = '23514';
    END IF;
    IF v_of.statut IS NULL OR v_of.statut NOT IN ('PLANIFIE', 'EN_COURS') THEN
        RAISE EXCEPTION 'OF non clôturable dans cet état' USING ERRCODE = '23514';
    END IF;
    IF p_conforme = 'OUI' THEN
        IF v_of.pf_id IS NULL OR v_of.recette_id IS NULL OR v_of.sku_id IS NULL THEN
            RAISE EXCEPTION 'OF incomplet' USING ERRCODE = '23514';
        END IF;
        IF v_of.quantite_prevue IS NULL OR v_of.quantite_prevue <= 0 THEN
            RAISE EXCEPTION 'Quantité prévue invalide' USING ERRCODE = '23514';
        END IF;
        -- Do NOT infer a batch conversion: quantite_par_unite means per one
        -- produced unit, exactly as in the pre-existing Python implementation.
        SELECT recette_id, pf_id, actif INTO v_recipe FROM public.recettes
         WHERE recette_id = v_of.recette_id FOR SHARE;
        IF NOT FOUND OR v_recipe.pf_id IS DISTINCT FROM v_of.pf_id
           OR upper(btrim(coalesce(v_recipe.actif, ''))) <> 'OUI' THEN
            RAISE EXCEPTION 'Recette absente, inactive ou incompatible' USING ERRCODE = '23514';
        END IF;
        SELECT pf_id INTO v_sku_pf_id FROM public.sku_conditionnement
         WHERE sku_id = v_of.sku_id FOR SHARE;
        IF NOT FOUND OR v_sku_pf_id IS DISTINCT FROM v_of.pf_id THEN
            RAISE EXCEPTION 'SKU absent ou incompatible' USING ERRCODE = '23514';
        END IF;

        FOR v_line IN SELECT mp_id, quantite_par_unite
                        FROM public.lignes_recette
                       WHERE recette_id = v_of.recette_id FOR SHARE
        LOOP
            IF v_line.mp_id IS NULL OR length(btrim(v_line.mp_id)) = 0
               OR v_line.quantite_par_unite IS NULL
               OR v_line.quantite_par_unite::text IN ('NaN', 'Infinity', '-Infinity')
               OR v_line.quantite_par_unite <= 0 THEN
                RAISE EXCEPTION 'Nomenclature invalide' USING ERRCODE = '23514';
            END IF;
            v_line_qty := v_line.quantite_par_unite * p_quantite_produite;
            IF v_line_qty <= 0 OR v_line_qty >= 1000000000000000 THEN
                RAISE EXCEPTION 'Besoin matière hors limites' USING ERRCODE = '23514';
            END IF;
            v_needs := jsonb_set(v_needs, ARRAY[v_line.mp_id],
                to_jsonb(coalesce((v_needs ->> v_line.mp_id)::numeric, 0) + v_line_qty), true);
            v_item_count := v_item_count + 1;
        END LOOP;
        IF v_item_count = 0 THEN
            RAISE EXCEPTION 'Recette sans composant' USING ERRCODE = '23514';
        END IF;
        IF p_emballage_mp_id IS NOT NULL THEN
            v_needs := jsonb_set(v_needs, ARRAY[p_emballage_mp_id],
                to_jsonb(coalesce((v_needs ->> p_emballage_mp_id)::numeric, 0) + p_emballage_consomme), true);
        END IF;
    END IF;

    INSERT INTO public.erp_of_closures(of_id, request_payload)
    VALUES(p_of_id, v_request);

    IF p_conforme = 'OUI' THEN
        -- Sort deterministically to avoid two simultaneous OFs locking the
        -- same set of MPs in different orders (one advisory lock per MP).
        FOR v_mp_id IN SELECT mp_id FROM jsonb_object_keys(v_needs) AS x(mp_id) ORDER BY mp_id
        LOOP
            v_required := (v_needs ->> v_mp_id)::numeric;
            IF v_required <= 0 OR v_required >= 1000000000000000 THEN
                RAISE EXCEPTION 'Besoin cumulé matière hors limites' USING ERRCODE = '23514';
            END IF;
            -- Nested function invocation stays IN THIS SAME database transaction.
            v_movement := public.erp_apply_stock_movement(
                'OF-MP-' || encode(sha256(convert_to(p_of_id || ':' || v_mp_id, 'UTF8')), 'hex'),
                'MP', 'SORTIE', v_mp_id, v_required, NULL,
                'Production OF ' || p_of_id, NULL);
            IF v_movement IS NULL OR jsonb_typeof(v_movement -> 'lot_allocations') <> 'array' THEN
                RAISE EXCEPTION 'FIFO ne retourne pas les lots consommés' USING ERRCODE = '23514';
            END IF;
            v_cost_total := v_cost_total + (v_movement ->> 'cost_total')::numeric;
            FOR v_lot IN SELECT lot_id, taken FROM jsonb_to_recordset(v_movement -> 'lot_allocations')
                              AS x(lot_id text, taken numeric)
            LOOP
                IF v_lot.lot_id IS NULL OR v_lot.taken IS NULL OR v_lot.taken <= 0 THEN
                    RAISE EXCEPTION 'Traçabilité FIFO invalide' USING ERRCODE = '23514';
                END IF;
                INSERT INTO public.consommations_of(
                    consommation_id, of_id, mp_id, lot_id, quantite_consommee)
                VALUES ('CNOF-' || gen_random_uuid()::text, p_of_id,
                        v_mp_id, v_lot.lot_id, v_lot.taken);
                v_consumed_rows := v_consumed_rows + 1;
            END LOOP;
        END LOOP;
        v_pf_movement := public.erp_apply_stock_movement(
            'OF-PF-' || encode(sha256(convert_to(p_of_id || ':' || v_of.sku_id, 'UTF8')), 'hex'),
            'PF', 'ENTREE', v_of.sku_id, p_quantite_produite,
            v_cost_total / p_quantite_produite, 'Production OF ' || p_of_id, NULL);
        IF v_pf_movement IS NULL OR (v_pf_movement ->> 'lot_id') IS NULL THEN
            RAISE EXCEPTION 'Entrée PF non confirmée' USING ERRCODE = '23514';
        END IF;
    END IF;

    INSERT INTO public.controle_qualite(qc_id, of_id, date, conforme, remarques, controleur)
    VALUES ('QC-' || gen_random_uuid()::text, p_of_id, v_now, p_conforme, p_remarques, p_controleur);

    UPDATE public.ordres_fabrication
       SET statut = CASE WHEN p_conforme = 'OUI' THEN 'TERMINE' ELSE 'REJETE' END,
           date_debut = CASE WHEN p_conforme = 'OUI' AND
                                   (date_debut IS NULL OR date_debut = '')
                              THEN v_today ELSE date_debut END,
           date_fin = v_today,
           quantite_produite = CASE WHEN p_conforme = 'OUI' THEN p_quantite_produite ELSE 0 END,
           cout_total = round(v_cost_total, 2)
     WHERE of_id = p_of_id;

    v_result := jsonb_build_object(
        'of_id', p_of_id,
        'statut', CASE WHEN p_conforme = 'OUI' THEN 'TERMINE' ELSE 'REJETE' END,
        'quantite_produite', CASE WHEN p_conforme = 'OUI' THEN p_quantite_produite ELSE 0 END,
        'cout_total', round(v_cost_total, 2),
        'nb_consommations', v_consumed_rows);

    UPDATE public.erp_of_closures SET result_payload = v_result WHERE of_id = p_of_id;
    INSERT INTO public.erp_of_outbox(of_id, payload)
    VALUES(p_of_id, jsonb_build_object('of_id', p_of_id, 'result', v_result));
    RETURN v_result;
END;
$body$;

-- Atomic state transition: only PLANIFIE -> EN_COURS, never reopen closed OFs.
CREATE OR REPLACE FUNCTION public.erp_start_manufacturing_order(p_of_id text)
RETURNS jsonb
LANGUAGE plpgsql
SECURITY INVOKER
SET search_path = pg_catalog, public
AS $start$
DECLARE
    v_status text;
BEGIN
    IF p_of_id IS NULL OR length(btrim(p_of_id)) = 0 OR length(p_of_id) > 200 THEN
        RAISE EXCEPTION 'Identifiant OF invalide' USING ERRCODE = '22023';
    END IF;
    SELECT statut INTO v_status FROM public.ordres_fabrication
     WHERE of_id = p_of_id FOR UPDATE;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'OF inexistant' USING ERRCODE = '23503';
    END IF;
    IF v_status = 'PLANIFIE' THEN
        UPDATE public.ordres_fabrication
           SET statut = 'EN_COURS',
               date_debut = CASE WHEN date_debut IS NULL OR date_debut = ''
                                 THEN to_char(now() AT TIME ZONE 'UTC', 'YYYY-MM-DD')
                                 ELSE date_debut END
         WHERE of_id = p_of_id;
    ELSIF v_status <> 'EN_COURS' THEN
        RAISE EXCEPTION 'Transition impossible : OF non planifié ou déjà clos'
            USING ERRCODE = '23514';
    END IF;
    RETURN jsonb_build_object('of_id', p_of_id, 'statut', 'EN_COURS');
END;
$start$;

REVOKE ALL ON FUNCTION public.erp_close_manufacturing_order(text,text,text,text,numeric,text,numeric)
    FROM PUBLIC, anon, authenticated;
GRANT EXECUTE ON FUNCTION public.erp_close_manufacturing_order(text,text,text,text,numeric,text,numeric)
    TO service_role;
REVOKE ALL ON FUNCTION public.erp_start_manufacturing_order(text)
    FROM PUBLIC, anon, authenticated;
GRANT EXECUTE ON FUNCTION public.erp_start_manufacturing_order(text) TO service_role;
REVOKE ALL ON public.erp_of_closures, public.erp_of_outbox FROM PUBLIC, anon, authenticated;
GRANT SELECT, INSERT, UPDATE ON public.erp_of_closures, public.erp_of_outbox TO service_role;

COMMIT;
