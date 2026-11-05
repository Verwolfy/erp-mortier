-- Référentiel de coûts industriels analytiques, séparé des stocks et du SCF.
-- Déploiement TEST en premier. N'altère ni erp_close_manufacturing_order ni stock_actuel_pf.
BEGIN;

CREATE TABLE IF NOT EXISTS public.erp_cost_periods (
 period_id text PRIMARY KEY,
 libelle text NOT NULL CHECK(length(btrim(libelle)) BETWEEN 1 AND 150),
 date_debut date NOT NULL,
 date_fin date NOT NULL,
 statut text NOT NULL DEFAULT 'BROUILLON' CHECK(statut IN ('BROUILLON','VALIDE','CLOTURE')),
 created_at timestamptz NOT NULL DEFAULT now(),
 CHECK(date_fin >= date_debut)
);

CREATE TABLE IF NOT EXISTS public.erp_cost_natures (
 nature_code text PRIMARY KEY CHECK(nature_code ~ '^[A-Z][A-Z0-9_]{1,39}$'),
 libelle text NOT NULL CHECK(length(btrim(libelle)) BETWEEN 1 AND 150),
 description text NOT NULL DEFAULT '',
 actif boolean NOT NULL DEFAULT true
);

CREATE TABLE IF NOT EXISTS public.erp_cost_pools (
 pool_id text PRIMARY KEY,
 period_id text NOT NULL REFERENCES public.erp_cost_periods(period_id) ON DELETE RESTRICT,
 nature_code text NOT NULL REFERENCES public.erp_cost_natures(nature_code) ON DELETE RESTRICT,
 base_imputation text NOT NULL CHECK(base_imputation IN ('UNITS','KG','HOURS_LABOR','HOURS_MACHINE','KWH','DIRECT_COST')),
 montant_dzd numeric(22,6) NOT NULL CHECK(montant_dzd>=0 AND montant_dzd<1000000000000000),
 justificatif text NOT NULL CHECK(length(btrim(justificatif)) BETWEEN 1 AND 500),
 statut text NOT NULL DEFAULT 'SIMULATION' CHECK(statut IN ('SIMULATION','DOCUMENTE')),
 created_at timestamptz NOT NULL DEFAULT now(),
 UNIQUE(period_id,nature_code,base_imputation,pool_id)
);

CREATE TABLE IF NOT EXISTS public.erp_cost_drivers (
 period_id text NOT NULL REFERENCES public.erp_cost_periods(period_id) ON DELETE RESTRICT,
 of_id text NOT NULL REFERENCES public.ordres_fabrication(of_id) ON DELETE RESTRICT,
 base_imputation text NOT NULL CHECK(base_imputation IN ('UNITS','KG','HOURS_LABOR','HOURS_MACHINE','KWH','DIRECT_COST')),
 valeur numeric(22,6) NOT NULL CHECK(valeur>=0 AND valeur<1000000000000000),
 justificatif text NOT NULL CHECK(length(btrim(justificatif)) BETWEEN 1 AND 500),
 created_at timestamptz NOT NULL DEFAULT now(),
 PRIMARY KEY(period_id,of_id,base_imputation)
);

CREATE INDEX IF NOT EXISTS erp_cost_pools_period_idx ON public.erp_cost_pools(period_id,base_imputation);
CREATE INDEX IF NOT EXISTS erp_cost_drivers_period_idx ON public.erp_cost_drivers(period_id,base_imputation);

-- Vue exclusivement analytique : aucune écriture ni changement du CUMP.
-- Repartir un pool au prorata des bases saisies pour les OF de la période.
-- Un pool sans assiette positive ne produit aucune ligne : audit requis avant validation.
CREATE OR REPLACE VIEW public.erp_cost_allocations
WITH (security_invoker = true) AS
WITH assiettes AS (
 SELECT period_id,base_imputation,sum(valeur) AS total_valeur
 FROM public.erp_cost_drivers GROUP BY period_id,base_imputation
),
repartitions AS (
 SELECT p.period_id,p.pool_id,p.nature_code,p.base_imputation,
        d.of_id,d.valeur,p.montant_dzd,a.total_valeur,
        (p.montant_dzd*d.valeur / NULLIF(a.total_valeur,0)) AS montant_impute_dzd
 FROM public.erp_cost_pools p
 JOIN public.erp_cost_drivers d
   ON d.period_id=p.period_id AND d.base_imputation=p.base_imputation
 JOIN assiettes a
   ON a.period_id=p.period_id AND a.base_imputation=p.base_imputation
 WHERE a.total_valeur>0
)
SELECT r.period_id,r.pool_id,r.nature_code,r.base_imputation,r.of_id,
       r.valeur AS valeur_assiette,r.total_valeur,r.montant_dzd AS montant_pool_dzd,
       r.montant_impute_dzd,o.cout_total AS cout_direct_of_dzd,
       o.quantite_produite AS quantite_produite
FROM repartitions r JOIN public.ordres_fabrication o ON o.of_id=r.of_id;

-- Vérification fail-closed des assiettes, périodes et OF avant usage analytique.
CREATE OR REPLACE FUNCTION public.erp_cost_period_audit(p_period_id text)
RETURNS jsonb LANGUAGE plpgsql STABLE SET search_path='pg_catalog','public'
AS $fn$
DECLARE v_period record; v_unallocated integer; v_misdated integer;
 v_total numeric; v_allocated numeric;
BEGIN
 SELECT period_id,date_debut,date_fin INTO v_period FROM public.erp_cost_periods
  WHERE period_id=p_period_id;
 IF NOT FOUND THEN RAISE EXCEPTION 'Période introuvable' USING ERRCODE='23503'; END IF;
 SELECT count(*) INTO v_unallocated
 FROM public.erp_cost_pools p
 WHERE p.period_id=p_period_id AND p.montant_dzd>0
 AND NOT EXISTS(
  SELECT 1 FROM public.erp_cost_drivers d
   WHERE d.period_id=p_period_id AND d.base_imputation=p.base_imputation AND d.valeur>0
 );
 SELECT count(*) INTO v_misdated
 FROM public.erp_cost_drivers d
 JOIN public.ordres_fabrication o ON o.of_id=d.of_id
 WHERE d.period_id=p_period_id
   AND (o.statut<>'TERMINE'
        OR o.date_fin IS NULL
        OR o.date_fin !~ '^[0-9]{4}-[0-9]{2}-[0-9]{2}$'
        OR (CASE WHEN o.date_fin ~ '^[0-9]{4}-[0-9]{2}-[0-9]{2}$'
            THEN o.date_fin::date ELSE NULL END)
           NOT BETWEEN v_period.date_debut AND v_period.date_fin);
 SELECT coalesce(sum(montant_dzd),0) INTO v_total FROM public.erp_cost_pools WHERE period_id=p_period_id;
 SELECT coalesce(sum(montant_impute_dzd),0) INTO v_allocated
 FROM public.erp_cost_allocations WHERE period_id=p_period_id;
 RETURN jsonb_build_object('period_id',p_period_id,'pools_sans_assiette',v_unallocated,
  'of_hors_periode_ou_non_termines',v_misdated,'total_pools_dzd',v_total,
  'total_impute_dzd',v_allocated,
  'audit_ok',(v_unallocated=0 AND v_misdated=0 AND abs(v_allocated-v_total)<0.00001));
END $fn$;

-- Défense en profondeur : périodes validées immuables pour les charges et assiettes.
CREATE OR REPLACE FUNCTION public.erp_cost_check_editable()
RETURNS trigger LANGUAGE plpgsql SET search_path='pg_catalog','public'
AS $fn$
DECLARE v_period_id text; v_status text;
BEGIN
 v_period_id := CASE WHEN TG_OP='DELETE' THEN OLD.period_id ELSE NEW.period_id END;
 SELECT statut INTO v_status FROM public.erp_cost_periods
  WHERE period_id=v_period_id FOR UPDATE;
 IF v_status IS DISTINCT FROM 'BROUILLON' THEN
  RAISE EXCEPTION 'Période analytique non modifiable' USING ERRCODE='23514';
 END IF;
 IF TG_OP='DELETE' THEN RETURN OLD; END IF;
 IF TG_OP='UPDATE' AND NEW.period_id IS DISTINCT FROM OLD.period_id THEN
  RAISE EXCEPTION 'Transfert entre périodes interdit' USING ERRCODE='23514';
 END IF;
 RETURN NEW;
END $fn$;

DROP TRIGGER IF EXISTS erp_cost_pool_edit_guard ON public.erp_cost_pools;
CREATE TRIGGER erp_cost_pool_edit_guard
 BEFORE INSERT OR UPDATE OR DELETE ON public.erp_cost_pools
 FOR EACH ROW EXECUTE FUNCTION public.erp_cost_check_editable();
DROP TRIGGER IF EXISTS erp_cost_driver_edit_guard ON public.erp_cost_drivers;
CREATE TRIGGER erp_cost_driver_edit_guard
 BEFORE INSERT OR UPDATE OR DELETE ON public.erp_cost_drivers
 FOR EACH ROW EXECUTE FUNCTION public.erp_cost_check_editable();

CREATE OR REPLACE FUNCTION public.erp_cost_validate_period(p_period_id text)
RETURNS jsonb LANGUAGE plpgsql SET search_path='pg_catalog','public'
AS $fn$
DECLARE v_state text; v_audit jsonb;
BEGIN
 SELECT statut INTO v_state FROM public.erp_cost_periods
 WHERE period_id=p_period_id FOR UPDATE;
 IF v_state IS DISTINCT FROM 'BROUILLON' THEN
   RAISE EXCEPTION 'Période non validable' USING ERRCODE='23514'; END IF;
 IF NOT EXISTS (SELECT 1 FROM public.erp_cost_pools WHERE period_id=p_period_id)
 OR NOT EXISTS (SELECT 1 FROM public.erp_cost_drivers WHERE period_id=p_period_id) THEN
   RAISE EXCEPTION 'Charges et assiettes obligatoires' USING ERRCODE='23514'; END IF;
 v_audit := public.erp_cost_period_audit(p_period_id);
 IF v_audit->>'audit_ok' IS DISTINCT FROM 'true' THEN
   RAISE EXCEPTION 'Audit de répartition non conforme' USING ERRCODE='23514'; END IF;
 UPDATE public.erp_cost_periods SET statut='VALIDE' WHERE period_id=p_period_id;
 RETURN v_audit;
END $fn$;

-- Bloque les corrections silencieuses de dates ou d'état après validation.
CREATE OR REPLACE FUNCTION public.erp_cost_period_state_guard()
RETURNS trigger LANGUAGE plpgsql SET search_path='pg_catalog','public'
AS $fn$
BEGIN
 IF OLD.statut<>'BROUILLON' THEN
   RAISE EXCEPTION 'Période validée immuable' USING ERRCODE='23514'; END IF;
 IF NEW.date_debut IS DISTINCT FROM OLD.date_debut OR
    NEW.date_fin IS DISTINCT FROM OLD.date_fin OR
    NEW.libelle IS DISTINCT FROM OLD.libelle THEN
   RAISE EXCEPTION 'Modifier les dates ou libellés nécessite une nouvelle période' USING ERRCODE='23514';
 END IF;
 IF NEW.statut NOT IN ('BROUILLON','VALIDE') THEN
   RAISE EXCEPTION 'Transition de période non permise' USING ERRCODE='23514'; END IF;
 -- Une validation directe par UPDATE n'est pas permise; seule la RPC verrouille
 -- et effectue l'audit. GUC locale impossible à forger en tant que contrôle fort,
 -- donc le backend doit rester strictement service_role.
 RETURN NEW;
END $fn$;
DROP TRIGGER IF EXISTS erp_cost_period_state_guard ON public.erp_cost_periods;
CREATE TRIGGER erp_cost_period_state_guard
 BEFORE UPDATE ON public.erp_cost_periods
 FOR EACH ROW EXECUTE FUNCTION public.erp_cost_period_state_guard();

-- Aucun droit Data API public. Utilisation uniquement par le backend serveur habilité.
DO $priv$
DECLARE t text;
BEGIN
 FOREACH t IN ARRAY ARRAY['erp_cost_periods','erp_cost_natures','erp_cost_pools','erp_cost_drivers']
 LOOP
  EXECUTE format('ALTER TABLE public.%I ENABLE ROW LEVEL SECURITY',t);
  EXECUTE format('REVOKE ALL ON public.%I FROM PUBLIC, anon, authenticated',t);
  EXECUTE format('GRANT SELECT, INSERT, UPDATE, DELETE ON public.%I TO service_role',t);
 END LOOP;
END $priv$;
REVOKE ALL ON public.erp_cost_allocations FROM PUBLIC, anon, authenticated;
GRANT SELECT ON public.erp_cost_allocations TO service_role;
REVOKE ALL ON FUNCTION public.erp_cost_period_audit(text) FROM PUBLIC, anon, authenticated;
GRANT EXECUTE ON FUNCTION public.erp_cost_period_audit(text) TO service_role;
REVOKE ALL ON FUNCTION public.erp_cost_validate_period(text) FROM PUBLIC, anon, authenticated;
GRANT EXECUTE ON FUNCTION public.erp_cost_validate_period(text) TO service_role;

-- Référentiel des natures sans montant fictif : seuls les libellés sont installés.
INSERT INTO public.erp_cost_natures(nature_code,libelle,description) VALUES
('MAIN_OEUVRE','Main-d’œuvre directe','Coût analytique de main-d’œuvre de fabrication'),
('ENERGIE','Énergie','Consommation énergétique imputable'),
('AMORTISSEMENT','Amortissement','Part des dotations imputée aux OF'),
('FRAIS_INDIRECTS','Frais indirects','Charges indirectes avec clé explicite'),
('FRAIS_APPROCHE','Frais d’approche','Sous contrôle anti-double imputation avec achats'),
('REBUT','Rebuts','Coût des unités non conformes distinct des stocks conformes')
ON CONFLICT(nature_code) DO NOTHING;
COMMIT;
