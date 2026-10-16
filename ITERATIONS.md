# Journal de la boucle de vérification — périmètre effectivement testé

**Périmètre réel :** module neuf isolé `erp_hardening`, pas le dépôt ERP d'origine. Impossible de noter globalement l'ancien ERP après correction sans accès au code complet et à un Supabase de préproduction. Les notes ci-dessous sont des **estimations manuelles** pour le module livré, pas une certification.

| Itération | PLAN — faiblesse prioritaire | DO — modification | VERIFY | DECIDE |
|---|---|---|---|---|
| 1 | Correction: calcul de recettes faux si batch différent de 1 | Calcul BOM avec Decimal + contrôle d'unité; façade RPC | Tests de proportion, petits lots, densité, validation | ITERATING |
| 2 | Robustesse: risque de stocks incohérents et rejoués | Migration SQL avec transactions, lots FIFO, clé d'idempotence, vérification d'identité SQL et permissions | 34 tests Python, compilation OK; SQL statique uniquement | ITERATING |
| 3 | Sécurité/qualité: recette modifiable après approbation, FK insuffisantes | Verrous par article, triggers d'immuabilité, FK composées de société/lot, FIFO séquentiel, sanitation des erreurs réseau | 42 tests Python OK; la base Supabase réelle reste non testée | ITERATING |

## Auto-évaluation de cette livraison (1–10)

| Critère | Note | Motif concret |
|---|---:|---|
| Correction | 7 | Calculs unitaires validés; transactions SQL non exécutées en PostgreSQL |
| Performance | 7 | Aucun appel SQL par champ et calculs O(n), mais aucun benchmark SQL ni charge concurrente |
| Robustesse | 7 | Validation, contrôle stock et rollback conçus, mais pas éprouvés sur SQL réel |
| Lisibilité | 9 | Composants nommés, responsabilités séparées, instructions complètes |
| Bonnes pratiques Python/Supabase | 8 | Décimales exactes, transactions RPC, RLS et permissions; intégration Auth à réaliser |
| Sécurité | 7 | Contrôle DB, schéma non exposé; tests d'intrusion et audit de l'ERP amont non réalisés |

**Verdict : ITERATING — pas FINAL pour l'ERP complet.** On ne peut pas attribuer ≥9 partout sans accès au dépôt intégral et tests PostgreSQL de bout en bout. Il serait trompeur de déclarer « 100% fonctionnel ».

## Prochaines validations indispensables

- Monter Supabase local / préproduction, appliquer migration, vérifier via `pg_get_functiondef`, rôle `anon`, utilisateur non autorisé, membre autre société, reprise réseau avec même UUID, deux OF concurrents, commande en stock insuffisant, recette archivée, course approbation/édition.
- Tester les temps de réponse et le verrouillage sur centaines de lots, le bon ordre FIFO et les coûts réels par OF.
- Lire tout l'ERP original, écrire les adaptateurs vers anciens modules, migrer les données, supprimer les anciennes écritures concurrentes; auditer secrets et accès Google Sheets, la facturation et la partie double.
- Corriger/retirer les secrets éventuellement présents dans l'historique Git puis effectuer rotation des comptes impliqués.
