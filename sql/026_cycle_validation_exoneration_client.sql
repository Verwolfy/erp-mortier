-- ERP 026 : garde-fous de cycle de vie des attestations, sans activation fiscale.
-- Migration destinée à TEST d'abord. Aucun seed, pas de droit d'écriture API.
BEGIN;
CREATE SCHEMA IF NOT EXISTS erp_private;
REVOKE ALL ON SCHEMA erp_private FROM PUBLIC, anon, authenticated, service_role;

CREATE TABLE public.erp_exonerations_tva_evenements (
    evenement_id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    attestation_id uuid NOT NULL REFERENCES public.erp_exonerations_tva_clients(attestation_id)
      ON UPDATE RESTRICT ON DELETE RESTRICT,
    type_evenement text NOT NULL
      CHECK (type_evenement IN ('CREATION','REVISION','VALIDATION','REVOCATION')),
    ancien_statut text,
    nouveau_statut text NOT NULL,
    acteur_sql text NOT NULL,
    survenu_le timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX erp_exo_evenements_attestation_idx
  ON public.erp_exonerations_tva_evenements(attestation_id, survenu_le);
ALTER TABLE public.erp_exonerations_tva_evenements ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON public.erp_exonerations_tva_evenements
  FROM PUBLIC, anon, authenticated, service_role;

CREATE FUNCTION erp_private.erp_exo_garder_entete()
RETURNS trigger
LANGUAGE plpgsql
SECURITY INVOKER
SET search_path = pg_catalog
AS $fn$
DECLARE
    concurrentes integer;
    porte integer;
BEGIN
    IF TG_OP = 'DELETE' THEN
        RAISE EXCEPTION 'Suppression attestation interdite : révoquer le dossier'
          USING ERRCODE = '23514';
    END IF;
    IF TG_OP = 'INSERT' THEN
        IF NEW.statut <> 'A_VALIDER' OR NEW.date_validation IS NOT NULL
           OR NEW.valide_par IS NOT NULL THEN
            RAISE EXCEPTION 'Seul un brouillon non validé peut être créé'
              USING ERRCODE = '23514';
        END IF;
        RETURN NEW;
    END IF;
    IF OLD.statut = 'REVOQUEE' THEN
        RAISE EXCEPTION 'Attestation révoquée immuable'
          USING ERRCODE = '23514';
    END IF;
    IF OLD.statut = 'VALIDEE' THEN
        IF NEW.statut <> 'REVOQUEE'
            OR (to_jsonb(NEW) - 'statut') IS DISTINCT FROM
               (to_jsonb(OLD) - 'statut') THEN
            RAISE EXCEPTION 'Attestation validée immuable sauf révocation'
              USING ERRCODE = '23514';
        END IF;
        RETURN NEW;
    END IF;
    -- Etat initial A_VALIDER. Aucune réactivation d'un dossier clos.
    IF NEW.statut NOT IN ('A_VALIDER','VALIDEE','REVOQUEE') THEN
        RAISE EXCEPTION 'Transition fiscale interdite'
          USING ERRCODE = '23514';
    END IF;
    IF NEW.statut = 'VALIDEE' THEN
        PERFORM pg_catalog.pg_advisory_xact_lock(
            pg_catalog.hashtextextended(NEW.client_id, 25026)
        );
        SELECT count(*) INTO porte
          FROM public.erp_exonerations_tva_skus p
         WHERE p.attestation_id = NEW.attestation_id;
        IF porte < 1 THEN
            RAISE EXCEPTION 'Validation impossible sans portée SKU'
              USING ERRCODE = '23514';
        END IF;
        SELECT count(*) INTO concurrentes
          FROM public.erp_exonerations_tva_clients d
         WHERE d.client_id = NEW.client_id
           AND d.attestation_id <> NEW.attestation_id
           AND d.statut = 'VALIDEE'
           AND d.date_effet <= NEW.date_fin
           AND NEW.date_effet <= d.date_fin;
        IF concurrentes > 0 THEN
            RAISE EXCEPTION 'Attestation client validée concurrente'
              USING ERRCODE = '23514';
        END IF;
    END IF;
    RETURN NEW;
END;
$fn$;

CREATE FUNCTION erp_private.erp_exo_garder_portee()
RETURNS trigger
LANGUAGE plpgsql
SECURITY INVOKER
SET search_path = pg_catalog
AS $fn$
DECLARE
    dossier uuid;
    statut_actuel text;
BEGIN
    dossier := CASE WHEN TG_OP = 'DELETE' THEN OLD.attestation_id
                     ELSE NEW.attestation_id END;
    IF TG_OP = 'UPDATE' AND OLD.attestation_id <> NEW.attestation_id THEN
        RAISE EXCEPTION 'Réaffectation de portée interdite'
          USING ERRCODE = '23514';
    END IF;
    SELECT statut INTO statut_actuel
      FROM public.erp_exonerations_tva_clients
      WHERE attestation_id = dossier FOR UPDATE;
    IF statut_actuel IS DISTINCT FROM 'A_VALIDER' THEN
        RAISE EXCEPTION 'Portée modifiable uniquement sur brouillon'
          USING ERRCODE = '23514';
    END IF;
    IF TG_OP = 'DELETE' THEN
        RETURN OLD;
    END IF;
    RETURN NEW;
END;
$fn$;

CREATE FUNCTION erp_private.erp_exo_journaliser_entete()
RETURNS trigger
LANGUAGE plpgsql
SECURITY INVOKER
SET search_path = pg_catalog
AS $fn$
BEGIN
    INSERT INTO public.erp_exonerations_tva_evenements
      (attestation_id, type_evenement, ancien_statut, nouveau_statut, acteur_sql)
    VALUES
      (NEW.attestation_id,
       CASE WHEN TG_OP='INSERT' THEN 'CREATION'
            WHEN NEW.statut='VALIDEE' AND OLD.statut <> 'VALIDEE' THEN 'VALIDATION'
            WHEN NEW.statut='REVOQUEE' THEN 'REVOCATION'
            ELSE 'REVISION' END,
       CASE WHEN TG_OP='INSERT' THEN NULL ELSE OLD.statut END,
       NEW.statut,
       session_user);
    RETURN NEW;
END;
$fn$;

CREATE TRIGGER erp_exo_garde_entete
 BEFORE INSERT OR UPDATE OR DELETE ON public.erp_exonerations_tva_clients
 FOR EACH ROW EXECUTE FUNCTION erp_private.erp_exo_garder_entete();
CREATE TRIGGER erp_exo_garde_portee
 BEFORE INSERT OR UPDATE OR DELETE ON public.erp_exonerations_tva_skus
 FOR EACH ROW EXECUTE FUNCTION erp_private.erp_exo_garder_portee();
CREATE TRIGGER erp_exo_journal_entete
 AFTER INSERT OR UPDATE ON public.erp_exonerations_tva_clients
 FOR EACH ROW EXECUTE FUNCTION erp_private.erp_exo_journaliser_entete();

REVOKE ALL ON ALL FUNCTIONS IN SCHEMA erp_private FROM PUBLIC, anon, authenticated, service_role;
DO $check$
BEGIN
 IF has_table_privilege('service_role','public.erp_exonerations_tva_clients','INSERT')
    OR has_table_privilege('service_role','public.erp_exonerations_tva_clients','UPDATE')
    OR has_table_privilege('service_role','public.erp_exonerations_tva_skus','INSERT')
    OR has_table_privilege('authenticated','public.erp_exonerations_tva_evenements','SELECT')
 THEN
     RAISE EXCEPTION 'Droits exonération ouverts accidentellement';
 END IF;
END;
$check$;
COMMIT;
