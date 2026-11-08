# OPT-04 — Observabilité des lectures Supabase par rendu

**Date :** 2026-11-08  
**Branche :** `perf/opt04-render-query-metrics-20261108`  
**Périmètre :** Python + Streamlit + Supabase ; aucune migration ni changement de données.

## Problème et objectif

Après OPT-01 (cache daté), OPT-02 (un panneau KPI à la fois) et OPT-03 (projection minimale de provenance), les temps mesurés sur le serveur SQL ne permettent pas d'expliquer la latence de l'interface. Les lectures strictes `core/strict_reads.py` effectuent une vérification RBAC côté serveur **à chaque page**, puis exécutent le `SELECT`. La fabrication répétée de clients Supabase peut également coûter du temps. Il faut d'abord mesurer ces coûts de façon reproductible avant de mutualiser un client ou de toucher aux droits SQL.

## Implémentation

- `core/query_diagnostics.py` : mesures `ContextVar` **limitées au rendu** ; aucune écriture, aucun log, aucun export, aucune identité de session persistée.
- `core/strict_reads.py` : compte et chronomètre chaque `_require_read_permission` et chaque `execute()` de pages strictes, y compris les refus et les erreurs. Les contrôles existants (total exact, clés, pagination, bornes, exceptions) restent inchangés.
- `core/db_service.py` : chronomètre `create_client` uniquement. Pas de cache de client Auth entre sessions ; vérification de la cible inchangée.
- `modules/dashboards/service.py` : scope de mesure borné à `dashboard_read_scope`, compte les réutilisations du cache, mode DEMO 100 % local.
- `modules/dashboards/views.py` : section technique visible **uniquement aux profils administrateurs**, donnant les nombres de pages, contrôles, clients créés, hits de cache et les temps cumulés en ms.

### Ce que ces métriques signifient

| Valeur | Signification |
|---|---|
| Pages Supabase | Tentatives `execute()` de lectures strictes (pas tous les RPC ni toutes les requêtes HTTP) |
| Contrôles d'accès | Vérifications RBAC avant chaque page de lecture |
| Clients créés | Créations Python `create_client()` pendant le rendu (pour les droits et les données) |
| Lectures réutilisées | Réemplois des caches par rendu, sans requête supplémentaire |
| Durées | Sommes des durées par catégorie en ms, **chevauchantes et non additives** |

**Limites :** ce n'est pas une mesure du chargement complet du navigateur, ni la liste exhaustive des appels HTTP de l'ERP, ni une preuve de la vitesse de production. Le diagnostic n'enregistre ni SQL, ni noms de tables, ni contenu de réponse, ni credentials.

## Réception

1. Exécuter les tests `tests/test_query_diagnostics_opt04.py` : isolation de scope imbriqué, panne, RBAC, comptage, client éphémère, DEMO.
2. Lancer **2 suites complètes** des workflows GitHub et une **troisième exécution** sur le même commit de branche ; vérifier le commit `main` après fusion.
3. Parcourir les neuf vues avec un compte administrateur autorisé. Comparer la vue Direction, puis Achats et Finance, sur une période contrôlée. Noter séparément le délai de rendu navigateur et les valeurs techniques, sans capturer de données sensibles.
4. Ne pas déployer de pooling partagé de `create_client` sans preuve d'isolation Auth et tests de révocation entre utilisateurs.

## Suites

- `OPT-05` : à partir des compteurs réels, réduire les créations de client **uniquement si le gain dépasse le risque** et les tests montrent l'absence de mélange d'identités.
- Reprendre `ENV-01` et `TX-01` avec une base TEST indépendante. Aucune écriture de test en production, `DB-UNI-01` reste gelé.
- Terminer les vérifications authentifiées du déploiement et la rotation du mot de passe administrateur ; ne jamais copier le secret actuel dans le dépôt.
