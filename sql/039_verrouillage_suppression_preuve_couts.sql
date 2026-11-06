-- 039: same row lock for evidence removal and period validation.
-- Prevents a concurrent deletion from detaching evidence after period approval.
BEGIN;
CREATE OR REPLACE FUNCTION public.erp_cost_evidence_delete_guard()
RETURNS trigger LANGUAGE plpgsql SECURITY DEFINER
SET search_path=pg_catalog,public
AS $fn$
DECLARE v_status text;
BEGIN
 SELECT t.statut INTO v_status
 FROM public.erp_cost_pools p
 JOIN public.erp_cost_periods t ON t.period_id=p.period_id
 WHERE p.pool_id=OLD.pool_id FOR UPDATE OF t;
 IF v_status IS DISTINCT FROM 'BROUILLON' THEN
   RAISE EXCEPTION 'Pièce analytique verrouillée par période validée'
     USING ERRCODE='23514';
 END IF;
 RETURN OLD;
END $fn$;
REVOKE ALL ON FUNCTION public.erp_cost_evidence_delete_guard()
 FROM PUBLIC, anon, authenticated, service_role;
COMMIT;
