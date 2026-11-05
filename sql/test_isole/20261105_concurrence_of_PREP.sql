-- EXCLUSIVEMENT erp-mortier-test ffuhbmcfyexsbjwhryvj.
-- Préparation persistante temporaire, suivie de NETTOYAGE ciblé.
BEGIN;
SET LOCAL statement_timeout='45000ms';
DO $guard$ BEGIN
 IF EXISTS(SELECT 1 FROM public.matieres_premieres WHERE mp_id IN ('IT26_OFR_RAW','IT26_OFR_PACK'))
 OR EXISTS(SELECT 1 FROM public.erp_production_creations WHERE operation_id='IT26_OFR_OF')
 THEN RAISE EXCEPTION 'Fixtures OF concurrents déjà présentes'; END IF;
END $guard$;
GRANT UPDATE ON public.produits,public.matieres_premieres,
 public.sku_conditionnement,public.recettes,public.lignes_recette TO service_role;
INSERT INTO public.matieres_premieres(mp_id,nom,categorie_mp,unite_stock,actif)
VALUES ('IT26_OFR_RAW','[TEST] Matière OF concurrence','Granulat','kg','OUI'),
 ('IT26_OFR_PACK','[TEST] Emballage OF concurrence','EMBALLAGE','U','OUI');
INSERT INTO public.produits(pf_id,nom,categorie_pf,unite_production,actif)
VALUES ('IT26_OFR_PF','[TEST] Produit OF concurrence','Mortier','KG','OUI');
INSERT INTO public.sku_conditionnement
(sku_id,pf_id,format,poids_net,unite_vente,facteur_conversion,emballage_mp_id,prix_vente_defaut,actif)
VALUES ('IT26_OFR_SKU','IT26_OFR_PF','SAC 1KG',1,'SAC',1,'IT26_OFR_PACK',20,'OUI');
SET LOCAL ROLE service_role;
DO $test$
DECLARE v_recipe text; v_of text;
BEGIN
 PERFORM public.erp_apply_stock_movement('IT26_OFR_RAW_IN','MP','ENTREE','IT26_OFR_RAW',10,5,'[TEST] Stock RAW', '2027-11-05');
 PERFORM public.erp_apply_stock_movement('IT26_OFR_PACK_IN','MP','ENTREE','IT26_OFR_PACK',5,1,'[TEST] Stock PACK','2027-11-05');
 v_recipe := (public.erp_create_recipe('IT26_OFR_RECIPE','IT26_OFR_PF','V-RACE',2,'[TEST] recette','2026-11-05',
 '[{"mp_id":"IT26_OFR_RAW","quantite_par_unite":"1"}]'::jsonb))->>'recette_id';
 v_of := (public.erp_create_manufacturing_order('IT26_OFR_OF','IT26_OFR_PF',v_recipe,
 'IT26_OFR_SKU',2,'2026-11-05','[TEST] OF simultané'))->>'of_id';
 PERFORM public.erp_start_manufacturing_order(v_of);
 IF (SELECT statut FROM public.ordres_fabrication WHERE of_id=v_of)<>'EN_COURS'
 THEN RAISE EXCEPTION 'OF préparation incorrect'; END IF;
END
$test$;
RESET ROLE;
COMMIT;
SELECT result_payload FROM public.erp_production_creations WHERE operation_id='IT26_OFR_OF';
