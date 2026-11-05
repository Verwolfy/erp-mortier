-- TEST EXCLUSIVEMENT: ffuhbmcfyexsbjwhryvj.
-- Parcours achats MP / emballage -> bons de reception -> recette -> 2 OF -> cout du PF.
-- 100% fictif et reversible: aucune ecriture persistante, ROLLBACK final obligatoire.
BEGIN;
SET LOCAL statement_timeout='90s';
DO $scenario$
DECLARE
 v_recipe text; v_of1 text; v_of2 text;
 v_r1 jsonb; v_r2 jsonb;
 v_ca numeric; v_cb numeric; v_cp numeric;
 v_expected2 numeric; v_cmp_pf numeric;
 v_qty numeric; v_val_mp numeric; v_val_pf numeric;
BEGIN
 IF EXISTS (SELECT 1 FROM public.matieres_premieres WHERE mp_id LIKE 'IT26_PFCOST_%')
 OR EXISTS (SELECT 1 FROM public.produits WHERE pf_id='IT26_PFCOST_PF')
 OR EXISTS (SELECT 1 FROM public.sku_conditionnement WHERE sku_id='IT26_PFCOST_SKU')
 OR EXISTS (SELECT 1 FROM public.commandes_achats WHERE commande_achat_id LIKE 'IT26_PFCOST_%')
 OR EXISTS (SELECT 1 FROM public.erp_purchase_operations WHERE operation_id LIKE 'IT26_PFCOST_%')
 OR EXISTS (SELECT 1 FROM public.erp_production_creations WHERE operation_id LIKE 'IT26_PFCOST_%')
 THEN RAISE EXCEPTION 'Fixture IT26_PFCOST preexistante, test refuse'; END IF;

 INSERT INTO public.fournisseurs(fournisseur_id,nom,actif)
 VALUES ('IT26_PFCOST_FOU_RAW','[TEST] Fournisseur granulats','OUI'),
        ('IT26_PFCOST_FOU_PACK','[TEST] Fournisseur sacs','OUI');
 INSERT INTO public.matieres_premieres(mp_id,nom,categorie_mp,unite_stock,actif)
 VALUES ('IT26_PFCOST_RAW_A','[TEST] Charge minerale A','Granulat','kg','OUI'),
        ('IT26_PFCOST_RAW_B','[TEST] Liant B','Granulat','kg','OUI'),
        ('IT26_PFCOST_PACK','[TEST] Sac 5kg','EMBALLAGE','U','OUI');
 INSERT INTO public.produits(pf_id,nom,categorie_pf,unite_production,actif)
 VALUES ('IT26_PFCOST_PF','[TEST] Mortier demonstrateur','Mortier','KG','OUI');
 INSERT INTO public.sku_conditionnement
 (sku_id,pf_id,format,poids_net,unite_vente,facteur_conversion,emballage_mp_id,prix_vente_defaut,actif)
 VALUES ('IT26_PFCOST_SKU','IT26_PFCOST_PF','SAC 5KG',5,'SAC',5,'IT26_PFCOST_PACK',150,'OUI');

 SET LOCAL ROLE service_role;
 -- 1re vague: deux commandes metier distinctes, matieres + emballages.
 PERFORM public.erp_create_purchase_order(
 'IT26_PFCOST_PO1_OP','IT26_PFCOST_PO1','IT26_PFCOST_FOU_RAW',
 'MP','DZD',1,'VIREMENT','30 JOURS','2026-11-30',
 '[{"ligne_achat_id":"IT26_PFCOST_LA1A","mp_id":"IT26_PFCOST_RAW_A","unite_cond":"kg","qte_cond":100,"qte_totale":100,"prix_unitaire":10,"total_devise":1000},{"ligne_achat_id":"IT26_PFCOST_LA1B","mp_id":"IT26_PFCOST_RAW_B","unite_cond":"kg","qte_cond":60,"qte_totale":60,"prix_unitaire":20,"total_devise":1200}]'::jsonb);
 PERFORM public.erp_create_purchase_order(
 'IT26_PFCOST_PO2_OP','IT26_PFCOST_PO2','IT26_PFCOST_FOU_PACK',
 'EMBALLAGE','DZD',1,'VIREMENT','30 JOURS','2026-11-30',
 '[{"ligne_achat_id":"IT26_PFCOST_LA2","mp_id":"IT26_PFCOST_PACK","unite_cond":"U","qte_cond":10,"qte_totale":10,"prix_unitaire":3,"total_devise":30}]'::jsonb);

 PERFORM public.erp_receive_purchase_order(
 'IT26_PFCOST_REC1_OP','IT26_PFCOST_BR1','IT26_PFCOST_PO1',
 '2026-11-05','OUI','[TEST] Recep matieres vague 1','2027-11-05',
 '[{"ligne_br_id":"IT26_PFCOST_LBR1A","mp_id":"IT26_PFCOST_RAW_A","quantite_recue":100,"prix_unitaire":999},{"ligne_br_id":"IT26_PFCOST_LBR1B","mp_id":"IT26_PFCOST_RAW_B","quantite_recue":60,"prix_unitaire":20}]'::jsonb);
 PERFORM public.erp_receive_purchase_order(
 'IT26_PFCOST_REC2_OP','IT26_PFCOST_BR2','IT26_PFCOST_PO2',
 '2026-11-05','OUI','[TEST] Recep emballages vague 1','2027-11-05',
 '[{"ligne_br_id":"IT26_PFCOST_LBR2","mp_id":"IT26_PFCOST_PACK","quantite_recue":10,"prix_unitaire":777}]'::jsonb);

 -- Les prix fictifs manipules dans les lignes BR (999 et 777) ne doivent PAS remplacer les prix des bons de commande.
 -- Couts unitaires de la premiere vague issus du catalogue Achats.
 IF (SELECT cmp_actuel FROM public.stock_actuel WHERE mp_id='IT26_PFCOST_RAW_A') <> 10
 OR (SELECT cmp_actuel FROM public.stock_actuel WHERE mp_id='IT26_PFCOST_RAW_B') <> 20
 OR (SELECT cmp_actuel FROM public.stock_actuel WHERE mp_id='IT26_PFCOST_PACK') <> 3
 THEN RAISE EXCEPTION 'CUMP MP initial incompatible avec les achats'; END IF;

 v_recipe := (public.erp_create_recipe(
 'IT26_PFCOST_RECIPE_OP','IT26_PFCOST_PF','V-COST',1,
 '[TEST] 0,6kg charge et 0,4kg liant par 1kg mortier; emballage hors recette',
 '2026-11-05',
 '[{"mp_id":"IT26_PFCOST_RAW_A","quantite_par_unite":"0.6"},{"mp_id":"IT26_PFCOST_RAW_B","quantite_par_unite":"0.4"}]'::jsonb))->>'recette_id';
 v_of1 := (public.erp_create_manufacturing_order(
 'IT26_PFCOST_OF1_OP','IT26_PFCOST_PF',v_recipe,'IT26_PFCOST_SKU',
 4,'2026-11-05','[TEST] Premier lot 4 sacs'))->>'of_id';
 PERFORM public.erp_start_manufacturing_order(v_of1);
 v_r1 := public.erp_close_manufacturing_order(
 v_of1,'OUI','[TEST] Controle conforme lot 1','[TEST] Qualite',4,'IT26_PFCOST_PACK',4);
 -- 4 sacs de 5kg -> RAW_A=12kg, RAW_B=8kg, emballage=4U.
 -- Cout = 12*10 + 8*20 + 4*3 = 292 DZD, 73 DZD/sac.
 IF (v_r1->>'cout_total')::numeric <>292
 OR (v_r1->>'quantite_base')::numeric<>20
 OR (SELECT cout_revient FROM public.stock_actuel_pf WHERE sku_id='IT26_PFCOST_SKU')<>73
 OR (SELECT quantite_disponible FROM public.stock_actuel_pf WHERE sku_id='IT26_PFCOST_SKU')<>4
 THEN RAISE EXCEPTION 'OF1 cout attendu 292, observe %, PF %',v_r1,
 (SELECT row_to_json(s) FROM public.stock_actuel_pf s WHERE sku_id='IT26_PFCOST_SKU'); END IF;

 -- La cloture identique du meme OF ne doit ni doubler la production ni les couts.
 IF public.erp_close_manufacturing_order(
    v_of1,'OUI','[TEST] Controle conforme lot 1','[TEST] Qualite',4,'IT26_PFCOST_PACK',4)
    IS DISTINCT FROM v_r1 THEN
   RAISE EXCEPTION 'OF1 non idempotent'; END IF;
 IF (SELECT count(*) FROM public.erp_of_outbox WHERE of_id=v_of1)<>1 THEN
   RAISE EXCEPTION 'OF1 outbox duplique'; END IF;

 -- 2e vague de commandes, receptionnee apres fabrication initiale.
 PERFORM public.erp_create_purchase_order(
 'IT26_PFCOST_PO3_OP','IT26_PFCOST_PO3','IT26_PFCOST_FOU_RAW',
 'MP','DZD',1,'VIREMENT','30 JOURS','2026-11-30',
 '[{"ligne_achat_id":"IT26_PFCOST_LA3A","mp_id":"IT26_PFCOST_RAW_A","unite_cond":"kg","qte_cond":100,"qte_totale":100,"prix_unitaire":14,"total_devise":1400},{"ligne_achat_id":"IT26_PFCOST_LA3B","mp_id":"IT26_PFCOST_RAW_B","unite_cond":"kg","qte_cond":40,"qte_totale":40,"prix_unitaire":30,"total_devise":1200}]'::jsonb);
 PERFORM public.erp_create_purchase_order(
 'IT26_PFCOST_PO4_OP','IT26_PFCOST_PO4','IT26_PFCOST_FOU_PACK',
 'EMBALLAGE','DZD',1,'VIREMENT','30 JOURS','2026-11-30',
 '[{"ligne_achat_id":"IT26_PFCOST_LA4","mp_id":"IT26_PFCOST_PACK","unite_cond":"U","qte_cond":10,"qte_totale":10,"prix_unitaire":5,"total_devise":50}]'::jsonb);
 PERFORM public.erp_receive_purchase_order(
 'IT26_PFCOST_REC3_OP','IT26_PFCOST_BR3','IT26_PFCOST_PO3',
 '2026-11-05','OUI','[TEST] Recep matieres vague 2','2027-11-05',
 '[{"ligne_br_id":"IT26_PFCOST_LBR3A","mp_id":"IT26_PFCOST_RAW_A","quantite_recue":100,"prix_unitaire":14},{"ligne_br_id":"IT26_PFCOST_LBR3B","mp_id":"IT26_PFCOST_RAW_B","quantite_recue":40,"prix_unitaire":30}]'::jsonb);
 PERFORM public.erp_receive_purchase_order(
 'IT26_PFCOST_REC4_OP','IT26_PFCOST_BR4','IT26_PFCOST_PO4',
 '2026-11-05','OUI','[TEST] Recep emballages vague 2','2027-11-05',
 '[{"ligne_br_id":"IT26_PFCOST_LBR4","mp_id":"IT26_PFCOST_PACK","quantite_recue":10,"prix_unitaire":5}]'::jsonb);

 -- CUMP exacts apres sorties et nouveaux achats.
 -- A: (88*10+100*14)/188 = 570/47 ; B: (52*20+40*30)/92 = 560/23
 -- Sac: (6*3+10*5)/16 = 4,25
 SELECT cmp_actuel INTO v_ca FROM public.stock_actuel WHERE mp_id='IT26_PFCOST_RAW_A';
 SELECT cmp_actuel INTO v_cb FROM public.stock_actuel WHERE mp_id='IT26_PFCOST_RAW_B';
 SELECT cmp_actuel INTO v_cp FROM public.stock_actuel WHERE mp_id='IT26_PFCOST_PACK';
 IF abs(v_ca-(570::numeric/47))>0.00000000001
 OR abs(v_cb-(560::numeric/23))>0.00000000001
 OR v_cp<>4.25
 THEN RAISE EXCEPTION 'CUMP vague 2 differe oracle: A %, B %, sac %',v_ca,v_cb,v_cp; END IF;

 v_of2 := (public.erp_create_manufacturing_order(
 'IT26_PFCOST_OF2_OP','IT26_PFCOST_PF',v_recipe,'IT26_PFCOST_SKU',
 2,'2026-11-05','[TEST] Second lot 2 sacs apres changement prix'))->>'of_id';
 PERFORM public.erp_start_manufacturing_order(v_of2);
 -- Tentative de cloture avec un seul sac pour deux SKU : refus 23514 obligatoire.
 DECLARE
   v_rejected boolean := false;
 BEGIN
   BEGIN
     PERFORM public.erp_close_manufacturing_order(
       v_of2,'OUI','[TEST] Emballage insuffisant','[TEST] Qualite',2,'IT26_PFCOST_PACK',1);
   EXCEPTION WHEN SQLSTATE '23514' THEN v_rejected := true;
   END;
   IF NOT v_rejected THEN RAISE EXCEPTION 'Emballage insuffisant accepte'; END IF;
 END;
 v_r2 := public.erp_close_manufacturing_order(
 v_of2,'OUI','[TEST] Controle conforme lot 2','[TEST] Qualite',2,'IT26_PFCOST_PACK',2);
 v_expected2 := 6*(570::numeric/47) + 4*(560::numeric/23) + 2*4.25;
 -- COUT TOTAL OF2 stocke arrondi a 2 decimales ; stock PF a precision CUMP.
 SELECT quantite_disponible,cout_revient INTO STRICT v_qty,v_cmp_pf
 FROM public.stock_actuel_pf WHERE sku_id='IT26_PFCOST_SKU';
 IF (v_r2->>'cout_total')::numeric<>round(v_expected2,2)
 OR v_qty<>6
 OR abs(v_cmp_pf-((292+v_expected2)/6))>0.00000000001
 THEN RAISE EXCEPTION 'OF2 cout ou CUMP PF faux: output %, qte %, cmp %, expected2 %',
 v_r2,v_qty,v_cmp_pf,v_expected2; END IF;

 -- Coherence physique et conservation valorisee : achats 4880 DZD.
 IF (SELECT quantite_disponible FROM public.stock_actuel WHERE mp_id='IT26_PFCOST_RAW_A')<>182
 OR (SELECT quantite_disponible FROM public.stock_actuel WHERE mp_id='IT26_PFCOST_RAW_B')<>88
 OR (SELECT quantite_disponible FROM public.stock_actuel WHERE mp_id='IT26_PFCOST_PACK')<>14
 OR (SELECT count(*) FROM public.consommations_of WHERE of_id IN (v_of1,v_of2))<>6
 OR (SELECT count(*) FROM public.bons_reception WHERE bon_reception_id LIKE 'IT26_PFCOST_%')<>4
 OR (SELECT count(*) FROM public.commandes_achats WHERE commande_achat_id LIKE 'IT26_PFCOST_%')<>4
 OR (SELECT count(*) FROM public.lignes_bons_reception WHERE bon_reception_id LIKE 'IT26_PFCOST_%')<>6
 THEN RAISE EXCEPTION 'Traçabilite recette/achats ou quantites finales incoherentes'; END IF;
 SELECT coalesce(sum(quantite_disponible*cmp_actuel),0) INTO v_val_mp
 FROM public.stock_actuel WHERE mp_id IN ('IT26_PFCOST_RAW_A','IT26_PFCOST_RAW_B','IT26_PFCOST_PACK');
 v_val_pf := v_qty*v_cmp_pf;
 IF abs((v_val_mp+v_val_pf)-4880)>0.00000001
 THEN RAISE EXCEPTION 'Conservation valorisation non respectee: MP %, PF %, total %',
 v_val_mp,v_val_pf,v_val_mp+v_val_pf; END IF;

 -- Trace des deux OFs et des assertions finalisees, sans retention.
 RAISE NOTICE 'PF_COST_OK: OF1=292 (73/sac), OF2=%, PF_CUMP=%, MP_RESTANT=%, PF_VAL=%, GRAND_TOTAL=%',
 round(v_expected2,2),v_cmp_pf,v_val_mp,v_val_pf,v_val_mp+v_val_pf;
END $scenario$;
-- Simulation analytique autonome de frais indirects fictifs, non comptabilises.
-- Ne change ni le cout_total OF ni le CUMP du stock PF.
CREATE TEMP TABLE pg_temp.it26_pf_indirect_costs
 (lot text NOT NULL, nature text NOT NULL,
  montant_dzd numeric NOT NULL CHECK (montant_dzd>=0),
  hypothese text NOT NULL,
  PRIMARY KEY(lot,nature)) ON COMMIT DROP;
INSERT INTO pg_temp.it26_pf_indirect_costs(lot,nature,montant_dzd,hypothese) VALUES
 ('OF1','MAIN_OEUVRE',40,'[TEST] cout fictif de main oeuvre'),
 ('OF1','ENERGIE',20,'[TEST] energie fictive'),
 ('OF1','AMORTISSEMENT',12,'[TEST] dotation analytique fictive'),
 ('OF1','FRAIS_INDIRECTS',8,'[TEST] frais indirects fictifs'),
 ('OF1','FRAIS_APPROCHE',16,'[TEST] frais approche fictifs non imputes aux stocks MP'),
 ('OF2','MAIN_OEUVRE',25,'[TEST] cout fictif de main oeuvre'),
 ('OF2','ENERGIE',15,'[TEST] energie fictive'),
 ('OF2','AMORTISSEMENT',10,'[TEST] dotation analytique fictive'),
 ('OF2','FRAIS_INDIRECTS',5,'[TEST] frais indirects fictifs'),
 ('OF2','FRAIS_APPROCHE',9,'[TEST] frais approche fictifs non imputes aux stocks MP');

DO $analytique$
DECLARE
 v_direct_pf numeric; v_extra numeric; v_analytic numeric;
 v_theory numeric; v_per_sac numeric; v_of1_extra numeric; v_of2_extra numeric;
 v_scrap_sensitivity numeric;
BEGIN
 SELECT quantite_disponible*cout_revient INTO STRICT v_direct_pf
   FROM public.stock_actuel_pf WHERE sku_id='IT26_PFCOST_SKU';
 SELECT sum(montant_dzd) INTO v_extra FROM pg_temp.it26_pf_indirect_costs;
 SELECT sum(montant_dzd) INTO v_of1_extra FROM pg_temp.it26_pf_indirect_costs WHERE lot='OF1';
 SELECT sum(montant_dzd) INTO v_of2_extra FROM pg_temp.it26_pf_indirect_costs WHERE lot='OF2';
 v_theory := 292 + (6*(570::numeric/47) + 4*(560::numeric/23) + 2*4.25);
 v_analytic := v_direct_pf + v_extra;
 v_per_sac := v_analytic/6;
 IF abs(v_direct_pf-v_theory)>0.00000001
 OR v_of1_extra<>96 OR v_of2_extra<>64 OR v_extra<>160
 OR abs(v_analytic-(v_theory+160))>0.00000001
 OR abs(v_per_sac-(v_theory+160)/6)>0.00000001
 THEN RAISE EXCEPTION 'Ecart cout industriel test direct %, indirect %, complet %, unitaire %',
 v_direct_pf,v_extra,v_analytic,v_per_sac; END IF;
 IF abs((SELECT cout_revient FROM public.stock_actuel_pf WHERE sku_id='IT26_PFCOST_SKU')
       -(v_theory/6))>0.00000001
 THEN RAISE EXCEPTION 'CUMP officiel a ete pollue par la simulation analytique'; END IF;
 -- Sensibilite purement hypothetique: 1 unite supplementaire consommee mais rebut,
 -- sans sortie commerciale ni modification du stock, et 2 sacs conformes OF2.
 v_scrap_sensitivity := ((v_theory+160) +
       (3*(570::numeric/47)+2*(560::numeric/23)+4.25)) / 6;
 IF v_scrap_sensitivity<=v_per_sac THEN RAISE EXCEPTION 'Sensibilite rebut incorrecte'; END IF;
 RAISE NOTICE 'INDIRECT_COST_OK: cout direct %, charges simulation %, total analytique %, cout par sac %, rebut test %',
 v_direct_pf,v_extra,v_analytic,v_per_sac,v_scrap_sensitivity;
END $analytique$;

SELECT 'INDIRECT_COST_OK' AS verdict,
 round(sum(montant_dzd),2) AS frais_fictifs_dzd,
 round((SELECT quantite_disponible*cout_revient FROM public.stock_actuel_pf
        WHERE sku_id='IT26_PFCOST_SKU')+sum(montant_dzd),2) AS cout_industriel_analytique_dzd,
 round(((SELECT quantite_disponible*cout_revient FROM public.stock_actuel_pf
         WHERE sku_id='IT26_PFCOST_SKU')+sum(montant_dzd))/6,4) AS cout_analytique_par_sac_dzd
FROM pg_temp.it26_pf_indirect_costs;

SELECT 'PF_COST_AND_INDIRECT_COST_OK' AS verdict,
       '2 fournisseurs, 3 MP dont emballage, 4 achats, 4 receptions, 1 recette, 2 OF, 6 sacs' AS campagne,
       round((SELECT quantite_disponible*cout_revient FROM public.stock_actuel_pf WHERE sku_id='IT26_PFCOST_SKU'),4) AS cout_direct_total_dzd,
       round(sum(montant_dzd),2) AS frais_indirects_fictifs_dzd,
       round((SELECT quantite_disponible*cout_revient FROM public.stock_actuel_pf WHERE sku_id='IT26_PFCOST_SKU')+sum(montant_dzd),4) AS cout_analytique_total_dzd,
       round(((SELECT quantite_disponible*cout_revient FROM public.stock_actuel_pf WHERE sku_id='IT26_PFCOST_SKU')+sum(montant_dzd))/6,4) AS cout_analytique_par_sac_dzd,
       round((SELECT cout_revient FROM public.stock_actuel_pf WHERE sku_id='IT26_PFCOST_SKU'),4) AS cump_stock_officiel_direct_dzd,
       'ROLLBACK - fixtures non conservees' AS persistance
FROM pg_temp.it26_pf_indirect_costs;
ROLLBACK;
