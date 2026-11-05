# Tests de concurrence PostgreSQL réels — 5 novembre 2026

## État final
Deux essais d'accès simultané ont été exécutés par **deux connexions distinctes** contre le projet Supabase isolé `erp-mortier-test` (`ffuhbmcfyexsbjwhryvj`). Aucun appel d'écriture n'a été envoyé au projet de production `wenydirqtmkywbxbxfal`.

### 1. Commande client : même clé d'idempotence
- Préparation sur TEST : client, produit et SKU `IT26_PAR_*`; ajustement dans TEST de `GRANT UPDATE` sur `clients`, `produits`, `sku_conditionnement` pour le rôle `service_role` (droit déjà présent en production).
- Sessions A et B : appels **parallèles** à `erp_create_sales_order` avec le **même** `operation_id='IT26_PAR_ORDER'`, le même client et la même ligne. Session A maintient sa transaction 5 secondes.
- Les deux réponses : **même `commande_vente_id='CDV-0002'`**, état `EN_ATTENTE`, une ligne.
- Audit post-commit : **1 commande, 1 ligne, 1 journal d'opération**.
- Appel supplémentaire avec même operation_id mais quantité différente : **refus 23505** (`operation_id réutilisé avec données différentes`).
- Nettoyage ciblé `20261105_concurrence_commande_NETTOYAGE_TEST.sql` : exécuté ; contrôle SQL final : **0** ligne restante des fixtures.

### 2. Finance : référence bancaire simultanée
- Préparation sur TEST : client fictif, compte Banque et compte Tiers client portant le préfixe `IT26_PAR`.
- Sessions A et B : appels **parallèles** à `erp_finance_transaction('PAYMENT',...)` avec deux operation_id différents mais le **même compte bancaire et la même référence `IT26_PAR_FINREF`** ; montant fictif 50 DZD ; la session A conserve le verrou pendant 5 secondes.
- Session A : **succès**, création d'un règlement et de deux écritures équilibrées.
- Session B : **rejet PostgreSQL 23505** (`Référence de règlement déjà enregistrée sur ce compte`).
- Audit post-commit : **1 paiement, 2 écritures, 1 opération enregistrée**.
- Nettoyage ciblé `20261105_concurrence_finance_NETTOYAGE_TEST.sql` : exécuté ; contrôle SQL final : **0** compte, règlement, opération, écriture ou client portant les identifiants de concurrence.

## Isolation et limites
- Les tests concurrentiels ont nécessité des **fixtures TEMPORAIREMENT validées par COMMIT sur le projet TEST**, suivies de leur suppression ciblée (contrairement aux essais antérieurs à ROLLBACK intégral). L'absence de résidus a été vérifiée après les suppressions.
- Le GRANT UPDATE sur les trois référentiels de TEST est **conservé sur TEST** pour rapprocher son rôle technique des privilèges déjà présents en production. Aucune modification de droits de production.
- Ces essais montrent effectivement une protection contre les doublons de commande et les références bancaires concurrentes. Ils ne démontrent pas toutes les races possibles (réceptions d'achat simultanées, clôtures d'OF, sorties FIFO, lettrages simultanés), ni les délais réseau Streamlit, ni les jetons utilisateurs.
- Après essais, la production a été contrôlée en lecture seule : `DEMO26=80/80`, `SIM26=40/40`, quantité et facture de simulation cohérentes. **120 lignes fictives conservées et aucun rollback production exécuté.**

## Scripts versionnés sur GitHub
- `sql/test_isole/20261105_concurrence_commande_PREP_TEST.sql`
- `sql/test_isole/20261105_concurrence_commande_SESSION_A.sql`
- `sql/test_isole/20261105_concurrence_commande_SESSION_B.sql`
- `sql/test_isole/20261105_concurrence_commande_AUDIT.sql`
- `sql/test_isole/20261105_concurrence_commande_NETTOYAGE_TEST.sql`
- `sql/test_isole/20261105_concurrence_finance_PREP_TEST.sql`
- `sql/test_isole/20261105_concurrence_finance_SESSION_A.sql`
- `sql/test_isole/20261105_concurrence_finance_SESSION_B.sql`
- `sql/test_isole/20261105_concurrence_finance_AUDIT.sql`
- `sql/test_isole/20261105_concurrence_finance_NETTOYAGE_TEST.sql`

**Important :** ces scripts sont réservés au projet TEST ; ne jamais exécuter les scripts de préparation ou les appels concurrents sur la production.

## Suite recommandée
Contrôler la CI des scripts, tester deux réceptions simultanées d'une même commande d'achat et deux clôtures d'un même OF sur TEST, puis vérifier les flux via les sessions applicatives autorisées. Ne pas confondre preuves PostgreSQL et navigation authentifiée Streamlit.
