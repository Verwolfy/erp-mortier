-- TEST UNIQUEMENT ffuhbmcfyexsbjwhryvj ; nettoyage versionné obligatoire.
BEGIN;
SET LOCAL statement_timeout='45s';
DO $guard$ BEGIN
 IF EXISTS (SELECT 1 FROM public.matieres_premieres WHERE mp_id='IT26_FIFO_MP')
 OR EXISTS (SELECT 1 FROM public.erp_stock_operations WHERE operation_id LIKE 'IT26_FIFO_%')
 THEN RAISE EXCEPTION 'Fixture FIFO préexistante : arrêter'; END IF;
END $guard$;
INSERT INTO public.matieres_premieres(mp_id,nom,categorie_mp,unite_stock,actif)
VALUES ('IT26_FIFO_MP','[TEST] MP FIFO concurrent','Granulat','kg','OUI');
SET LOCAL ROLE service_role;
SELECT public.erp_apply_stock_movement('IT26_FIFO_IN_OLD','MP','ENTREE','IT26_FIFO_MP',4,5,'[TEST] FIFO ancien','2027-12-01');
SELECT public.erp_apply_stock_movement('IT26_FIFO_IN_NEW','MP','ENTREE','IT26_FIFO_MP',7,6,'[TEST] FIFO recent','2027-11-01');
RESET ROLE;
DO $dates$
DECLARE v_old text; v_new text;
BEGIN
 SELECT lot_id INTO STRICT v_old FROM public.mouvements
 WHERE mp_id='IT26_FIFO_MP' AND reference='[TEST] FIFO ancien' LIMIT 1;
 SELECT lot_id INTO STRICT v_new FROM public.mouvements
 WHERE mp_id='IT26_FIFO_MP' AND reference='[TEST] FIFO recent' LIMIT 1;
 IF v_old=v_new OR v_old IS NULL OR v_new IS NULL THEN
 RAISE EXCEPTION 'Lots non distincts'; END IF;
 UPDATE public.lots SET date_creation='2026-11-01 00:00:00' WHERE lot_id=v_old AND item_id='IT26_FIFO_MP';
 UPDATE public.lots SET date_creation='2026-11-02 00:00:00' WHERE lot_id=v_new AND item_id='IT26_FIFO_MP';
 IF (SELECT count(*) FROM public.lots WHERE item_id='IT26_FIFO_MP')<>2
 OR (SELECT quantite_disponible FROM public.stock_actuel WHERE mp_id='IT26_FIFO_MP')<>11
 THEN RAISE EXCEPTION 'Stock initial FIFO incorrect'; END IF;
END $dates$;
COMMIT;
