-- ERP 022 : journal de qualification fiscale TVA des SKU.
-- Aucun taux ni régime ne sont attribués par défaut. Aucune écriture Ventes.
BEGIN;

CREATE TABLE public.erp_sku_fiscalite (
    sku_id text NOT NULL REFERENCES public.sku_conditionnement(sku_id)
       ON UPDATE RESTRICT ON DELETE RESTRICT,
    date_effet date NOT NULL,
    date_fin date,
    categorie_tva text CHECK (
       categorie_tva IN ('NORMAL','REDUIT','EXONERE','HORS_CHAMP')
    ),
    code_parametre text CHECK (
       code_parametre IN ('TVA_TAUX_NORMAL','TVA_TAUX_REDUIT')
    ),
    statut text NOT NULL DEFAULT 'A_VALIDER'
       CHECK (statut IN ('A_VALIDER','VALIDEE')),
    source_juridique text,
    justification text,
    date_verification date,
    valide_par text,
    date_validation date,
    cree_le timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (sku_id, date_effet),
    CONSTRAINT erp_sku_fiscalite_dates CHECK (
        date_fin IS NULL OR date_fin >= date_effet
    ),
    CONSTRAINT erp_sku_fiscalite_codes CHECK ((
        (categorie_tva IS NULL AND code_parametre IS NULL)
        OR (categorie_tva = 'NORMAL' AND code_parametre = 'TVA_TAUX_NORMAL')
        OR (categorie_tva = 'REDUIT' AND code_parametre = 'TVA_TAUX_REDUIT')
        OR (categorie_tva IN ('EXONERE','HORS_CHAMP') AND code_parametre IS NULL)
    ) IS TRUE),
    CONSTRAINT erp_sku_fiscalite_justificatifs CHECK (
        statut <> 'VALIDEE'
        OR (
            categorie_tva IS NOT NULL
            AND nullif(btrim(source_juridique),'') IS NOT NULL
            AND nullif(btrim(justification),'') IS NOT NULL
            AND nullif(btrim(valide_par),'') IS NOT NULL
            AND date_verification IS NOT NULL
            AND date_validation IS NOT NULL
        )
    )
);

CREATE INDEX erp_sku_fiscalite_statut_idx
   ON public.erp_sku_fiscalite (sku_id,statut,date_effet);

ALTER TABLE public.erp_sku_fiscalite ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON public.erp_sku_fiscalite FROM PUBLIC, anon, authenticated;
-- Phase 1 : observation uniquement. L'écriture demandera un service à
-- autorisations fines, une non-superposition des périodes et validation métier.
GRANT SELECT ON public.erp_sku_fiscalite TO service_role;

COMMIT;
