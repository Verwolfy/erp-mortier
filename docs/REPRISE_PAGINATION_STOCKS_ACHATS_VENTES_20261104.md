# Sofiane ERP — Reprise pagination Stocks, Achats et Ventes (04/11/2026)

## Résultat publié sur main

Repo : `Verwolfy/erp-mortier` ; interface : https://nextgent-erp.streamlit.app/

- **Stocks** : `modules/stocks/views.py` ; clic « Afficher les mouvements de stock », numéro de page (1–1000), deux lectures `fetch_history_page_strict` sur `mouvements` et `mouvements_pf`, 50 lignes maximum par registre/page. Vrac et Emballages sont filtrés **sur la page MP chargée**, pas globalement ; les totaux affichés sont ceux des registres MP/PF.
- **Achats** : `modules/achats/views.py` ; clic « Afficher l'historique Achats » pour `commandes_achats` et `bons_reception`, 50 lignes maximum par registre/page, avec total exact de chaque registre. La réception métier conserve `get_commandes` complet pour son calcul.
- **Ventes** : `modules/ventes/views.py` ; profil lecture seule : factures chargées sur clic, 50/page via lecture stricte. Profil écriture : `get_factures` complet **conservé** pour création, validation et annulation, sans changement de calcul fiscal ni de contrôle d'état.
- **Sécurité** : `core/strict_reads.fetch_history_page_strict` (ajouté au lot précédent) valide droits RBAC serveur au clic, projection de colonnes, identifiants uniques, volume et exactitude de la page. Les mutations concurrentes entre deux pages restent possibles (offset sans snapshot).
- **Tests** : `tests/test_perf_histories_stocks_sales_purchases.py` vérifie les appels page/permissions implicites et maintien des workflows. Compteurs de callbacks dans `tests/test_010A_02D_02_stocks_activity.py`, `tests/test_010A_02D_02_achats_activity.py` et `tests/test_010A_02D_02_ventes_crm_activity.py` adaptés au nouveau bouton d'historique.
- Commits : `618be74`, `206a7fd`, `b75e0c7`, `7fdf474`, `1a8b06b`, `7b10c7c`, `a4e694a`.

## Sécurité et limites

Aucune écriture Supabase, aucun changement de schéma, de TVA ni de droits. Le SQL QR 033 reste non déployé. Projet PRODUCTION `wenydirqtmkywbxbxfal` ; projet TEST `ffuhbmcfyexsbjwhryvj` inactif. Pas de sauvegarde PostgreSQL demandée.

Les historiques ne sont plus visibles spontanément ; clic nécessaire. Les numéros de pages utilisent la clé primaire technique décroissante et non un tri strictement chronologique ; en présence de modifications concurrentes, la composition de page peut évoluer. Les indicateurs de stock global restent calculés par les fonctions existantes.

## Prochaines actions

1. Confirmer les workflows GitHub Actions du dernier commit (tests et audit réconciliation), corriger toute régression.
2. Vérifier visuellement Streamlit avec session habilitée et mode lecture seule, notamment pagination, refus RBAC et sélecteurs.
3. Étudier une pagination chronologique à clé composite sur index (date, ID), sans approximation ni troncature ; puis la navigation par curseur pour les gros volumes.
4. Auditer les risques fiscaux des constantes codées en dur indépendamment, sans modifier les taux sans validation réglementaire.
5. Registre QR 033 : transaction serveur, identités, droits et tests RLS avant toute activation en production.

**Règles de reprise :** avancer automatiquement sur le code non critique ; donner 5 lignes concises en français : résultat, prochaine action, pourquoi, comment, ce que l'utilisateur doit faire.
