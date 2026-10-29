-- ERP 030 : TEST transactionnel, traçabilité acteur/opération ; données non persistées.
-- Les changements temporaires des indicateurs actif sont annulés par ROLLBACK.
BEGIN;
DO $smoke$
DECLARE
 auteur text;
 controleur text;
 client text;
 sku text;
 client_actif_original text;
 sku_actif_original text;
 attestation uuid;
 creer jsonb;
 op uuid := gen_random_uuid();
 payload jsonb;
 refuse boolean;
 journal integer;
BEGIN
 SELECT u.user_id INTO auteur
 FROM public.users u JOIN public.erp_security_authorities a ON a.user_id=u.user_id
 WHERE a.habilitation='SECURITY_MANAGER' AND a.actif AND a.retire_le IS NULL
   AND upper(btrim(coalesce(u.actif,''))) IN ('OUI','TRUE','YES','1') LIMIT 1;
 SELECT user_id INTO controleur FROM public.users
 WHERE user_id <> auteur
 AND upper(btrim(coalesce(actif,''))) IN ('OUI','TRUE','YES','1') LIMIT 1;
 SELECT client_id, actif INTO client, client_actif_original FROM public.clients
 WHERE upper(btrim(coalesce(actif,''))) IN ('OUI','TRUE','YES','1')
 ORDER BY client_id LIMIT 1;
 SELECT sku_id, actif INTO sku, sku_actif_original FROM public.sku_conditionnement
 WHERE upper(btrim(coalesce(actif,''))) IN ('OUI','TRUE','YES','1')
 ORDER BY sku_id LIMIT 1;
 IF auteur IS NULL OR controleur IS NULL OR client IS NULL OR sku IS NULL
 THEN RAISE EXCEPTION 'Références TEST insuffisantes'; END IF;

 INSERT INTO public.erp_security_authorities(
   user_id,habilitation,actif,attribue_par,attribue_le
 ) VALUES (controleur,'SECURITY_MANAGER',true,auteur,now());
 INSERT INTO public.erp_exonerations_tva_validateurs(user_id,actif,attribue_par)
 VALUES (controleur,true,auteur);

 payload := jsonb_build_object(
  'client_id',client,'reference_attestation','FICTIF-ROLLBACK-029-'||op::text,
  'autorite_emettrice','AUTORITE FICTIVE',
  'justification','TEST NON JURIDIQUE',
  'reference_piece_interne','TEST-ROLLBACK',
  'date_effet','2026-01-01','date_fin','2026-12-31',
  'sku_ids',jsonb_build_array(sku));
 creer := public.erp_exoneration_tva_action(auteur,'CREER_BROUILLON',op,payload);
 attestation := (creer->>'attestation_id')::uuid;
 IF creer->>'statut'<>'A_VALIDER' THEN
    RAISE EXCEPTION 'Brouillon non créé'; END IF;

 UPDATE public.clients SET actif='NON' WHERE client_id=client;
 refuse := false;
 BEGIN
  PERFORM public.erp_exoneration_tva_action(
   controleur,'VALIDER',gen_random_uuid(),
   jsonb_build_object('attestation_id',attestation::text,
    'verification_documentaire',true,'date_verification','2026-10-29',
    'reference_avis_validation','AVIS-TEST'));
 EXCEPTION WHEN check_violation THEN refuse := true;
 END;
 IF NOT refuse THEN RAISE EXCEPTION 'Client inactif accepté'; END IF;
 UPDATE public.clients SET actif=client_actif_original WHERE client_id=client;

 UPDATE public.sku_conditionnement SET actif='NON' WHERE sku_id=sku;
 refuse := false;
 BEGIN
  PERFORM public.erp_exoneration_tva_action(
   controleur,'VALIDER',gen_random_uuid(),
   jsonb_build_object('attestation_id',attestation::text,
    'verification_documentaire',true,'date_verification','2026-10-29',
    'reference_avis_validation','AVIS-TEST'));
 EXCEPTION WHEN check_violation THEN refuse := true;
 END;
 IF NOT refuse THEN RAISE EXCEPTION 'SKU inactif accepté'; END IF;
 UPDATE public.sku_conditionnement SET actif=sku_actif_original WHERE sku_id=sku;

 IF (public.erp_exoneration_tva_action(
   controleur,'VALIDER',gen_random_uuid(),
   jsonb_build_object('attestation_id',attestation::text,
    'verification_documentaire',true,'date_verification','2026-10-29',
    'reference_avis_validation','AVIS-TEST')))->>'statut'<>'VALIDEE'
 THEN RAISE EXCEPTION 'Validation redevenue éligible refusée'; END IF;

 IF (public.erp_exoneration_tva_action(
   controleur,'REVOQUER',gen_random_uuid(),
   jsonb_build_object('attestation_id',attestation::text,
    'motif_revocation','TEST D ANNULATION')))->>'statut'<>'REVOQUEE'
 THEN RAISE EXCEPTION 'Révocation indisponible'; END IF;
 SELECT count(*) INTO journal FROM public.erp_exonerations_tva_evenements
 WHERE attestation_id=attestation;
 IF journal<>3 THEN RAISE EXCEPTION 'Journal attendu 3, obtenu %',journal; END IF;
 SELECT count(*) INTO journal
 FROM public.erp_exonerations_tva_evenements e
 JOIN public.erp_exonerations_tva_operations o
   ON o.operation_id=e.operation_id
 WHERE e.attestation_id=attestation
   AND e.acteur_metier=o.acteur_id
   AND e.type_evenement=CASE o.action
     WHEN 'CREER_BROUILLON' THEN 'CREATION'
     WHEN 'VALIDER' THEN 'VALIDATION'
     WHEN 'REVOQUER' THEN 'REVOCATION' END;
 IF journal<>3 THEN
    RAISE EXCEPTION 'Traçabilité métier 030 incomplète : %',journal;
 END IF;
 RAISE NOTICE 'SMOKE 029/030 OK : inactivité, 3 événements avec acteur et opération ; ROLLBACK';
END;
$smoke$;
ROLLBACK;
