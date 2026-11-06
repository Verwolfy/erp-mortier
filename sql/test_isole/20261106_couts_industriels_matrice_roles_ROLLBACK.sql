-- Campagne SQL des droits analytiques: TEST seulement, aucune persistance.
BEGIN;
SET LOCAL statement_timeout='20s';
DO $permissions$
DECLARE role_name text; denied boolean;
BEGIN
 FOREACH role_name IN ARRAY ARRAY['anon','authenticated'] LOOP
  EXECUTE format('SET LOCAL ROLE %I',role_name);
  denied:=false;
  BEGIN EXECUTE 'SELECT 1 FROM public.erp_cost_pool_scf_evidence LIMIT 1';
  EXCEPTION WHEN insufficient_privilege THEN denied:=true; END;
  IF NOT denied THEN RAISE EXCEPTION 'Lecture preuves autorisée au rôle %',role_name; END IF;

  denied:=false;
  BEGIN EXECUTE 'SELECT 1 FROM public.erp_cost_scf_reconciliation LIMIT 1';
  EXCEPTION WHEN insufficient_privilege THEN denied:=true; END;
  IF NOT denied THEN RAISE EXCEPTION 'Lecture rapprochement autorisée au rôle %',role_name; END IF;

  denied:=false;
  BEGIN PERFORM public.erp_cost_validate_period('DOES_NOT_EXIST');
  EXCEPTION WHEN insufficient_privilege THEN denied:=true; END;
  IF NOT denied THEN RAISE EXCEPTION 'Validation RPC autorisée au rôle %',role_name; END IF;
  RESET ROLE;
 END LOOP;

 SET LOCAL ROLE service_role;
 denied:=false;
 BEGIN
  UPDATE public.erp_cost_periods SET statut='VALIDE' WHERE period_id='DOES_NOT_EXIST';
 EXCEPTION WHEN insufficient_privilege THEN denied:=true; END;
 IF NOT denied THEN RAISE EXCEPTION 'UPDATE direct période permis au service_role'; END IF;
 RESET ROLE;
END $permissions$;
SELECT 'COST_ROLE_MATRIX_OK' AS verdict;
ROLLBACK;
