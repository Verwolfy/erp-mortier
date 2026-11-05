-- SESSION A : lancer simultanément avec SESSION B, TEST ffuhbmcfyexsbjwhryvj seulement.
-- Le SELECT conserve le verrou de la transaction le temps du pg_sleep.
BEGIN;
SET LOCAL statement_timeout='25000ms';
SET LOCAL ROLE service_role;
WITH op AS MATERIALIZED (SELECT public.erp_create_sales_order('IT26_PAR_ORDER','IT26_PAR_CLIENT','2026-11-05','[{"sku_id":"IT26_PAR_SKU","quantite":"2","prix_unitaire":"20"}]'::jsonb) AS resultat)
SELECT pg_sleep(5) FROM op;
COMMIT;
SELECT operation_id,result_payload FROM public.erp_sales_order_creations WHERE operation_id='IT26_PAR_ORDER';
