# LOT-06B — Isolation des catégories Stocks MP et PF

Date : 2026-11-08. Branche : `perf/lot06b-stocks-category-lazy-20261108`.

## Constat et correction

Après LOT-06A, seule la vue principale Stocks consultée est exécutée. Cependant, dans « État des Stocks », les trois sous-onglets Streamlit exécutaient simultanément leurs lectures MP, PF et référentiels SKU/Produits.

Ce lot remplace les trois sous-onglets par `Catégorie de stock`, un sélecteur à trois choix. La catégorie Vrac ou Emballages lit uniquement le référentiel MP et les stocks MP ; la catégorie PF ne lit que le stock PF et les catalogues SKU/Produits. Les calculs de classification de catégorie et les colonnes exposées restent inchangés.

## Preuve de non-régression

- Cinq tests nouveaux testent les trois catégories, la non-interférence d'un service MP indisponible sur la vue PF et le refus des permissions avant la sélection.
- Les anciens tests de la vue Stocks et du signalement d'activité sont adaptés aux **deux** sélecteurs.
- Les sous-vues ne sont pas des opérations d'écriture. Les flux des réceptions manuelles, opérations incertaines, `operation_id`, droits, formulaires et historiques restent inchangés.
- Aucun SQL, aucune mutation Supabase, RLS/GRANT, migration ni secret introduit.

## Mesure attendue et limites

| Vue | Lectures métier nécessaires | Lectures évitées |
|---|---|---|
| Vrac / Emballages | MP et stock MP | Stock PF, SKU, Produits |
| Produits Finis | Stock PF, SKU, Produits | MP et stock MP |

Il s'agit d'un nombre déterministe de **familles d'appels supprimées** et non d'une preuve de gain de latence. L'instrumentation OPT-04 peut servir à mesurer les résultats en mode réel après vérification du déploiement.

## Suite

- LOT-07 Achats : sélectionner Commande / Réception / Historique ; déjà fusionné sur `main` via PR #62, commit `649c71d2c2410b27b7d9333b7cef5c49e0c760fc`.
- LOT-08 Production : éviter les lectures des panneaux non sélectionnés, sans changer la fabrication, les consommations, les clôtures ou les contrôles qualité.
- Recette authentifiée Streamlit et rotation du mot de passe administrateur restent requises ; la base TEST inactive interdit les tests d'écriture de validation en production.
