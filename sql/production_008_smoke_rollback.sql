-- Après installation de la migration 008 sur un environnement DE TEST.
-- Exécuter sous SQL Editor (rôle administrateur/service_role), ROLLBACK final.
-- Si les référentiels sont vides, le test est IGNORÉ (pas « réussi »).
BEGIN;
DO $test$
DECLARE
    v_pf text;
    v_mp text;
    v_sku text;
    v_op text := 'SMOKE-008-' || gen_random_uuid()::text;
    v_req jsonb;
    v_first jsonb;
    v_retry jsonb;
    v_of jsonb;
    v_count bigint;
BEGIN
    SELECT pf_id INTO v_pf FROM public.produits
       WHERE upper(btrim(coalesce(actif, ''))) = 'OUI' LIMIT 1;
    SELECT mp_id INTO v_mp FROM public.matieres_premieres
       WHERE upper(btrim(coalesce(actif, ''))) = 'OUI'
         AND upper(btrim(coalesce(categorie_mp, ''))) NOT IN ('EMBALLAGE', 'EMBALLAGE_CONSOMMABLE')
       LIMIT 1;
    IF v_pf IS NULL OR v_mp IS NULL THEN
        RAISE NOTICE 'TEST 008 IGNORE : référentiels PF/MP actifs insuffisants';
        RETURN;
    END IF;
    v_req := jsonb_build_array(jsonb_build_object('mp_id', v_mp, 'quantite_par_unite', '1'));
    v_first := public.erp_create_recipe(v_op, v_pf, 'SMOKE-V1', 100, '', '2026-10-23', v_req);
    v_retry := public.erp_create_recipe(v_op, v_pf, 'SMOKE-V1', 100, '', '2026-10-23', v_req);
    IF v_first IS DISTINCT FROM v_retry THEN
        RAISE EXCEPTION 'TEST 008 ECHEC : rejouer crée un nouveau document';
    END IF;
    SELECT count(*) INTO v_count FROM public.lignes_recette
       WHERE recette_id = v_first ->> 'recette_id';
    IF v_count <> 1 THEN
        RAISE EXCEPTION 'TEST 008 ECHEC : lignes de recette incorrectes';
    END IF;
    RAISE NOTICE 'TEST 008 RECETTE OK : % / 1 ligne, idempotent', v_first ->> 'recette_id';
    SELECT sku_id INTO v_sku FROM public.sku_conditionnement
       WHERE pf_id = v_pf AND sku_id <> 'SKU-007'
         AND upper(btrim(coalesce(actif, ''))) = 'OUI' LIMIT 1;
    IF v_sku IS NULL THEN
        RAISE NOTICE 'TEST 008 OF IGNORE : pas de SKU actif compatible';
        RETURN;
    END IF;
    v_of := public.erp_create_manufacturing_order(v_op || '-OF', v_pf,
       v_first ->> 'recette_id', v_sku, 2, '2026-10-23', 'Test 008');
    IF v_of IS DISTINCT FROM public.erp_create_manufacturing_order(v_op || '-OF', v_pf,
       v_first ->> 'recette_id', v_sku, 2, '2026-10-23', 'Test 008') THEN
        RAISE EXCEPTION 'TEST 008 ECHEC : répétition OF non idempotente';
    END IF;
    RAISE NOTICE 'TEST 008 OF OK : % idempotent', v_of ->> 'of_id';
END;
$test$;
ROLLBACK;
