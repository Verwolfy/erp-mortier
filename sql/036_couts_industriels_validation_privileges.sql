-- 036: privilege-closed state transitions for industrial cost periods.
-- Existing validated periods are untouched. CUMP and accounting unchanged.
BEGIN;

CREATE OR REPLACE FUNCTION public.erp_cost_guard_period_insert()
RETURNS trigger
LANGUAGE plpgsql
SET search_path = pg_catalog, public
AS $body$
BEGIN
  IF NEW.statut IS DISTINCT FROM 'BROUILLON' THEN
    RAISE EXCEPTION 'Une nouvelle période doit démarrer BROUILLON'
      USING ERRCODE = '23514';
  END IF;
  RETURN NEW;
END;
$body$;

DROP TRIGGER IF EXISTS erp_cost_guard_period_insert ON public.erp_cost_periods;
CREATE TRIGGER erp_cost_guard_period_insert
BEFORE INSERT ON public.erp_cost_periods
FOR EACH ROW EXECUTE FUNCTION public.erp_cost_guard_period_insert();

-- No direct transition to VALIDE by service_role: only trusted definer RPC
-- has permissions to UPDATE period status. Other period edits stay prohibited.
REVOKE UPDATE, DELETE ON TABLE public.erp_cost_periods FROM service_role;
GRANT SELECT, INSERT ON TABLE public.erp_cost_periods TO service_role;

CREATE OR REPLACE FUNCTION public.erp_cost_validate_period(p_period_id text)
RETURNS jsonb
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = pg_catalog, public
AS $body$
DECLARE
  v_status text;
  v_audit jsonb;
BEGIN
  IF p_period_id IS NULL OR length(btrim(p_period_id)) NOT BETWEEN 1 AND 128 THEN
    RAISE EXCEPTION 'Identifiant de période invalide' USING ERRCODE = '22023';
  END IF;

  SELECT statut INTO v_status
  FROM public.erp_cost_periods
  WHERE period_id = p_period_id FOR UPDATE;
  IF v_status IS DISTINCT FROM 'BROUILLON' THEN
    RAISE EXCEPTION 'Période absente ou non validable' USING ERRCODE = '23514';
  END IF;

  IF NOT EXISTS (
    SELECT 1 FROM public.erp_cost_pools WHERE period_id = p_period_id
  ) OR NOT EXISTS (
    SELECT 1 FROM public.erp_cost_drivers WHERE period_id = p_period_id
  ) THEN
    RAISE EXCEPTION 'Charges et assiettes obligatoires' USING ERRCODE = '23514';
  END IF;

  IF EXISTS (
    SELECT 1 FROM public.erp_cost_pools
    WHERE period_id = p_period_id AND statut <> 'DOCUMENTE'
  ) THEN
    RAISE EXCEPTION 'Charges simulées non validables' USING ERRCODE = '23514';
  END IF;

  v_audit := public.erp_cost_period_audit(p_period_id);
  IF v_audit->>'audit_ok' IS DISTINCT FROM 'true' THEN
    RAISE EXCEPTION 'Audit non conforme' USING ERRCODE = '23514';
  END IF;

  UPDATE public.erp_cost_periods SET statut='VALIDE'
  WHERE period_id = p_period_id;
  RETURN v_audit;
END;
$body$;

-- Harden function ownership to the database migration role and narrow EXECUTE.
REVOKE ALL ON FUNCTION public.erp_cost_validate_period(text)
  FROM PUBLIC, anon, authenticated;
GRANT EXECUTE ON FUNCTION public.erp_cost_validate_period(text) TO service_role;

-- Reassert protection of the period table from client roles.
REVOKE ALL ON TABLE public.erp_cost_periods FROM PUBLIC, anon, authenticated;
COMMIT;
