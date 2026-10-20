-- Test sur projet Supabase TEST UNIQUEMENT : toutes les lignes sont annulées par ROLLBACK.
-- Nécessite une installation de sql/002_atomic_stock_movement.sql.
BEGIN;

INSERT INTO public.matieres_premieres (mp_id, nom)
VALUES ('__TEST_RPC_STOCK_MP_7c1b29', 'MP DE TEST (ROLLBACK)');

-- 100 unités à 2; 100 unités à 4 -> CMP 3
SELECT public.erp_apply_stock_movement(
    '__TEST_STOCK_RECEIPT_A_7c1b29', 'MP', 'ENTREE',
    '__TEST_RPC_STOCK_MP_7c1b29', 100, 2, 'BR-SMOKE-A', NULL);
SELECT public.erp_apply_stock_movement(
    '__TEST_STOCK_RECEIPT_B_7c1b29', 'MP', 'ENTREE',
    '__TEST_RPC_STOCK_MP_7c1b29', 100, 4, 'BR-SMOKE-B', NULL);

-- Prélever 150 unités: 100 du premier lot + 50 du second, coût CMP 450.
SELECT public.erp_apply_stock_movement(
    '__TEST_STOCK_ISSUE_7c1b29', 'MP', 'SORTIE',
    '__TEST_RPC_STOCK_MP_7c1b29', 150, NULL, 'OF-SMOKE-1', NULL);

-- Retry identique: ne doit JAMAIS provoquer un deuxième prélèvement.
SELECT public.erp_apply_stock_movement(
    '__TEST_STOCK_ISSUE_7c1b29', 'MP', 'SORTIE',
    '__TEST_RPC_STOCK_MP_7c1b29', 150, NULL, 'OF-SMOKE-1', NULL);

DO $assertions$
DECLARE
    v_quantity numeric;
    v_lots numeric;
    v_moves integer;
    v_outbox integer;
BEGIN
    SELECT quantite_disponible INTO v_quantity FROM public.stock_actuel
       WHERE mp_id = '__TEST_RPC_STOCK_MP_7c1b29';
    SELECT sum(quantite_restante) INTO v_lots FROM public.lots
       WHERE type_item = 'MP' AND item_id = '__TEST_RPC_STOCK_MP_7c1b29';
    SELECT count(*) INTO v_moves FROM public.mouvements
       WHERE mp_id = '__TEST_RPC_STOCK_MP_7c1b29';
    SELECT count(*) INTO v_outbox FROM public.erp_stock_outbox
       WHERE operation_id LIKE '__TEST_STOCK_%_7c1b29';
    IF v_quantity IS DISTINCT FROM 50 OR v_lots IS DISTINCT FROM 50
       OR v_moves <> 4 OR v_outbox <> 3 THEN
        RAISE EXCEPTION 'ÉCHEC STOCK: global %, lots %, mouvements %, outbox %',
            v_quantity, v_lots, v_moves, v_outbox;
    END IF;
END;
$assertions$;

ROLLBACK;
