-- EXCLUSIVEMENT erp-mortier-test ffuhbmcfyexsbjwhryvj.
-- Nettoyage STRICT des fixtures de clôture OF concurrente.
BEGIN;
SET LOCAL statement_timeout='30000ms';
DO $safe$
DECLARE v_of text; v_rec text;
BEGIN
 SELECT result_payload->>'of_id' INTO v_of FROM public.erp_production_creations
 WHERE operation_id='IT26_OFR_OF';
 SELECT result_payload->>'recette_id' INTO v_rec FROM public.erp_production_creations
 WHERE operation_id='IT26_OFR_RECIPE';
 IF v_of IS NULL OR v_rec IS NULL
 OR (SELECT pf_id FROM public.ordres_fabrication WHERE of_id=v_of) IS DISTINCT FROM 'IT26_OFR_PF'
 OR (SELECT pf_id FROM public.recettes WHERE recette_id=v_rec) IS DISTINCT FROM 'IT26_OFR_PF'
 THEN RAISE EXCEPTION 'Fixtures OF non reconnues : refus de nettoyage'; END IF;
 IF EXISTS(SELECT 1 FROM public.ordres_fabrication
           WHERE recette_id=v_rec AND of_id<>v_of)
 OR EXISTS(SELECT 1 FROM public.commandes_ventes WHERE client_id LIKE 'IT26_OFR_%')
 THEN RAISE EXCEPTION 'Dépendances inattendues : nettoyage refusé'; END IF;
 DELETE FROM public.mouvements_pf WHERE sku_id='IT26_OFR_SKU';
 DELETE FROM public.mouvements WHERE mp_id IN ('IT26_OFR_RAW','IT26_OFR_PACK');
 DELETE FROM public.consommations_of WHERE of_id=v_of;
 DELETE FROM public.controle_qualite WHERE of_id=v_of;
 DELETE FROM public.erp_of_outbox WHERE of_id=v_of;
 DELETE FROM public.erp_of_closures WHERE of_id=v_of;
 DELETE FROM public.ordres_fabrication WHERE of_id=v_of;
 DELETE FROM public.erp_production_creations WHERE operation_id IN ('IT26_OFR_RECIPE','IT26_OFR_OF');
 DELETE FROM public.lignes_recette WHERE recette_id=v_rec;
 DELETE FROM public.recettes WHERE recette_id=v_rec;
 DELETE FROM public.lots WHERE (type_item='MP' AND item_id IN ('IT26_OFR_RAW','IT26_OFR_PACK'))
   OR (type_item='PF' AND item_id='IT26_OFR_SKU');
 DELETE FROM public.stock_actuel WHERE mp_id IN ('IT26_OFR_RAW','IT26_OFR_PACK');
 DELETE FROM public.stock_actuel_pf WHERE sku_id='IT26_OFR_SKU';
 DELETE FROM public.erp_stock_outbox
  WHERE operation_id IN (SELECT operation_id FROM public.erp_stock_operations
                         WHERE request_payload->>'item_id' IN
                         ('IT26_OFR_RAW','IT26_OFR_PACK','IT26_OFR_SKU'));
 DELETE FROM public.erp_stock_operations WHERE request_payload->>'item_id' IN
                         ('IT26_OFR_RAW','IT26_OFR_PACK','IT26_OFR_SKU');
 DELETE FROM public.sku_conditionnement WHERE sku_id='IT26_OFR_SKU';
 DELETE FROM public.produits WHERE pf_id='IT26_OFR_PF';
 DELETE FROM public.matieres_premieres WHERE mp_id IN ('IT26_OFR_RAW','IT26_OFR_PACK');
END
$safe$;
COMMIT;
