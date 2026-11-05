-- Exclusivement TEST ffuhbmcfyexsbjwhryvj : session B en parallèle de A.
BEGIN;
SET LOCAL statement_timeout='25000ms';
SET LOCAL ROLE service_role;
SELECT public.erp_receive_purchase_order(
 'IT26_RACE_REC_B','IT26_RACE_BR_B','IT26_RACE_PO',
 '2026-11-05','OUI','[TEST] Réception concurrente','2027-11-05',
 '[{"ligne_br_id":"IT26_RACE_BRL_B","mp_id":"IT26_RACE_MP","quantite_recue":7,"prix_unitaire":5}]'::jsonb) AS resultat;
COMMIT;
