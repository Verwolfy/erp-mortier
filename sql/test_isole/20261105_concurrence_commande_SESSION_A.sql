-- SESSION A : lancer simultanément avec SESSION B, TEST ffuhbmcfyexsbjwhryvj seulement.
-- Le SELECT conserve le verrou de la transaction le temps du pg_sleep.
SET statement_timeout='25000ms';
WITH op AS MATERIALIZED (SELECT public.erp_create_sales_order('IT26_PAR_ORDER','IT26_PAR_CLIENT','2026-11-05','[{"sku_id":"IT26_PAR_SKU","quantite":"2","prix_unitaire":"20"}]'::jsonb) AS resultat)
SELECT pg_backend_pid() AS backend, resultat, pg_sleep(5) AS garde_verrou FROM op;
