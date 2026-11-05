-- TEST ffuhbmcfyexsbjwhryvj. Lancer en parallèle de SESSION_A.
BEGIN;
SET LOCAL statement_timeout='25000ms';
SET LOCAL ROLE service_role;
SELECT public.erp_apply_stock_movement('IT26_FIFO_OUT_B','MP','SORTIE','IT26_FIFO_MP',6,NULL,'[TEST] FIFO sortie B',NULL);
COMMIT;
