# OPT-05 — Réutilisation strictement intra-page du client Supabase

Date : 2026-11-08. Branche : `perf/opt05-page-client-reuse-20261108`.  
Source de vérité : `Verwolfy/erp-mortier`.

## Constat

Dans `fetch_data_strict` et `fetch_history_page_strict`, chaque page effectue toujours deux actions réseau distinctes : (1) vérification du compte et des droits de lecture en base Supabase ; (2) récupération de la page métier avec `count=exact`.

Avant ce lot, **chacune de ces deux actions créait son propre objet client Supabase**, même si elles étaient exécutées dans la même page synchronisée. Le temps de création est instrumenté par OPT-04, mais aucune mesure authentifiée de production n'est encore disponible. L'amélioration ci-dessous est fondée sur le nombre déterministe de constructions et les tests simulés, pas sur un gain de latence réel.

## Changement

- `db_service.strict_read_page_client_scope()` établit une portée `ContextVar` vide, **strictement pour une page** de lecture. Son contenu est nettoyé en fin de portée, même en cas d'exception.
- `get_supabase_client()` conserve la vérification de la cible Supabase **à chaque appel**. Il ne retourne le client déjà créé que si l'URL, la clé et l'identité de la session Streamlit n'ont pas changé pendant cette page. Sinon, accès refusé.
- Hors de cette portée, `get_supabase_client()` continue à créer un client neuf à chaque appel. Aucun `st.cache_resource`, cache global ou contexte Auth partagé entre rendus, utilisateurs et pages.
- `strict_reads.fetch_data_strict` et `fetch_history_page_strict` enveloppent **la garde RBAC et l'exécution de SELECT**, pas la boucle complète de pagination. Les droits sont revalidés **à chaque page** comme avant.
- Aucun code de mutation, SQL, schéma, RPC, RLS, fiscalité, comptabilité ni donnée n'a changé.

## Contrat quantifiable

| Scénario | Constructions client avant | Après |
|---|---:|---:|
| 1 page : vérification RBAC puis SELECT | 2 | 1 |
| 2 pages avec permissions revalidées | 4 | 2 |
| Accès hors lecture stricte (2 appels séparés) | 2 | 2 |
| Refus RBAC avant lecture | Aucun SELECT métier | Aucun SELECT métier |

La diminution est **50 % des constructions de client dans ces scénarios précis**, et **non** 50 % des appels SQL, du trafic réseau ou du temps de chargement. L'authentification est toujours interrogée par réseau pour chaque page, et les compteurs OPT-04 doivent confirmer le coût réel avant toute nouvelle optimisation.

## Sécurité et tests

`tests/test_opt05_page_client_scope.py` vérifie sur un simulateur **sans réseau** :

- 1 client partagé uniquement entre `users` et sa page métier ; client distinct à la page suivante ;
- rappel du serveur des droits à chaque page, refus d'accès quand le compte est désactivé entre deux pages ;
- historique paginé inchangé ;
- identité/clé de cible changées pendant une page → refus ;
- portée imbriquée isolée, exception et fin de scope nettoyées ;
- appels hors portée jamais mis en cache et aucun SELECT métier si le compte est inactif.

La suite complète GitHub doit être verte sur la PR puis sur le merge `main`. Une recette réelle authentifiée et une comparaison des compteurs OPT-04, séparées des tests unitaires, demeurent obligatoires avant d'annoncer un gain en millisecondes.

## Risques et limites

- Un client Supabase Python peut mémoriser une session Auth localement ; c'est pourquoi son réemploi est délibérément limité **à l'autorisation puis à la lecture d'une seule page**, sans passage entre utilisateurs, sans persistance et avec vérification de changement d'identité/cible.
- Les tests locaux ne démontrent pas l'absence d'un défaut propre au navigateur hébergé ou à la configuration de production.
- La source de données Supabase principale reste intacte. Environnement TEST isolé et tests E2E d'écriture toujours à débloquer, sans test d'écriture en production.
- `DB-UNI-01` reste gelé. Mot de passe administrateur : rotation requise, ne jamais enregistrer de secret dans GitHub ni dans des rapports.

## Prochaine phase recommandée

1. Vérifier les compteurs visibles par un administrateur sur Direction, Achats, Finance, dans l'instance hébergée réellement déployée ; noter les valeurs et latences de rendu sans aucune donnée métier.
2. Prioriser sur preuve les appels Supabase les plus coûteux ; ne pas déduire une amélioration de latence du seul compteur de clients.
3. Terminer tests TEST isolés, contrôle version déployée, Ruff / Mypy / couverture, et rotation administrateur.
