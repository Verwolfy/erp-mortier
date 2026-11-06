-- TEST UNIQUEMENT : ffuhbmcfyexsbjwhryvj. Fixtures ephemeres, aucune persistance.
BEGIN;
-- Base fictive de pieces SCF equilibrees, exclusivement dans le BEGIN/ROLLBACK des tests.
DO $fixtures_scf$
DECLARE v_a text; v_b text; v_piece uuid; n integer;
BEGIN
 IF EXISTS(SELECT 1 FROM public.scf_exercices WHERE exercice_id='IT26_COST_EX') THEN
  RAISE EXCEPTION 'Exercice fixture deja present'; END IF;
 IF EXISTS (SELECT 1 FROM public.scf_plan_comptes WHERE numero_compte IN ('69999991','69999992'))
 THEN RAISE EXCEPTION 'Comptes fictifs SCF preexistants'; END IF;
 INSERT INTO public.scf_plan_comptes(numero_compte,libelle,actif,mouvementable) VALUES
 ('69999991','[TEST] Compte analytique debit',true,true),
 ('69999992','[TEST] Compte analytique credit',true,true);
 v_a:='69999991';
 v_b:='69999992';
 INSERT INTO public.scf_exercices(exercice_id,date_debut,date_fin,statut)
 VALUES ('IT26_COST_EX','2026-01-01','2026-12-31','OUVERT');
 INSERT INTO public.scf_journaux(code_journal,libelle) VALUES ('IT26_COST','[TEST] Journal analytique');
 FOR n IN 1..2 LOOP
  v_piece:=gen_random_uuid();
  INSERT INTO public.scf_pieces(
  piece_id,exercice_id,code_journal,reference,document_source,date_ecriture,libelle,statut)
  VALUES (v_piece,'IT26_COST_EX','IT26_COST','IT26_COST_DOC_'||n,
          '[TEST] COST_DOC_'||n,'2026-11-05','[TEST] Piece fictive equilibree','BROUILLON');
  INSERT INTO public.scf_lignes(piece_id,numero,compte,debit,credit)
  VALUES(v_piece,1,v_a,200,0),(v_piece,2,v_b,0,200);
  UPDATE public.scf_pieces SET statut='VALIDEE' WHERE piece_id=v_piece;
 END LOOP;
END $fixtures_scf$;
SET LOCAL statement_timeout='45s';
DO $case$
DECLARE
 a jsonb; v_a numeric; v_b numeric; v_count integer; v_rejected boolean;
BEGIN
 IF EXISTS(SELECT 1 FROM public.ordres_fabrication WHERE of_id IN ('IT26_IND_OF1','IT26_IND_OF2'))
 OR EXISTS(SELECT 1 FROM public.erp_cost_periods WHERE period_id='IT26_IND_PERIOD')
 THEN RAISE EXCEPTION 'Fixture deja presente'; END IF;

 -- OF fictifs uniquement pour validation du referentiel, PAS des fabrications reelles.
 INSERT INTO public.ordres_fabrication(of_id,quantite_prevue,quantite_produite,date_planification,date_fin,statut,cout_total,notes)
 VALUES ('IT26_IND_OF1',10,10,'2026-11-05','2026-11-05','TERMINE',300,'[TEST] OF fictif cout direct'),
        ('IT26_IND_OF2',5,5,'2026-11-05','2026-11-05','TERMINE',200,'[TEST] OF fictif cout direct');
 INSERT INTO public.erp_cost_periods(period_id,libelle,date_debut,date_fin,statut)
 VALUES ('IT26_IND_PERIOD','[TEST] Periode analytique','2026-11-01','2026-11-30','BROUILLON');
 INSERT INTO public.erp_cost_pools(pool_id,period_id,nature_code,base_imputation,montant_dzd,justificatif,statut)
 VALUES ('IT26_IND_POOL_E','IT26_IND_PERIOD','ENERGIE','HOURS_MACHINE',120,'[TEST] facture hypothetique','SIMULATION'),
        ('IT26_IND_POOL_M','IT26_IND_PERIOD','MAIN_OEUVRE','HOURS_LABOR',90,'[TEST] feuille hypothetique','SIMULATION');
 -- Validation avant les assiettes : fail-closed.
 v_rejected:=false;
 BEGIN PERFORM public.erp_cost_validate_period('IT26_IND_PERIOD');
 EXCEPTION WHEN SQLSTATE '23514' THEN v_rejected:=true; END;
 IF NOT v_rejected THEN RAISE EXCEPTION 'Validation incomplete acceptee'; END IF;

 INSERT INTO public.erp_cost_drivers(period_id,of_id,base_imputation,valeur,justificatif) VALUES
 ('IT26_IND_PERIOD','IT26_IND_OF1','HOURS_MACHINE',2,'[TEST] heures machine'),
 ('IT26_IND_PERIOD','IT26_IND_OF2','HOURS_MACHINE',4,'[TEST] heures machine'),
 ('IT26_IND_PERIOD','IT26_IND_OF1','HOURS_LABOR',1,'[TEST] heures main oeuvre'),
 ('IT26_IND_PERIOD','IT26_IND_OF2','HOURS_LABOR',2,'[TEST] heures main oeuvre');
 SELECT coalesce(sum(montant_impute_dzd),0) INTO v_a FROM public.erp_cost_allocations
 WHERE period_id='IT26_IND_PERIOD' AND of_id='IT26_IND_OF1';
 SELECT coalesce(sum(montant_impute_dzd),0) INTO v_b FROM public.erp_cost_allocations
 WHERE period_id='IT26_IND_PERIOD' AND of_id='IT26_IND_OF2';
 IF v_a<>70 OR v_b<>140 THEN
 RAISE EXCEPTION 'Imputation incorrecte OF1 %, OF2 %',v_a,v_b; END IF;

 a:=public.erp_cost_period_audit('IT26_IND_PERIOD');
 IF a->>'audit_ok'<>'true' OR (a->>'total_pools_dzd')::numeric<>210
 OR (a->>'total_impute_dzd')::numeric<>210 THEN
 RAISE EXCEPTION 'Audit non conforme %',a; END IF;
 -- Même avec les assiettes complètes, des pools marqués SIMULATION ne doivent pas être validables.
 v_rejected:=false;
 BEGIN PERFORM public.erp_cost_validate_period('IT26_IND_PERIOD');
 EXCEPTION WHEN SQLSTATE '23514' THEN v_rejected:=true; END;
 IF NOT v_rejected THEN RAISE EXCEPTION 'Simulation validee a tort'; END IF;
 -- Même avec un justificatif texte, le statut DOCUMENTE ne passe pas sans FK SCF validee.
 v_rejected:=false;
 BEGIN
   UPDATE public.erp_cost_pools SET statut='DOCUMENTE'
    WHERE pool_id='IT26_IND_POOL_E';
 EXCEPTION WHEN SQLSTATE '23514' THEN v_rejected:=true; END;
 IF NOT v_rejected THEN RAISE EXCEPTION 'Charge DOCUMENTE sans piece acceptee'; END IF;
 INSERT INTO public.erp_cost_pool_scf_evidence(pool_id,piece_id,scf_ligne_id,explication_imputation)
 SELECT 'IT26_IND_POOL_E', s.piece_id,l.ligne_id,'[TEST] rattachement fictif du pool energie' FROM public.scf_pieces s JOIN public.scf_lignes l ON l.piece_id=s.piece_id AND l.debit>0 WHERE s.document_source='[TEST] COST_DOC_1';
 INSERT INTO public.erp_cost_pool_scf_evidence(pool_id,piece_id,scf_ligne_id,explication_imputation)
 SELECT 'IT26_IND_POOL_M', s.piece_id,l.ligne_id,'[TEST] rattachement fictif du pool main oeuvre' FROM public.scf_pieces s JOIN public.scf_lignes l ON l.piece_id=s.piece_id AND l.debit>0 WHERE s.document_source='[TEST] COST_DOC_2';
 -- Dépassement du débit comptable : 201 > 200 doit être refusé.
 v_rejected:=false;
 BEGIN
  UPDATE public.erp_cost_pools SET montant_dzd=201,statut='DOCUMENTE'
   WHERE pool_id='IT26_IND_POOL_E';
 EXCEPTION WHEN SQLSTATE '23514' THEN v_rejected:=true; END;
 IF NOT v_rejected THEN RAISE EXCEPTION 'Depassement debit SCF accepte'; END IF;

 -- Interdiction d'utiliser la même ligne comptable sur deux charges.
 INSERT INTO public.erp_cost_pools(pool_id,period_id,nature_code,base_imputation,montant_dzd,justificatif,statut)
 VALUES ('IT26_IND_POOL_DUP','IT26_IND_PERIOD','ENERGIE','KG',1,'[TEST] doublon ligne','SIMULATION');
 v_rejected:=false;
 BEGIN
  INSERT INTO public.erp_cost_pool_scf_evidence(pool_id,piece_id,scf_ligne_id,explication_imputation)
  SELECT 'IT26_IND_POOL_DUP',s.piece_id,l.ligne_id,'[TEST] doublon interdit'
  FROM public.scf_pieces s JOIN public.scf_lignes l ON l.piece_id=s.piece_id AND l.debit>0
  WHERE s.document_source='[TEST] COST_DOC_1';
 EXCEPTION WHEN unique_violation THEN v_rejected:=true; END;
 IF NOT v_rejected THEN RAISE EXCEPTION 'Double imputation ligne SCF acceptee'; END IF;
 DELETE FROM public.erp_cost_pools WHERE pool_id='IT26_IND_POOL_DUP';
 UPDATE public.erp_cost_pools SET statut='DOCUMENTE' WHERE period_id='IT26_IND_PERIOD';
 -- La RPC est strictement idempotente sur une preuve déjà existante et identique.
 IF (SELECT public.erp_cost_document_pool_atomic('IT26_IND_PERIOD','IT26_IND_POOL_E',
    e.piece_id,e.scf_ligne_id,e.explication_imputation)->>'documented'
    FROM public.erp_cost_pool_scf_evidence e WHERE e.pool_id='IT26_IND_POOL_E') IS DISTINCT FROM 'true'
 THEN RAISE EXCEPTION 'RPC documentaire non idempotente'; END IF;
 -- Une répétition ambiguë avec une autre justification doit échouer.
 v_rejected:=false;
 BEGIN
  PERFORM public.erp_cost_document_pool_atomic('IT26_IND_PERIOD','IT26_IND_POOL_E',
     e.piece_id,e.scf_ligne_id,'[TEST] justification volontairement differente')
    FROM public.erp_cost_pool_scf_evidence e WHERE e.pool_id='IT26_IND_POOL_E';
 EXCEPTION WHEN SQLSTATE '23514' THEN v_rejected:=true; END;
 IF NOT v_rejected THEN RAISE EXCEPTION 'Preuve différente acceptée'; END IF;
 IF (SELECT count(*) FROM public.erp_cost_scf_reconciliation
     WHERE period_id='IT26_IND_PERIOD' AND rapprochement_ok IS TRUE
       AND montant_debit_scf_dzd=200
       AND solde_non_impute_dzd>=0)<>2 THEN
  RAISE EXCEPTION 'Rapprochement unitaire SCF incorrect';
 END IF;
 a:=public.erp_cost_validate_period('IT26_IND_PERIOD');
 IF a->>'audit_ok'<>'true' OR
  (SELECT statut FROM public.erp_cost_periods WHERE period_id='IT26_IND_PERIOD')<>'VALIDE'
 THEN RAISE EXCEPTION 'Validation non confirmee'; END IF;

 -- Snapshot capturé dans la même transaction que VALIDE.
 IF (SELECT count(*) FROM public.erp_cost_of_validation_snapshot
     WHERE period_id='IT26_IND_PERIOD')<>2 THEN
  RAISE EXCEPTION 'Snapshot de validation incomplet'; END IF;
 IF (SELECT count(*) FROM public.erp_cost_of_validation_drift
     WHERE period_id='IT26_IND_PERIOD' AND derive_detectee IS FALSE)<>2 THEN
  RAISE EXCEPTION 'Dérive détectée avant changement de OF'; END IF;
 -- Simulation d'un changement tardif de coût direct : le snapshot reste figé.
 UPDATE public.ordres_fabrication SET cout_total=cout_total+1
 WHERE of_id='IT26_IND_OF1';
 IF (SELECT count(*) FROM public.erp_cost_of_validation_drift
     WHERE period_id='IT26_IND_PERIOD' AND derive_detectee IS TRUE)<>1 THEN
  RAISE EXCEPTION 'Modification du coût direct non détectée'; END IF;
 UPDATE public.ordres_fabrication SET cout_total=cout_total-1
 WHERE of_id='IT26_IND_OF1';
 IF (SELECT count(*) FROM public.erp_cost_of_validation_drift
     WHERE period_id='IT26_IND_PERIOD' AND derive_detectee IS TRUE)<>0 THEN
  RAISE EXCEPTION 'Écart de validation persistant'; END IF;
 -- Toute mutation de pools, assiettes et periode validee doit etre refusee.
 v_rejected:=false;
 BEGIN UPDATE public.erp_cost_pools SET montant_dzd=121 WHERE pool_id='IT26_IND_POOL_E';
 EXCEPTION WHEN SQLSTATE '23514' THEN v_rejected:=true; END;
 IF NOT v_rejected THEN RAISE EXCEPTION 'Montant apres validation modifiable'; END IF;
 v_rejected:=false;
 BEGIN UPDATE public.erp_cost_drivers SET valeur=5 WHERE period_id='IT26_IND_PERIOD' AND of_id='IT26_IND_OF1' AND base_imputation='HOURS_MACHINE';
 EXCEPTION WHEN SQLSTATE '23514' THEN v_rejected:=true; END;
 IF NOT v_rejected THEN RAISE EXCEPTION 'Assiette apres validation modifiable'; END IF;
 v_rejected:=false;
 BEGIN UPDATE public.erp_cost_periods SET libelle='Change' WHERE period_id='IT26_IND_PERIOD';
 EXCEPTION WHEN SQLSTATE '23514' THEN v_rejected:=true; END;
 IF NOT v_rejected THEN RAISE EXCEPTION 'Periode validee modifiable'; END IF;

 IF (SELECT cout_analytique_total_dzd FROM public.erp_cost_of_summary
     WHERE period_id='IT26_IND_PERIOD' AND of_id='IT26_IND_OF1')<>370
 OR (SELECT cout_analytique_par_unite_dzd FROM public.erp_cost_of_summary
     WHERE period_id='IT26_IND_PERIOD' AND of_id='IT26_IND_OF1')<>37
 OR (SELECT cout_analytique_total_dzd FROM public.erp_cost_of_summary
     WHERE period_id='IT26_IND_PERIOD' AND of_id='IT26_IND_OF2')<>340
 OR (SELECT cout_analytique_par_unite_dzd FROM public.erp_cost_of_summary
     WHERE period_id='IT26_IND_PERIOD' AND of_id='IT26_IND_OF2')<>68
 THEN RAISE EXCEPTION 'Cout analytique ou cout unitaire incorrect'; END IF;
 -- Le lien documentaire d'une période validée doit être immuable.
 v_rejected:=false;
 BEGIN
  DELETE FROM public.erp_cost_pool_scf_evidence WHERE pool_id='IT26_IND_POOL_E';
 EXCEPTION WHEN SQLSTATE '23514' THEN v_rejected:=true; END;
 IF NOT v_rejected THEN
   RAISE EXCEPTION 'Suppression d une preuve de periode validee acceptee';
 END IF;
 SELECT count(*) INTO v_count FROM public.erp_cost_allocations WHERE period_id='IT26_IND_PERIOD';
 IF v_count<>4 THEN RAISE EXCEPTION 'Lignes de repartition incorrectes: %',v_count; END IF;
 RAISE NOTICE 'COST_REFERENCE_OK OF1 allocation 70 (total 370), OF2 allocation 140 (total 340)';
END $case$;
SELECT 'COST_SNAPSHOT_DRIFT_OK' AS verdict,
  70::numeric AS imputation_of1_dzd,
  140::numeric AS imputation_of2_dzd,
  210::numeric AS total_impute_dzd,
  'ROLLBACK' AS persistance;
ROLLBACK;
