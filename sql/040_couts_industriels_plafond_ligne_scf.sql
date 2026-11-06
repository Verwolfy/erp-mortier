-- 040 : plafond quantitatif par ligne SCF au debit, une ligne = une charge.
-- Controle de coherence documentaire, pas une determination automatique d'eligibilite.
BEGIN;
DO $migration$
BEGIN
 IF EXISTS (SELECT 1 FROM public.erp_cost_pool_scf_evidence) THEN
  RAISE EXCEPTION 'Références SCF déjà présentes : rapprochement manuel préalable';
 END IF;
END $migration$;

ALTER TABLE public.erp_cost_pool_scf_evidence
 ADD COLUMN scf_ligne_id bigint NOT NULL
 REFERENCES public.scf_lignes(ligne_id) ON DELETE RESTRICT;
ALTER TABLE public.erp_cost_pool_scf_evidence
 ADD CONSTRAINT erp_cost_evidence_unique_scf_line UNIQUE(scf_ligne_id);

CREATE OR REPLACE FUNCTION public.erp_cost_evidence_guard()
RETURNS trigger LANGUAGE plpgsql SECURITY DEFINER
SET search_path=pg_catalog,public
AS $fn$
DECLARE v_period text; v_state text; v_amount numeric; v_debit numeric;
BEGIN
 IF TG_OP='UPDATE' AND (
   NEW.pool_id IS DISTINCT FROM OLD.pool_id OR
   NEW.piece_id IS DISTINCT FROM OLD.piece_id OR
   NEW.scf_ligne_id IS DISTINCT FROM OLD.scf_ligne_id)
 THEN
   RAISE EXCEPTION 'Déplacement de preuve interdit' USING ERRCODE='23514';
 END IF;
 SELECT period_id,montant_dzd INTO v_period,v_amount
 FROM public.erp_cost_pools WHERE pool_id=NEW.pool_id;
 IF NOT FOUND THEN RAISE EXCEPTION 'Charge introuvable' USING ERRCODE='23503'; END IF;
 SELECT statut INTO v_state FROM public.erp_cost_periods
 WHERE period_id=v_period FOR UPDATE;
 IF v_state IS DISTINCT FROM 'BROUILLON' THEN
   RAISE EXCEPTION 'Période analytique verrouillée' USING ERRCODE='23514';
 END IF;
 SELECT l.debit INTO v_debit
 FROM public.scf_lignes l JOIN public.scf_pieces s ON s.piece_id=l.piece_id
 WHERE l.ligne_id=NEW.scf_ligne_id
 AND l.piece_id=NEW.piece_id
 AND s.statut='VALIDEE' AND s.date_validation IS NOT NULL;
 IF v_debit IS NULL OR v_debit<=0 THEN
   RAISE EXCEPTION 'Ligne SCF au débit validée et concordante obligatoire'
     USING ERRCODE='23514';
 END IF;
 IF v_amount>v_debit THEN
   RAISE EXCEPTION 'Imputation supérieure au débit de la ligne SCF'
     USING ERRCODE='23514';
 END IF;
 RETURN NEW;
END $fn$;

CREATE OR REPLACE FUNCTION public.erp_cost_require_evidence()
RETURNS trigger LANGUAGE plpgsql SECURITY DEFINER
SET search_path=pg_catalog,public
AS $fn$
DECLARE v_debit numeric;
BEGIN
 IF NEW.statut='DOCUMENTE' THEN
  SELECT l.debit INTO v_debit
  FROM public.erp_cost_pool_scf_evidence e
  JOIN public.scf_pieces s ON s.piece_id=e.piece_id
  JOIN public.scf_lignes l ON l.ligne_id=e.scf_ligne_id AND l.piece_id=e.piece_id
  WHERE e.pool_id=NEW.pool_id AND s.statut='VALIDEE' AND s.date_validation IS NOT NULL;
  IF v_debit IS NULL OR v_debit<=0 OR NEW.montant_dzd>v_debit THEN
   RAISE EXCEPTION 'Charge sans débit SCF validé suffisant' USING ERRCODE='23514';
  END IF;
 END IF;
 RETURN NEW;
END $fn$;

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
  RAISE EXCEPTION 'Période non validable' USING ERRCODE='23514'; END IF;
 IF NOT EXISTS(SELECT 1 FROM public.erp_cost_pools WHERE period_id=p_period_id)
 OR NOT EXISTS(SELECT 1 FROM public.erp_cost_drivers WHERE period_id=p_period_id) THEN
  RAISE EXCEPTION 'Charges et assiettes obligatoires' USING ERRCODE='23514'; END IF;
 IF EXISTS (
  SELECT 1 FROM public.erp_cost_pools p
  LEFT JOIN public.erp_cost_pool_scf_evidence e ON e.pool_id=p.pool_id
  LEFT JOIN public.scf_pieces s ON s.piece_id=e.piece_id
  LEFT JOIN public.scf_lignes l ON l.ligne_id=e.scf_ligne_id AND l.piece_id=e.piece_id
  WHERE p.period_id=p_period_id
  AND (p.statut<>'DOCUMENTE' OR l.ligne_id IS NULL
    OR s.statut IS DISTINCT FROM 'VALIDEE' OR s.date_validation IS NULL
    OR l.debit<=0 OR p.montant_dzd>l.debit)
 ) THEN
  RAISE EXCEPTION 'Imputation non rapprochée du débit SCF' USING ERRCODE='23514'; END IF;
 v_audit:=public.erp_cost_period_audit(p_period_id);
 IF v_audit->>'audit_ok' IS DISTINCT FROM 'true' THEN
  RAISE EXCEPTION 'Audit de répartition non conforme' USING ERRCODE='23514'; END IF;
 UPDATE public.erp_cost_periods SET statut='VALIDE' WHERE period_id=p_period_id;
 RETURN v_audit;
END $fn$;
-- Lecture de rapprochement : aucune ecriture comptable, montant restant de la ligne.
CREATE OR REPLACE VIEW public.erp_cost_scf_reconciliation
WITH (security_invoker=true) AS
SELECT p.period_id,p.pool_id,p.nature_code,p.montant_dzd AS montant_impute_dzd,
       s.piece_id,s.reference AS reference_scf,s.statut AS statut_scf,
       e.scf_ligne_id,l.compte,l.debit AS montant_debit_scf_dzd,
       (l.debit-p.montant_dzd) AS solde_non_impute_dzd,
       (p.statut='DOCUMENTE' AND s.statut='VALIDEE'
        AND s.date_validation IS NOT NULL AND l.debit>0
        AND p.montant_dzd<=l.debit) AS rapprochement_ok
FROM public.erp_cost_pools p
LEFT JOIN public.erp_cost_pool_scf_evidence e ON e.pool_id=p.pool_id
LEFT JOIN public.scf_pieces s ON s.piece_id=e.piece_id
LEFT JOIN public.scf_lignes l ON l.ligne_id=e.scf_ligne_id AND l.piece_id=e.piece_id;
REVOKE ALL ON public.erp_cost_scf_reconciliation FROM PUBLIC,anon,authenticated;
GRANT SELECT ON public.erp_cost_scf_reconciliation TO service_role;

REVOKE ALL ON FUNCTION public.erp_cost_validate_period(text) FROM PUBLIC,anon,authenticated;
GRANT EXECUTE ON FUNCTION public.erp_cost_validate_period(text) TO service_role;
COMMIT;