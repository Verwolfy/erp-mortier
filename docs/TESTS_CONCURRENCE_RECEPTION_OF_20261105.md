# Campagne de concurrence réelle — réception et clôture OF

**Date :** 5 novembre 2026  
**Projet isolé uniquement :** `erp-mortier-test` — `ffuhbmcfyexsbjwhryvj`  
**Production :** `wenydirqtmkywbxbxfal` — lecture seule pendant cette campagne.

## Résultat 1 — Deux réceptions simultanées

La fixture de test crée une commande d'achat de **10 kg**. Deux connexions PostgreSQL distinctes lancent en parallèle la RPC réelle `erp_receive_purchase_order`, chacune demandant **7 kg**, et la session A garde son verrou transactionnel pendant 5 secondes.

- Session A : succès, commande `PARTIELLEMENT_RECEPTIONNE`.
- Session B : rejet SQLSTATE **23514**, quantité supérieure au commandé (7 + 7 > 10).
- Audit avant nettoyage : **1 réception**, **7 kg reçus**, **7 kg en stock**, **1 journal d'opération**.
- Nettoyage SQL ciblé exécuté avec `COMMIT`, puis contrôle : commande, matière, réception, journal et mouvements **à zéro**.

**Scripts :** `sql/test_isole/20261105_concurrence_reception_{PREP,SESSION_A,SESSION_B,AUDIT,NETTOYAGE}.sql`.

## Résultat 2 — Deux clôtures simultanées du même OF

La fixture de test crée deux références MP (matière et emballage), un produit, un SKU et sa recette. Les RPC stock créent **10 kg MP** et **5 emballages** ; l'OF de 2 unités est démarré avant le test concurrent.

Deux sessions PostgreSQL appellent **simultanément** `erp_close_manufacturing_order` avec le **même OF et les mêmes paramètres**, la session A gardant le verrou 5 secondes.

- Deux réponses identiques : `OF-0002`, statut `TERMINE`, **2 unités fabriquées**, coût simulé 12 DZD.
- Audit après commit : **1 clôture**, **1 contrôle qualité**, **2 lignes de consommation**, MP restante **8 kg**, emballages restants **3**, PF produit **2 unités**.
- Clôture contradictoire `conforme=NON` après clôture acceptée : refus SQLSTATE **23505** (`OF déjà clôturé avec paramètres différents`).
- Nettoyage SQL ciblé effectué ; **0 résidu** pour produits, MP, SKU, OF, lots, journaux et opérations de stock vérifiés.

**Scripts :** `sql/test_isole/20261105_concurrence_of_{PREP,SESSION_A,SESSION_B,AUDIT,NETTOYAGE}.sql`.

## FIFO et autres tests antérieurs

Le test SQL `FIFO_TEST_OK` a validé dans une transaction `BEGIN/ROLLBACK` le FIFO sur deux lots (4 kg anciens, 7 kg récents, sortie 6 kg → ancien 0, récent 5), l'idempotence et le refus d'une surconsommation. **Il ne simule pas deux sorties FIFO simultanées**.

Des essais de concurrence précédents avaient confirmé le même `operation_id` sur deux commandes clients (une commande créée), et deux références bancaires identiques avec des `operation_id` distincts (un seul paiement accepté).

## Intégrité et limites

- **TEST :** toutes les fixtures de cette campagne ont été supprimées par les scripts de nettoyage, après vérification des identifiants. Les `GRANT UPDATE` additionnels sur les tables référentielles TEST restent en place, et reproduisent les droits déjà présents en production ; ils n'ont pas été appliqués à la production.
- **PRODUCTION :** contrôle SQL lecture seule final `DEMO26 80/80`, `SIM26 40/40`, quantités MP/PF équilibrées, facture simulée et paiement 2 380 DZD cohérents. Aucune opération d'écriture en production.
- **Limites restantes :** véritables appels API et UI Streamlit authentifiés non testés ; concurrence de deux sorties FIFO, lettrages simultanés, timeout réseau réel, RLS/permissions d'utilisateur final non testés.
- **Garde-fous de CI :** `tests/test_isolated_receipt_concurrency_contract.py` et `tests/test_isolated_of_concurrency_contract.py`. Vérifier les workflows du dernier commit avant de conclure à CI verte.
- **Rollback des données de démonstration PROD :** `sql/demo/20261105_rollback_TOTAL_120_lignes_FICTIVES.sql` toujours non exécuté, à conserver.

## Suite

1. Vérifier CI GitHub après les nouveaux scripts et tests.
2. Vérifier `erp-mortier-test` remis à `INACTIVE` après mise en pause.
3. Prioriser les essais d'interface avec compte autorisé sur base TEST, puis concurrence FIFO et lettrages depuis deux sessions.
4. Continuer à conserver les 120 lignes fictives de production jusqu'à la fin des simulations.
