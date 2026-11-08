# Réconciliation des migrations de coûts industriels — preuves du 8 novembre 2026

## Méthode

Comparaison **lecture seule** entre `supabase_migrations.schema_migrations.statements[1]` sur la production `wenydirqtmkywbxbxfal` et les fichiers SQL de `Verwolfy/erp-mortier`, branche `main`, sur le code en vigueur le 8 novembre 2026. Chaque version native possède exactement **un** segment de `statements`.

Aucune migration n'a été exécutée, aucun registre modifié, aucune donnée ni autorisation touchée. La comparaison est une égalité **exacte des chaînes complètes**, commentaires et sauts de ligne compris, et non une simple proximité de nom.

| Version native | Fichier GitHub | Taille (caractères) | Identité exacte |
| --- | --- | ---: | --- |
| 20261105220851 | `sql/034_referentiel_couts_industriels_analytiques.sql` | 10641 | Oui |
| 20261105220858 | `sql/035_cout_industriel_synthese_validation.sql` | 2645 | Oui |
| 20261105223306 | `sql/036_couts_industriels_validation_privileges.sql` | 2873 | Oui |
| 20261105223313 | `sql/037_cost_guard_security_definer.sql` | 1085 | Oui |
| 20261106093254 | `sql/038_couts_industriels_pieces_scf_validees.sql` | 6053 | Oui |
| 20261106093953 | `sql/039_verrouillage_suppression_preuve_couts.sql` | 805 | Oui |
| 20261106095642 | `sql/040_couts_industriels_plafond_ligne_scf.sql` | 5684 | Oui |
| 20261106104342 | `sql/041_couts_industriels_documentation_atomique.sql` | 3327 | Oui |
| 20261106105631 | `sql/042_snapshot_validation_couts_industriels.sql` | 3358 | Oui |
| 20261106142953 | `sql/043_export_couts_valides_snapshot.sql` | 5156 | Oui |

## Synthèse des 33 versions natives Supabase

- 10 migrations de coûts industriels (tableau ci-dessus) : **correspondance textuelle exacte nouvellement vérifiée**.
- 21 migrations ERP antérieures (012 à 032) : états et preuves archivés dans `docs/RECONCILIATION_MIGRATIONS_PREUVES_20261105.md` ; 17 identités exactes et 4 équivalences documentées après normalisation d'en-têtes/espaces. Le présent lot **n'a pas réexécuté** ces 21 comparaisons.
- 2 migrations du site NextGen (`20261031204336` et `20261031220121`) : appliquées dans le registre Supabase mais **SQL de source hors du dépôt ERP** ; comparaison à leur référentiel d'origine **non réalisée**.

En tout, **31 migrations ERP** sont associées aux fichiers du dépôt selon les contrôles nouveaux et antérieurs. Il reste **2 migrations du site** dont la source doit être rapprochée, puis un audit de schéma **réel** (tables, index, contraintes, fonctions, triggers, vues, politiques RLS et GRANT).

## Limites explicites

L'égalité d'une chaîne SQL enregistrée dans le registre natif ne démontre pas que tous ses objets sont encore présents ni que leurs définitions n'ont jamais été modifiées hors migration. La table `public.schema_migrations` vide n'est pas à remplir artificiellement. L'environnement TEST `erp-mortier-test` était `INACTIVE` lors du contrôle.

Les candidats `sql/supabase_pending/erp_034_fk_indexes_CANDIDAT_NON_EXECUTE.sql` et `erp_035_crm_idempotence_CANDIDAT_NON_EXECUTE.sql` **ne sont pas des migrations appliquées**.

## Suite

1. Contrôler la provenance des deux migrations du site NextGen dans son dépôt source, sans importer des données client.
2. Réaliser un diff d'objets réels et de permissions (lecture seule) entre schéma attendu et production ; toute différence destructive nécessite arbitrage.
3. Activer un environnement de test approprié uniquement après vérification du coût et de l'autorisation ; y tester les parcours RPC refusés/acceptés.
4. Ne pas déclarer l'ERP entièrement réconcilié ni homologué sur la seule base de ce tableau.
