-- EXCLUSIVEMENT TEST : ffuhbmcfyexsbjwhryvj. Nettoyage ciblé après audit.
BEGIN;
DO $g$
BEGIN
 IF EXISTS(
   SELECT 1 FROM public.erp_sales_order_creations
   WHERE operation_id='IT26_PAR_ORDER'
     AND (result_payload IS NULL
          OR result_payload->>'commande_vente_id' IS NULL
          OR result_payload->>'commande_vente_id' !~ '^CDV-[0-9]+$')
 ) THEN
   RAISE EXCEPTION 'Identifiant commande absent ou inattendu';
 END IF;
 IF EXISTS(
   SELECT 1 FROM public.commandes_ventes v
   JOIN public.erp_sales_order_creations o
     ON v.commande_vente_id=o.result_payload->>'commande_vente_id'
   WHERE o.operation_id='IT26_PAR_ORDER'
     AND (v.client_id<>'IT26_PAR_CLIENT'
          OR EXISTS(SELECT 1 FROM public.bons_livraison b
                    WHERE b.commande_vente_id=v.commande_vente_id)
          OR EXISTS(SELECT 1 FROM public.factures f
                    WHERE f.commande_vente_id=v.commande_vente_id))
 ) THEN
   RAISE EXCEPTION 'Commande liée à une opération externe : suppression bloquée';
 END IF;
END
$g$;
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
-- Les trois GRANT UPDATE de la préparation sont conservés sur TEST
-- pour aligner l'exécution SQL test sur les droits existants en production.
COMMIT;
