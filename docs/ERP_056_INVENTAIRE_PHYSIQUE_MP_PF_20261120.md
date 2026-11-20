# ERP-056 — Module Inventaire physique MP/PF (20 novembre 2026)

## Objectif et périmètre livré
Le module Stocks possède désormais une cinquième vue `📋 Inventaire & Régularisation`, dédiée au **constat physique** des stocks MP, emballages et PF (SKU) sans contaminer les lots, coûts moyens pondérés (PMP), factures ou écritures SCF.

**Parcours implémenté :**
1. Création d'une campagne `INV-...` avec périmètre `MP`, `PF` ou `TOUS`, libellé, auteur et photographie datée du stock courant.
2. Lignes de comptage initialement vides, chacune avec quantité théorique/PMP **figés** ; aucune quantité physique n'est présumée.
3. Saisie ou correction des quantités physiques par article, zéro autorisé, motif d'écart exigé par l'interface. Auteur et date de comptage conservés en base.
4. Affichage des écarts quantitatifs, valorisation au **PMP du snapshot** si renseigné, décompte des écarts sans PMP ; jamais de coût inventé.
5. Soumission bloquée tant que **toutes** les références n'ont pas été comptées. Campagne figée ensuite.
6. Approbation réservée à un administrateur actif distinct du créateur **et** du soumetteur, avec justification obligatoire de 10 caractères minimum. Avant approbation, la base compare les quantités et PMP courants aux snapshots de toutes les lignes, et refuse aussi une augmentation/suppression des références.
7. Résultat approuvé `SANS_ECART` ou `ECARTS_A_QUALIFIER`. **Aucune correction de stock n'est exécutée** par cette validation.
8. Export des lignes **XLSX, CSV et PDF** via `core/export_formats.py` (charte NEXTGEN, copie interne non certifiée SCF).

**Limites expressément conservées :** aucune régularisation automatique, aucun inventaire signé SCF, aucun import Excel massif, aucun comptage par lot/dépôt, aucun mouvement `PERTE`/`RETOUR_CLIENT` ; leur traitement exige un circuit métier séparé de contrôle qualité, de motifs et de valorisation sécurisée. Ne jamais transformer un écart théorique en coût, entrée ou sortie fictif.

## Base Supabase principal — réellement appliqué
Projet : `wenydirqtmkywbxbxfal`.
Migrations additive et serveur seulement :
- `sql/ERP_056_inventaire_physique_campagne_20261120.sql` : création des tables `public.erp_inventaires` et `public.erp_inventaire_lignes`, index, contraintes, RLS et fonctions `erp_inventory_permission`, `erp_inventory_create`, `erp_inventory_count`, `erp_inventory_submit`, `erp_inventory_approve`.
- `sql/ERP_056b_inventaire_derives_referentiel_20261120.sql` : refus d'approuver si de nouveaux articles ont été ajoutés au stock entre photographie et approbation.

RLS activée sur les 2 tables. `anon` et `authenticated` n'ont **aucun accès SELECT direct**, ni exécution de RPC. Le `service_role` du serveur ERP peut accéder aux tables et RPC ; chaque RPC revérifie en **base** l'acteur ERP actif, son droit Stocks en écriture et, pour approbation, son rôle ADMIN et sa séparation de tâches. Cette séparation est essentielle puisque la clé service_role bypass RLS.

**Vérification exécutée :** transaction SQL avec `ROLLBACK` sur le principal : campagne `MP`, 115 lignes, création rejouée (idempotence), 115 comptages, soumission, refus de modifier une campagne soumise, refus d'auto-approbation. Après annulation : **0 campagne conservée**, aucun changement de stock. Les contrôles des permissions de fonction montrent `anon`/ `authenticated` sans droit `EXECUTE`, `service_role` habilité.

Le conseiller sécurité Supabase relève `rls_enabled_no_policy` : pour ces deux tables, ce comportement est **volontaire**, car aucune lecture ou écriture directe via les rôles exposés n'est autorisée. Consulter la sécurité globale du projet séparément ; ne pas ajouter une policy `USING(true)` par commodité.

**Précondition pour validation réelle :** un seul compte ERP actif (rôle ADMIN) observé au 20/11/2026 ; la double validation exige au moins un autre compte actif habilité. **Aucun compte supplémentaire n'a été créé.**

## Code et tests
- `modules/stocks/inventory_service.py` : vérification fraîche compte + droits ERP ; pagination déterministe et fail-closed, appels RPC ; refus du résultat de RPC inattendu, reprise via même référence après timeout.
- `modules/stocks/inventory_views.py` : création, sélection, saisie comptage, soumission, approbation indépendante, états et téléchargements.
- `modules/stocks/views.py` : nouveau panneau, chargé à la demande sans impacts sur les autres vues.
- `tests/test_erp056_inventory.py` : validation des quantités, rôles et session, calcul des écarts, garde-fou SQL, absence de preuve RPC après timeout.
- `tests/test_lot06_stocks_lazy.py` : menu Stocks désormais à cinq panneaux.

## Contrôles en attente / poursuite
1. Vérifier les conclusions du **dernier** commit `main` dans les deux workflows GitHub (suite complète et audit). Ne pas prétendre CI verte si des tests échouent.
2. Effectuer un test réel de navigation Streamlit authentifié après synchronisation du code hébergé. L'issue [#78](https://github.com/Verwolfy/erp-mortier/issues/78) signale un historique de version déployée incohérente.
3. Ajouter un second compte réel actif avec droits adaptés, **après validation des personnes et des délégations** ; ne pas créer une identité fictive d'approbateur.
4. Phase 2 : comptage par emplacement et lot, import Excel contrôlé, motifs `PERTE`/`RETOUR_CLIENT`, circuit d'ajustement stock atomique avec coûts justifiés, CQ et audit, sans écriture comptable automatique.
5. Ne pas activer des coûts fiscaux/SCF hors preuves validées. Ticket transversal [#80](https://github.com/Verwolfy/erp-mortier/issues/80).

## Précautions
- Supabase TEST `ffuhbmcfyexsbjwhryvj` était inactif et n'a pas été réveillé.
- Aucun inventaire réel, faux comptage, stock, mouvement, lot, recette, facture, règlement ou écritures SCF créé lors du développement.
- Un inventaire approuvé qui révèle un écart n'autorise pas automatiquement sa régularisation : il devient `ECARTS_A_QUALIFIER`.
