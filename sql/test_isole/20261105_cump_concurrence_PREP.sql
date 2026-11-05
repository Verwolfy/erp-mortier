-- Exclusivement TEST ffuhbmcfyexsbjwhryvj. A exécuter après publication du nettoyage.
BEGIN;
SET LOCAL statement_timeout='30s';
DO $guard$ BEGIN
 IF EXISTS (SELECT 1 FROM public.matieres_premieres WHERE mp_id='IT26_CUMPR_MP')
 OR EXISTS (SELECT 1 FROM public.erp_stock_operations WHERE operation_id LIKE 'IT26_CUMPR_%')
 OR EXISTS (SELECT 1 FROM public.lots WHERE item_id='IT26_CUMPR_MP')
 THEN RAISE EXCEPTION 'Fixtures CUMPR preexistantes'; END IF;
END $guard$;
INSERT INTO public.matieres_premieres(mp_id,nom,categorie_mp,unite_stock,actif)
VALUES ('IT26_CUMPR_MP','[TEST] Reception CUMP concurrente','Granulat','kg','OUI');
SET LOCAL ROLE service_role;
SELECT public.erp_apply_stock_movement('IT26_CUMPR_IN0','MP','ENTREE','IT26_CUMPR_MP',10,100,'[TEST] CUMPR INITIAL',NULL);
RESET ROLE;
DO $audit$ BEGIN
 IF (SELECT quantite_disponible FROM public.stock_actuel WHERE mp_id='IT26_CUMPR_MP')<>10
 OR (SELECT cmp_actuel FROM public.stock_actuel WHERE mp_id='IT26_CUMPR_MP')<>100
 THEN RAISE EXCEPTION 'CUMP initial != 100'; END IF;
END $audit$;
COMMIT;
