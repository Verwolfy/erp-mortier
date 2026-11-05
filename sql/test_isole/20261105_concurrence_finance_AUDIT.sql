-- Lecture seule, projet TEST uniquement. Attendu : 1 paiement et 2 écritures.
SELECT (SELECT count(*) FROM public.reglements
 WHERE reference_trace='IT26_PAR_FINREF' AND compte_id='IT26_PAR_BANK') AS paiements,
 (SELECT count(*) FROM public.ecritures_comptables
 WHERE document_source_id IN (SELECT reglement_id FROM public.reglements
 WHERE reference_trace='IT26_PAR_FINREF' AND compte_id='IT26_PAR_BANK')) AS ecritures,
 (SELECT count(*) FROM public.erp_finance_operations WHERE operation_id IN
 ('IT26_PAR_PAY_A','IT26_PAR_PAY_B')) AS operations_reussies;
