-- ERP 031 : validation de bout en bout uniquement sur Supabase TEST.
-- Test fictif transactionnel. TOUT est annulé par le ROLLBACK final.
BEGIN;
DO $smoke$
DECLARE
  auteur text;
  controleur text;
  client text;
  sku text;
  autre_sku text;
  op uuid := gen_random_uuid();
  id_dossier uuid;
  input jsonb;
  r jsonb;
BEGIN
 SELECT u.user_id INTO auteur
 FROM public.users u
 JOIN public.erp_security_authorities a ON a.user_id=u.user_id
 WHERE a.habilitation='SECURITY_MANAGER'
   AND a.actif AND a.retire_le IS NULL
   AND upper(btrim(coalesce(u.actif,''))) IN ('OUI','TRUE','YES','1')
 LIMIT 1;
 SELECT user_id INTO controleur
 FROM public.users
 WHERE user_id<>auteur
   AND upper(btrim(coalesce(actif,''))) IN ('OUI','TRUE','YES','1')
 LIMIT 1;
 SELECT client_id INTO client FROM public.clients
 WHERE upper(btrim(coalesce(actif,''))) IN ('OUI','TRUE','YES','1')
 ORDER BY client_id LIMIT 1;
 SELECT sku_id INTO sku FROM public.sku_conditionnement
 WHERE upper(btrim(coalesce(actif,''))) IN ('OUI','TRUE','YES','1')
 ORDER BY sku_id LIMIT 1;
 SELECT sku_id INTO autre_sku FROM public.sku_conditionnement
 WHERE sku_id<>sku
   AND upper(btrim(coalesce(actif,''))) IN ('OUI','TRUE','YES','1')
 ORDER BY sku_id LIMIT 1;
 IF auteur IS NULL OR controleur IS NULL OR client IS NULL
    OR sku IS NULL OR autre_sku IS NULL THEN
    RAISE EXCEPTION 'Jeu TEST insuffisant pour contrôle 031';
 END IF;

 -- En l'absence de dossier, on ne donne jamais de preuve de TVA zéro.
 r:=public.erp_exoneration_tva_precontrole_vente(client,ARRAY[sku],CURRENT_DATE);
 IF r->>'statut'<>'AUCUN_DOSSIER' OR (r->>'autorise_facturation')::boolean
 THEN RAISE EXCEPTION 'Absence dossier mal traitée'; END IF;

 INSERT INTO public.erp_security_authorities(
   user_id,habilitation,actif,attribue_par,attribue_le
 ) VALUES (controleur,'SECURITY_MANAGER',true,auteur,now());
 INSERT INTO public.erp_exonerations_tva_validateurs(user_id,actif,attribue_par)
 VALUES (controleur,true,auteur);
 input := jsonb_build_object(
   'client_id',client,
   'reference_attestation','FICTIF-ROLLBACK-031-'||op::text,
   'autorite_emettrice','AUTORITE FICTIVE',
   'justification','TEST NON JURIDIQUE',
   'reference_piece_interne','TEST-ROLLBACK',
   'date_effet',(CURRENT_DATE-interval '2 days')::date::text,
   'date_fin',(CURRENT_DATE+interval '2 days')::date::text,
   'sku_ids',jsonb_build_array(sku));
 id_dossier := (
   public.erp_exoneration_tva_action(auteur,'CREER_BROUILLON',op,input)
 )->>'attestation_id';
 r:=public.erp_exoneration_tva_precontrole_vente(client,ARRAY[sku],CURRENT_DATE);
 IF r->>'statut'<>'A_BLOQUER'
    OR r->>'motif'<>'ATTESTATION_NON_HOMOLOGUEE'
 THEN RAISE EXCEPTION 'Dossier en attente reconnu à tort'; END IF;

 PERFORM public.erp_exoneration_tva_action(
   controleur,'VALIDER',gen_random_uuid(),
   jsonb_build_object('attestation_id',id_dossier::text,
     'verification_documentaire',true,
     'date_verification',CURRENT_DATE::text,
     'reference_avis_validation','TEST-DOCUMENTAIRE'));
 r:=public.erp_exoneration_tva_precontrole_vente(client,ARRAY[sku],CURRENT_DATE);
 IF r->>'statut'<>'PRECONTROLE_OK'
    OR r->>'attestation_id'<>id_dossier::text
    OR (r->>'autorise_facturation')::boolean
 THEN RAISE EXCEPTION 'Precontrôle incorrect sur dossier validé'; END IF;

 r:=public.erp_exoneration_tva_precontrole_vente(
   client,ARRAY[sku,autre_sku],CURRENT_DATE);
 IF r->>'motif'<>'PORTEE_SKU_PARTIELLE'
 THEN RAISE EXCEPTION 'SKU hors portée accepté'; END IF;

 PERFORM public.erp_exoneration_tva_action(
   controleur,'REVOQUER',gen_random_uuid(),
   jsonb_build_object('attestation_id',id_dossier::text,
     'motif_revocation','ANNULATION TEST'));
 r:=public.erp_exoneration_tva_precontrole_vente(client,ARRAY[sku],CURRENT_DATE);
 IF r->>'statut'<>'A_BLOQUER'
 THEN RAISE EXCEPTION 'Révocation ignorée'; END IF;

 RAISE NOTICE 'SMOKE 031 OK : absent / en attente / validé / partiel / révoqué ; ROLLBACK';
END;
$smoke$;
ROLLBACK;
