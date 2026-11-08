# Réconciliation des migrations du site NextGen — 8 novembre 2026

## Source et méthode

Comparaison en lecture seule des deux dernières versions de site répertoriées dans la base Supabase de production `wenydirqtmkywbxbxfal` avec leur véritable dépôt source `Verwolfy/nextgen-website` sur `main`. Le dépôt ERP `Verwolfy/erp-mortier` ne porte pas ces deux fichiers : **ce n'est pas une migration manquante dans l'ERP**.

| Version native | Fichier source | Résultat |
| --- | --- | --- |
| `20261031204336` `nextgen_site_publication_private_20261031` | [NextGen SQL 001](https://github.com/Verwolfy/nextgen-website/blob/main/sql/001_site_publication_PROPOSITION_NON_EXECUTEE.sql) | Texte identique sur les **3859 premiers caractères** ; fichier GitHub avec **un saut de ligne final supplémentaire**. Égalité après suppression de ce saut de ligne final seulement. |
| `20261031220121` `nextgen_site_demandes_private_20261031` | [NextGen SQL 003](https://github.com/Verwolfy/nextgen-website/blob/main/sql/003_site_demandes_PROPOSITION_NON_EXECUTEE.sql) | **Identité textuelle exacte**, 2519 caractères de chaque côté. |

Le nom de fichier `PROPOSITION_NON_EXECUTEE` est historique : les deux versions figurent réellement dans `supabase_migrations.schema_migrations`. La documentation du site `docs/SQL_003_APPLICATION_20261031.md` donne en outre le contexte de la décision d'application SQL 003. **Ne jamais rejouer ces scripts à cause de leur nom**.

## Contrôles de schéma et de droits réellement effectués

Sur les objets publics en production, contrôlés via `pg_class`, `pg_attribute` et `has_table_privilege` :

| Objet | Type | Colonnes | RLS | SELECT anon | SELECT authenticated | SELECT service_role |
| --- | --- | ---: | --- | --- | --- | --- |
| `public.site_produits` | Table | 18 | Oui | Non | Non | Oui |
| `public.site_demandes` | Table | 20 | Oui | Non | Non | Oui |
| `public.site_products` | Vue | 13 | Sans objet direct | Non | Non | Oui |

La vue ne porte pas de RLS propre : elle ne dispose toutefois pas de privilège SELECT pour `anon` ni `authenticated` au moment du contrôle. Ne pas élargir les GRANT. La conformité de toutes les autres permissions, fonctions et déclencheurs n'est pas déduite de ce tableau.

## Bilan des 33 versions

- **21 versions ERP antérieures** : source et écarts documentés dans `docs/RECONCILIATION_MIGRATIONS_PREUVES_20261105.md` (vérifications historiques).
- **10 versions ERP 034–043** : correspondance exacte **revérifiée en direct** dans `docs/RECONCILIATION_COUTS_MIGRATIONS_20261108.md`.
- **2 versions site** : correspondances **revérifiées en direct** dans le présent document (1 exacte, 1 différant d'un saut de ligne final).

**Les 33 versions enregistrées ont ainsi une provenance de SQL localisée et comparée**, selon la combinaison des preuves anciennes et nouvelles. Ceci **n'est pas** une certification que l'ensemble des objets SQL réels et droits actuels est conforme : un diff de schéma/ACL complet et des tests d'intégration en environnement TEST restent requis.

## Sûreté et limites

Aucune écriture de production, aucun rejeu, aucune création de migration, aucun changement RLS/GRANT et aucune suppression de données. Ne pas copier de données du site au dépôt ERP. Le site public et ses formulaires ne doivent pas être déclarés actifs à partir de la seule présence de ces objets privés.
