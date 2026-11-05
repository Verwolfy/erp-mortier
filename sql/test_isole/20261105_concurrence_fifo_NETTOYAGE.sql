-- TEST UNIQUEMENT ffuhbmcfyexsbjwhryvj ; ne jamais exécuter en production.
BEGIN;
SET LOCAL statement_timeout='30s';
DO $guard$
BEGIN
 IF EXISTS (SELECT 1 FROM public.mouvements WHERE mp_id='IT26_FIFO_MP'
            AND reference NOT IN ('[TEST] FIFO ancien','[TEST] FIFO recent','[TEST] FIFO sortie A','[TEST] FIFO sortie B'))
 OR EXISTS (SELECT 1 FROM public.erp_stock_operations
            WHERE request_payload->>'item_id'='IT26_FIFO_MP'
              AND operation_id NOT IN ('IT26_FIFO_IN_OLD','IT26_FIFO_IN_NEW','IT26_FIFO_OUT_A','IT26_FIFO_OUT_B'))
 OR EXISTS (SELECT 1 FROM public.lots WHERE item_id='IT26_FIFO_MP' AND type_item<>'MP')
 THEN RAISE EXCEPTION 'Dépendance inattendue : nettoyage FIFO refusé'; END IF;
 DELETE FROM public.mouvements WHERE mp_id='IT26_FIFO_MP';
 DELETE FROM public.erp_stock_outbox WHERE operation_id IN
  ('IT26_FIFO_IN_OLD','IT26_FIFO_IN_NEW','IT26_FIFO_OUT_A','IT26_FIFO_OUT_B');
 DELETE FROM public.erp_stock_operations WHERE operation_id IN
  ('IT26_FIFO_IN_OLD','IT26_FIFO_IN_NEW','IT26_FIFO_OUT_A','IT26_FIFO_OUT_B');
 DELETE FROM public.lots WHERE type_item='MP' AND item_id='IT26_FIFO_MP';
 DELETE FROM public.stock_actuel WHERE mp_id='IT26_FIFO_MP';
 DELETE FROM public.matieres_premieres WHERE mp_id='IT26_FIFO_MP';
END $guard$;
COMMIT;
