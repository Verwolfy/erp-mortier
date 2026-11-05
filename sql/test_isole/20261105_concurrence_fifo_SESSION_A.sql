-- TEST ffuhbmcfyexsbjwhryvj. Lancer avec SESSION_B sur deux connexions.
BEGIN;
SET LOCAL statement_timeout='25000ms';
SET LOCAL ROLE service_role;
WITH action AS MATERIALIZED (
 SELECT public.erp_apply_stock_movement('IT26_FIFO_OUT_A','MP','SORTIE','IT26_FIFO_MP',6,NULL,'[TEST] FIFO sortie A',NULL) AS resultat
)
SELECT pg_sleep(5) FROM action;
COMMIT;
SELECT result_payload FROM public.erp_stock_operations WHERE operation_id='IT26_FIFO_OUT_A';
