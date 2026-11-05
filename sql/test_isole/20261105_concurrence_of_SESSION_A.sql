-- EXCLUSIVEMENT TEST ffuhbmcfyexsbjwhryvj. Lancer avec B sur deux connexions.
BEGIN;
SET LOCAL statement_timeout='25000ms';
SET LOCAL ROLE service_role;
WITH action AS MATERIALIZED (SELECT public.erp_close_manufacturing_order((SELECT result_payload->>'of_id' FROM public.erp_production_creations WHERE operation_id='IT26_OFR_OF'),'OUI','[TEST] conforme simultané','TESTEUR',2,'IT26_OFR_PACK',2) AS resultat)
SELECT pg_sleep(5) FROM action;
COMMIT;
SELECT result_payload FROM public.erp_of_closures WHERE of_id=(SELECT result_payload->>'of_id' FROM public.erp_production_creations WHERE operation_id='IT26_OFR_OF');
