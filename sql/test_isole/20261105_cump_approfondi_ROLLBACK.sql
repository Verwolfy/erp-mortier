-- Test CUMP approfondi, TEST UNIQUEMENT: Supabase ffuhbmcfyexsbjwhryvj
-- AUCUN COMMIT. Fixtures fictives dans une unique transaction ROLLBACK.
-- Les assertions font échouer le test à la première incohérence.
BEGIN;
SET LOCAL statement_timeout = '60s';
DO $cump$
DECLARE
  v_qty numeric;
  v_cmp numeric;
  v_result jsonb;
  v_first jsonb;
  v_count integer;
  v_old_lots numeric;
BEGIN
  IF EXISTS (SELECT 1 FROM public.matieres_premieres WHERE mp_id IN ('IT26_CUMP_MP_A','IT26_CUMP_MP_B'))
     OR EXISTS (SELECT 1 FROM public.produits WHERE pf_id='IT26_CUMP_PF')
     OR EXISTS (SELECT 1 FROM public.sku_conditionnement WHERE sku_id='IT26_CUMP_SKU')
     OR EXISTS (SELECT 1 FROM public.erp_stock_operations WHERE operation_id LIKE 'IT26_CUMP_%')
  THEN RAISE EXCEPTION 'Test interdit : identifiants fictifs deja utilises'; END IF;

  INSERT INTO public.matieres_premieres(mp_id,nom,categorie_mp,unite_stock,actif)
  VALUES ('IT26_CUMP_MP_A','[TEST] CUMP prix variables','Granulat','kg','OUI'),
         ('IT26_CUMP_MP_B','[TEST] CUMP decimales','Granulat','kg','OUI');
  INSERT INTO public.produits(pf_id,nom,categorie_pf,unite_production,actif)
  VALUES ('IT26_CUMP_PF','[TEST] CUMP produit fini','Mortier','KG','OUI');
  INSERT INTO public.sku_conditionnement
  (sku_id,pf_id,format,poids_net,unite_vente,facteur_conversion,prix_vente_defaut,actif)
  VALUES ('IT26_CUMP_SKU','IT26_CUMP_PF','SAC TEST 1KG',1,'SAC',1,42,'OUI');

  -- A1: stock initial 10 kg x 100 => CUMP 100
  PERFORM public.erp_apply_stock_movement('IT26_CUMP_A_IN1','MP','ENTREE','IT26_CUMP_MP_A',10,100,'[TEST] CUMP A IN1',NULL);
  SELECT quantite_disponible,cmp_actuel INTO STRICT v_qty,v_cmp
    FROM public.stock_actuel WHERE mp_id='IT26_CUMP_MP_A';
  IF v_qty<>10 OR v_cmp<>100 THEN RAISE EXCEPTION 'A1 CUMP observe=%, qte=%; attendu 100,10',v_cmp,v_qty; END IF;

  -- A2: (10*100 + 20*130)/30 = 120
  PERFORM public.erp_apply_stock_movement('IT26_CUMP_A_IN2','MP','ENTREE','IT26_CUMP_MP_A',20,130,'[TEST] CUMP A IN2',NULL);
  SELECT quantite_disponible,cmp_actuel INTO STRICT v_qty,v_cmp
    FROM public.stock_actuel WHERE mp_id='IT26_CUMP_MP_A';
  IF v_qty<>30 OR v_cmp<>120 THEN RAISE EXCEPTION 'A2 CUMP observe=%, qte=%; attendu 120,30',v_cmp,v_qty; END IF;

  -- Ordre FIFO deterministe : les horodatages d'insertion en test peuvent etre identiques.
  UPDATE public.lots SET date_creation='2026-11-01 08:00:00'
   WHERE lot_id=(SELECT lot_id FROM public.mouvements
                  WHERE mp_id='IT26_CUMP_MP_A' AND reference='[TEST] CUMP A IN1');
  UPDATE public.lots SET date_creation='2026-11-02 08:00:00'
   WHERE lot_id=(SELECT lot_id FROM public.mouvements
                  WHERE mp_id='IT26_CUMP_MP_A' AND reference='[TEST] CUMP A IN2');
  -- A3: sortie 12: valeur 1440; CUMP INCHANGE 120; stock 18
  v_result := public.erp_apply_stock_movement('IT26_CUMP_A_OUT1','MP','SORTIE','IT26_CUMP_MP_A',12,NULL,'[TEST] CUMP A OUT1',NULL);
  SELECT quantite_disponible,cmp_actuel INTO STRICT v_qty,v_cmp
    FROM public.stock_actuel WHERE mp_id='IT26_CUMP_MP_A';
  IF v_qty<>18 OR v_cmp<>120 OR (v_result->>'cost_total')::numeric<>1440
  THEN RAISE EXCEPTION 'A3: qty %, cmp %, cout %',v_qty,v_cmp,v_result->>'cost_total'; END IF;
  SELECT count(*) INTO v_count FROM public.mouvements
  WHERE mp_id='IT26_CUMP_MP_A' AND reference='[TEST] CUMP A OUT1';
  IF v_count<>2 THEN RAISE EXCEPTION 'A3 FIFO mouvements observe %, attendu 2',v_count; END IF;
  IF EXISTS (SELECT 1 FROM public.mouvements
      WHERE mp_id='IT26_CUMP_MP_A' AND reference='[TEST] CUMP A OUT1' AND prix_entree<>120)
  THEN RAISE EXCEPTION 'A3: cout unitaire sortie != CUMP'; END IF;

  -- A4: (18*120 + 6*90)/24 = 112.5
  PERFORM public.erp_apply_stock_movement('IT26_CUMP_A_IN3','MP','ENTREE','IT26_CUMP_MP_A',6,90,'[TEST] CUMP A IN3',NULL);
  SELECT quantite_disponible,cmp_actuel INTO STRICT v_qty,v_cmp
    FROM public.stock_actuel WHERE mp_id='IT26_CUMP_MP_A';
  IF v_qty<>24 OR v_cmp<>112.5 THEN RAISE EXCEPTION 'A4 CUMP observe %, qte %',v_cmp,v_qty; END IF;

  -- A5: sortie totale valorisee 24*112.5=2700 ; CUMP peut rester memorise.
  PERFORM public.erp_apply_stock_movement('IT26_CUMP_A_OUT2','MP','SORTIE','IT26_CUMP_MP_A',24,NULL,'[TEST] CUMP A OUT2',NULL);
  SELECT quantite_disponible,cmp_actuel INTO STRICT v_qty,v_cmp
    FROM public.stock_actuel WHERE mp_id='IT26_CUMP_MP_A';
  IF v_qty<>0 OR v_cmp<>112.5 THEN RAISE EXCEPTION 'A5 stock vide qte %, cmp %',v_qty,v_cmp; END IF;
  SELECT coalesce(sum(quantite_restante),0) INTO v_old_lots FROM public.lots
  WHERE type_item='MP' AND item_id='IT26_CUMP_MP_A';
  IF v_old_lots<>0 THEN RAISE EXCEPTION 'A5 lots restants % au lieu de 0',v_old_lots; END IF;

  -- A6: nouveau stock apres epuisement : 5 x 55 => CUMP 55 (non 112.5)
  PERFORM public.erp_apply_stock_movement('IT26_CUMP_A_IN4','MP','ENTREE','IT26_CUMP_MP_A',5,55,'[TEST] CUMP A IN4',NULL);
  SELECT quantite_disponible,cmp_actuel INTO STRICT v_qty,v_cmp
    FROM public.stock_actuel WHERE mp_id='IT26_CUMP_MP_A';
  IF v_qty<>5 OR v_cmp<>55 THEN RAISE EXCEPTION 'A6 reinitialisation CUMP observe %, qte %',v_cmp,v_qty; END IF;
  v_first := public.erp_apply_stock_movement('IT26_CUMP_A_OUT3','MP','SORTIE','IT26_CUMP_MP_A',2,NULL,'[TEST] CUMP A OUT3',NULL);
  IF (v_first->>'cost_total')::numeric<>110 OR (v_first->>'quantity_remaining')::numeric<>3
  THEN RAISE EXCEPTION 'A6 cout sortie final inattendu %',v_first; END IF;

  -- A7: rejeu strictement identique : meme resultat et aucune autre ecriture.
  v_result := public.erp_apply_stock_movement('IT26_CUMP_A_OUT3','MP','SORTIE','IT26_CUMP_MP_A',2,NULL,'[TEST] CUMP A OUT3',NULL);
  IF v_result IS DISTINCT FROM v_first THEN RAISE EXCEPTION 'A7 idempotence resultat modifie'; END IF;
  SELECT count(*) INTO v_count FROM public.erp_stock_outbox
  WHERE operation_id='IT26_CUMP_A_OUT3';
  IF v_count<>1 THEN RAISE EXCEPTION 'A7 outbox en double: %',v_count; END IF;
  SELECT quantite_disponible INTO STRICT v_qty FROM public.stock_actuel WHERE mp_id='IT26_CUMP_MP_A';
  IF v_qty<>3 THEN RAISE EXCEPTION 'A7 rejeu a modifie stock %',v_qty; END IF;

  -- A8: protection operation_id contradictoire.
  BEGIN
    PERFORM public.erp_apply_stock_movement('IT26_CUMP_A_OUT3','MP','SORTIE','IT26_CUMP_MP_A',1,NULL,'[TEST] CUMP A OUT3',NULL);
    RAISE EXCEPTION 'A8 ERREUR: rejeu contradictoire accepte';
  EXCEPTION WHEN SQLSTATE '23505' THEN NULL; END;
  -- A9: surconsommation interdite (reste 3, tentative 4).
  BEGIN
    PERFORM public.erp_apply_stock_movement('IT26_CUMP_A_FAIL','MP','SORTIE','IT26_CUMP_MP_A',4,NULL,'[TEST] CUMP A FAIL',NULL);
    RAISE EXCEPTION 'A9 ERREUR: stock negatif accepte';
  EXCEPTION WHEN SQLSTATE '23514' THEN NULL; END;
  -- A10: une sortie avec cout impose est interdite.
  BEGIN
    PERFORM public.erp_apply_stock_movement('IT26_CUMP_A_BAD_COST','MP','SORTIE','IT26_CUMP_MP_A',1,42,'[TEST] CUMP A BAD COST',NULL);
    RAISE EXCEPTION 'A10 ERREUR: cout externe accepte';
  EXCEPTION WHEN SQLSTATE '22023' THEN NULL; END;
  -- A11: prix negatif en entree interdit.
  BEGIN
    PERFORM public.erp_apply_stock_movement('IT26_CUMP_A_NEG','MP','ENTREE','IT26_CUMP_MP_A',1,-1,'[TEST] CUMP A NEG',NULL);
    RAISE EXCEPTION 'A11 ERREUR: cout negatif accepte';
  EXCEPTION WHEN SQLSTATE '22023' THEN NULL; END;
  -- A12: quantite nulle interdite.
  BEGIN
    PERFORM public.erp_apply_stock_movement('IT26_CUMP_A_ZERO','MP','ENTREE','IT26_CUMP_MP_A',0,5,'[TEST] CUMP A ZERO',NULL);
    RAISE EXCEPTION 'A12 ERREUR: quantite nulle acceptee';
  EXCEPTION WHEN SQLSTATE '22023' THEN NULL; END;

  -- B1: precision decimale: (0.1*0.1 + 0.2*0.2) / 0.3 = 1/6.
  PERFORM public.erp_apply_stock_movement('IT26_CUMP_B_IN1','MP','ENTREE','IT26_CUMP_MP_B',0.1,0.1,'[TEST] CUMP B IN1',NULL);
  PERFORM public.erp_apply_stock_movement('IT26_CUMP_B_IN2','MP','ENTREE','IT26_CUMP_MP_B',0.2,0.2,'[TEST] CUMP B IN2',NULL);
  SELECT quantite_disponible,cmp_actuel INTO STRICT v_qty,v_cmp
    FROM public.stock_actuel WHERE mp_id='IT26_CUMP_MP_B';
  IF v_qty<>0.3 OR abs(v_cmp - (1::numeric/6))>0.000000000001
  THEN RAISE EXCEPTION 'B1 precision decimal qty %, CUMP %',v_qty,v_cmp; END IF;
  v_result := public.erp_apply_stock_movement('IT26_CUMP_B_OUT1','MP','SORTIE','IT26_CUMP_MP_B',0.3,NULL,'[TEST] CUMP B OUT1',NULL);
  IF abs((v_result->>'cost_total')::numeric-0.05)>0.000000000001
  THEN RAISE EXCEPTION 'B1 valorisation decimale %',v_result->>'cost_total'; END IF;

  -- PF1 : memes regles sur stock des produits finis, (2*25+3*40)/5 = 34.
  PERFORM public.erp_apply_stock_movement('IT26_CUMP_PF_IN1','PF','ENTREE','IT26_CUMP_SKU',2,25,'[TEST] CUMP PF IN1',NULL);
  PERFORM public.erp_apply_stock_movement('IT26_CUMP_PF_IN2','PF','ENTREE','IT26_CUMP_SKU',3,40,'[TEST] CUMP PF IN2',NULL);
  SELECT quantite_disponible,cout_revient INTO STRICT v_qty,v_cmp
    FROM public.stock_actuel_pf WHERE sku_id='IT26_CUMP_SKU';
  IF v_qty<>5 OR v_cmp<>34 THEN RAISE EXCEPTION 'PF1 CUMP %, qte %',v_cmp,v_qty; END IF;
  v_result := public.erp_apply_stock_movement('IT26_CUMP_PF_OUT1','PF','SORTIE','IT26_CUMP_SKU',1.5,NULL,'[TEST] CUMP PF OUT1',NULL);
  SELECT quantite_disponible,cout_revient INTO STRICT v_qty,v_cmp
    FROM public.stock_actuel_pf WHERE sku_id='IT26_CUMP_SKU';
  IF v_qty<>3.5 OR v_cmp<>34 OR (v_result->>'cost_total')::numeric<>51
  THEN RAISE EXCEPTION 'PF1 sortie qty %, CUMP %, cout %',v_qty,v_cmp,v_result->>'cost_total'; END IF;

  -- Controle de coherence stock / somme des lots et journaux.
  IF EXISTS (
   SELECT 1 FROM public.stock_actuel s WHERE s.mp_id IN ('IT26_CUMP_MP_A','IT26_CUMP_MP_B')
   AND s.quantite_disponible IS DISTINCT FROM
    (SELECT coalesce(sum(quantite_restante),0) FROM public.lots
     WHERE item_id=s.mp_id AND type_item='MP')
  ) THEN RAISE EXCEPTION 'Incoherence stock MP / somme lots'; END IF;
  IF (SELECT quantite_disponible FROM public.stock_actuel_pf WHERE sku_id='IT26_CUMP_SKU')
     IS DISTINCT FROM
    (SELECT coalesce(sum(quantite_restante),0) FROM public.lots
      WHERE item_id='IT26_CUMP_SKU' AND type_item='PF')
  THEN RAISE EXCEPTION 'Incoherence PF / somme lots'; END IF;
  IF (SELECT count(*) FROM public.erp_stock_operations WHERE operation_id LIKE 'IT26_CUMP_%')<>13
  THEN RAISE EXCEPTION 'Nombre d operations de stock inattendu'; END IF;
  IF (SELECT count(*) FROM public.erp_stock_outbox WHERE operation_id LIKE 'IT26_CUMP_%')<>13
  THEN RAISE EXCEPTION 'Nombre deventements outbox inattendu'; END IF;
  RAISE NOTICE 'CUMP_TEST_OK : MP, PF, precision, FIFO distinct, idempotence, controles negatifs';
END $cump$;
SELECT 'CUMP_TEST_OK' AS verdict, 'ROLLBACK obligatoire' AS persistance;
ROLLBACK;
