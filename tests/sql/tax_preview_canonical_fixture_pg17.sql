-- Schéma minimal de l'ancienne table CANONIQUE, données totalement fictives.
-- Exécuté sur PostgreSQL 17 jetable, jamais sur Supabase.
CREATE TABLE public.erp_sku_fiscalite (
    sku_id text NOT NULL REFERENCES public.sku_conditionnement(sku_id),
    date_effet date NOT NULL,
    date_fin date,
    categorie_tva text CHECK (categorie_tva IN ('NORMAL','REDUIT','EXONERE','HORS_CHAMP')),
    code_parametre text CHECK (code_parametre IN ('TVA_TAUX_NORMAL','TVA_TAUX_REDUIT')),
    statut text NOT NULL CHECK (statut IN ('A_VALIDER','VALIDEE')),
    source_juridique text,
    justification text,
    date_verification date,
    valide_par text,
    date_validation date,
    cree_le timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (sku_id,date_effet),
    CHECK (date_fin IS NULL OR date_fin >= date_effet),
    CHECK ((categorie_tva IS NULL AND code_parametre IS NULL) OR
           (categorie_tva='NORMAL' AND code_parametre='TVA_TAUX_NORMAL') OR
           (categorie_tva='REDUIT' AND code_parametre='TVA_TAUX_REDUIT') OR
           (categorie_tva IN ('EXONERE','HORS_CHAMP') AND code_parametre IS NULL)),
    CHECK (statut <> 'VALIDEE' OR
           (categorie_tva IS NOT NULL
            AND nullif(btrim(source_juridique),'') IS NOT NULL
            AND nullif(btrim(justification),'') IS NOT NULL
            AND nullif(btrim(valide_par),'') IS NOT NULL
            AND date_verification IS NOT NULL AND date_validation IS NOT NULL))
);
ALTER TABLE public.erp_sku_fiscalite ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON TABLE public.erp_sku_fiscalite FROM PUBLIC, anon, authenticated;
GRANT SELECT ON TABLE public.erp_sku_fiscalite TO service_role;

INSERT INTO public.sku_conditionnement(sku_id,actif)
VALUES ('SKU-SIM-EXO','OUI');
INSERT INTO public.erp_sku_fiscalite (
    sku_id,date_effet,categorie_tva,code_parametre,statut,
    source_juridique,justification,date_verification,valide_par,date_validation
) VALUES
('SKU-SIM-N','2026-01-01','NORMAL','TVA_TAUX_NORMAL','VALIDEE',
 'PREUVE-FICTIVE','SIMULATION-UNIQUEMENT','2026-01-02','ACTEUR-FICTIF','2026-01-03'),
('SKU-SIM-R','2026-01-01','REDUIT','TVA_TAUX_REDUIT','VALIDEE',
 'PREUVE-FICTIVE','SIMULATION-UNIQUEMENT','2026-01-02','ACTEUR-FICTIF','2026-01-03'),
('SKU-SIM-UNVERIFIE','2026-01-01',NULL,NULL,'A_VALIDER',
 NULL,NULL,NULL,NULL,NULL),
('SKU-SIM-INACTIF','2026-01-01','NORMAL','TVA_TAUX_NORMAL','VALIDEE',
 'PREUVE-FICTIVE','SIMULATION-UNIQUEMENT','2026-01-02','ACTEUR-FICTIF','2026-01-03'),
('SKU-SIM-EXO','2026-01-01','EXONERE',NULL,'VALIDEE',
 'PREUVE-FICTIVE','SIMULATION-UNIQUEMENT','2026-01-02','ACTEUR-FICTIF','2026-01-03');
