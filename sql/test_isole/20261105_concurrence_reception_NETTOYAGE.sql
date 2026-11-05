-- TEST UNIQUEMENT ffuhbmcfyexsbjwhryvj.
-- Nettoyage des seules références IT26_RACE du lot de réception.
BEGIN;
DO $guard$
BEGIN
  IF EXISTS (SELECT 1 FROM public.commandes_achats
             WHERE commande_achat_id = 'IT26_RACE_PO'
               AND fournisseur_id <> 'IT26_RACE_FOU')
  OR EXISTS (SELECT 1 FROM public.bons_reception
             WHERE commande_achat_id = 'IT26_RACE_PO'
               AND bon_reception_id NOT IN ('IT26_RACE_BR_A','IT26_RACE_BR_B'))
  THEN
    RAISE EXCEPTION 'Nettoyage interdit : références inattendues';
  END IF;
END
$guard$;
DELETE FROM public.mouvements WHERE mp_id='IT26_RACE_MP';
DELETE FROM public.lignes_bons_reception WHERE bon_reception_id IN ('IT26_RACE_BR_A','IT26_RACE_BR_B');
DELETE FROM public.bons_reception WHERE bon_reception_id IN ('IT26_RACE_BR_A','IT26_RACE_BR_B');
DELETE FROM public.lots WHERE item_id='IT26_RACE_MP' AND type_item='MP';
DELETE FROM public.stock_actuel WHERE mp_id='IT26_RACE_MP';
DELETE FROM public.erp_stock_outbox
WHERE operation_id IN (SELECT operation_id FROM public.erp_stock_operations
                       WHERE request_payload->>'item_id'='IT26_RACE_MP');
DELETE FROM public.erp_stock_operations WHERE request_payload->>'item_id'='IT26_RACE_MP';
DELETE FROM public.erp_purchase_outbox
WHERE operation_id IN ('IT26_RACE_CREATE','IT26_RACE_REC_A','IT26_RACE_REC_B');
DELETE FROM public.erp_purchase_operations
WHERE operation_id IN ('IT26_RACE_CREATE','IT26_RACE_REC_A','IT26_RACE_REC_B');
DELETE FROM public.lignes_achats WHERE commande_achat_id='IT26_RACE_PO';
DELETE FROM public.commandes_achats WHERE commande_achat_id='IT26_RACE_PO';
DELETE FROM public.matieres_premieres WHERE mp_id='IT26_RACE_MP';
DELETE FROM public.fournisseurs WHERE fournisseur_id='IT26_RACE_FOU';
COMMIT;
