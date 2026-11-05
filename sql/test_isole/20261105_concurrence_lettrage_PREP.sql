-- TEST UNIQUEMENT ffuhbmcfyexsbjwhryvj. Ne pas utiliser en production.
BEGIN;
SET LOCAL statement_timeout='30s';
DO $guard$
BEGIN
 IF EXISTS (SELECT 1 FROM public.clients WHERE client_id='IT26_LET_CLIENT')
 OR EXISTS (SELECT 1 FROM public.factures WHERE facture_id='IT26_LET_INVOICE')
 OR EXISTS (SELECT 1 FROM public.reglements WHERE reglement_id='IT26_LET_PAYMENT')
 OR EXISTS (SELECT 1 FROM public.comptes WHERE compte_id='IT26_LET_CASH')
 OR EXISTS (SELECT 1 FROM public.erp_finance_operations WHERE operation_id LIKE 'IT26_LET_%')
 THEN RAISE EXCEPTION 'Fixture lettrage préexistante'; END IF;
END $guard$;
INSERT INTO public.clients(client_id,nom,actif) VALUES
 ('IT26_LET_CLIENT','[TEST] Client lettrage concurrent','OUI');
INSERT INTO public.comptes(compte_id,nom_compte,type_compte,numero_compte,solde_initial,statut)
VALUES ('IT26_LET_CASH','[TEST] Banque lettrage','banque','IT26_LET_ACC',0,'OUI');
INSERT INTO public.reglements
(reglement_id,date_reglement,type_flux,partenaire_id,compte_id,mode_paiement,reference_trace,montant_total,montant_alloue,statut)
VALUES ('IT26_LET_PAYMENT','2026-11-05','ENCAISSEMENT','IT26_LET_CLIENT','IT26_LET_CASH',
'VIREMENT','IT26_LET_BANKREF',100,0,'VALIDE');
INSERT INTO public.factures
(facture_id,client_id,date,montant_ht,montant_tva,montant_ttc,montant_paye,statut,type_facture)
VALUES ('IT26_LET_INVOICE','IT26_LET_CLIENT','2026-11-05',100,0,100,0,'VALIDE','FactureClient');
COMMIT;
