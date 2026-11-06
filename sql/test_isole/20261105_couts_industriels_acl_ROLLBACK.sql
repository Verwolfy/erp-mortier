-- TEST ONLY: privilege boundary between service_role and SECURITY DEFINER validation.
BEGIN;
-- Base fictive de pieces SCF equilibrees, exclusivement dans le BEGIN/ROLLBACK des tests.
DO $fixtures_scf$
DECLARE v_a text; v_b text; v_piece uuid; n integer;
BEGIN
 IF EXISTS(SELECT 1 FROM public.scf_exercices WHERE exercice_id='IT26_COST_EX') THEN
  RAISE EXCEPTION 'Exercice fixture deja present'; END IF;
 SELECT numero_compte INTO v_a FROM public.scf_plan_comptes ORDER BY numero_compte LIMIT 1;
 SELECT numero_compte INTO v_b FROM public.scf_plan_comptes ORDER BY numero_compte OFFSET 1 LIMIT 1;
 IF v_a IS NULL OR v_b IS NULL THEN RAISE EXCEPTION 'Deux comptes SCF requis en TEST'; END IF;
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
  VALUES(v_piece,1,v_a,100,0),(v_piece,2,v_b,0,100);
  UPDATE public.scf_pieces SET statut='VALIDEE' WHERE piece_id=v_piece;
 END LOOP;
END $fixtures_scf$;
INSERT INTO public.ordres_fabrication
(of_id,quantite_prevue,quantite_produite,date_planification,date_fin,statut,cout_total,notes)
VALUES ('IT26_COSTACL_OF',2,2,'2026-11-05','2026-11-05','TERMINE',100,'[TEST] permissions') ;
SET LOCAL ROLE service_role;
DO $test$
DECLARE denied boolean;
BEGIN
 denied := false;
 BEGIN
  INSERT INTO public.erp_cost_periods(period_id,libelle,date_debut,date_fin,statut)
  VALUES ('IT26_COSTACL_BAD','[TEST] non brouillon','2026-11-01','2026-11-30','VALIDE');
 EXCEPTION WHEN SQLSTATE '23514' THEN denied := true; END;
 IF NOT denied THEN RAISE EXCEPTION 'Insertion directe VALIDE accepte'; END IF;

 INSERT INTO public.erp_cost_periods(period_id,libelle,date_debut,date_fin,statut)
 VALUES ('IT26_COSTACL_P','[TEST] garde statut','2026-11-01','2026-11-30','BROUILLON');
 denied := false;
 BEGIN
  UPDATE public.erp_cost_periods SET statut='VALIDE' WHERE period_id='IT26_COSTACL_P';
 EXCEPTION WHEN insufficient_privilege THEN denied := true; END;
 IF NOT denied THEN RAISE EXCEPTION 'Service role a modifie directement statut'; END IF;

 INSERT INTO public.erp_cost_pools(pool_id,period_id,nature_code,base_imputation,montant_dzd,justificatif,statut)
 VALUES ('IT26_COSTACL_POOL','IT26_COSTACL_P','ENERGIE','UNITS',100,'[TEST] 100 DZD simulés','SIMULATION');
 INSERT INTO public.erp_cost_drivers(period_id,of_id,base_imputation,valeur,justificatif)
 VALUES ('IT26_COSTACL_P','IT26_COSTACL_OF','UNITS',2,'[TEST] deux SKU');
 denied := false;
 BEGIN
  PERFORM public.erp_cost_validate_period('IT26_COSTACL_P');
 EXCEPTION WHEN SQLSTATE '23514' THEN denied := true; END;
 IF NOT denied THEN RAISE EXCEPTION 'Simulation validée sans pièce'; END IF;

 INSERT INTO public.erp_cost_pool_scf_evidence(pool_id,piece_id,explication_imputation)
 SELECT 'IT26_COSTACL_POOL',piece_id,'[TEST] rattachement fictif a une charge industrie' FROM public.scf_pieces WHERE document_source='[TEST] COST_DOC_1';
 UPDATE public.erp_cost_pools SET statut='DOCUMENTE',
 justificatif='[TEST] document fictif pour vérifier état' WHERE pool_id='IT26_COSTACL_POOL';
 IF (public.erp_cost_validate_period('IT26_COSTACL_P')->>'audit_ok') IS DISTINCT FROM 'true'
 THEN RAISE EXCEPTION 'RPC de validation ne fonctionne pas'; END IF;

 denied := false;
 BEGIN
  UPDATE public.erp_cost_pools SET montant_dzd=200 WHERE pool_id='IT26_COSTACL_POOL';
 EXCEPTION WHEN SQLSTATE '23514' THEN denied := true; END;
 IF NOT denied THEN RAISE EXCEPTION 'Charge validée modifiable'; END IF;
END $test$;
RESET ROLE;
SELECT 'COST_ACL_OK' AS verdict;
ROLLBACK;