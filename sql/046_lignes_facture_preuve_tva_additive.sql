-- ERP-046 : traçabilité TVA par ligne. Évolution additive sur base principale d'essais.
-- Ne change pas les factures/lignes existantes, la RPC erp_sale_transaction,
-- les privilèges/RLS, ni les règles TVA. Les champs restent NULL sur les
-- factures historiques tant que la nouvelle transaction n'est pas activée.
-- Ne pas recopier un taux global ancien dans les lignes, ce serait une
-- prétendue qualification juridique sans justification.
ALTER TABLE public.lignes_facture
  ADD COLUMN IF NOT EXISTS code_regle_tva text,
  ADD COLUMN IF NOT EXISTS assiette_tva numeric(20,2),
  ADD COLUMN IF NOT EXISTS taux_tva_ligne numeric(12,8),
  ADD COLUMN IF NOT EXISTS montant_tva_ligne numeric(20,2),
  ADD COLUMN IF NOT EXISTS date_fait_generateur_tva date,
  ADD COLUMN IF NOT EXISTS date_effet_regle_tva date,
  ADD COLUMN IF NOT EXISTS source_regle_tva text,
  ADD COLUMN IF NOT EXISTS date_verification_regle_tva date,
  ADD COLUMN IF NOT EXISTS source_classification_tva text,
  ADD COLUMN IF NOT EXISTS justification_classification_tva text,
  ADD COLUMN IF NOT EXISTS date_verification_classification_tva date,
  ADD COLUMN IF NOT EXISTS valide_par_classification_tva text;

-- Une ligne historique reste intégralement sans snapshot. Une ligne avec
-- code TVA exige la totalité des preuves, une assiette non négative,
-- une date/version cohérente et un montant recalculable.
-- NOT VALID puis VALIDATE : compatibilité des 4 lignes historiques contrôlée.
ALTER TABLE public.lignes_facture
  ADD CONSTRAINT erp_lignes_facture_tva_snapshot_complet
  CHECK ((
      (
        code_regle_tva IS NULL
        AND assiette_tva IS NULL
        AND taux_tva_ligne IS NULL
        AND montant_tva_ligne IS NULL
        AND date_fait_generateur_tva IS NULL
        AND date_effet_regle_tva IS NULL
        AND source_regle_tva IS NULL
        AND date_verification_regle_tva IS NULL
        AND source_classification_tva IS NULL
        AND justification_classification_tva IS NULL
        AND date_verification_classification_tva IS NULL
        AND valide_par_classification_tva IS NULL
      ) OR (
        code_regle_tva IN ('TVA_TAUX_NORMAL', 'TVA_TAUX_REDUIT')
        AND assiette_tva IS NOT NULL
        AND taux_tva_ligne IS NOT NULL
        AND montant_tva_ligne IS NOT NULL
        AND assiette_tva::text NOT IN ('NaN','Infinity','-Infinity')
        AND taux_tva_ligne::text NOT IN ('NaN','Infinity','-Infinity')
        AND montant_tva_ligne::text NOT IN ('NaN','Infinity','-Infinity')
        AND assiette_tva BETWEEN 0 AND 100000000000000
        AND taux_tva_ligne BETWEEN 0 AND 1
        AND montant_tva_ligne = round(assiette_tva * taux_tva_ligne, 2)
        AND total_ligne_ht IS NOT NULL
        AND assiette_tva <= total_ligne_ht
        AND date_fait_generateur_tva IS NOT NULL
        AND date_effet_regle_tva IS NOT NULL
        AND date_effet_regle_tva <= date_fait_generateur_tva
        AND date_verification_regle_tva IS NOT NULL
        AND date_verification_classification_tva IS NOT NULL
        AND nullif(btrim(source_regle_tva), '') IS NOT NULL
        AND nullif(btrim(source_classification_tva), '') IS NOT NULL
        AND nullif(btrim(justification_classification_tva), '') IS NOT NULL
        AND nullif(btrim(valide_par_classification_tva), '') IS NOT NULL
        AND length(source_regle_tva) <= 2000
        AND length(source_classification_tva) <= 2000
        AND length(justification_classification_tva) <= 2000
        AND length(valide_par_classification_tva) <= 200
      )
  ) IS TRUE) NOT VALID;

ALTER TABLE public.lignes_facture
  VALIDATE CONSTRAINT erp_lignes_facture_tva_snapshot_complet;

COMMENT ON COLUMN public.lignes_facture.code_regle_tva IS
  'NULL = facture historique non qualifiée ; code TVA daté uniquement après contrôle serveur.';
COMMENT ON COLUMN public.lignes_facture.assiette_tva IS
  'Assiette HT fiscalement calculée de la ligne, après affectation traçable de la remise globale.';
COMMENT ON COLUMN public.lignes_facture.montant_tva_ligne IS
  'TVA ligne arrondie au centime, montant vérifiable depuis assiette_tva et taux_tva_ligne.';
COMMENT ON CONSTRAINT erp_lignes_facture_tva_snapshot_complet ON public.lignes_facture IS
  'Snapshot incomplet interdit ; ne prouve pas seul une homologation des sources.';
