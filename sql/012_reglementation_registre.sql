-- Migration 012 / lot C : REFERENTIEL REGLEMENTAIRE, SCHEMA SEUL.
-- A REVOIR / TESTER : NE PAS EXECUTER SUR LA BASE PRINCIPALE SANS ACCORD DISTINCT.
-- Pas de seed juridique, pas de parametre fiscal actif, pas d'ecriture metier.
BEGIN;

CREATE TABLE IF NOT EXISTS public.schema_migrations (
    version text PRIMARY KEY,
    empreinte_sha256 text NOT NULL CHECK (empreinte_sha256 ~ '^[0-9a-f]{64}$'),
    appliquee_le timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS public.parametres_reglementaires (
    parametre_id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    code text NOT NULL CHECK (code ~ '^[A-Z0-9_]{3,80}$'),
    domaine text NOT NULL CHECK (length(btrim(domaine)) BETWEEN 1 AND 80),
    valeur numeric(24,12),
    unite text NOT NULL CHECK (length(btrim(unite)) BETWEEN 1 AND 40),
    date_effet date NOT NULL,
    date_fin date,
    statut_juridique text NOT NULL DEFAULT 'a_confirmer'
      CHECK (statut_juridique IN ('en_vigueur','projet','abrogee','a_confirmer')),
    niveau_confiance text NOT NULL DEFAULT 'NON_VERIFIEE'
      CHECK (niveau_confiance IN ('CONFIRMEE','RECOUPEE','DIVERGENTE',
                                 'NON_VERIFIEE','OBSOLETE','ERRONEE')),
    source text,
    texte_source text,
    date_verification date,
    cree_le timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT parametres_dates_valides CHECK (date_fin IS NULL OR date_fin >= date_effet),
    CONSTRAINT parametres_confirmes_documentes CHECK (
      statut_juridique <> 'en_vigueur' OR (
        niveau_confiance = 'CONFIRMEE' AND valeur IS NOT NULL
        AND nullif(btrim(source), '') IS NOT NULL
        AND date_verification IS NOT NULL
      )
    )
);
CREATE UNIQUE INDEX IF NOT EXISTS parametres_reglementaires_code_effet_uq
    ON public.parametres_reglementaires (code, date_effet);

CREATE TABLE IF NOT EXISTS public.regles_reglementaires (
    regle_id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    code text NOT NULL CHECK (code ~ '^[A-Z0-9_]{3,80}$'),
    domaine text NOT NULL CHECK (length(btrim(domaine)) BETWEEN 1 AND 80),
    type_regle text NOT NULL CHECK (type_regle IN ('progressif','calcul','echeance','autre')),
    donnees jsonb NOT NULL DEFAULT '{}'::jsonb
      CHECK (jsonb_typeof(donnees) = 'object'),
    date_effet date NOT NULL,
    date_fin date,
    statut_juridique text NOT NULL DEFAULT 'a_confirmer'
      CHECK (statut_juridique IN ('en_vigueur','projet','abrogee','a_confirmer')),
    niveau_confiance text NOT NULL DEFAULT 'NON_VERIFIEE'
      CHECK (niveau_confiance IN ('CONFIRMEE','RECOUPEE','DIVERGENTE',
                                 'NON_VERIFIEE','OBSOLETE','ERRONEE')),
    source text,
    texte_source text,
    date_verification date,
    cree_le timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT regles_dates_valides CHECK (date_fin IS NULL OR date_fin >= date_effet),
    CONSTRAINT regles_confirmees_documentees CHECK (
      statut_juridique <> 'en_vigueur' OR (
        niveau_confiance = 'CONFIRMEE'
        AND nullif(btrim(source), '') IS NOT NULL
        AND date_verification IS NOT NULL
      )
    )
);
CREATE UNIQUE INDEX IF NOT EXISTS regles_reglementaires_code_effet_uq
    ON public.regles_reglementaires (code, date_effet);

-- Verrouillage explicite de ces NOUVELLES tables : aucune lecture Data API
-- pour les clients anon/authenticated avant la conception d'un accès contrôlé.
ALTER TABLE public.schema_migrations ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.parametres_reglementaires ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.regles_reglementaires ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON public.schema_migrations FROM PUBLIC, anon, authenticated;
REVOKE ALL ON public.parametres_reglementaires FROM PUBLIC, anon, authenticated;
REVOKE ALL ON public.regles_reglementaires FROM PUBLIC, anon, authenticated;

GRANT SELECT,INSERT,UPDATE,DELETE ON public.parametres_reglementaires,
    public.regles_reglementaires TO service_role;
GRANT SELECT,INSERT ON public.schema_migrations TO service_role;
GRANT USAGE,SELECT ON SEQUENCE
    public.parametres_reglementaires_parametre_id_seq,
    public.regles_reglementaires_regle_id_seq TO service_role;

-- Ne pas ajouter de GRANT ni de politiques permissives côté navigateur.
-- L'application devra lire via son service serveur autorisé, après audit.
-- Aucune valeur officielle n'est chargee par cette migration.
-- La ligne de schema_migrations sera enregistree par le futur lanceur
-- apres verification de l'empreinte et execution transactionnelle.
COMMIT;
