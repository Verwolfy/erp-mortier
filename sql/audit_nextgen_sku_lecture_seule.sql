-- Audit NextGen ERP : LECTURE SEULE ; aucune écriture ni modification SQL.
SELECT
 (SELECT count(*) FROM public.sku_conditionnement WHERE sku_id LIKE 'NG-SKU-%' AND actif='OUI') AS sku_actifs,
 (SELECT count(DISTINCT pf_id) FROM public.sku_conditionnement WHERE sku_id LIKE 'NG-SKU-%') AS produits_couverts,
 (SELECT count(*) FROM public.matieres_premieres WHERE mp_id LIKE 'NG-MP-%' AND actif='OUI') AS matieres_candidates_actives,
 (SELECT count(*) FROM public.matieres_premieres WHERE mp_id LIKE 'NG-EMB-%' AND actif='OUI') AS emballages_actifs,
 (SELECT count(*) FROM public.sku_conditionnement WHERE sku_id LIKE 'SKU-00%' AND actif='NON') AS sku_historiques_archives,
 (SELECT count(*) FROM public.sku_conditionnement WHERE sku_id LIKE 'NG-SKU-%' AND prix_vente_defaut IS NOT NULL) AS prix_non_autorises,
 (SELECT count(*) FROM public.stock_actuel_pf WHERE sku_id LIKE 'NG-SKU-%' AND (quantite_disponible <> 0 OR cout_revient IS NOT NULL)) AS stocks_pf_incoherents,
 (SELECT count(*) FROM public.stock_actuel WHERE (mp_id LIKE 'NG-MP-%' OR mp_id LIKE 'NG-EMB-%') AND (quantite_disponible <> 0 OR cmp_actuel IS NOT NULL)) AS stocks_mp_incoherents,
 (SELECT count(*) FROM public.site_products) AS references_web_publiees;
