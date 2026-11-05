-- Lecture seule TEST ffuhbmcfyexsbjwhryvj. Attendu 30kg, CMP 100, valeur 3000 DZD.
WITH stats AS (
 SELECT
 (SELECT quantite_disponible FROM public.stock_actuel WHERE mp_id='IT26_CUMPR_MP') AS stock,
 (SELECT cmp_actuel FROM public.stock_actuel WHERE mp_id='IT26_CUMPR_MP') AS cump,
 (SELECT sum(quantite_restante) FROM public.lots WHERE item_id='IT26_CUMPR_MP' AND type_item='MP') AS somme_lots,
 (SELECT count(*) FROM public.lots WHERE item_id='IT26_CUMPR_MP' AND type_item='MP') AS nombre_lots,
 (SELECT count(*) FROM public.mouvements WHERE mp_id='IT26_CUMPR_MP' AND type_mouvement='ENTREE') AS entrees,
 (SELECT coalesce(sum(quantite*prix_entree),0) FROM public.mouvements WHERE mp_id='IT26_CUMPR_MP' AND type_mouvement='ENTREE') AS cout_entrees,
 (SELECT count(*) FROM public.erp_stock_operations WHERE operation_id IN ('IT26_CUMPR_IN0','IT26_CUMPR_INA','IT26_CUMPR_INB') AND result_payload IS NOT NULL) AS operations,
 (SELECT count(*) FROM public.erp_stock_outbox WHERE operation_id IN ('IT26_CUMPR_IN0','IT26_CUMPR_INA','IT26_CUMPR_INB')) AS evenements
)
SELECT *, (stock=30 AND cump=100 AND stock*cump=3000 AND somme_lots=30 AND nombre_lots=3
 AND entrees=3 AND cout_entrees=3000 AND operations=3 AND evenements=3) AS audit_ok FROM stats;
