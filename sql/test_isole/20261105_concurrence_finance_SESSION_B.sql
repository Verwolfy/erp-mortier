-- EXCLUSIVEMENT erp-mortier-test : ffuhbmcfyexsbjwhryvj.
-- SESSION B, parallèle à SESSION A, projet TEST uniquement.
BEGIN;
SET LOCAL statement_timeout='25000ms';
SET LOCAL ROLE service_role;
SELECT public.erp_finance_transaction('PAYMENT','IT26_PAR_PAY_B',jsonb_build_object('date_reglement','2026-11-05','type_flux','ENCAISSEMENT','partenaire_id','IT26_PAR_FINCLI','compte_id','IT26_PAR_BANK','contrepartie_compte_id','IT26_PAR_TIERS','mode_paiement','VIREMENT','reference_trace','IT26_PAR_FINREF','montant_total','50.00')) AS result;
COMMIT;
SELECT operation_id,result_payload FROM public.erp_finance_operations WHERE operation_id IN ('IT26_PAR_PAY_A','IT26_PAR_PAY_B');
