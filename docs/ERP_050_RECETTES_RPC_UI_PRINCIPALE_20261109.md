# ERP-050 — Recette des parcours métiers (9 novembre 2026)

## Périmètre et limites
- Projet principal en phase essais : Supabase `erp-mortier` (`wenydirqtmkywbxbxfal`).
- Base TEST `ffuhbmcfyexsbjwhryvj` maintenue **INACTIVE**, jamais réactivée.
- GitHub : `Verwolfy/erp-mortier`, branche unique `main`.
- **Aucun accès à une session utilisateur Streamlit réelle**, aucun secret ou cookie demandé ou copié. Les scénarios interface sont des tests automatisés de vrai code Streamlit avec doublures de session et de base, PAS une validation navigateur de l'instance déployée.
- Tous les appels RPC expérimentaux effectués sur la principale dans `BEGIN ... ROLLBACK`, sous rôle SQL `service_role` sans changement de `GRANT` ni de RLS.
- Aucune donnée juridique, fiscale ou comptable fabriquée, aucune validation de SKU simulée en base.

## Résultats de l'interface et de la CI
- Tests Streamlit/UI existants : authentification et session `app.py`, Achats, Stocks, Production, Ventes, CRM, Finance, RH, Dashboards, administration, sécurité et autres modules, avec jeux de données fictifs, sans réseau de production.
- Nouveau `tests/test_erp050_ui_demo_reference_gates.py` : 5 tests directs en utilisant les fixtures d'interface existantes, filtrage des fournisseurs/matières DEMO inactifs, refus référentiel tronqué, refus de session utilisateur fictif inactif.
- CI du commit `02d7203116b8e3254a9ff9db2eac76a2c001ed31` : `ERP - tests lot C facturation`, exécution GitHub [#42649338058](https://github.com/Verwolfy/erp-mortier/actions/runs/42649338058), **3287 passed, 1 warning, 0 failed** ; audit [#42649338137](https://github.com/Verwolfy/erp-mortier/actions/runs/42649338137) **success**.
- Les commits ajoutés après ce résultat nécessitent une nouvelle lecture de leur CI respective ; ne pas extrapoler les tests précédents.

## Parcours RPC réellement exécutés sur la principale, sans COMMIT
| Parcours | Scénarios exercés | Résultat |
|---|---|---|
| Achats/réceptions/stock MP | Création commande, rejeu idempotent, réception 4 puis 6 unités, rejeu réception partielle, statut final RECEPTIONNE, stock MP=10 dans transaction | RÉUSSI, ROLLBACK |
| Production/qualité/stock PF | Stock MP+emballages fictifs, recette créée et rejouée, OF créé et rejoué, démarrage, clôture qualité, stock PF=2 | RÉUSSI, ROLLBACK |
| Ventes/commandes/BL | Stock PF initial=2, commande créée/rejouée, SHIP exécuté/rejoué, stock final 0 ; aucune facture temporaire | RÉUSSI, ROLLBACK |
| Finance | Deux comptes temporaires, PAYMENT VIREMENT fictif, rejeu idempotent ; 1 règlement et 1 opération pendant la transaction | RÉUSSI, ROLLBACK |
| Coûts industriels | Audit du lot SIM `SIM-ERP49-COST-P1` ; 12500 DZD simulés, OF non terminé ; validation refusée `23514` (« Imputation non rapprochée du débit SCF ») | REFUS ATTENDU |
| Fiscalité datée | `erp_tva_sku_readiness(2026-11-09)` : 143 `SANS_FICHE`, 2 `A_VALIDER`, 0 prêts ; `erp_tax_preview_classified` refuse un SKU actif sans fiche (`23514`) | REFUS ATTENDU |

## Tests de sécurité reproductibles
- `tests/sql/erp_050_principale_rpc_rejets_rollback.sql` exécuté depuis `main` sur Supabase principal : **8 refus attendus / 8**, SQLSTATE exacts : fiscal 23514, facture absente 23503, facture SKU inactif 23503, livraison SKU inactif 23503, production inactive 23503, stock insuffisant 23514, validation coût SCF 23514, règlement invalide 22023.
- Vérification des **16 fonctions RPC sensibles** : `anon` et `authenticated` sans droit `EXECUTE`, `service_role` avec droit `EXECUTE` : 16/16 conformes.
- `tests/sql/erp_050_principale_parcours_lecture.sql` : **10/10 vrais** (Achats, Coûts, CRM, Finance/SCF, Production, Projets, RH, Site, Stocks, Ventes).
- L'absence de droits pour `anon`/`authenticated` confirme l'accès privilégié SQL, pas l'authentification applicative réelle ni la preuve du SHA Streamlit déployé.
- Supabase Advisor sécurité : 1 catégorie informative `rls_enabled_no_policy` sur 93 tables, cohérente avec accès direct non accordé ; aucun changement de politiques effectué. [Documentation Supabase](https://supabase.com/docs/guides/database/database-linter?lint=0008_rls_enabled_no_policy).

## Deux défauts mis en évidence (ouverts, non masqués)
### BLOQUANT — facturation historique
- Une facture brouillon fictive avec SKU temporairement actif, sans aucune fiche `erp_sku_fiscalite`, a été **acceptée** par `erp_sale_transaction('DRAFT', ...)` au montant HT 100 / TVA 19 / TTC 119.
- `FAC-2026-000002` n'a existé **que dans la transaction de test**, suivie de `ROLLBACK`. Relecture : zéro trace.
- Le fait que la simulation TVA par SKU refuse les SKU non qualifiés ne protège pas la RPC historique.
- **Issue [#76](https://github.com/Verwolfy/erp-mortier/issues/76)** : exigence de précontrôle atomique côté serveur, qualification par SKU et date, preuves ERP-046, idempotence. **Facturation réglementaire non homologuée et non activable en l'état.**

### À durcir — Achats sur références inactives
- Les RPC `erp_create_purchase_order` et `erp_receive_purchase_order` acceptent sous `service_role` des données `SIM-ERP49-` dont les fournisseurs et MP ont `actif='NON'` ; **ROLLBACK**.
- L'écran Achats filtre actuellement ces références avant proposition, mais la RPC n'impose pas le même invariant.
- **Issue [#77](https://github.com/Verwolfy/erp-mortier/issues/77)** : définir la règle d'exception pour réception d'une commande historique, puis garde-fou serveur compatible.

## Audit de non-régression des données (avant/après RPC)
Les compteurs ont été relus après tous les ROLLBACK :
- 4 factures, 4 lignes facture, 3 règlements ; 0 écriture comptable héritée ;
- 1 pièce SCF et 2 lignes SCF historiques ; 12 mouvements MP, 6 mouvements PF ;
- 3 opérations Achat, 3 opérations Vente, 0 opération Finance persistante ;
- 145 SKU actifs, 0 `erp_sku_fiscalite.VALIDEE` ; 0 snapshot de coûts ;
- **0 ligne `SIM-ERP50-` persistante** sur clients, fournisseurs, produits, commandes achats/ventes, lots ; le numéro temporaire de facture est absent.

## État de validation
- **Réussi** : contrôles CI des tests simulés, rôle SQL, 10 domaines lecture, 8 refus métier, 4 parcours transactionnels avec idempotence et ROLLBACK, invariants sans mutation durable.
- **Non vérifié** : parcours dans le navigateur réellement authentifié à `nextgent-erp.streamlit.app`, SHA déployé, correspondance du code déployé, fonctionnement avec un utilisateur réel.
- **Bloqué** : facturation TVA par ligne à qualification réelle, réconciliation SCF effective, exceptions fiscales/timbre ; des justificatifs juridiques validés sont requis avant mise en service.
- **Décision** : ne pas certifier « tous les parcours E2E en production ». Préserver le moteur historique sans élargissement de droits ni bascule fiscale dangereuse. Les issues #76 et #77 définissent les prochains correctifs.

Une validation par un expert-comptable algérien est nécessaire avant toute production réglementaire réelle.
