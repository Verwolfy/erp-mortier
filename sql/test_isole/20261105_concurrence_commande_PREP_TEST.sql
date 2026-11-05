-- UNIQUEMENT erp-mortier-test ffuhbmcfyexsbjwhryvj
-- Prépare les références de test nécessaires aux deux appels CONCURRENTS.
-- Ne jamais exécuter sur la production.
BEGIN;
DO $g$ BEGIN
 IF EXISTS (SELECT 1 FROM public.clients WHERE client_id='IT26_PAR_CLIENT')
 OR EXISTS (SELECT 1 FROM public.erp_sales_order_creations WHERE operation_id='IT26_PAR_ORDER')
 THEN RAISE EXCEPTION 'Les références IT26_PAR existent déjà : inspecter avant de rejouer';
 END IF;
END $g$;
-- Aligne seulement les permissions requises par les FOR SHARE des RPC sur TEST.
GRANT UPDATE ON public.clients,public.produits,public.sku_conditionnement TO service_role;
INSERT INTO public.clients(client_id,nom,actif)
VALUES ('IT26_PAR_CLIENT','[TEST] Concurrence clients','OUI');
INSERT INTO public.produits(pf_id,nom,categorie_pf,unite_production,actif)
VALUES ('IT26_PAR_PF','[TEST] Produit concurrence','Mortier','KG','OUI');
INSERT INTO public.sku_conditionnement(sku_id,pf_id,format,poids_net,unite_vente,
  facteur_conversion,prix_vente_defaut,actif)
VALUES ('IT26_PAR_SKU','IT26_PAR_PF','SAC 1KG',1,'SAC',1,20,'OUI');
COMMIT;
