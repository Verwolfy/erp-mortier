-- SESSION B : lancer en parallèle à SESSION A, même operation_id / même payload.
-- Un seul document commande doit être créé.
SET statement_timeout='25000ms';
SELECT pg_backend_pid() AS backend, public.erp_create_sales_order('IT26_PAR_ORDER','IT26_PAR_CLIENT','2026-11-05','[{"sku_id":"IT26_PAR_SKU","quantite":"2","prix_unitaire":"20"}]'::jsonb) AS resultat;
