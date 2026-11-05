-- TEST ffuhbmcfyexsbjwhryvj. Lancer en parallèle de SESSION_B.
BEGIN;
SET LOCAL statement_timeout='25000ms';
SET LOCAL ROLE service_role;
WITH action AS MATERIALIZED (
 SELECT public.erp_finance_transaction('ALLOCATE','IT26_LET_ALLOC_A',
 '{"reglement_id":"IT26_LET_PAYMENT","type_document":"FactureClient","document_id":"IT26_LET_INVOICE","montant_applique":70}'::jsonb) AS resultat
)
SELECT pg_sleep(5) FROM action;
COMMIT;
SELECT result_payload FROM public.erp_finance_operations WHERE operation_id='IT26_LET_ALLOC_A';
