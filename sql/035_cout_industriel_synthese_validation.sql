-- Synthèse analytique par période/OF + validation limitée aux pièces documentées.
-- Complète 034. Ne modifie ni les coûts directs ni le CUMP.
BEGIN;
CREATE OR REPLACE VIEW public.erp_cost_of_summary
WITH (security_invoker = true) AS
WITH allocations AS (
 SELECT period_id,of_id,sum(montant_impute_dzd) AS total_impute
 FROM public.erp_cost_allocations GROUP BY period_id,of_id
), assiettes AS (
 SELECT DISTINCT period_id,of_id FROM public.erp_cost_drivers
)
SELECT d.period_id,d.of_id,o.statut AS statut_of,
       o.quantite_produite,
       o.cout_total AS cout_direct_of_dzd,
       coalesce(a.total_impute,0) AS charges_imputees_dzd,
       o.cout_total+coalesce(a.total_impute,0) AS cout_analytique_total_dzd,
       (o.cout_total+coalesce(a.total_impute,0))/NULLIF(o.quantite_produite,0) AS cout_analytique_par_unite_dzd
FROM assiettes d JOIN public.ordres_fabrication o ON o.of_id=d.of_id
LEFT JOIN allocations a ON a.period_id=d.period_id AND a.of_id=d.of_id;

REVOKE ALL ON public.erp_cost_of_summary FROM PUBLIC,anon,authenticated;
GRANT SELECT ON public.erp_cost_of_summary TO service_role;

CREATE OR REPLACE FUNCTION public.erp_cost_validate_period(p_period_id text)
RETURNS jsonb LANGUAGE plpgsql SET search_path='pg_catalog','public'
AS $fn$
DECLARE v_status text; v_audit jsonb;
BEGIN
 SELECT statut INTO v_status FROM public.erp_cost_periods WHERE period_id=p_period_id FOR UPDATE;
 IF v_status IS DISTINCT FROM 'BROUILLON' THEN
  RAISE EXCEPTION 'Période non validable' USING ERRCODE='23514'; END IF;
 IF NOT EXISTS (SELECT 1 FROM public.erp_cost_pools WHERE period_id=p_period_id)
 OR NOT EXISTS (SELECT 1 FROM public.erp_cost_drivers WHERE period_id=p_period_id) THEN
  RAISE EXCEPTION 'Charges et assiettes obligatoires' USING ERRCODE='23514'; END IF;
 -- Les hypothèses de simulation restent en brouillon. Une validation requiert
 -- que chaque pool ait été rattaché à une pièce justificative réelle.
 IF EXISTS (SELECT 1 FROM public.erp_cost_pools
            WHERE period_id=p_period_id AND statut<>'DOCUMENTE') THEN
  RAISE EXCEPTION 'Charges simulées non validables sans justificatifs documentés'
   USING ERRCODE='23514'; END IF;
 v_audit := public.erp_cost_period_audit(p_period_id);
 IF v_audit->>'audit_ok' IS DISTINCT FROM 'true' THEN
  RAISE EXCEPTION 'Audit de répartition non conforme' USING ERRCODE='23514'; END IF;
 UPDATE public.erp_cost_periods SET statut='VALIDE' WHERE period_id=p_period_id;
 RETURN v_audit;
END $fn$;
REVOKE ALL ON FUNCTION public.erp_cost_validate_period(text) FROM PUBLIC,anon,authenticated;
GRANT EXECUTE ON FUNCTION public.erp_cost_validate_period(text) TO service_role;
COMMIT;
