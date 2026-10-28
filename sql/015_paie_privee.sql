-- Migration 015, LOT F : conservation privée des bulletins préparatoires.
-- BROUILLON : non appliqué ; ne remplace pas fiches_de_paie existant.
-- Contrôle du calcul IRG complet et droits RH indispensables AVANT activation.
BEGIN;

CREATE TABLE IF NOT EXISTS public.paie_periodes_v2 (
    periode_id text PRIMARY KEY,
    annee integer NOT NULL CHECK (annee BETWEEN 2000 AND 2100),
    mois integer NOT NULL CHECK (mois BETWEEN 1 AND 12),
    statut text NOT NULL DEFAULT 'OUVERTE'
      CHECK (statut IN ('OUVERTE','CLOTUREE')),
    UNIQUE (annee, mois)
);

CREATE TABLE IF NOT EXISTS public.paie_bulletins_v2 (
    bulletin_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    employe_id text NOT NULL REFERENCES public.employes(employe_id),
    periode_id text NOT NULL REFERENCES public.paie_periodes_v2(periode_id),
    date_paie date NOT NULL,
    salaire_brut numeric(20,2) NOT NULL CHECK (salaire_brut >= 0),
    assiette_sociale numeric(20,2) NOT NULL CHECK (assiette_sociale >= 0),
    assiette_irg numeric(20,2) NOT NULL CHECK (assiette_irg >= 0),
    cotisation_salarie numeric(20,2) NOT NULL CHECK (cotisation_salarie >= 0),
    cotisation_employeur numeric(20,2) NOT NULL CHECK (cotisation_employeur >= 0),
    irg numeric(20,2) NOT NULL CHECK (irg >= 0),
    autres_retenues numeric(20,2) NOT NULL DEFAULT 0 CHECK (autres_retenues >= 0),
    net_a_payer numeric(20,2) NOT NULL CHECK (net_a_payer >= 0),
    preuve_calcul jsonb NOT NULL CHECK (jsonb_typeof(preuve_calcul)='object'),
    statut text NOT NULL DEFAULT 'PREPARE' CHECK (statut IN ('PREPARE','VALIDE')),
    valide_le timestamptz,
    cree_le timestamptz NOT NULL DEFAULT now(),
    UNIQUE (employe_id,periode_id),
    CHECK (assiette_sociale <= salaire_brut AND assiette_irg <= salaire_brut),
    CHECK (salaire_brut - cotisation_salarie - irg - autres_retenues = net_a_payer),
    CHECK ((statut='PREPARE' AND valide_le IS NULL)
           OR (statut='VALIDE' AND valide_le IS NOT NULL))
);

CREATE TABLE IF NOT EXISTS public.paie_lignes_v2 (
    ligne_id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    bulletin_id uuid NOT NULL REFERENCES public.paie_bulletins_v2(bulletin_id),
    numero integer NOT NULL CHECK (numero BETWEEN 1 AND 200),
    code text NOT NULL CHECK (code ~ '^[A-Z0-9_]{2,80}$'),
    libelle text NOT NULL CHECK (length(btrim(libelle)) BETWEEN 1 AND 200),
    nature text NOT NULL CHECK (nature IN ('GAIN','RETENUE','INFORMATION')),
    montant numeric(20,2) NOT NULL CHECK (montant >= 0),
    UNIQUE (bulletin_id, numero)
);

CREATE OR REPLACE FUNCTION public.paie_v2_garder_bulletins()
RETURNS trigger LANGUAGE plpgsql SECURITY INVOKER
SET search_path = pg_catalog, public
AS $func$
DECLARE
    v_periode text;
BEGIN
    IF TG_OP='DELETE' THEN
        IF OLD.statut='VALIDE' THEN
            RAISE EXCEPTION 'Bulletin valide immuable' USING ERRCODE='23514';
        END IF;
        RETURN OLD;
    END IF;
    IF TG_OP='INSERT' THEN
        IF NEW.statut <> 'PREPARE' OR NEW.valide_le IS NOT NULL THEN
            RAISE EXCEPTION 'Insertion bulletin valide interdite' USING ERRCODE='23514';
        END IF;
        RETURN NEW;
    END IF;
    IF OLD.statut='VALIDE' THEN
        RAISE EXCEPTION 'Bulletin valide immuable' USING ERRCODE='23514';
    END IF;
    IF NEW.statut='VALIDE' THEN
        SELECT statut INTO v_periode FROM public.paie_periodes_v2
          WHERE periode_id=NEW.periode_id FOR SHARE;
        IF v_periode IS DISTINCT FROM 'OUVERTE'
           OR NEW.preuve_calcul->>'statut_irg' IS DISTINCT FROM 'CONFIRMEE'
           OR nullif(btrim(NEW.preuve_calcul->>'source_irg'),'') IS NULL
           OR nullif(btrim(NEW.preuve_calcul->>'source_cnas'),'') IS NULL THEN
            RAISE EXCEPTION 'Preuve fiscale/sociale ou periode manquante' USING ERRCODE='23514';
        END IF;
        NEW.valide_le := now();
    END IF;
    RETURN NEW;
END;
$func$;

CREATE OR REPLACE FUNCTION public.paie_v2_garder_lignes()
RETURNS trigger LANGUAGE plpgsql SECURITY INVOKER
SET search_path = pg_catalog, public
AS $func$
DECLARE
    v_id uuid;
    v_statut text;
BEGIN
    v_id := CASE WHEN TG_OP='DELETE' THEN OLD.bulletin_id ELSE NEW.bulletin_id END;
    IF TG_OP='UPDATE' AND NEW.bulletin_id IS DISTINCT FROM OLD.bulletin_id THEN
        RAISE EXCEPTION 'Deplacement de ligne de paie interdit' USING ERRCODE='23514';
    END IF;
    SELECT statut INTO v_statut FROM public.paie_bulletins_v2
      WHERE bulletin_id=v_id FOR UPDATE;
    IF v_statut IS DISTINCT FROM 'PREPARE' THEN
        RAISE EXCEPTION 'Ligne de paie non modifiable' USING ERRCODE='23514';
    END IF;
    IF TG_OP='DELETE' THEN RETURN OLD; END IF;
    RETURN NEW;
END;
$func$;

DO $triggers$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_catalog.pg_trigger
      WHERE tgrelid='public.paie_bulletins_v2'::regclass AND tgname='paie_v2_immutabilite_bulletins' AND NOT tgisinternal) THEN
    CREATE TRIGGER paie_v2_immutabilite_bulletins
      BEFORE INSERT OR UPDATE OR DELETE ON public.paie_bulletins_v2
      FOR EACH ROW EXECUTE FUNCTION public.paie_v2_garder_bulletins();
  END IF;
  IF NOT EXISTS (SELECT 1 FROM pg_catalog.pg_trigger
      WHERE tgrelid='public.paie_lignes_v2'::regclass AND tgname='paie_v2_immutabilite_lignes' AND NOT tgisinternal) THEN
    CREATE TRIGGER paie_v2_immutabilite_lignes
      BEFORE INSERT OR UPDATE OR DELETE ON public.paie_lignes_v2
      FOR EACH ROW EXECUTE FUNCTION public.paie_v2_garder_lignes();
  END IF;
END;
$triggers$;

ALTER TABLE public.paie_periodes_v2 ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.paie_bulletins_v2 ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.paie_lignes_v2 ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON public.paie_periodes_v2,public.paie_bulletins_v2,
              public.paie_lignes_v2 FROM PUBLIC, anon, authenticated;
GRANT SELECT,INSERT,UPDATE,DELETE ON public.paie_periodes_v2,
  public.paie_bulletins_v2,public.paie_lignes_v2 TO service_role;
GRANT USAGE,SELECT ON SEQUENCE public.paie_lignes_v2_ligne_id_seq TO service_role;
-- Aucun accès RH/paie direct : la séparation des rôles applicatifs
-- et la journalisation des lectures sont à réaliser avant activation.
COMMIT;
