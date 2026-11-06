# Campagne 042 — Instantané de validation des coûts industriels
Date : 2026-11-06

## Résultat
L'ERP conserve un snapshot immuable des valeurs d'OF au moment où la période analytique passe de BROUILLON à VALIDE, et détecte une divergence ultérieure entre le snapshot et la vue de coûts courants. Migration **042** appliquée et testée sur Supabase TEST puis appliquée à PRODUCTION.

## Livrables GitHub main
- `sql/042_snapshot_validation_couts_industriels.sql` : table `erp_cost_of_validation_snapshot` avec PK (period_id,of_id), RLS, SELECT seulement au service_role, pas d'écriture autorisée aux clients ni à service_role ; trigger `erp_cost_snapshot_on_validation_trigger` AFTER UPDATE OF statut sur `erp_cost_periods`, fonction SECURITY DEFINER. Snapshot créé dans la transaction de validation.
- `erp_cost_of_validation_drift` : vue SECURITY INVOKER qui compare statut OF, quantité, coût direct, frais imputés et coût analytique total avec le snapshot et expose `derive_detectee`.
- `modules/production/cost_service.py` : rapport récupère `validation_drift`.
- `modules/production/cost_views.py` : alerte Streamlit si différence détectée, tableau des valeurs validées et courantes.
- `tests/test_industrial_cost_scf_evidence_contract.py` et `tests/test_industrial_cost_views_flows.py` : contrats et scénarios d'affichage de la dérive.
- `sql/test_isole/20261106_snapshot_derives_couts_ROLLBACK.sql` : scénario transactionnel avec deux OF fictifs, validation, snapshot, modification temporaire du coût direct, détection d'écart puis rétablissement et ROLLBACK.

## Preuves réelles TEST
- Migration `erp_cost_of_validation_snapshot_20261106` : success=true.
- `COST_SNAPSHOT_DRIFT_OK` : coût imputé OF1=70 DZD, OF2=140 DZD, total=210 DZD; snapshots de 2 OF à la validation; 1 dérive détectée quand cout_total d'un OF fictif augmente puis 0 après correction; ROLLBACK.
- Régression `COST_ATOMIC_DOCUMENT_OK`, `COST_ACL_OK` et `COST_ROLE_MATRIX_OK`, toutes réussies.
- Contrôle indépendant après les tests : 0 snapshot, 0 période et 0 charge de test, 0 pièce comptable fictive.
- Droits : `authenticated` ne peut lire ni la table snapshot ni la vue drift ; `service_role` SELECT=true.

## CI
Commit de test `fd541ce7715754f2238ac4640df6c1b4b622c2e8` :
- Tests ERP : https://github.com/Verwolfy/erp-mortier/actions/runs/42205871946 — SUCCESS.
- Audit de réconciliation : https://github.com/Verwolfy/erp-mortier/actions/runs/42205871956 — SUCCESS.
- Suite ERP : **2 584 passed, 7 skipped, 133 warnings**.

## Production
- Migration `erp_cost_of_validation_snapshot_20261106` : success=true.
- Contrôle après déploiement : `periodes=0`, `charges=0`, `instantanes=0`; vue `erp_cost_of_validation_drift` présente; `authenticated` SELECT=false, `service_role` SELECT=true.
- Aucun stock, CUMP ni document SCF modifié, aucun montant fictif importé.

## Limites
- Un instantané validé n'empêche pas une modification de l'OF original; il **détecte** la dérive sans changer les flux industriels ou comptables.
- La vue compare les valeurs courantes à celles capturées. Tout réajustement comptable exige un contrôle métier distinct.
- Les simulations de l'interface ne remplacent pas un test navigateur authentifié réel.
- Le service `get_period_report` utilise des plafonds `limit(1000)` pour la liste de dérives et d'autres plafonds sur les allocations; à traiter si la volumétrie dépasse ces seuils.
- Supabase TEST doit être suspendu à l'issue de la campagne.

## Étape suivante
Qualification Streamlit avec deux véritables profils; alerte si dérive; vérification de la cohérence entre instantané, OF et référence SCF. Puis supervision des plafonds de pagination si nécessaire.
