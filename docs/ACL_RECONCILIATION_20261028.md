# Audit ACL — Supabase TEST / PRODUCTION — 28 octobre 2026

## Décision de sauvegarde

Le propriétaire a explicitement indiqué qu'il **ne souhaite pas de sauvegarde PostgreSQL**.
Le script facultatif reste conservé dans le dépôt, mais son exécution n'est
**pas** une condition préalable automatique pour la poursuite du développement.
Cette décision ne valide pas une opération destructive non contrôlée.

## Comparaison en lecture seule

- **81 tables publiques** comparées dans chaque base ; RLS activée sur les 81.
- Même inventaire de tables, colonnes, index, fonctions et contraintes dans les
  vérifications précédentes.
- **66 différences d'ACL**, uniquement sur les droits `service_role` des tables
  historiques. Les nouvelles tables réglementaires, SCF et paie ont des
  permissions identiques sur les deux projets.
- En production, 76 tables ont une ACL `service_role` complète et cinq
  tables ont seulement le droit propriétaire `postgres`.
- Sur TEST, les permissions de `service_role` sont plus restrictives.

| ACL `service_role` sur TEST | ACL `service_role` sur production | Nombre de tables |
|---|---|---:|
| `Dxtm` | `arwdDxtm` | 14 |
| `arDxtm` | `arwdDxtm` | 33 |
| `arwDxtm` | `arwdDxtm` | 15 |
| `rwDxtm` | `arwdDxtm` | 2 |
| `rDxtm` | `arwdDxtm` | 2 |
| **Total** | | **66** |

Codes PostgreSQL : `a` INSERT, `r` SELECT, `w` UPDATE, `d` DELETE,
`D` TRUNCATE, `x` REFERENCES, `t` TRIGGER, `m` MAINTAIN.
Ce tableau décrit uniquement les **ACL des tables**, pas les permissions de
fonction, de séquence ni le contrôle des rôles applicatifs.

## Analyse

**Ces différences ne sont pas des anomalies à corriger aveuglément.**
Le niveau de restriction de TEST peut être intentionnel, notamment pour empêcher
les écritures accidentelles pendant les vérifications. Reproduire les permissions
de production sur TEST serait une augmentation importante de privilèges.

Aucun droit supplémentaire n'est nécessaire pour les nouveaux registres :
ils ont déjà les autorisations serveur requises et la RLS est active.

Les nouveaux composants ne sont pas déclarés conformes en production, car
les règles fiscales et sociales officielles n'ont pas été validées et chargées.

## Statut

**AUDIT TERMINÉ — PAS DE GRANT OU REVOKE APPLIQUÉ.**

Les autres chantiers peuvent continuer indépendamment : exactitude décimale,
tests, validation du calcul fiscal et intégration progressive des interfaces.
Les changements de droits restent soumis à un examen précis par table et usage.
