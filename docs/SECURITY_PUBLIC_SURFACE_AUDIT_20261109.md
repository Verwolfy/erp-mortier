# SECURITY-01 — audit reproductible des droits PostgreSQL (9 novembre 2026)

**Périmètre** : base Supabase production `erp-mortier` (`wenydirqtmkywbxbxfal`), schéma `public`, lecture seule via `execute_sql`. Le SQL utilisé est versionné dans `sql/audits/security_public_surface_readonly_20261109.sql`. Aucune mutation, ni activation de nouvelle policy, ni modification de `GRANT`.

## Résultats mesurés

| Contrôle | Résultat |
|---|---:|
| Relations publiques (tables/vues) | 101 |
| Tables publiques ordinaires | 96 |
| Tables avec RLS | 96 |
| Tables RLS sans policy explicite | 92 |
| Vues | 5 |
| Vues sans `security_invoker=true` | 0 |
| Vues non lisibles par `service_role` | 0 |
| Relations accessibles en SELECT par `anon` ou `authenticated` | 0 |
| Relations accessibles en INSERT par `anon` ou `authenticated` | 0 |
| Fonctions publiques | 39 |
| Fonctions exécutables par `anon` ou `authenticated` | 8 |
| Parmi elles, fonctions ordinaires hors `RETURNS trigger` | 0 |
| Fonctions `SECURITY DEFINER` | 18 |
| Fonctions `SECURITY DEFINER` exécutables par `anon` ou `authenticated` | 0 |
| Fonctions `SECURITY DEFINER` sans `search_path` déclaré | 0 |

**Interprétation** : la surface SQL directe du schéma `public` est fermée aux clients `anon` et `authenticated` pour les privilèges testés. Le simple avertissement `rls_enabled_no_policy` sur 92 tables ne démontre pas une fuite : le refus par défaut est possible. Ce constat **ne prouve pas** l'absence de fuite par une fonction autorisée via un autre rôle, un autre schéma, un proxy applicatif ou un déploiement externe.



**Précision sur les 8 fonctions accessibles aux clients** : les huit renvoient le type PostgreSQL `trigger` et sont exécutées avec les droits de l'appelant (`SECURITY INVOKER`). Cela ne constitue pas une preuve d'exploitation par appel RPC ordinaire ; un audit des déclencheurs et de leurs tables reste néanmoins nécessaire. Aucun privilège n'a été modifié.

## Mesures et suites nécessaires

- Rejouer le SQL en lecture seule après chaque migration affectant `public` ou les privilèges, et comparer les compteurs à une référence auditable.
- Pour un audit complet, étendre le périmètre à `UPDATE`, `DELETE`, droits de schéma, séquences, privilèges hérités, fonctions et vues dans d'autres schémas exposés, rôles personnalisés et configurations REST.
- Examiner les 18 fonctions `SECURITY DEFINER` individuellement : vérification d'identité, paramétrage du `search_path`, schémas d'exécution et logique métier ; **ne jamais ouvrir automatiquement les droits**.
- Conserver les données `DEMO/SIM`. Ne faire aucune migration d'index ou de facturation en production avant des tests intégrés sur une base isolée.
- Tests statiques `tests/test_security_public_surface_readonly.py` : analyse du SQL avec `pglast` et contrôle des primitives auditées.

## Restrictions

Le projet TEST Supabase était inactif lors du diagnostic précédent ; aucune validation TX/E2E authentifiée n'est revendiquée. Les taux et montants fiscaux ne sont ni calculés ni certifiés par cet audit. Les valeurs fiscales codées en dur dans l'ancienne transaction Ventes restent à traiter distinctement.
