-- ERP-046 : test PostgreSQL 17 exclusivement éphémère, valeurs totalement fictives.
BEGIN;
CREATE FUNCTION pg_temp.reject_sql(case_name text, statement text)
RETURNS void LANGUAGE plpgsql AS $assert$
DECLARE rejected boolean := false;
BEGIN
  BEGIN EXECUTE statement; EXCEPTION WHEN OTHERS THEN rejected := true; END;
  IF NOT rejected THEN
    RAISE EXCEPTION 'ERP-046 : refus manquant : %', case_name;
  END IF;
END;
$assert$;

DO $assert_legacy$
BEGIN
  IF (SELECT count(*) FROM public.lignes_facture WHERE ligne_facture_id='LFA-SIM-LEGACY'
    AND code_regle_tva IS NULL AND montant_tva_ligne IS NULL) <> 1 THEN
    RAISE EXCEPTION 'ERP-046 : ligne historique incorrecte';
  END IF;
END;
$assert_legacy$;

-- Preuve TVA positive (fictive) et calcul exact au centime.
INSERT INTO public.lignes_facture(
    ligne_facture_id, facture_id, sku_id, total_ligne_ht,
    code_regle_tva, assiette_tva, taux_tva_ligne, montant_tva_ligne,
    date_fait_generateur_tva, date_effet_regle_tva,
    source_regle_tva, date_verification_regle_tva,
    source_classification_tva, justification_classification_tva,
    date_verification_classification_tva, valide_par_classification_tva
) VALUES (
    'LFA-SIM-COMPLETE','FAC-SIM','SKU-SIM-N',100.00,
    'TVA_TAUX_NORMAL',90.00,0.20,18.00,
    '2026-11-09','2026-01-01',
    'TAUX-SIMULATION','2026-01-02',
    'CLASSEMENT-SIMULATION','JUSTIFICATION-SIMULATION',
    '2026-01-03','VALIDATEUR-SIMULATION'
);

SELECT pg_temp.reject_sql('snapshot incomplet', $sql$
 INSERT INTO public.lignes_facture(ligne_facture_id,total_ligne_ht,code_regle_tva)
 VALUES('BAD-PARTIAL', 100, 'TVA_TAUX_NORMAL')
$sql$);

SELECT pg_temp.reject_sql('taux TVA forgé', $sql$
 UPDATE public.lignes_facture SET montant_tva_ligne = 17.99
 WHERE ligne_facture_id = 'LFA-SIM-COMPLETE'
$sql$);

SELECT pg_temp.reject_sql('taux TVA NaN', $sql$
 UPDATE public.lignes_facture SET taux_tva_ligne = 'NaN'::numeric
 WHERE ligne_facture_id = 'LFA-SIM-COMPLETE'
$sql$);

SELECT pg_temp.reject_sql('preuve effacée', $sql$
 UPDATE public.lignes_facture SET source_classification_tva = ''
 WHERE ligne_facture_id = 'LFA-SIM-COMPLETE'
$sql$);

SELECT pg_temp.reject_sql('taux hors bornes', $sql$
 UPDATE public.lignes_facture SET taux_tva_ligne = 1.1
 WHERE ligne_facture_id = 'LFA-SIM-COMPLETE'
$sql$);

SELECT pg_temp.reject_sql('assiette supérieure HT', $sql$
 UPDATE public.lignes_facture SET assiette_tva = 101.00, montant_tva_ligne = 20.20
 WHERE ligne_facture_id = 'LFA-SIM-COMPLETE'
$sql$);

SELECT pg_temp.reject_sql('date effet postérieure au fait générateur', $sql$
 UPDATE public.lignes_facture SET date_effet_regle_tva = '2027-01-01'
 WHERE ligne_facture_id = 'LFA-SIM-COMPLETE'
$sql$);

SELECT pg_temp.reject_sql('regime hors périmètre pilote', $sql$
 UPDATE public.lignes_facture SET code_regle_tva='TVA_EXONERE'
 WHERE ligne_facture_id = 'LFA-SIM-COMPLETE'
$sql$);

SELECT pg_temp.reject_sql('snapshot legacy partiellement inventé', $sql$
 UPDATE public.lignes_facture SET montant_tva_ligne=19.00
 WHERE ligne_facture_id = 'LFA-SIM-LEGACY'
$sql$);

DO $final$
BEGIN
  IF (SELECT count(*) FROM public.lignes_facture WHERE ligne_facture_id='LFA-SIM-COMPLETE'
      AND montant_tva_ligne=18.00 AND assiette_tva=90.00) <> 1 THEN
    RAISE EXCEPTION 'ERP-046 : snapshot valide corrompu';
  END IF;
END;
$final$;
ROLLBACK;
