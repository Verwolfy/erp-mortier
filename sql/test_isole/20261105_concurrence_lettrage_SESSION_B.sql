-- TEST ffuhbmcfyexsbjwhryvj. Lancer en parallèle de SESSION_A.
BEGIN;
SET LOCAL statement_timeout='25000ms';
SET LOCAL ROLE service_role;
SELECT public.erp_finance_transaction('ALLOCATE','IT26_LET_ALLOC_B',
 '{"reglement_id":"IT26_LET_PAYMENT","type_document":"FactureClient","document_id":"IT26_LET_INVOICE","montant_applique":70}'::jsonb);
COMMIT;
