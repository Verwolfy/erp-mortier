-- Lecture seule, TEST ffuhbmcfyexsbjwhryvj exclusivement.
SELECT o.operation_id, o.result_payload->>'commande_vente_id' AS commande_vente_id,
 (SELECT count(*) FROM public.commandes_ventes v WHERE v.commande_vente_id=o.result_payload->>'commande_vente_id') AS commandes,
 (SELECT count(*) FROM public.lignes_commande_ventes l WHERE l.commande_vente_id=o.result_payload->>'commande_vente_id') AS lignes,
 (SELECT count(*) FROM public.erp_sales_order_creations z WHERE z.operation_id='IT26_PAR_ORDER') AS journaux,
 (SELECT count(*) FROM public.commandes_ventes v WHERE v.client_id='IT26_PAR_CLIENT') AS commandes_client_test
FROM public.erp_sales_order_creations o WHERE o.operation_id='IT26_PAR_ORDER';
