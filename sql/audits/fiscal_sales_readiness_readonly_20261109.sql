-- FISCAL-READINESS-01. Diagnostic de préparation, EXCLUSIVEMENT LECTURE SEULE.
-- Cette requête ne détermine aucun taux légal nouveau et n'autorise pas
-- l'émission de factures. Tous les compteurs reflètent l'état constaté.
WITH taux AS (
    SELECT
      count(*) FILTER (WHERE code = 'TVA_TAUX_NORMAL'
          AND statut_juridique = 'en_vigueur'
          AND niveau_confiance = 'CONFIRMEE'
          AND unite = 'fraction'
          AND nullif(btrim(source), '') IS NOT NULL
          AND date_verification IS NOT NULL
          AND date_effet <= current_date
          AND (date_fin IS NULL OR date_fin >= current_date)) AS tva_normale_confirmee,
      count(*) FILTER (WHERE code = 'TVA_TAUX_REDUIT'
          AND statut_juridique = 'en_vigueur'
          AND niveau_confiance = 'CONFIRMEE'
          AND unite = 'fraction'
          AND nullif(btrim(source), '') IS NOT NULL
          AND date_verification IS NOT NULL
          AND date_effet <= current_date
          AND (date_fin IS NULL OR date_fin >= current_date)) AS tva_reduite_confirmee,
      count(*) FILTER (WHERE code = 'TVA_VENTE_TAUX'
          AND date_effet <= current_date
          AND (date_fin IS NULL OR date_fin >= current_date)) AS tva_vente_ancien_moteur
    FROM public.parametres_reglementaires
), classement AS (
    SELECT
      count(*) AS lignes_classification,
      count(*) FILTER (WHERE statut = 'A_VALIDER') AS lignes_a_valider,
      count(*) FILTER (WHERE statut = 'VALIDEE'
          AND date_effet <= current_date
          AND (date_fin IS NULL OR date_fin >= current_date)) AS lignes_validees_applicables
    FROM public.erp_sku_fiscalite
), skus AS (
    SELECT
      count(*) FILTER (WHERE s.actif = 'OUI') AS skus_actifs,
      count(*) FILTER (WHERE s.actif = 'OUI' AND NOT EXISTS (
          SELECT 1 FROM public.erp_sku_fiscalite c
          WHERE c.sku_id = s.sku_id
            AND c.statut = 'VALIDEE'
            AND c.date_effet <= current_date
            AND (c.date_fin IS NULL OR c.date_fin >= current_date)
      )) AS skus_actifs_sans_classement_valide
    FROM public.sku_conditionnement s
), moteur AS (
    SELECT
      to_regprocedure('public.erp_facture_parametre(text,date,text)') IS NOT NULL
          AS fonction_parametre_deployee,
      to_regprocedure('public.erp_sale_transaction(text,text,jsonb)') IS NOT NULL
          AS fonction_vente_deployee,
      coalesce((
          SELECT
              position('0.19' IN pg_get_functiondef(p.oid)) > 0
              OR position('0.01' IN pg_get_functiondef(p.oid)) > 0
              OR position('2500' IN pg_get_functiondef(p.oid)) > 0
          FROM pg_proc p
          WHERE p.oid = to_regprocedure('public.erp_sale_transaction(text,text,jsonb)')
      ), false) AS rpc_contient_anciens_litteraux
)
SELECT
    current_date AS date_controle,
    taux.tva_normale_confirmee, taux.tva_reduite_confirmee,
    taux.tva_vente_ancien_moteur,
    classement.lignes_classification, classement.lignes_a_valider,
    classement.lignes_validees_applicables,
    skus.skus_actifs, skus.skus_actifs_sans_classement_valide,
    moteur.fonction_parametre_deployee, moteur.fonction_vente_deployee,
    moteur.rpc_contient_anciens_litteraux,
    false AS homologation_reglementaire_automatique
FROM taux CROSS JOIN classement CROSS JOIN skus CROSS JOIN moteur;
