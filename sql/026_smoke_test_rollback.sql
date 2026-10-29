-- EXÉCUTER UNIQUEMENT sur TEST avec un rôle administrateur SQL.
-- Toutes les données fictives sont effacées par ROLLBACK.
BEGIN;
DO $smoke$
DECLARE d uuid;
DECLARE test_client text;
DECLARE test_sku text;
DECLARE refus boolean;
DECLARE n integer;
BEGIN
  SELECT min(client_id) INTO test_client FROM public.clients;
  SELECT min(sku_id) INTO test_sku FROM public.sku_conditionnement;
  IF test_client IS NULL OR test_sku IS NULL THEN
    RAISE EXCEPTION 'Clients et SKU TEST requis';
  END IF;
  INSERT INTO public.erp_exonerations_tva_clients(
    client_id,reference_attestation,autorite_emettrice,justification,
    reference_piece_interne,date_effet,date_fin
  ) VALUES (
    test_client,'FICTIF-ROLLBACK-026-' || floor(extract(epoch from clock_timestamp()))::bigint,
    'AUTORITE-FICTIVE-TEST','EXEMPLE SANS VALEUR JURIDIQUE',
    'PIECE-SIMULEE-ROLLBACK',date '2026-01-01',date '2026-12-31'
  ) RETURNING attestation_id INTO d;

  refus := false;
  BEGIN
    UPDATE public.erp_exonerations_tva_clients SET
      statut='VALIDEE',date_verification=date '2026-01-02',
      date_validation=date '2026-01-03',valide_par='TEST'
    WHERE attestation_id=d;
  EXCEPTION WHEN check_violation THEN refus := true;
  END;
  IF NOT refus THEN RAISE EXCEPTION 'Validation sans SKU acceptée'; END IF;

  INSERT INTO public.erp_exonerations_tva_skus(attestation_id,sku_id)
    VALUES (d,test_sku);
  UPDATE public.erp_exonerations_tva_clients SET
    statut='VALIDEE',date_verification=date '2026-01-02',
    date_validation=date '2026-01-03',valide_par='TEST'
  WHERE attestation_id=d;

  refus := false;
  BEGIN
    UPDATE public.erp_exonerations_tva_clients
       SET justification='ALTERATION' WHERE attestation_id=d;
  EXCEPTION WHEN check_violation THEN refus := true;
  END;
  IF NOT refus THEN RAISE EXCEPTION 'Modification après validation acceptée'; END IF;

  refus := false;
  BEGIN
    DELETE FROM public.erp_exonerations_tva_skus WHERE attestation_id=d;
  EXCEPTION WHEN check_violation THEN refus := true;
  END;
  IF NOT refus THEN RAISE EXCEPTION 'Suppression portée validée acceptée'; END IF;

  UPDATE public.erp_exonerations_tva_clients SET statut='REVOQUEE'
    WHERE attestation_id=d;
  refus := false;
  BEGIN
    UPDATE public.erp_exonerations_tva_clients SET statut='VALIDEE'
    WHERE attestation_id=d;
  EXCEPTION WHEN check_violation THEN refus := true;
  END;
  IF NOT refus THEN RAISE EXCEPTION 'Réactivation après révocation acceptée'; END IF;

  SELECT count(*) INTO n FROM public.erp_exonerations_tva_evenements
    WHERE attestation_id=d;
  IF n <> 3 THEN RAISE EXCEPTION 'Journal incomplet : %',n; END IF;
  RAISE NOTICE 'Contrôles 026 réussis : ROLLBACK des données fictives';
END;
$smoke$;
ROLLBACK;
