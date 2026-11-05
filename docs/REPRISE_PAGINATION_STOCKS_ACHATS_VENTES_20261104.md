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


## Suivi de régression CI (04/11/2026)
- Première CI du lot `899c7e5` a relevé **2 tests historiques obsolètes**, et non une erreur de compilation : `test_read_only_role_can_view_history_not_write` attendait un chargement automatique des commandes Achats ; `test_denied_write_cannot_retry_old_pending_operation` attendait l'absence de tout bouton Stocks lorsque l'écriture est interdite.
- Adaptation des assertions en préservant la sécurité : en Achats lecture seule, aucun chargement global avant clic ; en Stocks lecture seule, seul le bouton d'historique est accessible et aucune entrée en stock ne peut être relancée.
- Commits correctifs : `ca3a1f7` et `811a804`.
- CI de validation des correctifs : tests `41916595600`, audit `41916595967` (verdict à confirmer).
- Cette modification concerne les écrans de consultation uniquement. Aucun taux fiscal, droit SQL, solde, commande, facture ou stock modifié.


## Extension — tri chronologique contrôlé (04/11/2026)
- `core/strict_reads.fetch_history_page_strict` accepte désormais un `date_column` **facultatif** et autorisé par la projection de lecture. Ordre SQL : date métier décroissante (`nullsfirst=False`), puis clé technique décroissante pour départager les mêmes dates. Sans date, conserve l'ordre par identifiant technique. Aucun tri client après récupération ne sert à reconstituer des pages.
- Historique Stocks : `mouvements.date`, `mouvements_pf.date`.
- Achats : `commandes_achats.date_commande`, `bons_reception.date_reception`.
- Ventes (consultation lecture seule) : `factures.date`.
- CRM : `interactions.date_creation`.
- Production : `controle_qualite.date`. `consommations_of` n'a **pas de date métier** dans le schéma exploité ; conserve le tri technique et n'invente aucune date.
- `tests/test_history_page_strict.py` : test double ordre SQL, dates nulles en dernier, rejet des colonnes non accessibles, rétrocompatibilité des historiques sans date, présence des paramètres par module.
- Commits : `5b4d31e`, `87d4989`, `9a1d89f`, `93fe951`, `7f06f7f`, `500d168`, `3e3aaf8`.
- Attention : pagination par **offset** sans snapshot transactionnel, une insertion concurrente peut toujours décaler les pages. Un curseur `(date,id)` devra être évalué distinctement. Aucun changement Supabase ni fiscal.


## Extension du 05/11/2026 — filtre temporel côté serveur
- Le tri chronologique était déjà réalisé et vérifié sur `main` (commit de départ `3162ad70`, CI tests + audit réussis). Ne pas le réimplémenter.
- `core/strict_reads.py` : `fetch_history_page_strict` accepte maintenant `start_date` + `end_date` facultatifs, **uniquement ensemble** et avec `date_column` préalablement autorisée. Validation ISO stricte et début <= fin, filtres `.gte/.lte` appliqués **avant** le tri et l'offset, donc le total `count=exact` correspond à la période filtrée.
- `core/history_filters.py` : contrôle UI facultatif de plage, défaut **aucun filtre** ; dates proposées 30 derniers jours quand le filtre est coché ; plage inversée bloquée avant consultation.
- `modules/stocks/views.py` : filtre sur la date des `mouvements` et `mouvements_pf`.
- `modules/achats/views.py` : filtre sur `commandes_achats.date_commande` et `bons_reception.date_reception`.
- `modules/ventes/views.py` : filtre sur `factures.date` **en consultation seule** ; validations et écritures conservées.
- `tests/test_history_period_filter.py` : essais de dates invalides, requêtes strictes, RBAC et absence de requête avant validation ; `tests/test_perf_histories_stocks_sales_purchases.py` adapté ; tests d'interface isolés Stocks/Achats utilisent un faux `core.history_filters` pour ne contacter aucun service.
- Commits : `8619bd2`, `46b4023`, `db0f0ec`, `fe40001`, `bc2b527`, `ce84668`, `80c1467`, `035de97`, `522be7a`.
- CI du dernier commit de code `522be7a` : tests `42006716863`, audit `42006716882`; vérifier leur verdict et corriger toute régression.
- Aucun changement Supabase ni création de facture, taxe, mouvement de stock, commande ; aucune migration QR ou permission SQL. La pagination reste par offset, sans snapshot transactionnel ; filtre de dates uniquement pour des colonnes de type date compatibles.
- Suite : valider CI ; tester les nouveaux filtres dans Streamlit (Stocks, Achats, Ventes lecture seule), vérifier comportement des dates et droits RBAC, mesurer ensuite les temps de réponse, envisager curseur stable si nécessaire.
