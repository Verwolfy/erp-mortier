# Incident production — Dashboard TypeError, 2026-11-08

## Symptôme rapporté

Sur Streamlit Cloud, `app.py:299 → app.py:181 → modules/dashboards/views.py:118 → modules/dashboards/service.py:141`, l'écran Dashboard plante lors du diagnostic `get_dashboard_data_provenance()` avec `TypeError`. Le message exact a été masqué par Streamlit Cloud et **n'est pas disponible**. Il ne faut donc **pas** affirmer que le déploiement avait une signature incompatible ; c'est une hypothèse plausible.

## Diagnostic vérifié sur GitHub

- `main` avant correctif : `bacb7f317e7fb660146ce38adf64879b0a60d2aa`.
- `modules/dashboards/service.py:141` appelle `fetch_provenance_identifiers(table, only_primary_key=True)`.
- `core/strict_reads.py` dans ce même `main` accepte bien `only_primary_key=False` et gère les lectures paginées strictes.
- Le chemin `modules/dashboards/views.py:118` intercepte `PermissionError` et `DataReadError`, mais **pas** `TypeError`. Ainsi une erreur de compatibilité ou TypeError non pris en charge remonte jusqu'à Streamlit et casse le Dashboard.
- Les tests de branche précédents simulaient le lecteur avec la bonne signature ; ils n'exerçaient pas le cas de déploiement incohérent.

## Correctif proposé

Branche : `fix/incident-dashboard-provenance-typeerror-20261108`.

1. `service.py` : si la lecture optimisée des identifiants soulève `TypeError`, réessayer via `fetch_data(table)`, la lecture stricte paginée historique. Même RBAC, `count=exact`, bornes et validation des clés ; **pas de requête libre ni de droits contournés**. Cache local au rendu seulement, jamais d'erreur mémorisée.
2. `views.py` : un `TypeError` du **diagnostic auxiliaire** ne fait plus planter toute la page ; affiche explicitement « provenance non vérifiable, KPI non certifiés ». Les contrôles de rôle précédant le diagnostic restent actifs. Les erreurs des calculs métier ne sont pas masquées.
3. `tests/test_dashboard_provenance_typeerror_hotfix.py` : cinq tests offline, signature obsolète, droits refusés, lecture incomplète non mémorisée, continuité de navigation, refus d'accès préalable.

## Validation et publication

- Attendre les 2 workflows CI complets de la PR d'incident et vérifier au moins une exécution supplémentaire du même SHA.
- Fusionner le correctif seul si vert, puis valider sur `main`.
- L'observation GitHub publique Streamlit **ne remplace pas** l'authentification. Vérifier dans Streamlit Cloud après le nouveau déploiement que le Dashboard s'ouvre en mode réel et DEMO et que la bannière de provenance est cohérente.
- Pour trouver l'origine précise, récupérer **uniquement le type et les frames de la trace d'erreur** du journal Streamlit Cloud, sans imprimer variables, clés ou données privées. Vérifier que le processus a chargé les mêmes versions de `service.py` et `strict_reads.py` que le commit publié.
- Aucune migration SQL, donnée, mot de passe, GRANT/RLS ni environnement TEST touché.

## Suite après stabilisation

Reprendre les optimisations par lots, avec priorité au chargement à la demande des modules Stocks, Achats puis Production. Ne pas fusionner la branche Stocks inachevée `perf/lot06-stocks-lazy-20261108` ; les opérations d'écriture et les tests historiques doivent rester intacts. Rotation du mot de passe administrateur toujours nécessaire ; ENV-01 / base TEST inactive et tests E2E restent des limites.
