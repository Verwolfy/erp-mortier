-- Lecture seule. Attendu: 1 allocation 70 DZD, reste 30 DZD.
WITH stats AS (
 SELECT
 (SELECT count(*) FROM public.lettrage WHERE document_id='IT26_LET_INVOICE'
 AND reglement_id='IT26_LET_PAYMENT') AS allocations,
 (SELECT coalesce(sum(montant_applique),0) FROM public.lettrage WHERE document_id='IT26_LET_INVOICE') AS lettrage_total,
 (SELECT montant_alloue FROM public.reglements WHERE reglement_id='IT26_LET_PAYMENT') AS montant_alloue,
 (SELECT montant_paye FROM public.factures WHERE facture_id='IT26_LET_INVOICE') AS montant_paye,
 (SELECT count(*) FROM public.erp_finance_operations WHERE operation_id IN ('IT26_LET_ALLOC_A','IT26_LET_ALLOC_B')
 AND result_payload IS NOT NULL) AS operations_reussies,
 (SELECT count(*) FROM public.erp_finance_outbox WHERE operation_id IN ('IT26_LET_ALLOC_A','IT26_LET_ALLOC_B')) AS evenements
)
SELECT *, (allocations=1 AND lettrage_total=70 AND montant_alloue=70 AND montant_paye=70 AND operations_reussies=1 AND evenements=1) AS audit_ok
FROM stats;
