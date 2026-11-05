-- TEST ffuhbmcfyexsbjwhryvj. Lancer en parallele avec SESSION_A, connexion distincte.
BEGIN;
SET LOCAL statement_timeout='25000ms';
SET LOCAL ROLE service_role;
SELECT public.erp_apply_stock_movement('IT26_CUMPR_INB','MP','ENTREE','IT26_CUMPR_MP',15,80,'[TEST] CUMPR ENTREE B',NULL);
COMMIT;
