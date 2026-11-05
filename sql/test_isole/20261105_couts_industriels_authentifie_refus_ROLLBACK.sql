-- TEST ONLY: SQL role-based refusal for authenticated clients.
BEGIN;
SET LOCAL ROLE authenticated;
DO $acl$
DECLARE denied boolean;
BEGIN
 denied:=false;
 BEGIN
   PERFORM 1 FROM public.erp_cost_periods LIMIT 1;
 EXCEPTION WHEN insufficient_privilege THEN denied:=true;
 END;
 IF NOT denied THEN RAISE EXCEPTION 'authenticated SELECT non refuse'; END IF;
 denied:=false;
 BEGIN
   PERFORM public.erp_cost_validate_period('NO_SUCH_PERIOD');
 EXCEPTION WHEN insufficient_privilege THEN denied:=true;
 END;
 IF NOT denied THEN RAISE EXCEPTION 'authenticated RPC non refuse'; END IF;
END $acl$;
RESET ROLE;
SELECT 'AUTHENTICATED_DENIED_OK' AS verdict;
ROLLBACK;
