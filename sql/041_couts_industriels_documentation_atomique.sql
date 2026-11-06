-- 041 : liaison SCF + statut DOCUMENTE atomiques dans une transaction SQL.
-- Répare le risque d'une preuve écrite sans statut après une panne entre deux requêtes HTTP.
-- Pré-requis : migrations 034 à 040. Ne modifie ni SCF, ni stock, ni CUMP.
BEGIN;
CREATE OR REPLACE FUNCTION public.erp_cost_document_pool_atomic(
 p_period_id text, p_pool_id text, p_piece_id uuid,
 p_scf_ligne_id bigint, p_explication text)
RETURNS jsonb
LANGUAGE plpgsql SECURITY DEFINER
SET search_path=pg_catalog,public
AS $fn$
DECLARE v_pool record; v_statut text; v_debit numeric; v_existing record;
BEGIN
 IF p_period_id IS NULL OR length(btrim(p_period_id)) NOT BETWEEN 1 AND 128
 OR p_pool_id IS NULL OR length(btrim(p_pool_id)) NOT BETWEEN 1 AND 128
 OR p_piece_id IS NULL OR p_scf_ligne_id IS NULL OR p_scf_ligne_id<=0
 OR p_explication IS NULL OR length(btrim(p_explication)) NOT BETWEEN 10 AND 1000 THEN
  RAISE EXCEPTION 'Paramètres documentaires invalides' USING ERRCODE='22023';
 END IF;

 -- Sérialise avec la validation de période (même ligne et même verrou).
 SELECT statut INTO v_statut FROM public.erp_cost_periods
 WHERE period_id=p_period_id FOR UPDATE;
 IF v_statut IS DISTINCT FROM 'BROUILLON' THEN
  RAISE EXCEPTION 'Période non modifiable' USING ERRCODE='23514'; END IF;
 SELECT pool_id,statut,montant_dzd INTO v_pool FROM public.erp_cost_pools
 WHERE pool_id=p_pool_id AND period_id=p_period_id FOR UPDATE;
 IF NOT FOUND OR v_pool.statut NOT IN ('SIMULATION','DOCUMENTE') THEN
  RAISE EXCEPTION 'Charge non documentable' USING ERRCODE='23514'; END IF;
 -- Statut DOCUMENTE déjà présent : un second appel identique est sans effet.
 SELECT piece_id,scf_ligne_id,explication_imputation INTO v_existing
 FROM public.erp_cost_pool_scf_evidence WHERE pool_id=p_pool_id FOR UPDATE;
 IF FOUND THEN
  IF v_existing.piece_id IS DISTINCT FROM p_piece_id
   OR v_existing.scf_ligne_id IS DISTINCT FROM p_scf_ligne_id
   OR v_existing.explication_imputation IS DISTINCT FROM btrim(p_explication) THEN
    RAISE EXCEPTION 'Preuve différente déjà rattachée; correction manuelle nécessaire'
     USING ERRCODE='23514';
  END IF;
 END IF;

 SELECT l.debit INTO v_debit
 FROM public.scf_lignes l
 JOIN public.scf_pieces s ON s.piece_id=l.piece_id
 WHERE l.ligne_id=p_scf_ligne_id AND l.piece_id=p_piece_id
 AND s.statut='VALIDEE' AND s.date_validation IS NOT NULL;
 IF v_debit IS NULL OR v_debit<=0 OR v_pool.montant_dzd>v_debit THEN
  RAISE EXCEPTION 'Débit SCF absent, non validé ou insuffisant'
   USING ERRCODE='23514';
 END IF;

 IF v_existing.piece_id IS NULL THEN
  INSERT INTO public.erp_cost_pool_scf_evidence
    (pool_id,piece_id,scf_ligne_id,explication_imputation)
  VALUES (p_pool_id,p_piece_id,p_scf_ligne_id,btrim(p_explication));
 END IF;
 IF v_pool.statut='SIMULATION' THEN
  UPDATE public.erp_cost_pools
  SET statut='DOCUMENTE',justificatif=('SCF:'||p_piece_id::text)
  WHERE pool_id=p_pool_id AND period_id=p_period_id;
 END IF;
 RETURN jsonb_build_object('documented',true,'pool_id',p_pool_id,
  'period_id',p_period_id,'piece_id',p_piece_id,'scf_ligne_id',p_scf_ligne_id);
END $fn$;

REVOKE ALL ON FUNCTION public.erp_cost_document_pool_atomic(text,text,uuid,bigint,text)
 FROM PUBLIC,anon,authenticated;
GRANT EXECUTE ON FUNCTION public.erp_cost_document_pool_atomic(text,text,uuid,bigint,text)
 TO service_role;
COMMIT;
