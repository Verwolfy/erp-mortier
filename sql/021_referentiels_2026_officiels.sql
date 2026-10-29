-- ERP 021 : référentiels OFFICIELS vérifiés le 29/10/2026 (sans opérations comptables).
-- L'effet 2026-01-01 borne le SNAPSHOT de règles vérifié pour 2026,
-- et ne prétend pas être la date d'origine historique des taux.
-- Aucune affectation TVA à un SKU, ni choix du régime de l'entreprise.
-- Pas de compte SCF actif ou mouvementable ; pas de journal ou exercice.
-- Pas d'ancienne règle TVA_VENTE_TAUX ou TIMBRE_ESPECES_TAUX.
BEGIN;

WITH officiels(
 code,domaine,valeur,unite,date_effet,date_fin,
 statut_juridique,niveau_confiance,source,texte_source,date_verification
) AS (VALUES
    ('TVA_TAUX_NORMAL', 'TVA', 0.19, 'fraction', '2026-01-01'::date, NULL::date, 'en_vigueur', 'CONFIRMEE', 'https://www.mfdgi.gov.dz/fr/professionnels/services-pro/regime-reel/la-taxe-sur-la-valeur-ajoutee', 'Taux général 19% selon fiche DGI actualisée le 23 février 2026. Référence juridique générale ; l''assujettissement d''une transaction reste à qualifier.', '2026-10-29'::date),
    ('TVA_TAUX_REDUIT', 'TVA', 0.09, 'fraction', '2026-01-01'::date, NULL::date, 'en_vigueur', 'CONFIRMEE', 'https://www.mfdgi.gov.dz/fr/professionnels/services-pro/regime-reel/la-taxe-sur-la-valeur-ajoutee', 'Taux réduit 9% sur seules catégories éligibles selon art. 23 du CTCA, modifié notamment par art. 53 de la LF 2026 (JO 88 du 31 décembre 2025).', '2026-10-29'::date)
)
INSERT INTO public.parametres_reglementaires (
 code,domaine,valeur,unite,date_effet,date_fin,statut_juridique,
 niveau_confiance,source,texte_source,date_verification
)
SELECT * FROM officiels WHERE true
ON CONFLICT (code,date_effet) DO NOTHING;

-- Source DGI : régimes réel et simplifié, article G50 pour le régime réel.
WITH regle(
 code,domaine,type_regle,donnees,date_effet,date_fin,
 statut_juridique,niveau_confiance,source,texte_source,date_verification
) AS (
 VALUES (
 'TVA_G50_MENSUEL_REGIME_REEL','TVA','echeance',
 '{"periodicite":"mensuelle","periode_reference":"mois_precedent","jour_limite":20,"regime":"reel","declaration":"G50","application_entreprise":"NON_CLASSEE","notes":"La périodicité et les règles particulières dépendent du régime réel du contribuable. Ne pas appliquer aux régimes spéciaux."}'::jsonb,
 '2026-01-01'::date,NULL::date,
 'en_vigueur','CONFIRMEE',
 'https://www.mfdgi.gov.dz/fr/professionnels/services-pro/regime-reel/la-taxe-sur-la-valeur-ajoutee',
 'DGI, obligations déclaratives au régime réel : dépôt G50 dans les 20 premiers jours du mois pour le mois précédent ; l’entreprise doit confirmer son régime.', 
 '2026-10-29'::date
 )
)
INSERT INTO public.regles_reglementaires(
 code,domaine,type_regle,donnees,date_effet,date_fin,
 statut_juridique,niveau_confiance,source,texte_source,date_verification
)
SELECT * FROM regle WHERE true
ON CONFLICT (code,date_effet) DO NOTHING;

WITH comptes(numero_compte,libelle,actif,mouvementable) AS (VALUES
    ('31', 'Matières premières et fournitures', false, false),
    ('35', 'Stocks de produits', false, false),
    ('355', 'Produits finis', false, false),
    ('38', 'Achats stockés', false, false),
    ('381', 'Matières premières et fournitures stockées', false, false),
    ('40', 'Fournisseurs et comptes rattachés', false, false),
    ('401', 'Fournisseurs de stocks et services', false, false),
    ('41', 'Clients et comptes rattachés', false, false),
    ('411', 'Clients', false, false),
    ('42', 'Personnel et comptes rattachés', false, false),
    ('421', 'Personnel, rémunérations dues', false, false),
    ('43', 'Organismes sociaux et comptes rattachés', false, false),
    ('431', 'Sécurité sociale', false, false),
    ('44', 'État, collectivités publiques, organismes internationaux et comptes rattachés', false, false),
    ('445', 'État, taxes sur le chiffre d''affaires', false, false),
    ('51', 'Banques, établissements financiers et assimilés', false, false),
    ('512', 'Banques comptes courants', false, false),
    ('53', 'Caisse', false, false),
    ('60', 'Achats consommés', false, false),
    ('601', 'Matières premières', false, false),
    ('63', 'Charges de personnel', false, false),
    ('631', 'Rémunérations du personnel', false, false),
    ('635', 'Cotisations aux organismes sociaux', false, false),
    ('70', 'Ventes de marchandises, de produits fabriqués, de prestations de services et produits annexes', false, false),
    ('701', 'Ventes de produits finis', false, false)
)
INSERT INTO public.scf_plan_comptes(numero_compte,libelle,actif,mouvementable)
SELECT * FROM comptes WHERE true
ON CONFLICT (numero_compte) DO NOTHING;

-- Vérifications transactionnelles des collisions : ne pas écraser un référentiel existant
-- et ANNULER tout ce lot en cas de divergence.
DO $verification$
DECLARE n integer;
BEGIN
  SELECT count(*) INTO n FROM public.parametres_reglementaires
    WHERE (code='TVA_TAUX_NORMAL' AND date_effet='2026-01-01')
       OR (code='TVA_TAUX_REDUIT' AND date_effet='2026-01-01');
  IF n<>2 THEN RAISE EXCEPTION 'Paramètres TVA 2026 incomplets'; END IF;
  IF EXISTS (
    SELECT 1 FROM public.parametres_reglementaires
    WHERE date_effet='2026-01-01'
      AND ((code='TVA_TAUX_NORMAL' AND (valeur<>0.19 OR unite<>'fraction'))
        OR (code='TVA_TAUX_REDUIT' AND (valeur<>0.09 OR unite<>'fraction'))
        OR (code IN ('TVA_TAUX_NORMAL','TVA_TAUX_REDUIT')
            AND (statut_juridique<>'en_vigueur' OR niveau_confiance<>'CONFIRMEE'
                 OR source IS DISTINCT FROM 'https://www.mfdgi.gov.dz/fr/professionnels/services-pro/regime-reel/la-taxe-sur-la-valeur-ajoutee')))
  ) THEN RAISE EXCEPTION 'Collision avec des règles TVA existantes'; END IF;
  IF NOT EXISTS(
    SELECT 1 FROM public.regles_reglementaires
    WHERE code='TVA_G50_MENSUEL_REGIME_REEL' AND date_effet='2026-01-01'
      AND domaine='TVA' AND type_regle='echeance'
      AND statut_juridique='en_vigueur' AND niveau_confiance='CONFIRMEE'
      AND donnees->>'application_entreprise'='NON_CLASSEE'
  ) THEN RAISE EXCEPTION 'Règle G50 du référentiel absente ou contradictoire'; END IF;
  IF (SELECT count(*) FROM public.scf_plan_comptes
       WHERE numero_compte IN ('31','35','355','38','381','40','401','41','411','42','421','43','431','44','445','51','512','53','60','601','63','631','635','70','701')
       AND (actif OR mouvementable)) > 0 THEN
    RAISE EXCEPTION 'Collision : comptes SCF déjà activés, revue obligatoire';
  END IF;
  IF EXISTS(
    SELECT 1 FROM (VALUES
    ('31', 'Matières premières et fournitures', false, false),
    ('35', 'Stocks de produits', false, false),
    ('355', 'Produits finis', false, false),
    ('38', 'Achats stockés', false, false),
    ('381', 'Matières premières et fournitures stockées', false, false),
    ('40', 'Fournisseurs et comptes rattachés', false, false),
    ('401', 'Fournisseurs de stocks et services', false, false),
    ('41', 'Clients et comptes rattachés', false, false),
    ('411', 'Clients', false, false),
    ('42', 'Personnel et comptes rattachés', false, false),
    ('421', 'Personnel, rémunérations dues', false, false),
    ('43', 'Organismes sociaux et comptes rattachés', false, false),
    ('431', 'Sécurité sociale', false, false),
    ('44', 'État, collectivités publiques, organismes internationaux et comptes rattachés', false, false),
    ('445', 'État, taxes sur le chiffre d''affaires', false, false),
    ('51', 'Banques, établissements financiers et assimilés', false, false),
    ('512', 'Banques comptes courants', false, false),
    ('53', 'Caisse', false, false),
    ('60', 'Achats consommés', false, false),
    ('601', 'Matières premières', false, false),
    ('63', 'Charges de personnel', false, false),
    ('631', 'Rémunérations du personnel', false, false),
    ('635', 'Cotisations aux organismes sociaux', false, false),
    ('70', 'Ventes de marchandises, de produits fabriqués, de prestations de services et produits annexes', false, false),
    ('701', 'Ventes de produits finis', false, false)
    ) AS v(numero_compte,libelle,actif,mouvementable)
    LEFT JOIN public.scf_plan_comptes s USING (numero_compte)
    WHERE s.numero_compte IS NULL OR s.libelle IS DISTINCT FROM v.libelle
  ) THEN RAISE EXCEPTION 'Nomenclature SCF différente : lot non appliqué'; END IF;
END;
$verification$;
COMMIT;
