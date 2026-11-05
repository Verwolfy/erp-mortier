# Campagne de simulation des frais industriels — 05/11/2026

## Portée et statut initial
- Dépôt : `Verwolfy/erp-mortier`, branche `main`.
- Projet TEST : `ffuhbmcfyexsbjwhryvj`. Restauré pour exécuter la suite ; validation SQL en attente lors de la création de ce document.
- Production : `wenydirqtmkywbxbxfal`. Aucune modification.
- Base éprouvée de la campagne précédente : `docs/TEST_COUT_PF_ACHATS_EMBALLAGE_RECETTE_20261105.md`.
- Script étendu : `sql/test_isole/20261105_cout_pf_achats_emballage_recette_ROLLBACK.sql`.
- Oracle test Python : `tests/test_cout_pf_achats_recette_contract.py`.

## Constat ERP
`erp_close_manufacturing_order` calcule aujourd'hui les coûts **MP au CUMP + conditionnements**. Le schéma examiné expose `ordres_fabrication.cout_total`, sans tables explicites de paramétrage de coûts industriels indirects dans les noms recherchés (`%cout%`, `%charge%`, `%frais%`, `%fabrication%`, `%recette%`). Cela n'exclut pas d'autres référentiels sous d'autres noms; ne pas affirmer une absence exhaustive.

## Simulation analytique fictive
Une table temporaire `pg_temp.it26_pf_indirect_costs` est créée **au sein de la transaction du scénario complet**, jamais en production, puis disparaît avec `ROLLBACK`. Elle contient :
| Nature fictive | OF1 DZD | OF2 DZD |
|---|---:|---:|
| Main-d'œuvre | 40 | 25 |
| Énergie | 20 | 15 |
| Amortissement | 12 | 10 |
| Frais indirects | 8 | 5 |
| Frais d'approche | 16 | 9 |
| **Total** | **96** | **64** |

Les coûts directs issus de la campagne test sont :
- OF1 (4 sacs) : 292 DZD.
- OF2 (2 sacs) : `386257/2162 ≈ 178,6572617946` DZD.
- Total direct : `470,6572617946` DZD pour 6 sacs, coût direct moyen `78,4428769658` DZD/sac.
- Frais supplémentaires simulés : 160 DZD.
- **Total analytique simulé attendu : 630,6572617946 DZD**.
- **Coût analytique unitaire attendu : 105,1095436324 DZD/sac**.

Les frais d'approche sont traités dans l'**analyse seulement** ; leur intégration éventuelle au prix d'entrée des composants nécessite une règle métier et comptable définie et sourcée, sinon risque de double comptage.

Un scénario de sensibilité de rebut augmente artificiellement le coût associé à une unité consommée non conforme, sans toucher à la vraie quantité de PF en stock ni affirmer qu'il s'agit de la méthode réglementaire retenue.

## Validation nécessaire
- Vérifier `SELECT 1` sur TEST.
- Exécuter le script SQL complet, vérifier sorties `PF_COST_OK` **et** `INDIRECT_COST_OK`, et le montant total attendu de 630,66 DZD, 105,1095 DZD/sac.
- Confirmer que le CUMP en stock **reste direct** : environ 78,4429 DZD/sac et non 105,1095.
- Vérifier zéro ligne `IT26_PFCOST_*` persistée dans les tables pertinentes après `ROLLBACK`.
- Remettre TEST en pause et contrôler `INACTIVE`.
- Vérifier CI GitHub au commit HEAD ; ne pas la supposer verte.

## Décisions et garde-fous
- Pas de modification de la fonction de production, de comptabilisation, des règles SCF/RLS, ou des tarifs légaux.
- Coûts 100 % hypothétiques, pas de base légale, ne pas intégrer aux documents comptables.
- Évolution future possible : référentiel de coûts datés, clés d'imputation, heures-machine, énergie par batch, taux de rebut, frais d'approche et méthodes de valorisation, **après spécification/validation**.
