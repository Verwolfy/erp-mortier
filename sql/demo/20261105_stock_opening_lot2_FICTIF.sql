-- Lot DEMO26 complémentaire : mouvements d'ouverture de stocks déjà existants.
-- Ne change jamais les soldes actuels, ne crée aucune pièce fiscale.
BEGIN;
DO $g$ BEGIN
  IF (SELECT quantite_disponible FROM public.stock_actuel WHERE mp_id='DEMO26_MP2') IS DISTINCT FROM 220
     OR (SELECT quantite_disponible FROM public.stock_actuel_pf WHERE sku_id='DEMO26_SKU2') IS DISTINCT FROM 60
     OR EXISTS (SELECT 1 FROM public.mouvements WHERE mouvement_id='DEMO26_MV2')
     OR EXISTS (SELECT 1 FROM public.mouvements_pf WHERE mouvement_pf_id='DEMO26_MVP2')
  THEN RAISE EXCEPTION 'État de démonstration inattendu : annulation'; END IF;
END $g$;
INSERT INTO public.mouvements(mouvement_id,date,type_mouvement,mp_id,quantite,reference,prix_entree)
VALUES ('DEMO26_MV2','2026-11-01','ENTREE','DEMO26_MP2',220,'DEMO26_STOCK_INITIAL',250);
INSERT INTO public.mouvements_pf(mouvement_pf_id,date,type_mouvement,sku_id,quantite,reference,cout_unitaire)
VALUES ('DEMO26_MVP2','2026-11-01','ENTREE','DEMO26_SKU2',60,'DEMO26_STOCK_INITIAL',1500);
COMMIT;
