-- EXCLUSIVEMENT TEST ffuhbmcfyexsbjwhryvj. Lecture seule.
WITH of_ref AS (SELECT result_payload->>'of_id' AS id
 FROM public.erp_production_creations WHERE operation_id='IT26_OFR_OF')
SELECT
 (SELECT count(*) FROM public.erp_of_closures WHERE of_id=(SELECT id FROM of_ref)) AS closures,
 (SELECT count(*) FROM public.controle_qualite WHERE of_id=(SELECT id FROM of_ref)) AS controles,
 (SELECT statut FROM public.ordres_fabrication WHERE of_id=(SELECT id FROM of_ref)) AS statut,
 (SELECT quantite_disponible FROM public.stock_actuel WHERE mp_id='IT26_OFR_RAW') AS mp_restante,
 (SELECT quantite_disponible FROM public.stock_actuel WHERE mp_id='IT26_OFR_PACK') AS emballage_restant,
 (SELECT quantite_disponible FROM public.stock_actuel_pf WHERE sku_id='IT26_OFR_SKU') AS pf_produit,
 (SELECT count(*) FROM public.consommations_of WHERE of_id=(SELECT id FROM of_ref)) AS lignes_consommation;
