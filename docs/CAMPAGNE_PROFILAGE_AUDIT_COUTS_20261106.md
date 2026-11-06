# Lot 047 — Profilage SQL de l'audit analytique
Date : 6 novembre 2026

## Résultat vérifié
- Projet : Sofiane ERP / `Verwolfy/erp-mortier`, branche `main`.
- TEST : Supabase `ffuhbmcfyexsbjwhryvj`; tests sous `BEGIN...ROLLBACK`.
- PROD : Supabase `wenydirqtmkywbxbxfal`; aucune migration ni modification de données.
- Commit de tests `5115cf44691a36b4c3733fc5ff946ed89e0109bf`.
- CI ERP [succès](https://github.com/Verwolfy/erp-mortier/actions/runs/42217862490) : **2 618 tests réussis, 7 ignorés, 133 avertissements**.
- Audit de réconciliation [succès](https://github.com/Verwolfy/erp-mortier/actions/runs/42217862512).

## Échantillons réellement exécutés
Plan de mesure PostgreSQL `EXPLAIN (ANALYZE, BUFFERS, FORMAT JSON)`, résultats indicatifs d'une seule exécution sur TEST.

| Opération | 500 OF / 1 000 assiettes | 2 000 OF / 4 000 assiettes |
|---|---:|---:|
| `erp_cost_period_audit` | 10,899 ms | 40,183 ms |
| Agrégation `erp_cost_allocations` | 7,596 ms | 31,771 ms |
| Filtre `erp_cost_drivers` | 0,409 ms | 1,527 ms |
| Blocs cache pour audit | 3 064 | 12 182 |
| Blocs cache pour allocations | 3 041 | 12 133 |
| Verdict | `COST_PROFILE_047_OK` | `COST_PROFILE_047_OK` |

Deux pools fictifs, montant total 210 DZD, `audit_ok=true` avant les mesures. Augmentation approximativement proportionnelle aux données dans cet essai : ~3,69× de durée audit pour 4× plus d'OF. Les résultats ne sont ni SLA ni mesure en production.

## Analyse
- Le coût dominant observé est l'agrégation des allocations, pas le simple filtre des assiettes.
- Index existants vérifiés : `erp_cost_drivers(period_id,base_imputation)`, clé primaire `(period_id,of_id,base_imputation)`, `erp_cost_pools(period_id,base_imputation)`, clé primaire `ordres_fabrication(of_id)`.
- Aucun ralentissement disproportionné n'est établi sur ces deux tailles. **Pas de nouvel index ni refonte SQL recommandés sans mesures complémentaires**.
- L'optimisation du lot 046 (audit complet sur demande, recalcul obligatoire en validation) reste pertinente.

## Scripts et sécurité
- `sql/test_isole/20261106_profilage_audit_industriel_047_ROLLBACK.sql` : 500 OF, 1 000 assiettes.
- `sql/test_isole/20261106_profilage_audit_industriel_047_VOLUME_ROLLBACK.sql` : 2 000 OF, 4 000 assiettes.
- `tests/test_industrial_cost_profile_contract.py` : vérification transactionnelle, délai de sécurité, absence d'écritures SCF ou stock.
- Les deux tests SQL se terminent par `ROLLBACK`, ont été exécutés avec succès et présentent `COST_PROFILE_047_OK`.
- Contrôles indépendants après chaque essai : zéro OF, période, pool ou assiette de profilage conservé.
- Aucun changement CUMP, stock ou écritures SCF; aucun faux référentiel de production.

## Limites et suites
- Un unique EXPLAIN par variante ne donne pas de distribution robuste de latence; répéter à charge comparable et relever la variance avant optimisation.
- PostgreSQL TEST ne reproduit pas nécessairement la concurrence ou le matériel de PROD.
- Pour un audit réglementaire, la lecture HTTP paginée ne vaut pas snapshot transactionnel certifié.
- Qualification utilisateur avec une véritable session navigateur Production + Finance et profil limité toujours ouverte.
- Côté coûts, seul un rapprochement SCF validé permet de documenter une charge; l'éligibilité industrielle reste à contrôler par Finance.
