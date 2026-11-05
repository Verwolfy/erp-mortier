-- Exclusivement TEST ffuhbmcfyexsbjwhryvj. Refuser toute dépendance inconnue.
BEGIN;
SET LOCAL statement_timeout='30s';
DO $guard$
BEGIN
 IF EXISTS (SELECT 1 FROM public.mouvements WHERE mp_id='IT26_CUMPR_MP'
      AND reference NOT IN ('[TEST] CUMPR INITIAL','[TEST] CUMPR ENTREE A','[TEST] CUMPR ENTREE B','[TEST] CUMPR SORTIE'))
 OR EXISTS (SELECT 1 FROM public.erp_stock_operations
   WHERE request_payload->>'item_id'='IT26_CUMPR_MP'
   AND operation_id NOT IN ('IT26_CUMPR_IN0','IT26_CUMPR_INA','IT26_CUMPR_INB','IT26_CUMPR_OUT'))
 OR EXISTS (SELECT 1 FROM public.lots WHERE item_id='IT26_CUMPR_MP' AND type_item<>'MP')
 THEN RAISE EXCEPTION 'Nettoyage CUMPR interdit : dependance inconnue'; END IF;
 DELETE FROM public.mouvements WHERE mp_id='IT26_CUMPR_MP';
 DELETE FROM public.erp_stock_outbox
   WHERE operation_id IN ('IT26_CUMPR_IN0','IT26_CUMPR_INA','IT26_CUMPR_INB','IT26_CUMPR_OUT');
 DELETE FROM public.erp_stock_operations
   WHERE operation_id IN ('IT26_CUMPR_IN0','IT26_CUMPR_INA','IT26_CUMPR_INB','IT26_CUMPR_OUT');
 DELETE FROM public.lots WHERE item_id='IT26_CUMPR_MP' AND type_item='MP';
 DELETE FROM public.stock_actuel WHERE mp_id='IT26_CUMPR_MP';
 DELETE FROM public.matieres_premieres WHERE mp_id='IT26_CUMPR_MP';
END $guard$;
COMMIT;
