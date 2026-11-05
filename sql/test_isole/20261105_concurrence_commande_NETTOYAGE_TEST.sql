-- UNIQUEMENT TEST ffuhbmcfyexsbjwhryvj. Éxécuter après contrôle des résultats.
-- Ne supprime que les identifiants du test concurrentiel.
BEGIN;
DO $g$ BEGIN
 IF EXISTS(SELECT 1 FROM public.erp_sales_order_creations
           WHERE operation_id='IT26_PAR_ORDER' AND
           result_payload->>'commande_vente_id' NOT LIKE 'CDV-%')
 THEN RAISE EXCEPTION 'Identifiant commande inattendu'; END IF;
END $g$;
DELETE FROM public.lignes_commande_ventes WHERE commande_vente_id IN
 (SELECT result_payload->>'commande_vente_id' FROM public.erp_sales_order_creations
  WHERE operation_id='IT26_PAR_ORDER');
DELETE FROM public.commandes_ventes WHERE commande_vente_id IN
 (SELECT result_payload->>'commande_vente_id' FROM public.erp_sales_order_creations
  WHERE operation_id='IT26_PAR_ORDER');
DELETE FROM public.erp_sales_order_creations WHERE operation_id='IT26_PAR_ORDER';
DELETE FROM public.sku_conditionnement WHERE sku_id='IT26_PAR_SKU';
DELETE FROM public.produits WHERE pf_id='IT26_PAR_PF';
DELETE FROM public.clients WHERE client_id='IT26_PAR_CLIENT';
-- Conserver les GRANT TEST, intentionnellement alignés sur les droits de production.
COMMIT;
