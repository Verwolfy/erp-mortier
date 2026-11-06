-- 043 — Export analytique cohérent, borné et en lecture seule.
-- Lot 048. Un appel SQL STABLE partage un snapshot MVCC unique.
-- Ne pas qualifier cet export de comptabilité légale certifiée.
BEGIN;
CREATE OR REPLACE FUNCTION public.erp_cost_export_validated(p_period_id text)
RETURNS jsonb
LANGUAGE plpgsql STABLE SECURITY DEFINER
SET search_path=pg_catalog,public
AS $fn$
DECLARE
  v_period record;
  v_pool_count bigint;
  v_of_count bigint;
  v_driver_count bigint;
  v_evidence_count bigint;
  v_pool_total numeric;
  v_alloc_total numeric;
  v_missing bigint;
  v_payload jsonb;
BEGIN
 IF p_period_id IS NULL OR length(btrim(p_period_id)) NOT BETWEEN 1 AND 128 THEN
  RAISE EXCEPTION 'Identifiant de période invalide' USING ERRCODE='22023';
 END IF;
 SELECT period_id,libelle,date_debut,date_fin,statut
 INTO v_period FROM public.erp_cost_periods WHERE period_id=p_period_id;
 IF NOT FOUND OR v_period.statut IS DISTINCT FROM 'VALIDE' THEN
  RAISE EXCEPTION 'Export réservé à une période analytique validée'
    USING ERRCODE='23514';
 END IF;

 SELECT count(*),coalesce(sum(montant_dzd),0)
 INTO v_pool_count,v_pool_total
 FROM public.erp_cost_pools WHERE period_id=p_period_id;
 SELECT count(*),coalesce(sum(charges_imputees_dzd),0)
 INTO v_of_count,v_alloc_total
 FROM public.erp_cost_of_validation_snapshot WHERE period_id=p_period_id;
 SELECT count(*) INTO v_driver_count
 FROM public.erp_cost_drivers WHERE period_id=p_period_id;
 SELECT count(*) INTO v_evidence_count
 FROM public.erp_cost_pool_scf_evidence e
 JOIN public.erp_cost_pools p ON p.pool_id=e.pool_id
 WHERE p.period_id=p_period_id;

 IF v_pool_count=0 OR v_of_count=0 OR v_driver_count=0
 OR v_pool_count>5000 OR v_of_count>5000 OR v_driver_count>10000 THEN
  RAISE EXCEPTION 'Export absent, incomplet ou volumétrie supérieure à la limite'
   USING ERRCODE='23514';
 END IF;
 IF abs(v_pool_total-v_alloc_total)>=0.00001 THEN
  RAISE EXCEPTION 'Totaux analytique et instantané divergents'
   USING ERRCODE='23514';
 END IF;
 IF v_pool_count<>v_evidence_count THEN
  RAISE EXCEPTION 'Charges sans preuve SCF' USING ERRCODE='23514';
 END IF;
 SELECT count(*) INTO v_missing
 FROM public.erp_cost_pools p
 LEFT JOIN public.erp_cost_pool_scf_evidence e ON e.pool_id=p.pool_id
 LEFT JOIN public.scf_pieces s ON s.piece_id=e.piece_id
 LEFT JOIN public.scf_lignes l
   ON l.ligne_id=e.scf_ligne_id AND l.piece_id=e.piece_id
 WHERE p.period_id=p_period_id
 AND (p.statut IS DISTINCT FROM 'DOCUMENTE'
   OR s.statut IS DISTINCT FROM 'VALIDEE'
   OR s.date_validation IS NULL OR l.debit IS NULL OR l.debit<=0
   OR p.montant_dzd>l.debit);
 IF v_missing<>0 THEN
  RAISE EXCEPTION 'Preuve SCF manquante ou insuffisante'
   USING ERRCODE='23514';
 END IF;
 -- Toutes les agrégations ci-dessous sont lues dans le même snapshot de
 -- la fonction STABLE; aucun découpage en pages par requêtes HTTP.
 SELECT jsonb_build_object(
   'format','erp_cost_validated_export_v1',
   'scope','analytique_non_comptable',
   'snapshot_type','single_sql_statement',
   'generated_at',transaction_timestamp(),
   'period',jsonb_build_object(
      'period_id',v_period.period_id,'libelle',v_period.libelle,
      'date_debut',v_period.date_debut,'date_fin',v_period.date_fin,
      'statut',v_period.statut),
   'totals',jsonb_build_object(
      'charges_dzd',v_pool_total,
      'impute_valide_dzd',v_alloc_total,
      'pools',v_pool_count,'of',v_of_count,'assiettes',v_driver_count),
   'pools',(
      SELECT coalesce(jsonb_agg(
        jsonb_build_object('pool_id',p.pool_id,'nature_code',p.nature_code,
          'base_imputation',p.base_imputation,'montant_dzd',p.montant_dzd,
          'statut',p.statut,'piece_id',e.piece_id,
          'scf_ligne_id',e.scf_ligne_id,'explication',e.explication_imputation)
        ORDER BY p.pool_id),'[]'::jsonb)
      FROM public.erp_cost_pools p
      JOIN public.erp_cost_pool_scf_evidence e ON e.pool_id=p.pool_id
      WHERE p.period_id=p_period_id),
   'of_snapshots',(
      SELECT coalesce(jsonb_agg(
        jsonb_build_object('of_id',s.of_id,'statut_of',s.statut_of,
          'quantite_produite',s.quantite_produite,
          'cout_direct_of_dzd',s.cout_direct_of_dzd,
          'charges_imputees_dzd',s.charges_imputees_dzd,
          'cout_analytique_total_dzd',s.cout_analytique_total_dzd,
          'captured_at',s.captured_at)
        ORDER BY s.of_id),'[]'::jsonb)
      FROM public.erp_cost_of_validation_snapshot s
      WHERE s.period_id=p_period_id),
   'drivers',(
      SELECT coalesce(jsonb_agg(
        jsonb_build_object('of_id',d.of_id,
          'base_imputation',d.base_imputation,'valeur',d.valeur,
          'justificatif',d.justificatif)
        ORDER BY d.of_id,d.base_imputation),'[]'::jsonb)
      FROM public.erp_cost_drivers d WHERE d.period_id=p_period_id)
 ) INTO v_payload;
 RETURN v_payload;
END $fn$;

REVOKE ALL ON FUNCTION public.erp_cost_export_validated(text)
 FROM PUBLIC,anon,authenticated;
GRANT EXECUTE ON FUNCTION public.erp_cost_export_validated(text)
 TO service_role;
COMMIT;