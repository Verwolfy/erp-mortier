# ERP-061 — Recette transversale multi-modules, cycle Achats → Finance

**Date : 23 novembre 2026**. Dépôt privé : `Verwolfy/erp-mortier`, branche `main`. Supabase principal : `wenydirqtmkywbxbxfal`. Projet Supabase TEST : `ffuhbmcfyexsbjwhryvj` laissé inactif. **Sans TinyFish**.

## Conditions et limites de la recette

Recette réalisée à l'aide des **vraies RPC PostgreSQL du principal**, mais uniquement à l'intérieur de `BEGIN ... DO ... ROLLBACK`, et de l'analyse du code/tests GitHub ; **aucun parcours visuel complet de l'interface Streamlit authentifiée n'a été exécuté dans cette session**. Les identifiants ERP ne permettent pas, sans navigateur authentifié connecté, d'attester les clics, affichages, impressions physiques et comportements de la version effectivement hébergée (issue #78). Aucune API bancaire, email fournisseur, fiscalité, paie, signature ou écriture métier persistante n'a été actionnée.

Objectif demandé : demande d'achat → validation → commande fournisseur et impression → suivi → réception → stock/PMP → facture fournisseur → paiement/lettrage, et étendre la revue à tous les modules.

## 1. Cycle Achats réellement exécuté en transaction annulée

Cas de recette synthétique : fournisseur actif `DEMO26_FOU1`, MP active `DEMO26_MP1` en **kg**, devise DZD/taux 1, 10 kg × 100 DZD = **1 000 DZD**, date souhaitée 15/12/2026.

| Étape | RPC / contrôle | Verdict |
|---|---|---|
| Demande d'achat avant BC | Pas de table/état ni circuit de validation dans le module Achats | **MANQUANT** |
| Émission commande en base | `erp_create_purchase_order` ; montant et statut `EN_ATTENTE` contrôlés | **PASS** |
| Rejeu après timeout | Même `operation_id`, autre proposition de numéro documentaire | **PASS : pas de double BC** |
| Stock avant livraison | Aucune entrée à la simple création du BC | **PASS** |
| Réception partielle 4 kg | `erp_receive_purchase_order` / conformité OUI, état `PARTIELLEMENT_RECEPTIONNE` | **PASS** |
| Réception finale 6 kg | Même RPC, état `RECEPTIONNE` | **PASS** |
| Effet Stock | 2 mouvements MP et 2 liens réels de lots aux lignes BR | **PASS** |
| Valorisation PMP | Quantité +10, PMP recalculé selon quantité initiale et coût d'achat historique en DZD | **PASS** |
| Réception supplémentaire | Tentative de +1 kg après 10/10 reçu | **PASS : refusée** |
| Annulation du test | `ROLLBACK` ; 0 BC/BR/operation E2E persistés, stock MP initial restauré à 1 000 kg | **PASS** |

Deux premières exécutions ont échoué sur des **assertions erronées du script de recette** : champ `reference_document` inexistant puis recherche d'une référence exacte au lieu de `BR <BR-id> (Cmd <BC-id>)`. Elles n'ont rien persisté. La troisième exécution avec `mouvements.reference LIKE 'BR E2E61-BR%'` a réussi.

## 2. Impression d'une commande fournisseur

`modules/documents/erp_print.py` possède la catégorie `Commande fournisseur`, lit l'en-tête, les lignes et le fournisseur via lecteur RBAC, restitue les quantités/prix enregistrés puis génère un PDF corporate NEXTGEN (en-tête/pied). Test ajouté dans `tests/test_erp054_operation_print.py` : bon de commande fournisseur synthétique 10 kg × 100 DZD, total 1 000 DZD, PDF réel généré et signature `%PDF` vérifiée.

**Limite** : le PDF porte `COPIE DE CONSULTATION - NON SIGNÉE / NON ÉMISE`. Ce n'est **pas un bon de commande juridiquement émis**, ni une preuve de transmission au fournisseur. Émission signée, numéro de version, registre de transmission et approbation restent à réaliser (issue #86).

## 3. Finance et paiement fournisseur

**Blocages initiaux observés sur principal**
- Les 3 comptes `comptes` existants ont `statut='ACTIF'` ; l'écran Finance et la RPC nécessitent `statut='OUI'`. Aucun compte tiers fournisseur actif n'existe. Le paiement réel est donc inopérable sans configuration légitime.
- Les 2 factures fournisseurs enregistrées portent `statut_paiement='BROUILLON'`. Leurs pièces ne sont pas homologuées et leur validation manque dans les flux UI.
- **Bogue bloquant confirmé** : `erp_finance_transaction('ALLOCATE')` lève `42703 record "v_invoice" has no field "montant_paye"` lors du lettrage fournisseur. Cause : expression conjointe qui référence un champ de facture client sur un `record` fournisseur.

**Test de correction dans une transaction annulée**
- `CREATE OR REPLACE FUNCTION` de la RPC **uniquement à l'intérieur de `BEGIN...ROLLBACK`** : isoler la branche `FactureClient` et admettre uniquement `NON_PAYEE`/`PARTIELLE` comme états fournisseurs payables.
- Création temporaire par RPC de 2 comptes Banque + Tiers fournisseur (tous deux sans coordonnées bancaires réelles), et d'une facture fournisseur de test par SQL (car absence de workflow de saisie/validation).
- `PAYMENT` de **1 000 DZD** : 2 écritures équilibrées débit/credit = 1 000, dans la transaction seulement.
- `ALLOCATE` d'une facture `BROUILLON` : **refusé** par le correctif en simulation.
- Même facture temporaire au statut `NON_PAYEE` : lettrage **réussi**, statut `PAYEE`, `montant_alloue=1000`.
- `ROLLBACK` : **0** compte, facture, règlement, lettrage ou écriture de test conservé.

**Code préparé et commité** :
- `sql/006_atomic_finance.sql` : correctif pour futurs environnements.
- `sql/ERP_061_PREPARATION_lettrage_fournisseur_20261123.sql` : migration ciblée testée en `ROLLBACK`, **PAS APPLIQUÉE** à la RPC Finance principale. Une revue et approbation métier/financière sont requises avant DDL en production.
- `modules/finance/views.py` : ne propose plus les factures fournisseurs `BROUILLON` à l'affectation.
- Tests `tests/test_erp061_finance_purchase_regressions.py`, `tests/test_finance_views_security.py`, `tests/test_finance_security_006.py`.

Suivi bloquant : [#85](https://github.com/Verwolfy/erp-mortier/issues/85).

## 4. Autres modules, contrôles réels SQL et portée de validation

| Module | Vérification | Résultat / limite |
|---|---|---|
| **Production** | `erp_create_manufacturing_order` → `erp_start_manufacturing_order` → CQ/clôture, en `ROLLBACK` | Création, démarrage et contrôle qualité **PASS** ; scénario rejeté terminable sans mouvement. Un OF réellement conforme avec emballage/lots adaptés **non homologué** : SKU DEMO sans `emballage_mp_id`, SKU PROOF emballage stock 0 |
| **Ventes** | `erp_create_sales_order` / idempotence puis `erp_sale_transaction('SHIP')` | Commande **PASS** ; livraison **refusée correctement** faute de lot FIFO `ACTIF`; 0 BL ou opération persistée |
| **Stocks** | Contrôle stock MP/PMP/lots sur réception, 115 lignes MP, 146 PF | Transactionnel **PASS** ; inventaires ERP-056/057 existants en code/base, pas de campagne réelle créée |
| **CRM** | 5 opportunités pipeline, 4 interactions ; fonctions, droits et tests du dépôt | **Lecture et couverture tests**, pas de mutation UI authentifiée |
| **RH** | 14 employés, 5 congés ; droits Paie séparés | **Lecture et couverture tests**, pas d'essai paie/salaire fictif |
| **Administration** | 5 pistes d'audit ; rôle serveur et ACL des RPC | **Lecture / contrôle d'accès**, aucun utilisateur ni permission modifiés |
| **Dashboards** | Présence et tests des agrégats, lecture seule | **Couverture code/tests**, pas de comparaison graphique de l'instance hébergée ; attention à l'inclusion des références DEMO |
| **Documents** | Générateur de copies PO/BR/OF/BL/factures (factures fiscales non émises) | **Test PDF code** ; impression physique/envoi email non effectués |
| **Finance** | Paiement/lettrage | **BLOCAGE production**, correctif fonctionnel prouvé en transaction annulée, déploiement SQL suspendu |

## 5. Audit relationnel et des permissions en base

- **6 vérifications relationnelles : 0 anomalie** : lignes achats orphelines, réception sans commande, lignes BR orphelines, BL sans commande, OF sans recette, écritures de règlements `REGF-` déséquilibrées.
- **5 RPC critiques** (BC, BR, Finance, Ventes, OF) : `anon EXECUTE=false`, `authenticated EXECUTE=false`, `service_role EXECUTE=true`.
- Dépôt : tests Python complets via GitHub Actions ; vérifier conclusion du **dernier SHA de main** après mise à jour documentaire.
- Persistance : `0` opération portant le préfixe `E2E61` dans achats, finance, production, ventes ; 0 comptes temporaires/commandes/règlements. Aucun transfert d'argent, aucune facturation fiscale.

## 6. Risques et priorités opérationnelles

1. **P0** — Clôturer [#85](https://github.com/Verwolfy/erp-mortier/issues/85) : approbation de la migration fournisseur, revue financière et déploiement contrôlé. Ne jamais convertir les comptes DEMO `ACTIF` en `OUI` sans validation.
2. **P0/P1** — [#86](https://github.com/Verwolfy/erp-mortier/issues/86) : implémenter demande d'achat avec approbation, émission contrôlée du BC, réception CQ, saisie et rapprochement 3 voies de la facture fournisseur, validation, échéance et paiement.
3. **P1** — Vérifier version Streamlit réellement déployée (issue [#78](https://github.com/Verwolfy/erp-mortier/issues/78)) : le code CI ne prouve pas le navigateur. Test visuel complet avec comptes humains habilités (Achats, Magasin, Finance, Production, Ventes, RH, Administration).
4. **P1** — Revoir les produits DEMO, emballages et lots FIFO ; ne pas fabriquer de ventes ni productions conformes.
5. **P1** — Générer un dossier de recette E2E avec pièces signées réelles sur un environnement TEST isolé ; ce projet est actuellement **inactif** et n'a pas été réveillé.

### Principes préservés
Aucune migration Finance appliquée, aucune commande fournisseur persistée, aucune réception permanente, aucun débit de stock et aucun paiement réel. Ni TinyFish ni navigateur distant n'ont été employés. Les données de test sont confinées à des transactions SQL explicitement annulées.
