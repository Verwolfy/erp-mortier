# Archives SQL déjà appliquées à Supabase PRINCIPALE

Ces SQL retracent les quatre migrations **déjà enregistrées** le 27 octobre 2026. Ne pas les rejouer à l'aveugle.

Ordre historique :
1. `20261027200803_erp_012_harden_principale_grants.sql`
2. `20261027201418_00_tables.sql` puis `_01_erp_auth_begin.sql`, `_02_erp_auth_finish.sql`, `_03_erp_security_add_permission.sql`, `_04_erp_security_create_user.sql`, `_05_erp_security_is_manager.sql` : six segments du **même** changement atomique `erp_013_security_tables_and_rpc`.
3. `20261027201513_erp_014_sales_order_security_fix.sql`
4. `20261027201607_erp_015_auto_rls_trigger.sql`

Les fichiers 013 ont été scindés uniquement pour la revue Git et doivent être considérés comme **une seule migration**. Le référentiel d'exécution est `supabase_migrations.schema_migrations` sur la base PRINCIPALE.

La migration originale 011 du dépôt (si présente en local) ne doit pas être rejouée sur PRINCIPALE sans comparaison avec `erp_014`. Les comptes d'essai et secrets de TEST n'ont pas été copiés.

Point de retour : sauvegarde du schéma public de PRINCIPALE effectuée le 27/10/2026 avant ces migrations, hors Git.
