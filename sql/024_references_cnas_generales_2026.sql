-- ERP 024 : taux de RÉFÉRENCE issus du décret 15-236 (JO 49/2015, p.7).
-- Les taux du régime général ne sont PAS des paramètres de paie exécutables.
-- Ces codes terminés par _REF sont différents de CNAS_SALARIE_TAUX,
-- CNAS_EMPLOYEUR_TAUX attendus par le simulateur.
-- L'année 2026 borne l'instantané documentaire, pas l'effet juridique
-- historique du décret. Revalidation des dispositions récentes et du régime
-- sectoriel obligatoire avant activation de toute cotisation réelle.
BEGIN;

WITH references_cnas (
  code,domaine,valeur,unite,date_effet,date_fin,statut_juridique,
  niveau_confiance,source,texte_source,date_verification
) AS (VALUES
  ('CNAS_REG_GENERAL_EMPLOYEUR_REF','CNAS',0.25::numeric,'fraction','2026-01-01'::date,'2026-12-31'::date,'a_confirmer','RECOUPEE','https://www.joradp.dz/FTP/jo-francais/2015/F2015049.pdf','Référence générale : JO 49 du 16/09/2015, décret 15-236 art. 1. Quote-part employeur 25%. Instantané documentaire 2026, pas date d''effet historique. Vérifier amendements, statut entreprise, assiette et dispositifs sectoriels avant activation.','2026-10-29'::date),
  ('CNAS_REG_GENERAL_SALARIE_REF','CNAS',0.09::numeric,'fraction','2026-01-01'::date,'2026-12-31'::date,'a_confirmer','RECOUPEE','https://www.joradp.dz/FTP/jo-francais/2015/F2015049.pdf','Référence générale : JO 49 du 16/09/2015, décret 15-236 art. 1. Quote-part salarié 9%. Instantané documentaire 2026, pas date d''effet historique. Vérifier amendements, statut entreprise, assiette et dispositifs sectoriels avant activation.','2026-10-29'::date),
  ('CNAS_REG_GENERAL_FONDS_OEUVRES_REF','CNAS',0.005::numeric,'fraction','2026-01-01'::date,'2026-12-31'::date,'a_confirmer','RECOUPEE','https://www.joradp.dz/FTP/jo-francais/2015/F2015049.pdf','Référence générale : JO 49 du 16/09/2015, décret 15-236 art. 1. Quote-part fonds des œuvres sociales 0,50%. Instantané documentaire 2026, pas date d''effet historique. Vérifier amendements, statut entreprise, assiette et dispositifs sectoriels avant activation.','2026-10-29'::date)
)
INSERT INTO public.parametres_reglementaires (
  code,domaine,valeur,unite,date_effet,date_fin,statut_juridique,
  niveau_confiance,source,texte_source,date_verification
)
SELECT * FROM references_cnas WHERE true
ON CONFLICT (code,date_effet) DO NOTHING;

DO $verification$
DECLARE n integer;
BEGIN
  SELECT count(*) INTO n FROM public.parametres_reglementaires
    WHERE code IN (
      'CNAS_REG_GENERAL_EMPLOYEUR_REF',
      'CNAS_REG_GENERAL_SALARIE_REF',
      'CNAS_REG_GENERAL_FONDS_OEUVRES_REF'
    ) AND date_effet='2026-01-01';
  IF n <> 3 THEN
    RAISE EXCEPTION 'Références CNAS incomplètes';
  END IF;
  IF EXISTS(
    SELECT 1 FROM (VALUES
      ('CNAS_REG_GENERAL_EMPLOYEUR_REF',0.25::numeric),
      ('CNAS_REG_GENERAL_SALARIE_REF',0.09::numeric),
      ('CNAS_REG_GENERAL_FONDS_OEUVRES_REF',0.005::numeric)
    ) AS att(code,valeur)
    JOIN public.parametres_reglementaires p
      ON p.code=att.code AND p.date_effet='2026-01-01'
    WHERE p.domaine<>'CNAS'
       OR p.valeur IS DISTINCT FROM att.valeur
       OR p.unite<>'fraction'
       OR p.date_fin IS DISTINCT FROM '2026-12-31'::date
       OR p.statut_juridique<>'a_confirmer'
       OR p.niveau_confiance<>'RECOUPEE'
       OR p.source IS DISTINCT FROM 'https://www.joradp.dz/FTP/jo-francais/2015/F2015049.pdf'
       OR p.date_verification IS DISTINCT FROM '2026-10-29'::date
  ) THEN
    RAISE EXCEPTION 'Collision des références CNAS (aucun écrasement)';
  END IF;
  IF 0.25::numeric + 0.09::numeric + 0.005::numeric <> 0.345::numeric THEN
    RAISE EXCEPTION 'Somme des parts de cotisation non conforme';
  END IF;
END;
$verification$;
COMMIT;
