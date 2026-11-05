-- TEST ffuhbmcfyexsbjwhryvj. Lancer en parallele avec SESSION_B, connexion distincte.
BEGIN;
SET LOCAL statement_timeout='25000ms';
SET LOCAL ROLE service_role;
WITH action AS MATERIALIZED (
 SELECT public.erp_apply_stock_movement('IT26_CUMPR_INA','MP','ENTREE','IT26_CUMPR_MP',5,160,'[TEST] CUMPR ENTREE A',NULL) AS resultat
)
SELECT pg_sleep(5) FROM action;
COMMIT;
SELECT result_payload FROM public.erp_stock_operations WHERE operation_id='IT26_CUMPR_INA';
