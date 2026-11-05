-- TEST UNIQUEMENT ffuhbmcfyexsbjwhryvj. Fixtures IT26_LET uniquement.
BEGIN;
SET LOCAL statement_timeout='30s';
DO $guard$
BEGIN
 IF EXISTS (SELECT 1 FROM public.factures WHERE client_id='IT26_LET_CLIENT' AND facture_id<>'IT26_LET_INVOICE')
 OR EXISTS (SELECT 1 FROM public.reglements WHERE partenaire_id='IT26_LET_CLIENT' AND reglement_id<>'IT26_LET_PAYMENT')
 OR EXISTS (SELECT 1 FROM public.lettrage WHERE document_id='IT26_LET_INVOICE'
  AND reglement_id<>'IT26_LET_PAYMENT')
 OR EXISTS (SELECT 1 FROM public.erp_finance_operations WHERE operation_id LIKE 'IT26_LET_%'
 AND operation_id NOT IN ('IT26_LET_ALLOC_A','IT26_LET_ALLOC_B'))
 OR EXISTS (SELECT 1 FROM public.ecritures_comptables WHERE document_source_id='IT26_LET_PAYMENT')
 THEN RAISE EXCEPTION 'Nettoyage lettrage refusé: dépendance ou opération inattendue'; END IF;
 DELETE FROM public.lettrage WHERE document_id='IT26_LET_INVOICE' AND reglement_id='IT26_LET_PAYMENT';
 DELETE FROM public.erp_finance_outbox WHERE operation_id IN ('IT26_LET_ALLOC_A','IT26_LET_ALLOC_B');
 DELETE FROM public.erp_finance_operations WHERE operation_id IN ('IT26_LET_ALLOC_A','IT26_LET_ALLOC_B');
 DELETE FROM public.factures WHERE facture_id='IT26_LET_INVOICE' AND client_id='IT26_LET_CLIENT';
 DELETE FROM public.reglements WHERE reglement_id='IT26_LET_PAYMENT' AND partenaire_id='IT26_LET_CLIENT';
 DELETE FROM public.clients WHERE client_id='IT26_LET_CLIENT';
 DELETE FROM public.comptes WHERE compte_id='IT26_LET_CASH';
END $guard$;
COMMIT;
