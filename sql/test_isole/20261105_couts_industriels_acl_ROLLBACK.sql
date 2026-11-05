-- TEST ONLY: privilege boundary between service_role and SECURITY DEFINER validation.
BEGIN;
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