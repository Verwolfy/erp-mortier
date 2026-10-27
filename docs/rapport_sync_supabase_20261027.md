# Synchronisation ERP Mortier — 27 octobre 2026

Source : Supabase TEST `ffuhbmcfyexsbjwhryvj`.
Cible : Supabase PRINCIPALE `wenydirqtmkywbxbxfal`.

Migrations réellement appliquées à PRINCIPALE :
- `erp_012_harden_principale_grants` : retrait GRANT directs anonymes, défauts et chemin du compteur.
- `erp_013_security_tables_and_rpc` : cinq tables de sécurité, cinq RPC et secret propre à PRINCIPALE.
- `erp_014_sales_order_security_fix` : correctif de privilèges sur commande client.
- `erp_015_auto_rls_trigger` : activation automatique de RLS sur les nouvelles tables.

Ne pas restaurer TEST sur PRINCIPALE. Les sauvegardes originales sont hors Git.
Le déploiement de `main` nécessite l’intégration des scripts complets et les tests applicatifs.
