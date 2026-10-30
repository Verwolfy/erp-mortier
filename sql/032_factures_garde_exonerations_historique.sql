-- ERP 032 — garde TVA transactionnelle sur les factures historiques.
-- Exploitation : GitHub main / Supabase PRODUCTION exclusivement.
-- Aucune modification des montants ou taux historiques, aucune donnée fictive.
-- Principe conservateur : tout dossier fiscal client (y compris revoque,
-- en attente ou expire) bloque creation/validation de la facture historique
-- tant qu'un calcul TVA par ligne n'est pas homologue.
BEGIN;

CREATE FUNCTION erp_private.erp_factures_verrou_exonerations()
RETURNS trigger
LANGUAGE plpgsql VOLATILE SECURITY INVOKER
SET search_path = pg_catalog
AS $fn$
DECLARE
    v_controler boolean := false;
BEGIN
    IF TG_OP = 'INSERT' THEN
        -- Une insertion directe en statut VALIDE ne doit pas contourner le RPC.
        v_controler := true;
    ELSIF TG_OP = 'UPDATE' THEN
        -- Ne pas bloquer les annulations, rapprochements de paiement,
        -- ni les mises a jour sans effet sur les bases fiscales.
        v_controler := NEW.statut IN ('BROUILLON','VALIDE') AND (
           NEW.client_id IS DISTINCT FROM OLD.client_id
           OR NEW.date IS DISTINCT FROM OLD.date
           OR NEW.statut IS DISTINCT FROM OLD.statut
           OR NEW.taux_tva IS DISTINCT FROM OLD.taux_tva
           OR NEW.montant_ht IS DISTINCT FROM OLD.montant_ht
           OR NEW.montant_tva IS DISTINCT FROM OLD.montant_tva
           OR NEW.montant_ttc IS DISTINCT FROM OLD.montant_ttc
           OR NEW.remise_globale IS DISTINCT FROM OLD.remise_globale
        );
    END IF;
    IF NOT v_controler THEN
        RETURN NEW;
    END IF;
    IF NEW.client_id IS NULL OR btrim(NEW.client_id) = '' THEN
        RAISE EXCEPTION 'Facture refusee : client non verifiable'
            USING ERRCODE='23514';
    END IF;

    -- Meme verrou client que la creation/homologation du dossier fiscal.
    -- La lecture s'effectue apres acquisition de ce verrou.
    PERFORM pg_catalog.pg_advisory_xact_lock(
        pg_catalog.hashtextextended(NEW.client_id, 25026)
    );
    IF EXISTS (
        SELECT 1
        FROM public.erp_exonerations_tva_clients d
        WHERE d.client_id = NEW.client_id
    ) THEN
        RAISE EXCEPTION
           'Facturation historique interdite : dossier d exonération client existant'
            USING ERRCODE='23514';
    END IF;
    RETURN NEW;
END;
$fn$;

-- Synchronise les creations de dossiers A_VALIDER avec les nouvelles
-- factures. Ne modifie pas les transitions ni les privileges d'exoneration.
CREATE OR REPLACE FUNCTION erp_private.erp_exo_garder_entete()
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
        -- Meme verrou transactionnel que l'ecriture de facture : aucun
        -- dossier nouvellement ouvert ne peut contourner la garde facture.
        PERFORM pg_catalog.pg_advisory_xact_lock(
            pg_catalog.hashtextextended(NEW.client_id, 25026)
        );
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

CREATE TRIGGER erp_factures_garde_exonerations
BEFORE INSERT OR UPDATE ON public.factures
FOR EACH ROW
EXECUTE FUNCTION erp_private.erp_factures_verrou_exonerations();

REVOKE ALL ON FUNCTION erp_private.erp_factures_verrou_exonerations()
  FROM PUBLIC, anon, authenticated, service_role;
REVOKE ALL ON FUNCTION erp_private.erp_exo_garder_entete()
  FROM PUBLIC, anon, authenticated, service_role;

DO $check$
BEGIN
 IF NOT EXISTS (
    SELECT 1 FROM pg_catalog.pg_trigger
    WHERE tgrelid='public.factures'::regclass
    AND tgname='erp_factures_garde_exonerations'
    AND tgenabled='O'
 )
 OR NOT EXISTS (
    SELECT 1 FROM pg_catalog.pg_proc p
    JOIN pg_catalog.pg_namespace n ON n.oid=p.pronamespace
    WHERE p.proname='erp_factures_verrou_exonerations'
    AND n.nspname='erp_private'
    AND p.prosecdef IS FALSE
 )
 THEN
   RAISE EXCEPTION 'Garde-fou transactionnel 032 incomplet';
 END IF;
END;
$check$;
COMMIT;
