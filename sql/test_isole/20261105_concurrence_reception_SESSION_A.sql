-- Exclusivement TEST ffuhbmcfyexsbjwhryvj : session A à lancer avec session B.
BEGIN;
SET LOCAL statement_timeout='25000ms';
SET LOCAL ROLE service_role;
WITH action AS MATERIALIZED (
 SELECT public.erp_receive_purchase_order(
 'IT26_RACE_REC_A','IT26_RACE_BR_A','IT26_RACE_PO',
 '2026-11-05','OUI','[TEST] Réception concurrente','2027-11-05',
 '[{"ligne_br_id":"IT26_RACE_BRL_A","mp_id":"IT26_RACE_MP","quantite_recue":7,"prix_unitaire":5}]'::jsonb) AS resultat
)
SELECT pg_sleep(5) FROM action;
COMMIT;
SELECT result_payload FROM public.erp_purchase_operations WHERE operation_id='IT26_RACE_REC_A';
