-- 042 — Snapshot immuable des OF lors de la validation analytique.
-- Additif : ne touche ni aux mouvements de stock, ni au CUMP ni aux écritures SCF.
BEGIN;

CREATE TABLE IF NOT EXISTS public.erp_cost_of_validation_snapshot (
 period_id text NOT NULL REFERENCES public.erp_cost_periods(period_id) ON DELETE RESTRICT,
 of_id text NOT NULL REFERENCES public.ordres_fabrication(of_id) ON DELETE RESTRICT,
 statut_of text NOT NULL,
 quantite_produite numeric,
 cout_direct_of_dzd numeric,
 charges_imputees_dzd numeric NOT NULL,
 cout_analytique_total_dzd numeric,
 captured_at timestamptz NOT NULL DEFAULT now(),
 PRIMARY KEY(period_id,of_id)
);

ALTER TABLE public.erp_cost_of_validation_snapshot ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON public.erp_cost_of_validation_snapshot FROM PUBLIC,anon,authenticated,service_role;
GRANT SELECT ON public.erp_cost_of_validation_snapshot TO service_role;

CREATE OR REPLACE FUNCTION public.erp_cost_snapshot_on_validation()
RETURNS trigger
LANGUAGE plpgsql SECURITY DEFINER
SET search_path=pg_catalog,public
AS $fn$
BEGIN
 IF NEW.statut='VALIDE' AND OLD.statut='BROUILLON' THEN
  -- Le trigger et la mise à jour de statut constituent la même transaction.
  INSERT INTO public.erp_cost_of_validation_snapshot(
   period_id,of_id,statut_of,quantite_produite,cout_direct_of_dzd,
   charges_imputees_dzd,cout_analytique_total_dzd)
  SELECT v.period_id,v.of_id,v.statut_of,v.quantite_produite,
         v.cout_direct_of_dzd,v.charges_imputees_dzd,
         v.cout_analytique_total_dzd
  FROM public.erp_cost_of_summary v WHERE v.period_id=NEW.period_id;
  IF NOT FOUND THEN
   RAISE EXCEPTION 'Snapshot de période vide' USING ERRCODE='23514';
  END IF;
 END IF;
 RETURN NEW;
END $fn$;

DROP TRIGGER IF EXISTS erp_cost_snapshot_on_validation_trigger ON public.erp_cost_periods;
CREATE TRIGGER erp_cost_snapshot_on_validation_trigger
AFTER UPDATE OF statut ON public.erp_cost_periods
FOR EACH ROW EXECUTE FUNCTION public.erp_cost_snapshot_on_validation();

REVOKE ALL ON FUNCTION public.erp_cost_snapshot_on_validation()
 FROM PUBLIC,anon,authenticated,service_role;

CREATE OR REPLACE VIEW public.erp_cost_of_validation_drift
WITH (security_invoker=true) AS
SELECT s.period_id,s.of_id,s.captured_at,
 s.statut_of AS statut_of_valide,s.quantite_produite AS quantite_validee,
 s.cout_direct_of_dzd AS cout_direct_valide_dzd,
 s.charges_imputees_dzd AS charges_validees_dzd,
 s.cout_analytique_total_dzd AS cout_total_valide_dzd,
 o.statut AS statut_of_actuel,o.quantite_produite AS quantite_actuelle,
 o.cout_total AS cout_direct_actuel_dzd,
 v.charges_imputees_dzd AS charges_actuelles_dzd,
 v.cout_analytique_total_dzd AS cout_total_actuel_dzd,
 (
  s.statut_of IS DISTINCT FROM o.statut OR
  s.quantite_produite IS DISTINCT FROM o.quantite_produite OR
  s.cout_direct_of_dzd IS DISTINCT FROM o.cout_total OR
  s.charges_imputees_dzd IS DISTINCT FROM v.charges_imputees_dzd OR
  s.cout_analytique_total_dzd IS DISTINCT FROM v.cout_analytique_total_dzd
 ) AS derive_detectee
FROM public.erp_cost_of_validation_snapshot s
LEFT JOIN public.ordres_fabrication o ON o.of_id=s.of_id
LEFT JOIN public.erp_cost_of_summary v
 ON v.period_id=s.period_id AND v.of_id=s.of_id;

REVOKE ALL ON public.erp_cost_of_validation_drift FROM PUBLIC,anon,authenticated;
GRANT SELECT ON public.erp_cost_of_validation_drift TO service_role;
COMMIT;
