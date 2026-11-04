# Sofiane ERP — Reprise contrôles Achats/Ventes — 4 novembre 2026

## État
- GitHub : `Verwolfy/erp-mortier/main`, Streamlit `https://nextgent-erp.streamlit.app/`.
- Supabase PRODUCTION : `wenydirqtmkywbxbxfal` ; TEST `ffuhbmcfyexsbjwhryvj` en pause, non modifié.
- Base de travail : contrôles antérieurs de qualité des référentiels et stocks intégrés dans Administration > Qualité référentiels. Dernier lot Stocks `b8c5495` : CI tests et audit réussis.
- **Aucune écriture SQL ni action métier** réalisée dans le présent lot. Les documents restent des brouillons non émis et le registre QR 033 reste non appliqué.

## Lot appliqué à GitHub main
- Nouveau `modules/admin/sales_purchases_quality.py` : lecture paginée avec RBAC serveur, refus d'un rapport partiel si une table ne peut pas être lue. Contrôle des liens :
  - `lignes_commande_ventes` -> `commandes_ventes` et `sku_conditionnement`;
  - `lignes_bons_livraison` -> `bons_livraison` et `sku_conditionnement`;
  - `lignes_facture` -> `factures` et `sku_conditionnement`;
  - `lignes_achats` -> `commandes_achats` et `matieres_premieres`;
  - `lignes_bons_reception` -> `bons_reception` et `matieres_premieres`;
  - Entêtes `bons_livraison` -> `commandes_ventes`, `factures` -> `commandes_ventes`, `bons_reception` -> `commandes_achats`, `factures_fournisseurs` -> `commandes_achats` et `fournisseurs`.
- Quantités : nombres finis et strictement positifs dans les lignes. Les relations à une commande depuis les factures peuvent être facultatives, et ne doivent pas être classées à tort comme erreurs.
- Résultats **agrégés**, sans lignes ni PII. Aucune correction automatique, taxe ou remise recalculée.
- `modules/admin/views.py` : bouton **Analyser les flux Achats et Ventes autorisés**.
- `tests/test_admin_sales_purchases_quality.py` : cas de références orphelines, quantités incorrectes, refus RBAC et absence d'écriture.
- `modules/help/views.py` actualisé.
- Commits : `96b1da3`, `05dc383`, `8e65b38`, `1278b95`.

## À poursuivre
1. Vérifier les deux workflows CI du dernier commit et réparer les régressions.
2. Tester en session Streamlit habilitée l'onglet Qualité référentiels et les refus RBAC ; le déploiement visuel n'est pas attesté par GitHub Actions.
3. Auditer les remises/totaux Achats et Ventes en lecture seule, sans inventer ni appliquer de paramètres TVA. `modules/ventes/service.py` possède encore des constantes fiscales codées en dur : revue légale nécessaire avant tout changement.
4. Vérifier ensuite les flux Finance/RH, en privilégiant les anomalies mesurables sans modification des données.
5. Ne pas activer le registre QR 033 sur production avant validation des modèles de droits et essais isolés.

## Sécurité
- Aucun service_role ajouté ; tous les accès de données passent par `core.db_service.fetch_data_paginated` avec autorisation de lecture par table.
- Aucune modification Supabase, aucune écriture de stock, facture ou commande ; aucune émission réglementaire.
