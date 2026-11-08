# ERP-034 — complétude des candidats d'index FK (8 novembre 2026)

**Statut : proposition versionnée, NON EXÉCUTÉE.** Aucun DDL, aucune modification de droit, aucune donnée de production changée. Aucune accélération réelle ne peut être affirmée avant création des index et mesure de charge.

## Constat vérifié

- Projet production `erp-mortier` (`wenydirqtmkywbxbxfal`), advisor Supabase `unindexed_foreign_keys` : **18** constats le 08/11/2026.
- Le candidat préexistant `sql/supabase_pending/erp_034_fk_indexes_CANDIDAT_NON_EXECUTE.sql` proposait **15** index.
- Les trois clés étrangères absentes de ce candidat, confirmées par `pg_constraint` :
  - `public.erp_cost_drivers(of_id)` → `public.ordres_fabrication(of_id)`, `ON DELETE RESTRICT` ;
  - `public.erp_cost_of_validation_snapshot(of_id)` → `public.ordres_fabrication(of_id)`, `ON DELETE RESTRICT` ;
  - `public.erp_cost_pools(nature_code)` → `public.erp_cost_natures(nature_code)`, `ON DELETE RESTRICT`.
- Elles sont ajoutées **uniquement au SQL candidat** via `CREATE INDEX CONCURRENTLY IF NOT EXISTS` ; test statique `tests/test_fk_index_candidates_034.py` garantissant la couverture des 18 paires table/colonne et l'absence d'autres instructions dans ce fichier.
- Advisor `unused_index` : 5 avertissements informatifs. **Ne pas supprimer** ces index sur cette seule base (faible trafic, statistiques remises à zéro, utilité lors des charges rares).
- Advisor sécurité : 92 tables avec RLS active sans politique explicite. Cela peut être un refus d'accès intentionnel ; aucune politique ajoutée.
- Contrôle SQL : 96 tables ordinaires `public` avec RLS active, 39 fonctions `public`, dont 18 `SECURITY DEFINER` ; **0** de ces fonctions était exécutable par `anon` ou `authenticated` au moment du contrôle. Ce constat ne remplace pas un audit d'autorisation.
- Historique : 33 migrations dans `supabase_migrations.schema_migrations`, 0 dans `public.schema_migrations`. Ne pas les dupliquer artificiellement.

## Préconditions pour exécution ultérieure

1. Réactiver ou mettre à disposition un environnement Supabase de test **sans engager de frais sans accord** ; vérifier le schéma et la confidentialité du jeu de test.
2. Mesurer les plans `EXPLAIN (ANALYZE, BUFFERS)` sur **TEST seulement**, valider la sélectivité, la volumétrie et les coûts en écriture. Privilégier un petit lot utile si 18 index sont disproportionnés.
3. Revalider le dernier advisor, les index existants et le schéma principal juste avant la préparation de migration.
4. Si validé, exécuter chaque `CREATE INDEX CONCURRENTLY` séparément, hors transaction ; prévoir les échecs, index invalides éventuels et le plan de retour. Ne pas appliquer le brouillon comme bloc transactionnel.
5. Après application autorisée : vérifier `pg_index.indisvalid`, les plans de requêtes, les migrations suivies et les performances réelles. Aucune création d'index n'a été faite dans ce lot.

## Réconciliation GitHub et CI

- Contrôle des **43 branches secondaires** au 08/11/2026 : **39** sans commit en avance de `main`; **4** branches historiques divergentes (`feat/nextgen-crm-inbox-readonly-20261101`, `feat/nextgen-crm-ui-fingerprint-20261101`, `feat/nextgen-privacy-dual-gate-20261101`, `feat/nextgen-sku-qualification-readonly-20261101`) avec respectivement **2, 1, 1 et 5** commits propres. Les six fichiers propres à ces fonctionnalités existent déjà dans `main`. **Ne pas les fusionner à l'aveugle** : revue de contenu requise pour éviter la régression et certifier leur remplacement fonctionnel.
- `main` au SHA `5598462cf92d5ce758358bf1769052996d6afca2` : workflows `lot_c_tests.yml` et `reconciliation_audit.yml` **success** pour ce SHA, runs [tests](https://github.com/Verwolfy/erp-mortier/actions/runs/42516360509) et [audit](https://github.com/Verwolfy/erp-mortier/actions/runs/42516360347).
- Le projet `erp-mortier-test` était **INACTIVE** lors du contrôle ; pas de test d'intégration réel sur une base test effectué. Pas de preuve de SHA déployé sur Streamlit.

**Décision :** laisser ERP-034 au stade candidat jusqu'à un essai en TEST et une mesure d'impact. Prochain lot : audits différentiels de branches/SQL, tests RPC/E2E en TEST, homologation Streamlit authentifiée, conformité réglementaire indépendante. Une validation par expert-comptable algérien est indispensable avant toute production réglementaire.
