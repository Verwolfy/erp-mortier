-- Lecture seule : rapprochement des stocks globaux et des quantités restantes en lots.
-- Exécuter d'abord sur la base de TEST. Chaque ligne retournée doit être examinée.
WITH lot_totals AS (
    SELECT type_item, item_id, sum(coalesce(quantite_restante, 0)) AS lots_quantity,
           count(*) AS number_of_lots
    FROM public.lots
    WHERE type_item IN ('MP','PF')
    GROUP BY type_item, item_id
), balances AS (
    SELECT 'MP'::text AS type_item, mp_id::text AS item_id,
           coalesce(quantite_disponible, 0) AS stock_quantity
      FROM public.stock_actuel
    UNION ALL
    SELECT 'PF'::text, sku_id::text, coalesce(quantite_disponible, 0)
      FROM public.stock_actuel_pf
)
SELECT coalesce(b.type_item, l.type_item) AS type_item,
       coalesce(b.item_id, l.item_id) AS item_id,
       b.stock_quantity,
       coalesce(l.lots_quantity, 0) AS lots_quantity,
       coalesce(l.number_of_lots, 0) AS number_of_lots,
       CASE WHEN b.item_id IS NULL THEN 'LOTS SANS STOCK GLOBAL'
            WHEN b.stock_quantity < 0 THEN 'STOCK NEGATIF'
            WHEN l.lots_quantity < 0 THEN 'LOTS NEGATIFS'
            ELSE 'ECART DE STOCK' END AS anomalie
FROM balances b
FULL OUTER JOIN lot_totals l
  ON l.type_item = b.type_item AND l.item_id = b.item_id
WHERE b.item_id IS NULL OR b.stock_quantity IS DISTINCT FROM coalesce(l.lots_quantity, 0)
ORDER BY type_item, item_id;

-- Les résultats ne corrigent rien automatiquement.
