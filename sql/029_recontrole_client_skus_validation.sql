-- ERP 029 : verrou supplémentaire lors de l'homologation d'une attestation.
-- N'ajoute aucun validateur ni certificat. N'affecte pas la facturation.
-- Préserve les signatures, les ACL et le contrat idempotent de la RPC 027.
BEGIN;
CREATE OR REPLACE FUNCTION public.erp_exoneration_tva_action(
 p_actor_id text, p_action text, p_operation_id uuid, p_payload jsonb
) RETURNS jsonb
LANGUAGE plpgsql VOLATILE SECURITY DEFINER
SET search_path = pg_catalog, pg_temp
AS $fn$
DECLARE
 d public.erp_exonerations_tva_clients%ROWTYPE;
 op public.erp_exonerations_tva_operations%ROWTYPE;
 x jsonb;
 sid text;
 client text;
 sdate date;
 edate date;
 verification date;
 avis text;
 raison text;
 ret jsonb;
 n integer := 0;
BEGIN
 IF p_actor_id IS NULL OR length(btrim(p_actor_id)) < 3
     OR p_operation_id IS NULL OR p_payload IS NULL
     OR jsonb_typeof(p_payload) <> 'object'
     OR p_action NOT IN ('CREER_BROUILLON','VALIDER','REVOQUER') THEN
   RAISE EXCEPTION 'Requête attestation invalide' USING ERRCODE='22023';
 END IF;
 IF NOT EXISTS(
   SELECT 1 FROM public.users u
   JOIN public.erp_security_authorities a ON a.user_id=u.user_id
   WHERE u.user_id=p_actor_id
   AND upper(btrim(coalesce(u.actif,''))) IN ('OUI','TRUE','YES','1')
   AND a.habilitation='SECURITY_MANAGER'
   AND a.actif IS TRUE AND a.retire_le IS NULL
 ) THEN
   RAISE EXCEPTION 'Gestionnaire non habilité' USING ERRCODE='42501';
 END IF;
 IF p_action <> 'CREER_BROUILLON' AND NOT EXISTS(
   SELECT 1 FROM public.erp_exonerations_tva_validateurs v
   WHERE v.user_id=p_actor_id AND v.actif IS TRUE
 ) THEN
   RAISE EXCEPTION 'Validateur fiscal distinct non habilité' USING ERRCODE='42501';
 END IF;

 INSERT INTO public.erp_exonerations_tva_operations
   (operation_id,acteur_id,action,payload)
 VALUES (p_operation_id,p_actor_id,p_action,p_payload)
 ON CONFLICT (operation_id) DO NOTHING;
 SELECT * INTO STRICT op FROM public.erp_exonerations_tva_operations
   WHERE operation_id=p_operation_id FOR UPDATE;
 IF op.acteur_id<>p_actor_id OR op.action<>p_action OR op.payload<>p_payload THEN
    RAISE EXCEPTION 'Opération rejouée avec des paramètres différents'
      USING ERRCODE='23505';
 END IF;
 IF op.attestation_id IS NOT NULL THEN
   SELECT * INTO STRICT d FROM public.erp_exonerations_tva_clients
   WHERE attestation_id=op.attestation_id;
   RETURN jsonb_build_object('operation_id',p_operation_id,'action',p_action,
       'attestation_id',d.attestation_id,'statut',d.statut,'idempotent',true);
 END IF;

 IF p_action='CREER_BROUILLON' THEN
   client := nullif(btrim(p_payload->>'client_id'),'');
   IF client IS NULL OR
       NOT EXISTS(SELECT 1 FROM public.clients c WHERE c.client_id=client
          AND upper(btrim(coalesce(c.actif,''))) IN ('OUI','TRUE','YES','1'))
      THEN RAISE EXCEPTION 'Client actif requis' USING ERRCODE='23514'; END IF;
   IF p_payload->>'reference_attestation' IS NULL
     OR length(btrim(p_payload->>'reference_attestation')) NOT BETWEEN 1 AND 200
     OR length(btrim(coalesce(p_payload->>'autorite_emettrice',''))) NOT BETWEEN 1 AND 200
     OR length(btrim(coalesce(p_payload->>'reference_piece_interne',''))) NOT BETWEEN 1 AND 250
     OR length(btrim(coalesce(p_payload->>'justification',''))) NOT BETWEEN 1 AND 2000
   THEN RAISE EXCEPTION 'Références documentaires incomplètes' USING ERRCODE='23514';
   END IF;
   sdate := (p_payload->>'date_effet')::date;
   edate := (p_payload->>'date_fin')::date;
   IF sdate IS NULL OR edate IS NULL OR edate<sdate
   THEN RAISE EXCEPTION 'Période invalide' USING ERRCODE='23514'; END IF;
   IF jsonb_typeof(p_payload->'sku_ids') <> 'array'
     OR jsonb_array_length(p_payload->'sku_ids') NOT BETWEEN 1 AND 200
   THEN RAISE EXCEPTION 'Portée SKU obligatoire' USING ERRCODE='23514'; END IF;
   INSERT INTO public.erp_exonerations_tva_clients
     (client_id,reference_attestation,autorite_emettrice,justification,
      reference_piece_interne,date_effet,date_fin,cree_par)
   VALUES (client,btrim(p_payload->>'reference_attestation'),
     btrim(p_payload->>'autorite_emettrice'),btrim(p_payload->>'justification'),
     btrim(p_payload->>'reference_piece_interne'),sdate,edate,p_actor_id)
   RETURNING * INTO d;
   FOR x IN SELECT value FROM jsonb_array_elements(p_payload->'sku_ids')
   LOOP
     IF jsonb_typeof(x)<>'string' OR
       NOT EXISTS (SELECT 1 FROM public.sku_conditionnement s
                   WHERE s.sku_id=x#>>'{}'
                     AND upper(btrim(coalesce(s.actif,''))) IN ('OUI','TRUE','YES','1'))
     THEN RAISE EXCEPTION 'SKU actif invalide' USING ERRCODE='23514'; END IF;
     sid := x#>>'{}';
     INSERT INTO public.erp_exonerations_tva_skus(attestation_id,sku_id)
       VALUES(d.attestation_id,sid);
     n:=n+1;
   END LOOP;
 ELSIF p_action='VALIDER' THEN
   IF p_payload->>'verification_documentaire' IS DISTINCT FROM 'true' THEN
     RAISE EXCEPTION 'Confirmation du contrôle documentaire requise'
       USING ERRCODE='23514';
   END IF;
   avis:=nullif(btrim(p_payload->>'reference_avis_validation'),'');
   IF avis IS NULL OR length(avis)>250
   THEN RAISE EXCEPTION 'Avis juridique/documentaire requis' USING ERRCODE='23514'; END IF;
   verification:=(p_payload->>'date_verification')::date;
   IF verification IS NULL OR verification>current_date
   THEN RAISE EXCEPTION 'Date vérification invalide' USING ERRCODE='23514'; END IF;
   SELECT * INTO STRICT d FROM public.erp_exonerations_tva_clients
      WHERE attestation_id=(p_payload->>'attestation_id')::uuid FOR UPDATE;
   IF d.statut<>'A_VALIDER' OR d.cree_par=p_actor_id OR d.cree_par IS NULL THEN
      RAISE EXCEPTION 'Double validation obligatoire, dossier non éligible'
        USING ERRCODE='23514';
   END IF;
   -- L'activation à la date de création du brouillon ne garantit pas
   -- l'éligibilité du client ni des SKU au jour de l'homologation.
   IF NOT EXISTS (
      SELECT 1 FROM public.clients c
       WHERE c.client_id=d.client_id
         AND upper(btrim(coalesce(c.actif,''))) IN ('OUI','TRUE','YES','1')
   ) THEN
      RAISE EXCEPTION 'Validation refusée : client devenu inactif'
        USING ERRCODE='23514';
   END IF;
   IF NOT EXISTS (
      SELECT 1 FROM public.erp_exonerations_tva_skus p
       WHERE p.attestation_id=d.attestation_id
   ) OR EXISTS (
      SELECT 1 FROM public.erp_exonerations_tva_skus p
      LEFT JOIN public.sku_conditionnement s ON s.sku_id=p.sku_id
       WHERE p.attestation_id=d.attestation_id
         AND (s.sku_id IS NULL
              OR upper(btrim(coalesce(s.actif,''))) NOT IN
                   ('OUI','TRUE','YES','1'))
   ) THEN
      RAISE EXCEPTION 'Validation refusée : portée SKU vide ou inactive'
        USING ERRCODE='23514';
   END IF;
   UPDATE public.erp_exonerations_tva_clients SET statut='VALIDEE',
      date_verification=verification,date_validation=current_date,
      valide_par=p_actor_id,reference_avis_validation=avis
   WHERE attestation_id=d.attestation_id;
 ELSIF p_action='REVOQUER' THEN
   raison:=nullif(btrim(p_payload->>'motif_revocation'),'');
   IF raison IS NULL OR length(raison)>2000
     THEN RAISE EXCEPTION 'Motif de révocation obligatoire' USING ERRCODE='23514'; END IF;
   SELECT * INTO STRICT d FROM public.erp_exonerations_tva_clients
      WHERE attestation_id=(p_payload->>'attestation_id')::uuid FOR UPDATE;
   IF d.statut<>'VALIDEE' OR d.cree_par=p_actor_id OR d.cree_par IS NULL THEN
     RAISE EXCEPTION 'Révocation non autorisée' USING ERRCODE='23514';
   END IF;
   UPDATE public.erp_exonerations_tva_clients SET statut='REVOQUEE'
     WHERE attestation_id=d.attestation_id;
 END IF;
 SELECT * INTO STRICT d FROM public.erp_exonerations_tva_clients
    WHERE attestation_id=d.attestation_id;
 UPDATE public.erp_exonerations_tva_operations SET attestation_id=d.attestation_id
   WHERE operation_id=p_operation_id;
 RETURN jsonb_build_object('operation_id',p_operation_id,'action',p_action,
   'attestation_id',d.attestation_id,'statut',d.statut,'idempotent',false,
   'nombre_sku_crees',CASE WHEN p_action='CREER_BROUILLON' THEN n ELSE NULL END);
END;
$fn$;
-- CREATE OR REPLACE ne doit pas réintroduire l'accès API.
REVOKE ALL ON FUNCTION public.erp_exoneration_tva_action(text,text,uuid,jsonb)
 FROM PUBLIC, anon, authenticated, service_role;
GRANT EXECUTE ON FUNCTION public.erp_exoneration_tva_action(text,text,uuid,jsonb)
 TO service_role;
DO $verify$
BEGIN
 IF has_function_privilege('anon',
      'public.erp_exoneration_tva_action(text,text,uuid,jsonb)','EXECUTE')
    OR has_function_privilege('authenticated',
      'public.erp_exoneration_tva_action(text,text,uuid,jsonb)','EXECUTE')
    OR NOT has_function_privilege('service_role',
      'public.erp_exoneration_tva_action(text,text,uuid,jsonb)','EXECUTE')
 THEN RAISE EXCEPTION 'Accès RPC exonération 029 incorrect'; END IF;
END;
$verify$;
COMMIT;
