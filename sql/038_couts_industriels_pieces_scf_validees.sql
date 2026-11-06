-- 038: lien structurel obligatoire vers une piece SCF VALIDEE pour toute charge DOCUMENTE.
-- Ne comptabilise aucun montant, ne modifie ni stock, ni OF, ni SCF.
BEGIN;
CREATE TABLE IF NOT EXISTS public.erp_cost_pool_scf_evidence (
  pool_id text PRIMARY KEY REFERENCES public.erp_cost_pools(pool_id) ON DELETE RESTRICT,
  piece_id uuid NOT NULL UNIQUE REFERENCES public.scf_pieces(piece_id) ON DELETE RESTRICT,
  explication_imputation text NOT NULL
    CHECK(length(btrim(explication_imputation)) BETWEEN 10 AND 1000),
  created_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS erp_cost_evidence_piece_idx
 ON public.erp_cost_pool_scf_evidence(piece_id);

CREATE OR REPLACE FUNCTION public.erp_cost_evidence_guard()
RETURNS trigger LANGUAGE plpgsql SECURITY DEFINER
SET search_path=pg_catalog,public
AS $fn$
DECLARE v_period text; v_status text;
BEGIN
 IF TG_OP='UPDATE' AND (NEW.pool_id IS DISTINCT FROM OLD.pool_id
       OR NEW.piece_id IS DISTINCT FROM OLD.piece_id) THEN
  RAISE EXCEPTION 'Réaffectation de pièce interdite' USING ERRCODE='23514';
 END IF;
 SELECT period_id INTO v_period FROM public.erp_cost_pools
 WHERE pool_id=NEW.pool_id;
 IF v_period IS NULL THEN RAISE EXCEPTION 'Charge introuvable' USING ERRCODE='23503'; END IF;
 SELECT statut INTO v_status FROM public.erp_cost_periods
 WHERE period_id=v_period FOR UPDATE;
 IF v_status IS DISTINCT FROM 'BROUILLON' THEN
  RAISE EXCEPTION 'Période non modifiable' USING ERRCODE='23514'; END IF;
 IF NOT EXISTS(SELECT 1 FROM public.scf_pieces s
               WHERE s.piece_id=NEW.piece_id
                 AND s.statut='VALIDEE'
                 AND s.date_validation IS NOT NULL) THEN
  RAISE EXCEPTION 'Pièce SCF non validée ou absente' USING ERRCODE='23514'; END IF;
 RETURN NEW;
END $fn$;

DROP TRIGGER IF EXISTS erp_cost_evidence_guard_trigger
 ON public.erp_cost_pool_scf_evidence;
CREATE TRIGGER erp_cost_evidence_guard_trigger
BEFORE INSERT OR UPDATE ON public.erp_cost_pool_scf_evidence
FOR EACH ROW EXECUTE FUNCTION public.erp_cost_evidence_guard();

-- Les suppressions restent possibles seulement en brouillon et via le role serveur.
CREATE OR REPLACE FUNCTION public.erp_cost_evidence_delete_guard()
RETURNS trigger LANGUAGE plpgsql SECURITY DEFINER
SET search_path=pg_catalog,public
AS $fn$
BEGIN
 IF NOT EXISTS(
 SELECT 1 FROM public.erp_cost_pools p
 JOIN public.erp_cost_periods t ON t.period_id=p.period_id
 WHERE p.pool_id=OLD.pool_id AND t.statut='BROUILLON') THEN
 RAISE EXCEPTION 'Période non modifiable' USING ERRCODE='23514'; END IF;
 RETURN OLD;
END $fn$;
DROP TRIGGER IF EXISTS erp_cost_evidence_delete_guard_trigger
 ON public.erp_cost_pool_scf_evidence;
CREATE TRIGGER erp_cost_evidence_delete_guard_trigger
BEFORE DELETE ON public.erp_cost_pool_scf_evidence
FOR EACH ROW EXECUTE FUNCTION public.erp_cost_evidence_delete_guard();

-- Contrôle d'une transition SIMULATION -> DOCUMENTE hors API Python.
CREATE OR REPLACE FUNCTION public.erp_cost_require_evidence()
RETURNS trigger LANGUAGE plpgsql SECURITY DEFINER
SET search_path=pg_catalog,public
AS $fn$
BEGIN
 IF NEW.statut='DOCUMENTE' AND NOT EXISTS(
 SELECT 1 FROM public.erp_cost_pool_scf_evidence e
 JOIN public.scf_pieces s ON s.piece_id=e.piece_id
 WHERE e.pool_id=NEW.pool_id AND s.statut='VALIDEE' AND s.date_validation IS NOT NULL
 ) THEN
 RAISE EXCEPTION 'Charge DOCUMENTE sans pièce SCF validée' USING ERRCODE='23514';
 END IF;
 RETURN NEW;
END $fn$;
DROP TRIGGER IF EXISTS erp_cost_require_evidence_trigger
 ON public.erp_cost_pools;
CREATE TRIGGER erp_cost_require_evidence_trigger
BEFORE INSERT OR UPDATE ON public.erp_cost_pools
FOR EACH ROW EXECUTE FUNCTION public.erp_cost_require_evidence();

-- Ajoute un contrôle de preuve à la validation de période existante.
CREATE OR REPLACE FUNCTION public.erp_cost_validate_period(p_period_id text)
RETURNS jsonb LANGUAGE plpgsql SECURITY DEFINER
SET search_path=pg_catalog,public
AS $fn$
DECLARE v_status text; v_audit jsonb;
BEGIN
 IF p_period_id IS NULL OR length(btrim(p_period_id)) NOT BETWEEN 1 AND 128 THEN
 RAISE EXCEPTION 'Identifiant de période invalide' USING ERRCODE='22023'; END IF;
 SELECT statut INTO v_status FROM public.erp_cost_periods
 WHERE period_id=p_period_id FOR UPDATE;
 IF v_status IS DISTINCT FROM 'BROUILLON' THEN
 RAISE EXCEPTION 'Période absente ou non validable' USING ERRCODE='23514'; END IF;
 IF NOT EXISTS(SELECT 1 FROM public.erp_cost_pools WHERE period_id=p_period_id)
 OR NOT EXISTS(SELECT 1 FROM public.erp_cost_drivers WHERE period_id=p_period_id) THEN
 RAISE EXCEPTION 'Charges et assiettes obligatoires' USING ERRCODE='23514'; END IF;
 IF EXISTS(
 SELECT 1 FROM public.erp_cost_pools p
 LEFT JOIN public.erp_cost_pool_scf_evidence e ON e.pool_id=p.pool_id
 LEFT JOIN public.scf_pieces s ON s.piece_id=e.piece_id
 WHERE p.period_id=p_period_id
 AND (p.statut<>'DOCUMENTE' OR s.piece_id IS NULL
      OR s.statut<>'VALIDEE' OR s.date_validation IS NULL)
 ) THEN
 RAISE EXCEPTION 'Charge non justifiée par pièce SCF validée' USING ERRCODE='23514'; END IF;
 v_audit:=public.erp_cost_period_audit(p_period_id);
 IF v_audit->>'audit_ok' IS DISTINCT FROM 'true' THEN
 RAISE EXCEPTION 'Audit de répartition non conforme' USING ERRCODE='23514'; END IF;
 UPDATE public.erp_cost_periods SET statut='VALIDE' WHERE period_id=p_period_id;
 RETURN v_audit;
END $fn$;
REVOKE ALL ON FUNCTION public.erp_cost_validate_period(text) FROM PUBLIC,anon,authenticated;
GRANT EXECUTE ON FUNCTION public.erp_cost_validate_period(text) TO service_role;

ALTER TABLE public.erp_cost_pool_scf_evidence ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON public.erp_cost_pool_scf_evidence FROM PUBLIC,anon,authenticated;
GRANT SELECT,INSERT,UPDATE,DELETE ON public.erp_cost_pool_scf_evidence TO service_role;
REVOKE ALL ON FUNCTION public.erp_cost_evidence_guard() FROM PUBLIC,anon,authenticated,service_role;
REVOKE ALL ON FUNCTION public.erp_cost_evidence_delete_guard() FROM PUBLIC,anon,authenticated,service_role;
REVOKE ALL ON FUNCTION public.erp_cost_require_evidence() FROM PUBLIC,anon,authenticated,service_role;

COMMIT;