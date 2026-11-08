# GOV-01 — Contrats de transitions métier observés (lot P0 initial)

Date : 2026-11-08. Référence : dépôt `Verwolfy/erp-mortier`, `main` avant cette PR au commit `218fbb80fa05294d3ce5331632e4dac4b096edda`.

**Portée : contrats de non-régression fondés sur les services Python et RPC SQL versionnées.** Les tests `tests/test_workflow_contracts_p0.py` vérifient l'existence des gardes dans les fichiers, mais **n'exécutent pas les transitions en base**. Le rôle de la future base TEST isolée est de prouver les effets et les rejets réels.

**Ne constitue pas une preuve de déploiement** ou d'activation de toutes les migrations en **PostgreSQL production**. L'audit statique ne remplace ni les tests transactionnels, ni la revue fonctionnelle des exceptions.

## A. Transitions et invariants prouvés dans les sources versionnées

| Contrat | Départ → arrivée | Entrée / auteur | Préconditions observées | Effets prévus et preuve fichier | Échec attendu |
|---|---|---|---|---|---|
| `ACH-ORDER` | Aucune commande → `EN_ATTENTE` | `modules/achats/service.py:create_commande_achat` ; contrôle `commandes_achats` | Fournisseur existant, lignes valides, montant recalculé, `operation_id` contrôlé | Commande et lignes dans `sql/004_atomic_purchases.sql:erp_create_purchase_order`, journal de résultat `erp_purchase_operations` | Ligne, fournisseur ou `operation_id` discordants : refus transactionnel |
| `ACH-RECEIVE` | `EN_ATTENTE` / `PARTIELLEMENT_RECEPTIONNE` → `PARTIELLEMENT_RECEPTIONNE` / `RECEPTIONNE` | `creer_bon_reception` ; droits Achats et Stocks | Conformité `OUI`, verrou `FOR UPDATE`, quantités cumulées non supérieures à commandées | BR, lots MP, mouvement stock et statut achat via `sql/004_atomic_purchases.sql:erp_receive_purchase_order` | Statut terminal, non-conformité ou sur-réception : refus avant stock |
| `STK-OUT` | Stock MP/PF disponible → stock décrémenté et lots alloués | `modules/stocks/service.py:enregistrer_sortie_*` | Stock global suffisant, coût défini, lots FIFO actifs, verrous | Mouvements, lots et quantités dans `sql/002_atomic_stock_movement.sql` | Stock insuffisant / incohérence lots : exception et annulation |
| `FAB-START` | `PLANIFIE` → `EN_COURS` (appel répété `EN_COURS` admis) | `modules/production/service.py:changer_statut_of` | OF existant, état `PLANIFIE` pour mutation initiale | `sql/003_atomic_manufacturing_close.sql:erp_start_manufacturing_order` | Un OF `TERMINE` / `REJETE` n'est pas réouvert |
| `FAB-CLOSE` | `PLANIFIE` / `EN_COURS` → `TERMINE` ou `REJETE` | `enregistrer_controle_qualite` | Recette active, SKU compatible, quantité, lot consommable ; conformité contrôlée | Consommations lots MP, entrée PF si conforme, clôture `erp_of_closures`, statut `sql/003_atomic_manufacturing_close.sql:erp_close_manufacturing_order` | OF déjà clos / recette incompatible / matière insuffisante : refus ; la clôture directement depuis `PLANIFIE` est **autorisée dans le SQL actuel** et doit être revue fonctionnellement |
| `VEN-DRAFT` | Aucune facture → `BROUILLON` | `modules/ventes/service.py:create_facture_brouillon` | Client, lignes, montants, origine d'avoir si applicable, compteur légal | `sql/005_atomic_sales.sql:erp_sale_transaction`, action `DRAFT` ; aucune sortie physique | Dossier exonération/historique nécessitant contrôle, montant incohérent : refus |
| `VEN-VALIDATE` | `BROUILLON` → `VALIDE` | `valider_facture`, action `VALIDATE` | Facture `BROUILLON`, pas de paiement, lignes, avoir contrôlé | `sql/005_atomic_sales.sql` ; statut commercial `VALIDE` | Facture déjà `VALIDE` ou `ANNULE` : refus |
| `VEN-CANCEL` | `BROUILLON` → `ANNULE` | `annuler_facture`, action `CANCEL` | Facture brouillon sans paiement | `sql/005_atomic_sales.sql` ; aucune entrée en stock automatique | Facture validée ou avec règlement : refus |
| `VEN-SHIP` | Commande expédiable → bon de livraison `EXPEDIE` | `creer_bon_livraison`, action `SHIP`, droits Ventes+Stocks | Commande statut accepté, cumul livré ≤ commandé, quantité SKU entière, lot FIFO disponible | `sql/005_atomic_sales.sql` ; BL et lignes de lots, sorties PF | Commande non expédiable ou dépassement : refus ; statut de commande après BL à réexaminer |
| `FIN-ALLOCATE` | Règlement `VALIDE` + facture payable → lettrage | `modules/finance/service.py:enregistrer_lettrage`, action `ALLOCATE` | Partenaire / sens cohérents, facture admissible, solde suffisant, verrou | `sql/006_atomic_finance.sql` ; écritures `lettrage`, solde alloué, `montant_paye` client ou statut paiement fournisseur | Double lettrage / sur-allocation / règlement non valide : refus |

**Note Finance :** le statut commercial des factures clients demeure `VALIDE` même après lettrage ; le montant `montant_paye` change. Ne pas imposer un état commercial `PAYEE` au hasard. Les factures fournisseurs utilisent leur statut de paiement.

## B. Gaps et arbitrages métier restant à traiter

- `ACH-01` : aucune politique de seuil d'approbation des commandes d'achats n'est prouvée par ces RPC ; proposer avant toute implémentation un circuit demandeur ≠ approbateur uniquement si validé métier.
- `FAB-START/CLOSE` : le code actuel autorise directement la clôture d'un OF `PLANIFIE`. Documenter l'exception et arbitrer une éventuelle obligation de démarrage.
- `VEN-SHIP` : réconcilier états commande/BL/livraisons cumulées. Ne pas inventer de transition commande tant que le SQL n'en fait pas la preuve.
- `SEC-01` : les permissions sont contrôlées par les services ; un audit de la protection SQL et des droits sur chaque document reste obligatoire dans l'environnement isolé.
- `TX-01` : la présence d'une clé d'opération et d'un verrou n'est pas un test de concurrence réel. Produire les scénarios double clic, RPC répétée, timeout, rollback et surcharge.
- `ENV-01` : connecter ultérieurement une base Supabase TEST séparée ; aucune écriture de test en production.
- `FIN-01` : verrouillage de période comptable et corrections/contrepassations restent à qualifier ; pas de certification SCF implicite.

## C. Tests et critères de réception du lot

- Ce lot ajoute un **contrat de garde statique** par flux principal et exige que les entrées services restent présentes ; toute suppression de garde citée casse la CI.
- La cible finale de `GOV-01` (**au moins un scénario accepté et refusé pour chaque transition**, zéro effet en cas de rejet, source/acteur audités) n'est **pas encore atteinte** : elle dépend de `ENV-01` et de véritables tests RPC sur base de test.
- Aucun changement de schéma ou de permission dans PostgreSQL production, aucun jeu `DEMO/SIM` supprimé.
- **La migration d'unicité PostgreSQL Clients/Fournisseurs demeure GELÉE**, conformément à la demande.
