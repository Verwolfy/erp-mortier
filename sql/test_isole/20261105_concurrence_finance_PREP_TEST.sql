-- TEST UNIQUEMENT ffuhbmcfyexsbjwhryvj : fixtures dédiées à la concurrence des paiements.
BEGIN;
DO $guard$ BEGIN
 IF EXISTS(SELECT 1 FROM public.clients WHERE client_id='IT26_PAR_FINCLI')
 OR EXISTS(SELECT 1 FROM public.reglements WHERE reference_trace='IT26_PAR_FINREF')
 THEN RAISE EXCEPTION 'Fixture concurrence finance déjà présente'; END IF;
END $guard$;
INSERT INTO public.clients(client_id,nom,actif) VALUES
('IT26_PAR_FINCLI','[TEST] Concurrence finance','OUI');
INSERT INTO public.comptes(compte_id,nom_compte,type_compte,numero_compte,solde_initial,statut)
VALUES ('IT26_PAR_BANK','[TEST] Banque concurrence','Banque','IT26_PAR_BANKNO',0,'OUI'),
       ('IT26_PAR_TIERS','[TEST] Tiers concurrence','Tiers client','IT26_PAR_TIERNO',0,'OUI');
COMMIT;
