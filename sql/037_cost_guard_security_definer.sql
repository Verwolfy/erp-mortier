-- 037: pool/driver edit guards can lock period row without granting service_role direct UPDATE.
-- Requires migration 036. The trigger cannot change period status; it only reads and locks.
BEGIN;
CREATE OR REPLACE FUNCTION public.erp_cost_check_editable()
RETURNS trigger
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = pg_catalog, public
AS $fn$
DECLARE
  v_period_id text;
  v_status text;
BEGIN
  v_period_id := CASE WHEN TG_OP='DELETE' THEN OLD.period_id ELSE NEW.period_id END;
  SELECT statut INTO v_status
    FROM public.erp_cost_periods
   WHERE period_id=v_period_id FOR UPDATE;
  IF v_status IS DISTINCT FROM 'BROUILLON' THEN
    RAISE EXCEPTION 'Période analytique non modifiable' USING ERRCODE='23514';
  END IF;
  IF TG_OP='DELETE' THEN
    RETURN OLD;
  END IF;
  IF TG_OP='UPDATE' AND NEW.period_id IS DISTINCT FROM OLD.period_id THEN
    RAISE EXCEPTION 'Transfert entre périodes interdit' USING ERRCODE='23514';
  END IF;
  RETURN NEW;
END;
$fn$;

REVOKE ALL ON FUNCTION public.erp_cost_check_editable()
  FROM PUBLIC, anon, authenticated, service_role;
COMMIT;
