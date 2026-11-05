-- TEST UNIQUEMENT ffuhbmcfyexsbjwhryvj : nettoyage borné.
BEGIN;
DO $guard$ BEGIN
 IF EXISTS(SELECT 1 FROM public.reglements WHERE reference_trace='IT26_PAR_FINREF'
    AND (partenaire_id<>'IT26_PAR_FINCLI' OR compte_id<>'IT26_PAR_BANK'
         OR montant_total<>50)) THEN
   RAISE EXCEPTION 'Paiement hors paramètres du test : nettoyage refusé';
 END IF;
END $guard$;
DELETE FROM public.ecritures_comptables WHERE document_source_id IN
 (SELECT reglement_id FROM public.reglements WHERE reference_trace='IT26_PAR_FINREF'
    AND compte_id='IT26_PAR_BANK');
DELETE FROM public.erp_finance_outbox WHERE operation_id IN
 ('IT26_PAR_PAY_A','IT26_PAR_PAY_B');
DELETE FROM public.erp_finance_operations WHERE operation_id IN
 ('IT26_PAR_PAY_A','IT26_PAR_PAY_B');
DELETE FROM public.reglements WHERE reference_trace='IT26_PAR_FINREF'
 AND compte_id='IT26_PAR_BANK' AND partenaire_id='IT26_PAR_FINCLI';
DELETE FROM public.comptes WHERE compte_id IN ('IT26_PAR_BANK','IT26_PAR_TIERS');
DELETE FROM public.clients WHERE client_id='IT26_PAR_FINCLI';
COMMIT;
