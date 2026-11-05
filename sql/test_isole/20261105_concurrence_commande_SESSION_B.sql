-- SESSION B : lancer en parallèle à SESSION A, même operation_id / même payload.
-- Un seul document commande doit être créé.
BEGIN;
SET LOCAL statement_timeout='25000ms';
SET LOCAL ROLE service_role;
SELECT public.erp_create_sales_order('IT26_PAR_ORDER','IT26_PAR_CLIENT','2026-11-05','[{"sku_id":"IT26_PAR_SKU","quantite":"2","prix_unitaire":"20"}]'::jsonb);
COMMIT;
SELECT operation_id,result_payload FROM public.erp_sales_order_creations WHERE operation_id='IT26_PAR_ORDER';
