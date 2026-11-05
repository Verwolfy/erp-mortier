-- Retour arrière du lot complémentaire seulement, avant rollback du lot initial.
BEGIN;
DELETE FROM public.mouvements_pf WHERE mouvement_pf_id='DEMO26_MVP2' AND reference='DEMO26_STOCK_INITIAL';
DELETE FROM public.mouvements WHERE mouvement_id='DEMO26_MV2' AND reference='DEMO26_STOCK_INITIAL';
COMMIT;
