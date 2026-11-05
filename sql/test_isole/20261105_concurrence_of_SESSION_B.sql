-- EXCLUSIVEMENT TEST ffuhbmcfyexsbjwhryvj. Lancer en parallèle à A.
BEGIN;
SET LOCAL statement_timeout='25000ms';
SET LOCAL ROLE service_role;
SELECT public.erp_close_manufacturing_order((SELECT result_payload->>'of_id' FROM public.erp_production_creations WHERE operation_id='IT26_OFR_OF'),'OUI','[TEST] conforme simultané','TESTEUR',2,'IT26_OFR_PACK',2) AS resultat;
COMMIT;
