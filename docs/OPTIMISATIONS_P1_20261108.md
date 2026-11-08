# OPT-01 — optimisation des lectures filtrées du Dashboard

Date : 2026-11-08 — branche `perf/dashboard-period-read-cache-20261108`.

## Résultat attendu et périmètre

- **Avant** : `_lire_periode(table, colonne, début, fin)` répétait les requêtes strictes Supabase même quand le même filtre était demandé plusieurs fois pendant un unique affichage.
- **Après** : une seule requête pour chaque combinaison exacte `(table, colonne, début, fin)` **dans le rendu courant**, les lectures répétées réutilisent les lignes lues.
- **Preuve déterministe** : trois appels consécutifs de même périmètre entraînent 3 appels simulés avant optimisation et 1 appel simulé après (réduction de 66,7 % des appels *redondants de cette séquence*, pas une mesure de vitesse réelle du Dashboard). Les 8 tests du lot vérifient les appels exacts.
- **Aucun cache transverse** : `ContextVar` est réinitialisé à la sortie du `dashboard_read_scope`; aucun cache global `st.cache_data`, aucune empreinte de session ou valeur utilisateur conservée.
- **Aucun mélange de périmètres** : périodes, tables, colonnes, portées imbriquées et mode démonstration sont indépendants.
- **Pas de faux résultat de sécurité** : un refus RBAC, une erreur de lecture ou une page incomplète ne sont pas mis en cache.
- **Copie profonde** des lignes renvoyées pour éviter les modifications des DataFrame et des objets imbriqués.
- **Aucun changement SQL** : formules, RLS/GRANT, migrations, données, comptabilité et fiscalité inchangés.

## Validation requise avant fusion

1. `pytest -q tests/test_dashboards_period_cache.py tests/test_dashboards_read_scope.py`
2. Suite Python complète `pytest -q`, idéalement trois passes sur le même commit.
3. Revue de non-régression des données en mode DEMO et sans portée.
4. Benchmark réel du temps d'affichage et du nombre de requêtes via télémétrie **anonymisée** après disponibilité d'une session Streamlit autorisée.
5. Tests d'intégration SQL en environnement isolé pour les workflows : séparés de cette optimisation, pas prétendus réussis.

**Limite** : cette optimisation réduit les doublons d'appels au cours d'un rendu ; elle ne réduit pas le volume d'une première lecture ni ne remplace les index SQL. Aucun gain absolu en millisecondes ou en RAM n'est présumé.

## Suite prioritaire

- `OPT-02` : mesurer le coût de `get_supabase_client()` par requête avant d'envisager une connexion réutilisée. Ne pas réutiliser une session Auth entre utilisateurs.
- `OPT-03` : mesurer les appels Dashboard les plus chers et les paginations réelles, sans exposer de données.
- `ENV-01` : conserver le bac TEST isolé et le verrou fail-closed ; ne jamais tester une écriture en production.
