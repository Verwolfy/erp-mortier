# Référentiel industriel analytique paramétrable — 05/11/2026

## Statut de déploiement
- Dépôt `Verwolfy/erp-mortier`, branche `main`.
- Migration 034 **appliquée avec succès** à Supabase TEST (`ffuhbmcfyexsbjwhryvj`) et production (`wenydirqtmkywbxbxfal`).
- Migration 035 (vue synthèse et validation documentée) **appliquée avec succès** sur les deux bases.
- Aucun changement à `erp_close_manufacturing_order`, `erp_apply_stock_movement`, `stock_actuel_pf` ni à la comptabilité SCF.
- Six **natures sans montants** configurées en production; zéro période, charge ou assiette réelle créée.
- L'onglet Production → Coûts industriels est versionné sur `main`, mais sa validation navigateur avec compte réel reste à effectuer.

## Tables et structure
- `erp_cost_periods` : période, début, fin, statut `BROUILLON`/`VALIDE`/`CLOTURE`.
- `erp_cost_natures` : natures configurables, six références initiales (main-d’œuvre, énergie, amortissement, frais indirects, frais d’approche, rebut). Aucun prix fictif enregistré.
- `erp_cost_pools` : montants DZD, nature, période, clé d'imputation, justificatif, statut `SIMULATION` ou `DOCUMENTE`.
- `erp_cost_drivers` : valeur mesurée de la clé par OF et période, plus source.
- `erp_cost_allocations` : vue des répartitions par nature/OF (pool × assiette OF / somme assiettes).
- `erp_cost_of_summary` : direct OF + charges allouées, coût total et par unité fabriquée.
- `erp_cost_period_audit(period_id)` : complétude, OF hors période/non terminés, conservation de la somme imputée.
- `erp_cost_validate_period(period_id)` : vérifie l'audit, exige les pièces `DOCUMENTE`, puis valide et fige la période.

## Clés autorisées
`UNITS` (unités SKU), `KG`, `HOURS_LABOR`, `HOURS_MACHINE`, `KWH`, `DIRECT_COST`. Les mesures doivent être saisies explicitement pour chaque OF. Aucune heure, consommation ou taux fictif installé en production. Une pièce peut être un justificatif explicite lié à la nature.

## Sécurité
- RLS activée sur les quatre tables; aucun accès direct SELECT pour `anon` ou `authenticated`; service_role seulement.
- Vues `security_invoker=true`, SELECT réservé au service_role.
- Interface serveur exige Production et Finance pour les lectures, et les deux droits d'écriture pour les modifications.
- Triggers bloquent les modifications de pools/assiettes après validation de la période.
- La validation requiert `DOCUMENTE`, mais l'authenticité des pièces reste une responsabilité métier; aucune certification réglementaire automatique.

## Test SQL réellement exécuté (TEST uniquement)
Fichier : `sql/test_isole/20261105_couts_industriels_referentiel_ROLLBACK.sql`.
- Deux OF fictifs 10 et 5 unités, coûts directs 300 et 200 DZD.
- Pool énergie 120 DZD selon heures machine (2h/4h) → 40/80 DZD.
- Pool main-d’œuvre 90 DZD selon heures main-d’œuvre (1h/2h) → 30/60 DZD.
- Coût analytique : OF1 370 DZD = 37 DZD/unité; OF2 340 DZD = 68 DZD/unité.
- Conservation : imputation totale = pools = 210 DZD.
- Validation interdite avant assiette et tant que statut `SIMULATION`.
- Validation réussie après marquage `DOCUMENTE` dans la fixture de test.
- Mutations après validation rejetées (`23514`).
- Verdict réel : `COST_REFERENCE_OK`; `ROLLBACK` final.
- Contrôle SQL après ROLLBACK : 0 période, 0 pool, 0 driver et 0 OF de test.

## Fichiers GitHub
- `sql/034_referentiel_couts_industriels_analytiques.sql`
- `sql/035_cout_industriel_synthese_validation.sql`
- `sql/test_isole/20261105_couts_industriels_referentiel_ROLLBACK.sql`
- `modules/production/cost_service.py`
- `modules/production/cost_views.py`
- `modules/production/views.py` (onglet intégré)
- `tests/test_industrial_cost_reference_contract.py`

## Limites et suite
1. Vérifier les workflows CI pour le HEAD de main et corriger les tests en échec le cas échéant.
2. Tester en navigateur authentifié le nouvel onglet et les droits Production + Finance.
3. Définir les règles documentaires et méthodes d'imputation réellement approuvées; aucun frais indirect ne sera automatiquement capitalisé dans le CUMP sans validation comptable.
4. Confirmer la pause de TEST (`INACTIVE`) après les essais.
