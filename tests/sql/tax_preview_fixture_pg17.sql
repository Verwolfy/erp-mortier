-- Base éphémère PostgreSQL 17 GitHub Actions UNIQUEMENT.
-- Données simulées ; aucun identifiant, aucune donnée de production.
CREATE ROLE anon NOLOGIN;
CREATE ROLE authenticated NOLOGIN;
CREATE ROLE service_role NOLOGIN BYPASSRLS;
GRANT USAGE ON SCHEMA public TO service_role;

CREATE TABLE public.sku_conditionnement (
    sku_id text PRIMARY KEY,
    actif text NOT NULL
);
CREATE TABLE public.parametres_reglementaires (
    code text NOT NULL,
    valeur numeric,
    unite text,
    statut_juridique text,
    niveau_confiance text,
    date_effet date NOT NULL,
    date_fin date,
    source text,
    date_verification date
);
GRANT SELECT ON public.sku_conditionnement, public.parametres_reglementaires TO service_role;

INSERT INTO public.sku_conditionnement(sku_id, actif) VALUES
    ('SKU-SIM-N', 'OUI'),
    ('SKU-SIM-R', 'OUI'),
    ('SKU-SIM-INACTIF', 'NON'),
    ('SKU-SIM-UNVERIFIE', 'OUI');
INSERT INTO public.parametres_reglementaires (
    code, valeur, unite, statut_juridique, niveau_confiance,
    date_effet, date_fin, source, date_verification
) VALUES
    ('TVA_TAUX_NORMAL', 0.20, 'fraction', 'en_vigueur', 'CONFIRMEE',
     '2026-01-01', NULL, 'TEST-FICTIF', '2026-01-02'),
    ('TVA_TAUX_REDUIT', 0.07, 'fraction', 'en_vigueur', 'CONFIRMEE',
     '2026-01-01', NULL, 'TEST-FICTIF', '2026-01-02');
