# OPT-02 — rendu à la demande des 9 panneaux Dashboard

**Date :** 2026-11-08. **Branche :** `perf/dashboard-lazy-panels-20261108`. **Stack conservée :** Python / Streamlit / Supabase.

## Cause et correction

Streamlit exécute le contenu de **tous les panneaux `st.tabs`** lors d'un rendu, même si un seul est affiché. La page `modules/dashboards/views.py` appelait les **9 fonctions d'agrégation métier** (`get_kpis_direction`, `get_kpis_pnl`, `get_kpis_ventes`, `get_kpis_achats`, `get_kpis_stocks`, `get_kpis_production`, `get_kpis_crm`, `get_kpis_rh`, `get_kpis_finance`).

La navigation utilise désormais un **sélecteur Streamlit explicite**, avec un unique `if active_panel == _DASHBOARD_PANELS[i]` par panneau et le même `read_section` fail-closed. On conserve les 9 vues, leurs sélecteurs de période, KPI, visualisations, contrôles d'accès et formules métier.

| Critère | Avant | Après |
|---|---|---|
| Fonctions d'agrégation KPI appelées à l'ouverture de l'écran | 9 | 1 (panneau sélectionné) |
| Recalcul des autres panneaux après changement de dates | Jusqu'à 8 inutiles | 0 |
| Isolation RBAC | Contrôle avant onglets | Contrôle avant navigation |
| DEMO vs données réelles | Sources exclusives | Inchangé |
| Alerte provenance DEMO/SIM | Vérification transversale | Conservée |
| Données/SQL/réglementation | Aucune modification | Aucune modification |

**Nuance :** 9 → 1 est une réduction des *fonctions de calcul initiales*, pas une mesure vérifiée du nombre de requêtes SQL ni du temps de chargement. La vérification de provenance continue de lire ses six tables en mode réel ; le générateur du jeu DEMO prépare encore les neuf sources, même quand un seul panneau est visible. Aucun gain en secondes n'est revendiqué sans mesure.

## Validation

- Les anciens contrats supposant le rendu simultané sont remplacés par des contrats plus stricts : neuf branches exclusives, aucune fonction KPI hors branche, isolation `read_section`, RBAC avant navigation, callback activité.
- `streamlit.testing.v1.AppTest` visite séparément chaque choix en mode DEMO : aucun accès Supabase, une à quatre métriques par vue, bannière DEMO persistante, pas d'exception, plus de 20 métriques cumulées.
- Les calculs, erreurs de lecture et pages métiers des neuf vues ne sont pas retouchés.
- Exécuter **toute la suite pytest**, trois passes sur le même commit de branche avant fusion ; inspecter aussi les deux workflows GitHub et le commit final `main`.
- Ne pas confondre validation automatisée et recette authentifiée du Streamlit hébergé.

## Suites d'optimisation proposées

1. Mesurer le nombre de requêtes et le délai de rendu en mode réel avec un utilisateur autorisé, journaux **sans donnée métier ni secrets**.
2. Réduire, après validation de politique métier, le coût de l'alerte de provenance toujours transversale (6 lectures globales).
3. Étudier les 18 clés étrangères non couvertes par index signalées par le conseiller Supabase. Exiger `EXPLAIN`/données de charge avant migration. Aucun index supprimé automatiquement.
4. Restaurer un environnement Supabase TEST distinct uniquement après vérification des conséquences et coûts. Aucun test d'écriture sur la base principale.

**Contrainte :** `DB-UNI-01` demeure gelé. Les mots de passe administrateur ne sont jamais enregistrés dans les sources ou tests. Rotation requise de l'identifiant courant et qualification de l'ancien secret public.
