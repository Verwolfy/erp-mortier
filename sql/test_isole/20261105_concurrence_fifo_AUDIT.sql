-- Lecture seule. Attendu: une sortie réussie, stock 5kg, ancien 0kg et récent 5kg.
WITH stats AS (
 SELECT
 (SELECT quantite_disponible FROM public.stock_actuel WHERE mp_id='IT26_FIFO_MP') AS stock_mp,
 (SELECT count(*) FROM public.erp_stock_operations
  WHERE operation_id IN ('IT26_FIFO_OUT_A','IT26_FIFO_OUT_B') AND result_payload IS NOT NULL) AS sorties_reussies,
 (SELECT count(*) FROM public.mouvements WHERE mp_id='IT26_FIFO_MP' AND type_mouvement='SORTIE') AS mouvements_sortie,
 (SELECT sum(quantite_restante) FROM public.lots WHERE item_id='IT26_FIFO_MP' AND type_item='MP') AS total_lots,
 (SELECT count(*) FROM public.lots WHERE item_id='IT26_FIFO_MP' AND type_item='MP') AS nb_lots
)
SELECT * , (stock_mp=5 AND sorties_reussies=1 AND mouvements_sortie=2 AND total_lots=5 AND nb_lots=2) AS audit_ok FROM stats;
