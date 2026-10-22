-- ITERATION DE VALIDATION : nécessite la migration SQL 002 installée.
-- La quantité produite et la quantité prévue sont en UNITES SKU complètes.
-- La recette est en quantité MP par 1 unité de production (KG ou L) ;
-- facteur_conversion = nombre de KG ou L par 1 unité SKU.
-- L'emballage associé au SKU est consommé à raison d'une unité par SKU.
-- Une seule transaction SQL réalise les sorties MP, CNOF, l'entrée PF et le CQ.
-- Ne pas utiliser avant tests intégrés et vérification physique des emballages
-- (notamment SKU-007, seau 20 L pour 20 kg de peinture).
-- Ne modifie pas les tables ou identifiants métier existants.
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

-- Défense en profondeur : les tables techniques ne sont pas publiques.
ALTER TABLE public.erp_of_closures ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.erp_of_outbox ENABLE ROW LEVEL SECURITY;

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
    v_sku record;
    v_product record;
    v_pack record;
    v_material record;
    v_qty_base numeric;
    v_unit text;
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
    -- Le stock PF est suivi en unités SKU (sacs, fûts, IBC, seaux).
    IF p_quantite_produite IS NULL OR p_quantite_produite::text IN ('NaN', 'Infinity', '-Infinity')
       OR p_quantite_produite < 0 OR p_quantite_produite >= 1000000000000000
       OR (p_conforme = 'OUI' AND p_quantite_produite = 0)
       OR p_quantite_produite <> trunc(p_quantite_produite) THEN
        RAISE EXCEPTION 'Quantité produite invalide : nombre entier de SKU requis' USING ERRCODE = '22023';
    END IF;
    IF p_emballage_consomme IS NULL OR p_emballage_consomme::text IN ('NaN', 'Infinity', '-Infinity')
       OR p_emballage_consomme < 0 OR p_emballage_consomme >= 1000000000000000
       OR p_emballage_consomme <> trunc(p_emballage_consomme) THEN
        RAISE EXCEPTION 'Quantité emballage invalide : nombre entier requis' USING ERRCODE = '22023';
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
        IF v_of.quantite_prevue IS NULL OR v_of.quantite_prevue::text IN ('NaN', 'Infinity', '-Infinity')
           OR v_of.quantite_prevue <= 0 OR v_of.quantite_prevue >= 1000000000000000
           OR v_of.quantite_prevue <> trunc(v_of.quantite_prevue) THEN
            RAISE EXCEPTION 'Quantité prévue invalide : unités SKU entières requises' USING ERRCODE = '23514';
        END IF;
        -- La recette stocke une quantité MP par 1 unité de production (KG ou L),
        -- et non une quantité MP par emballage ni une quantité MP par batch.
        SELECT recette_id, pf_id, actif INTO v_recipe FROM public.recettes
         WHERE recette_id = v_of.recette_id FOR SHARE;
        IF NOT FOUND OR v_recipe.pf_id IS DISTINCT FROM v_of.pf_id
           OR upper(btrim(coalesce(v_recipe.actif, ''))) <> 'OUI' THEN
            RAISE EXCEPTION 'Recette absente, inactive ou incompatible' USING ERRCODE = '23514';
        END IF;
        SELECT pf_id, actif, unite_production INTO v_product
          FROM public.produits WHERE pf_id = v_of.pf_id FOR SHARE;
        IF NOT FOUND OR upper(btrim(coalesce(v_product.actif, ''))) <> 'OUI'
           OR upper(btrim(coalesce(v_product.unite_production, ''))) NOT IN ('KG', 'L') THEN
            RAISE EXCEPTION 'Produit inactif ou unité de production inconnue (KG/L)' USING ERRCODE = '23514';
        END IF;
        SELECT pf_id, actif, unite_vente, facteur_conversion, emballage_mp_id
          INTO v_sku FROM public.sku_conditionnement
         WHERE sku_id = v_of.sku_id FOR SHARE;
        IF NOT FOUND OR v_sku.pf_id IS DISTINCT FROM v_of.pf_id
           OR upper(btrim(coalesce(v_sku.actif, ''))) <> 'OUI'
           OR upper(btrim(coalesce(v_sku.unite_vente, ''))) NOT IN ('SAC', 'FUT', 'IBC', 'SEAU') THEN
            RAISE EXCEPTION 'SKU absent, inactif ou unité de vente incompatible' USING ERRCODE = '23514';
        END IF;
        IF v_sku.facteur_conversion IS NULL OR v_sku.facteur_conversion::text IN ('NaN', 'Infinity', '-Infinity')
           OR v_sku.facteur_conversion <= 0 OR v_sku.facteur_conversion >= 1000000000000000 THEN
            RAISE EXCEPTION 'Facteur de conversion SKU invalide' USING ERRCODE = '23514';
        END IF;
        -- Interdiction de convertir les KG en litres : le facteur est dans
        -- l'unité de production du PF (KG pour mortiers/peinture, L pour adjuvant).
        v_unit := upper(btrim(v_product.unite_production));
        v_qty_base := p_quantite_produite * v_sku.facteur_conversion;
        IF v_qty_base <= 0 OR v_qty_base >= 1000000000000000 THEN
            RAISE EXCEPTION 'Quantité de production KG/L hors limites' USING ERRCODE = '23514';
        END IF;

        -- Chaque SKU doit consommer exactement son emballage enregistré.
        IF v_sku.emballage_mp_id IS NULL OR btrim(v_sku.emballage_mp_id) = ''
           OR p_emballage_mp_id IS DISTINCT FROM v_sku.emballage_mp_id
           OR p_emballage_consomme IS DISTINCT FROM p_quantite_produite THEN
            RAISE EXCEPTION 'Emballage incompatible : 1 emballage par unité SKU' USING ERRCODE = '23514';
        END IF;
        SELECT categorie_mp, unite_stock, actif INTO v_pack
          FROM public.matieres_premieres WHERE mp_id = p_emballage_mp_id FOR SHARE;
        IF NOT FOUND OR upper(btrim(coalesce(v_pack.categorie_mp, ''))) <> 'EMBALLAGE'
           OR upper(btrim(coalesce(v_pack.unite_stock, ''))) <> 'U'
           OR upper(btrim(coalesce(v_pack.actif, ''))) <> 'OUI' THEN
            RAISE EXCEPTION 'Référence emballage inactive, absente ou non suivie en unités' USING ERRCODE = '23514';
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
            SELECT categorie_mp, actif INTO v_material
              FROM public.matieres_premieres WHERE mp_id = v_line.mp_id FOR SHARE;
            IF NOT FOUND OR upper(btrim(coalesce(v_material.actif, ''))) <> 'OUI'
               OR upper(btrim(coalesce(v_material.categorie_mp, ''))) IN ('EMBALLAGE', 'EMBALLAGE_CONSOMMABLE') THEN
                RAISE EXCEPTION 'Matière de recette absente, inactive ou définie comme emballage' USING ERRCODE = '23514';
            END IF;
            v_line_qty := v_line.quantite_par_unite * v_qty_base;
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
        -- Le conditionnement fait partie du coût des PF et du FIFO.
        -- Ne jamais autoriser l'emballage dans les lignes de recette :
        -- sinon sa consommation serait calculée en KG/L et doublée.
        IF v_needs ? p_emballage_mp_id THEN
            RAISE EXCEPTION 'Emballage déjà présent dans la recette' USING ERRCODE = '23514';
        END IF;
        v_needs := jsonb_set(v_needs, ARRAY[p_emballage_mp_id], to_jsonb(p_emballage_consomme), true);
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
        'quantite_base', CASE WHEN p_conforme = 'OUI' THEN v_qty_base ELSE 0 END,
        'unite_production', v_unit,
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
