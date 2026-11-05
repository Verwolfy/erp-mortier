-- TEST ISOLÉ - EXCLUSIVEMENT ffuhbmcfyexsbjwhryvj (erp-mortier-test).
-- Production/qualité via vraies RPC. Aucun COMMIT : ROLLBACK final.
BEGIN;
SET LOCAL statement_timeout='45s';
-- Alignement ÉPHÉMÈRE des GRANTs TEST sur les droits production :
-- restauré automatiquement par ROLLBACK, sans changement durable.
GRANT UPDATE ON public.produits, public.matieres_premieres,
  public.sku_conditionnement, public.recettes,
  public.clients, public.fournisseurs, public.lignes_recette TO service_role;
INSERT INTO public.matieres_premieres(mp_id,nom,categorie_mp,unite_stock,actif)
VALUES ('IT26_RAW','[TEST] Liant','Granulat','kg','OUI'),
       ('IT26_PACK','[TEST] Sac','EMBALLAGE','U','OUI');
INSERT INTO public.produits(pf_id,nom,categorie_pf,unite_production,actif)
VALUES ('IT26_PF','[TEST] Mortier','Mortier','KG','OUI');
INSERT INTO public.sku_conditionnement
(sku_id,pf_id,format,poids_net,unite_vente,facteur_conversion,emballage_mp_id,prix_vente_defaut,actif)
VALUES ('IT26_SKU','IT26_PF','SAC 1KG',1,'SAC',1,'IT26_PACK',20,'OUI');
SET LOCAL ROLE service_role;
DO $test$
DECLARE
  a jsonb; b jsonb; recipe_id text; v_of_id text; v_reject_id text;
  q numeric;
  lines jsonb:='[{"mp_id":"IT26_RAW","quantite_par_unite":"1"}]'::jsonb;
BEGIN
  PERFORM public.erp_apply_stock_movement('IT26_STOCK_RAW','MP','ENTREE','IT26_RAW',10,5,'[TEST] appro', '2027-11-05');
  PERFORM public.erp_apply_stock_movement('IT26_STOCK_PACK','MP','ENTREE','IT26_PACK',5,1,'[TEST] emballage','2027-11-05');
  a:=public.erp_create_recipe('IT26_OP_RECIPE','IT26_PF','V-TEST',2,'[TEST] recette','2026-11-05',lines);
  b:=public.erp_create_recipe('IT26_OP_RECIPE','IT26_PF','V-TEST',2,'[TEST] recette','2026-11-05',lines);
  IF a IS DISTINCT FROM b THEN RAISE EXCEPTION 'Recette non idempotente'; END IF;
  recipe_id:=a->>'recette_id';
  BEGIN
    PERFORM public.erp_create_recipe('IT26_OP_RECIPE','IT26_PF','V-DIFF',2,'[TEST] recette','2026-11-05',lines);
    RAISE EXCEPTION 'Recette contradictoire acceptée';
  EXCEPTION WHEN unique_violation THEN NULL;
  END;
  a:=public.erp_create_manufacturing_order('IT26_OP_OF','IT26_PF',recipe_id,'IT26_SKU',2,'2026-11-05','[TEST] OF');
  b:=public.erp_create_manufacturing_order('IT26_OP_OF','IT26_PF',recipe_id,'IT26_SKU',2,'2026-11-05','[TEST] OF');
  IF a IS DISTINCT FROM b THEN RAISE EXCEPTION 'OF non idempotent'; END IF;
  v_of_id:=a->>'of_id';
  IF a->>'statut' <> 'PLANIFIE' THEN RAISE EXCEPTION 'Création OF non planifiée'; END IF;
  a:=public.erp_start_manufacturing_order(v_of_id);
  b:=public.erp_start_manufacturing_order(v_of_id);
  IF a IS DISTINCT FROM b OR a->>'statut'<>'EN_COURS' THEN
     RAISE EXCEPTION 'Démarrage OF non idempotent'; END IF;
  a:=public.erp_close_manufacturing_order(v_of_id,'OUI','[TEST] conforme','TESTEUR',2,'IT26_PACK',2);
  b:=public.erp_close_manufacturing_order(v_of_id,'OUI','[TEST] conforme','TESTEUR',2,'IT26_PACK',2);
  IF a IS DISTINCT FROM b OR a->>'statut'<>'TERMINE'
    THEN RAISE EXCEPTION 'Clôture qualité non idempotente'; END IF;
  BEGIN
    PERFORM public.erp_close_manufacturing_order(v_of_id,'NON','[TEST] contradictoire','TESTEUR',0,NULL,0);
    RAISE EXCEPTION 'Clôture contradictoire acceptée';
  EXCEPTION WHEN unique_violation THEN NULL;
  END;
  BEGIN
    PERFORM public.erp_start_manufacturing_order(v_of_id);
    RAISE EXCEPTION 'Re-démarrage d un OF clos accepté';
  EXCEPTION WHEN check_violation THEN NULL;
  END;
  -- Branche contrôle qualité NON : transition vers REJETE sans produire ni prélever.
  a:=public.erp_create_manufacturing_order('IT26_OP_OF_REJECT','IT26_PF',recipe_id,
                                           'IT26_SKU',1,'2026-11-05','[TEST] OF rejet');
  v_reject_id:=a->>'of_id';
  PERFORM public.erp_start_manufacturing_order(v_reject_id);
  a:=public.erp_close_manufacturing_order(v_reject_id,'NON',
                                          '[TEST] contrôle rejeté','TESTEUR',0,NULL,0);
  b:=public.erp_close_manufacturing_order(v_reject_id,'NON',
                                          '[TEST] contrôle rejeté','TESTEUR',0,NULL,0);
  IF a IS DISTINCT FROM b OR a->>'statut'<>'REJETE'
     OR (SELECT count(*) FROM public.controle_qualite WHERE of_id=v_reject_id)<>1
     OR (SELECT statut FROM public.ordres_fabrication WHERE of_id=v_reject_id)<>'REJETE'
  THEN RAISE EXCEPTION 'OF rejeté non idempotent ou non tracé'; END IF;
  IF (SELECT quantite_disponible FROM public.stock_actuel WHERE mp_id='IT26_RAW') IS DISTINCT FROM 8
    OR (SELECT quantite_disponible FROM public.stock_actuel WHERE mp_id='IT26_PACK') IS DISTINCT FROM 3
    OR (SELECT quantite_disponible FROM public.stock_actuel_pf WHERE sku_id='IT26_SKU') IS DISTINCT FROM 2
    OR (SELECT count(*) FROM public.controle_qualite WHERE of_id=v_of_id)<>1
    OR (SELECT count(*) FROM public.erp_of_closures WHERE erp_of_closures.of_id=v_of_id)<>1
    OR (SELECT statut FROM public.ordres_fabrication WHERE ordres_fabrication.of_id=v_of_id)<>'TERMINE'
  THEN RAISE EXCEPTION 'Stocks/qualité/états OF incohérents'; END IF;
END
$test$;
RESET ROLE;
SELECT 'PRODUCTION_QUALITE_TRANSITIONS_IDEMPOTENCE_OK' AS resultat;
ROLLBACK;
