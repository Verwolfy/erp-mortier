-- 047 — Profilage SQL isolé des coûts industriels (TEST UNIQUEMENT).
-- AUCUN SCF, stock ou OF fictif conservé : BEGIN/ROLLBACK obligatoires.
BEGIN;
SET LOCAL statement_timeout='45s';
SET LOCAL lock_timeout='5s';

DO $guard$
BEGIN
 IF EXISTS(SELECT 1 FROM public.erp_cost_periods WHERE period_id='IT26_PROFILE_047')
 OR EXISTS(SELECT 1 FROM public.ordres_fabrication WHERE of_id LIKE 'IT26_PROFILE_OF_%')
 THEN RAISE EXCEPTION 'Fixtures de profilage déjà présentes'; END IF;
END $guard$;

INSERT INTO public.ordres_fabrication(
 of_id,quantite_prevue,quantite_produite,date_planification,date_fin,
 statut,cout_total,notes)
SELECT 'IT26_PROFILE_OF_'||lpad(n::text,5,'0'),10,10,
 '2026-11-05','2026-11-05','TERMINE',100,'[TEST] Profilage analytique'
FROM generate_series(1,500) AS g(n);

INSERT INTO public.erp_cost_periods(period_id,libelle,date_debut,date_fin,statut)
VALUES('IT26_PROFILE_047','[TEST] Profilage coût 047',
 '2026-11-01','2026-11-30','BROUILLON');

INSERT INTO public.erp_cost_pools(
 pool_id,period_id,nature_code,base_imputation,montant_dzd,justificatif,statut)
VALUES
 ('IT26_PROFILE_POOL_E','IT26_PROFILE_047','ENERGIE','HOURS_MACHINE',120,'[TEST] hypothèse énergie','SIMULATION'),
 ('IT26_PROFILE_POOL_M','IT26_PROFILE_047','MAIN_OEUVRE','HOURS_LABOR',90,'[TEST] hypothèse main oeuvre','SIMULATION');

INSERT INTO public.erp_cost_drivers(period_id,of_id,base_imputation,valeur,justificatif)
SELECT 'IT26_PROFILE_047','IT26_PROFILE_OF_'||lpad(n::text,5,'0'),
 base,1,'[TEST] assiette mesurée'
FROM generate_series(1,500) AS g(n)
CROSS JOIN (VALUES ('HOURS_MACHINE'),('HOURS_LABOR')) AS b(base);

ANALYZE public.erp_cost_drivers;
ANALYZE public.erp_cost_pools;

CREATE TEMP TABLE it26_profile_047_results
(label text, execution_ms numeric, shared_hit_blocks numeric, plan jsonb)
ON COMMIT DROP;

DO $profile$
DECLARE
 v_plan jsonb;
 v_audit jsonb;
BEGIN
 v_audit:=public.erp_cost_period_audit('IT26_PROFILE_047');
 IF v_audit->>'audit_ok' IS DISTINCT FROM 'true'
 OR (v_audit->>'total_impute_dzd')::numeric<>210 THEN
  RAISE EXCEPTION 'Audit profilage non conforme : %',v_audit;
 END IF;
 EXECUTE $explain$
  EXPLAIN (ANALYZE, BUFFERS, FORMAT JSON)
  SELECT public.erp_cost_period_audit('IT26_PROFILE_047')
 $explain$ INTO v_plan;
 INSERT INTO it26_profile_047_results
 VALUES ('audit_rpc', (v_plan->0->>'Execution Time')::numeric,
         coalesce((v_plan->0->'Plan'->>'Shared Hit Blocks')::numeric,0),v_plan);
 EXECUTE $explain$
  EXPLAIN (ANALYZE, BUFFERS, FORMAT JSON)
  SELECT coalesce(sum(montant_impute_dzd),0)
  FROM public.erp_cost_allocations WHERE period_id='IT26_PROFILE_047'
 $explain$ INTO v_plan;
 INSERT INTO it26_profile_047_results
 VALUES ('allocations_sum', (v_plan->0->>'Execution Time')::numeric,
         coalesce((v_plan->0->'Plan'->>'Shared Hit Blocks')::numeric,0),v_plan);
 EXECUTE $explain$
  EXPLAIN (ANALYZE, BUFFERS, FORMAT JSON)
  SELECT count(*) FROM public.erp_cost_drivers
  WHERE period_id='IT26_PROFILE_047' AND valeur>0
 $explain$ INTO v_plan;
 INSERT INTO it26_profile_047_results
 VALUES ('drivers_filter', (v_plan->0->>'Execution Time')::numeric,
         coalesce((v_plan->0->'Plan'->>'Shared Hit Blocks')::numeric,0),v_plan);
END $profile$;

SELECT 'COST_PROFILE_047_OK' AS verdict, 500 AS ordres_fictifs,
 1000 AS assiettes_fictives, 2 AS charges_fictives,
 (SELECT jsonb_agg(jsonb_build_object(
  'operation',label,'execution_ms',execution_ms,'shared_hit_blocks',shared_hit_blocks))
  FROM it26_profile_047_results) AS mesures,
 'ROLLBACK' AS persistance;
ROLLBACK;