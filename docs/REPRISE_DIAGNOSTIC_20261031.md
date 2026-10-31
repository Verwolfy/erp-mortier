# Reprise autonome — 31 octobre 2026 (lecture seule)

## Périmètre vérifié
- GitHub : `Verwolfy/erp-mortier`, branche unique distante `main` à `1211b4e64c342bb1cdae67929263055b9f9435ea` avant ce rapport ; PR ouvertes : 0.
- GitHub Actions : workflow `ERP - tests lot C facturation`, exécution 41216390779 sur ce SHA : `completed/success` (31/10/2026 15:47 UTC). Ceci ne vaut pas certification globale ni confirmation d'un déploiement Streamlit.
- Supabase PRODUCTION : `wenydirqtmkywbxbxfal`, statut `ACTIVE_HEALTHY`. TEST : `ffuhbmcfyexsbjwhryvj`, statut `INACTIVE` ; aucune modification réalisée sur TEST.
- SQL lecture seule sur PRODUCTION : `sku_conditionnement=7`, `erp_sku_fiscalite=0`, `parametres_reglementaires=5`, `scf_plan_comptes=25`, `schema_migrations=0`.
- Historique Supabase retourné : 21 migrations, allant de `erp_012_harden_principale_grants` à `erp_032_factures_garde_exonerations_historique`, avec continuité 012–032.

## Constat et limites
- Le registre personnalisé `public.schema_migrations` demeure vide malgré l'historique interne de 21 migrations ; ne pas rejouer ces migrations aveuglément.
- Aucune qualification fiscale de SKU n'est présente ; ne pas inventer de classement ni autoriser la facturation à 0 %.
- Premier essai de dénombrement avec `actif IS TRUE` a échoué car la colonne `actif` est de type texte ; le second contrôle sans cette condition a réussi. Le nombre 7 est donc le total des SKU, pas une preuve SQL du nombre actif.
- Aucun `pytest` exécuté localement dans cette reprise ; un seul workflow GitHub pertinent a été vérifié vert.
- État du poste local, archivage des branches passées, conformité exhaustive du schéma et déploiement Streamlit non vérifiés.
- Aucun INSERT, UPDATE, DDL, modification RLS/GRANT, migration, suppression ni activation réglementaire.

## Suite recommandée
1. Comparer précisément le contenu des SQL 012–032 avec l'historique interne et l'état réel ; documenter les divergences de migrations.
2. Contrôler les colonnes, valeurs de statut, dates et preuves des cinq paramètres ; confirmer les garde-fous des transactions.
3. Étendre le contrôle GitHub Actions (suite complète) et les contrôles de sécurité/permissions en lecture seule.
4. Préparer la réconciliation du registre sans insérer de lignes non prouvées. Ne modifier RLS, GRANT, taux, exonérations ni données fiscales sans justification et validation critique.
5. Vérifier effectivement le déploiement de Streamlit ; la réussite de GitHub Actions ne l'établit pas.

## Décision
CONTINUER les audits et corrections compatibles, avec preuve ; les lots réglementaires restent partiels et exigent une validation professionnelle algérienne avant utilisation officielle.
