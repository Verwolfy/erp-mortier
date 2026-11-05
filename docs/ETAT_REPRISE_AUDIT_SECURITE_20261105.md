# Sofiane ERP — reprise et audit de sécurité/performances (2026-11-05)

## État vérifié
- GitHub principal `Verwolfy/erp-mortier`, branche `main`.
- CI sur commit `40d9f881` : réconciliation (run 42070955192) et lot C (run 42070956615) concluants : `success`.
- Supabase principale : projet `wenydirqtmkywbxbxfal`, 90 tables, 659 colonnes, 255 contraintes, 115 index, 28 fonctions, 11 triggers non internes, 1 vue, 4 politiques RLS.
- 90 tables RLS actives. Vérification des rôles : aucune table ayant SELECT/INSERT pour `anon`, ou SELECT pour `authenticated`, détectée dans `public`.
- Vue `site_products` : `security_invoker=true`, sans privilège SELECT pour `anon` et `authenticated`. Le site reste un périmètre distinct et ne fait pas l'objet de modifications ici.
- Les 4 politiques RLS existantes concernent `erp_finance_operations`, `erp_finance_outbox`, `erp_sales_operations`, `erp_sales_outbox` (service_role uniquement).
- 10 fonctions `SECURITY DEFINER` sans EXECUTE `anon`/`authenticated`. Six fonctions de déclenchement (`paie_v2_garder_*`, `scf_garder_*`) sont `SECURITY INVOKER`, avec privilège EXECUTE hérité de PUBLIC, mais cela ne suffit pas à établir qu'elles peuvent être invoquées directement : revue recommandée, aucune modification ACL.
- Droits par défaut `postgres` restreints pour les futurs objets dans `public` ; les privilèges par défaut de `supabase_admin` sont plus larges. Il faut vérifier l'impact sur chaque futur objet avant modification.
- Audit Supabase Security Advisor : 86 tables RLS sans politique, niveau INFO ; cohérent avec modèle de service privé, **pas** une recommandation d'ouvrir l'accès.
- Audit Supabase Performance Advisor : 15 contraintes de clés étrangères non couvertes par des index, niveau INFO ; 9 index signalés inutilisés. Ne supprimer aucun index sur cette seule base.

## Proposition préparée
- `sql/supabase_pending/erp_034_fk_indexes_CANDIDAT_NON_EXECUTE.sql` : **15 CREATE INDEX CONCURRENTLY IF NOT EXISTS**, une instruction par index, sans DML, sans changement de RLS ou GRANT, et avec mention explicite « CANDIDAT NON EXECUTE ».
- Le `CONCURRENTLY` nécessite une exécution hors transaction ; ce n'est pas une migration Supabase `apply_migration` ordinaire. Contrôle des plans et de la charge obligatoire avant toute exécution en production.
- Aucune écriture SQL effectuée en production pour cet audit.

## Réconciliation en cours
- SQL : voir `docs/RECONCILIATION_MIGRATIONS_PREUVES_20261105.md`, avec 21 migrations ERP rapprochées de leur SQL d'exécution.
- Branches : 4 divergentes portent des anciennes versions de fonctionnalités déjà enrichies sur main ; aucune fusion ni suppression justifiée sur la seule base des SHA. L'outil GitHub relié ne dispose pas de suppression de branche.
- Validation réglementaire par expert-comptable algérien nécessaire avant toute production fiscale/sociale.
- Scanner de constantes réglementaires exécuté à titre **non bloquant** dans le workflow de réconciliation : conformité générale non établie.

## Reprise, par priorité
1. Vérifier l'état des CI du commit qui introduit le SQL candidat.
2. Effectuer un contrôle statique des 15 CREATE INDEX et des index existants, puis tests hors production si un environnement de test devient accessible.
3. Vérifier les politiques et droits des fonctions et le schéma complet avant modification ; tout changement de RLS/GRANT demande l'accord du propriétaire.
4. Ne pas appliquer de données réglementaires incertaines, ni inventer les références ; conserver les statuts à confirmer.
5. Examiner l'historique des branches obsolètes puis ne supprimer que celles dont la fusion/sauvegarde de contenu est démontrée.

## État courant
Audit lecture seule réalisé. Candidat SQL committé sur `main`, **non exécuté** ; aucune modification Supabase, aucune suppression de branche.
