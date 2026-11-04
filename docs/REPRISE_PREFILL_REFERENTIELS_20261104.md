# Reprise NEXTGEN — Préremplissage documentaire depuis les référentiels — 4 novembre 2026

## Résultat du lot
- Branche GitHub : `Verwolfy/erp-mortier/main`. Supabase production : `wenydirqtmkywbxbxfal`, ACTIVE_HEALTHY. TEST `ffuhbmcfyexsbjwhryvj` conservé INACTIVE ; aucune modification.
- Analyse du schéma réel Supabase : référentiels existants `clients`, `fournisseurs`, `sku_conditionnement`, `produits`, `matieres_premieres`. Lecture SQL agrégée : **7 clients, 6 fournisseurs, 149 SKU, 56 produits, 120 matières premières** (totaux, pas forcément tous actifs).
- `modules/documents/prefill.py` introduit les listes filtrées d'entités actives :
  - Clients pour Devis/BC client/Facture/Avoir/BL ; fournisseurs pour Demande d'achat/BC fournisseur/BR/contrôle facture fournisseur.
  - SKU liés aux produits actifs pour les documents Ventes ; le prix catalogue est **informatif uniquement**, quantité et prix non préremplis.
  - Matières premières actives pour Bons de consommation/sortie/transfert/inventaire et documents de production ; aucun stock, lot, quantité ni prix modifié ou calculé.
- Lecture via `core.db_service.fetch_data_paginated` : contrôles de session et de droits RBAC serveur frais, pagination bornée 2000 références, aucune écriture.
- `modules/documents/views.py` : sélecteurs dans un panneau facultatif « Préremplir depuis les référentiels (lecture seule) », chargement explicite pour éviter appels sur chaque rerun, copie du tiers / ajout d'une ligne. Les inputs éditables et le QR restent inchangés. Le refus des lectures sans droits n'est pas contourné.
- `tests/test_documents_nextgen.py` : lecteurs simulés pour vérifier filtrage actif, mapping, non-mutation du brouillon initial, absence de prix imposé, compatibilité PDF/DOCX, plafond 200 lignes.
- `modules/help/views.py` : guide d'utilisation actualisé.
- Commits principaux : `e6ed8c5`, `56efb67`, `eb914e6`, `56c4040`, `456ee7b`, `a9bb1b4`, `a5609aa`.
- SQL de vérification seulement : aucun INSERT/UPDATE/DELETE, aucune migration, aucun changement GRANT/RLS, aucun secret.

## Non encore vérifié
- Le chemin complet des sélecteurs dans Streamlit authentifié et le rendu du PDF après préremplissage.
- Les permissions effectives de chaque profil autre que l'ADMIN (lecture interdite doit afficher une indisponibilité, pas le contenu).
- Le suivi QR centralisé et l'émission réglementaire (aucune des deux fonctions n'est implémentée).

## Prochaines actions
1. Vérifier verdict des workflows GitHub du dernier commit (test & audit) puis corriger toute erreur.
2. Sur Streamlit : Administration → Documents NEXTGEN → Charger les référentiels autorisés. Test Devis avec client et SKU, Bon de consommation avec matière ; vérifier édition, HT et exports.
3. Étudier un registre QR dans Supabase : schéma, permissions RLS et durée de conservation. **Ne pas déployer de nouvelles politiques RLS sans autorisation explicite.**
4. Tester pagination, longues désignations, aucun montant automatique hors documents financiers, et QR décodable.
5. Expertise comptable algérienne et validation juridique avant toute émission officielle.

## Contrôles de sécurité
- Ne pas exposer les contacts ou prix aux rôles non autorisés ; aucun service_role nouveau.
- Aucun taux fiscal inventé. Les montants HT dérivés de quantité × prix confirmé restent des brouillons.
- Les exports non officiels indiquent toujours « BROUILLON - NON VALABLE / NON EMIS ».
