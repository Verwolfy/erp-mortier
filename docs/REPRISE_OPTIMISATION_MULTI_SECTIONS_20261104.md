# Sofiane ERP / NEXTGEN — reprise des optimisations transverses — 2026-11-04

## État principal
- Dépôt `Verwolfy/erp-mortier`, branche `main` ; ERP Streamlit `https://nextgent-erp.streamlit.app/`.
- Production Supabase `wenydirqtmkywbxbxfal` ; base TEST `ffuhbmcfyexsbjwhryvj` inactive et non touchée.
- Documents NEXTGEN : 20 modèles PDF/Word/JSON, calcul HT en Decimal, QR et empreinte SHA256 locaux non certifiés, logo HD, import des brouillons JSON, préremplissage tiers/SKU/MP par lecture RBAC. Les documents sont **BROUILLON NON ÉMIS**.
- Registre QR `sql/033_document_trace_registry_PREPARATION.sql` préparé et non exécuté. Contient tables privées multiversion et événements immuables, RLS fermée. Aucune écriture Supabase réalisée.
- CI du précédent commit `6c0744078` : tests ERP et audit réconciliation **success**, runs `41899669463` et `41899669451`.

## Lot courant : audit qualité transversal
- `modules/admin/data_quality.py` ajouté : vérification à la demande en lecture seule des tables `clients`, `fournisseurs`, `produits`, `sku_conditionnement`, `matieres_premieres`.
- Contrôles : ID absents et doublons, nom/désignation absents, statut inactif compté séparément, SKU pointant vers produit manquant ; résultats **agrégés** sans PII.
- Lecteur `core.db_service.fetch_data_paginated` réutilisé, permissions RBAC réévaluées à chaque table, max 5000 lignes/table, aucune restitution partielle en cas d'erreur de lecture.
- `modules/admin/views.py` : onglet **Qualité référentiels**, bouton **Analyser les référentiels autorisés**. Aucune correction automatique.
- `tests/test_admin_data_quality.py` : contrôles doublons, manque, association SKU, refus RBAC et absence d'écriture ; `modules/help/views.py` actualisé.
- Commits du lot : `390dc1734`, `d21b4d7f7`, `e338d3b28`, `be83b31d2`.
- CI du dernier code/doc en cours au moment du présent rapport : consulter Actions `main` et ne pas considérer validé avant résultat.

## Blocage réglementaire découvert
- Dans `modules/ventes/service.py`, constantes `TAUX_TVA = Decimal("0.19")`, `TAUX_TIMBRE = Decimal("0.01")`, `MAX_TIMBRE = Decimal("2500.00")` subsistent. **Ne pas modifier ni appliquer ces règles en production sans revue de leurs usages, paramètres à date d'effet et validation réglementaire algérienne.**
- Conserver les verrous fiscaux existants et l'absence d'émission officielle non homologuée ; signaler au user comme point critique.
- Validation d'un expert-comptable algérien reste nécessaire avant toute production réglementaire.

## Suites concrètes
1. Contrôler les workflows GitHub du dernier commit et corriger les éventuels vrais échecs.
2. Vérifier l'affichage dans Administration > Qualité référentiels avec un compte habilité. Contrôler des rapports sans PII et refuser toute consultation sans les droits.
3. Ajouter d'autres contrôles non destructifs si besoin : Stocks (cohérence lot/stock), Achats (liens fournisseurs), Ventes (liaisons commande/client), Production (recettes/OF), sans contourner RLS et sans inventer d'anomalies.
4. Étudier le retrait des constantes fiscales codées en dur **après** audit de l'interface réglementaire paramétrée et des dépendances, sans changer de taux.
5. Registre QR 033 : conception du RPC transactionnel et des ACL, tests SQL isolés et approbation pour toute opération RLS/GRANT/DDL sur production.


## Lot complémentaire — intégrité des liens métier
- `modules/admin/data_quality.py` : `audit_operations` + `audit_operations_autorise`, lectures bornées via RBAC serveur, contrôle des liaisons :
  - `commandes_ventes.client_id` vers `clients.client_id` ;
  - `commandes_achats.fournisseur_id` vers `fournisseurs.fournisseur_id` ;
  - `ordres_fabrication.pf_id` vers `produits.pf_id`.
- `modules/admin/views.py` : deuxième bouton **Analyser les liens métier autorisés**, tableau de comptages et message d'alerte sans donnée individuelle.
- `tests/test_admin_data_quality.py` : cas lien manquant/introuvable, absence d'informations personnelles, échec fail-closed sur refus RBAC.
- `modules/help/views.py` mis à jour.
- Commits : `19e6864`, `4de480d`, `ad8cdcc`, `2a737cb`.
- Tests GitHub du dernier commit documentaire à confirmer, voir GitHub Actions `main`.
- Pas de SQL exécuté, pas de mouvement de stock, pas d'écriture Ventes, Achats ou Production.
