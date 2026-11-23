-- ERP-063 : PRÉPARATION uniquement, NE PAS APPLIQUER au principal.
-- Dépend de la migration ERP-062 (erp_purchase_requests).
-- Visa interne du bon de commande avant signature/transmission EXTERNES.
-- Un visa n'est NI une signature, NI une émission, NI un envoi.
BEGIN;

CREATE TABLE IF NOT EXISTS public.erp_purchase_po_visas (
 visa_id text PRIMARY KEY,
 commande_achat_id text NOT NULL UNIQUE
   REFERENCES public.commandes_achats(commande_achat_id),
 demande_id text NOT NULL UNIQUE
   REFERENCES public.erp_purchase_requests(demande_id),
 preparateur_id text NOT NULL REFERENCES public.users(user_id),
 validateur_id text REFERENCES public.users(user_id),
 statut text NOT NULL DEFAULT 'A_VISER'
   CHECK(statut IN ('A_VISER','VISE_INTERNE','REFUSE')),
 empreinte_source text NOT NULL CHECK(length(empreinte_source)=32),
 motif text CHECK(motif IS NULL OR length(motif)<=500),
 prepare_le timestamptz NOT NULL DEFAULT clock_timestamp(),
 decide_le timestamptz,
 CONSTRAINT erp_po_visa_separation
   CHECK(validateur_id IS NULL OR validateur_id<>preparateur_id)
);

CREATE TABLE IF NOT EXISTS public.erp_purchase_po_visa_operations (
 operation_id text PRIMARY KEY CHECK(length(btrim(operation_id)) BETWEEN 1 AND 128),
 action text NOT NULL CHECK(action IN ('PREPARE','VISA','REFUSE')),
 acteur_id text NOT NULL REFERENCES public.users(user_id),
 payload jsonb NOT NULL,
 resultat jsonb,
 cree_le timestamptz NOT NULL DEFAULT clock_timestamp()
);

ALTER TABLE public.erp_purchase_po_visas ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.erp_purchase_po_visa_operations ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON public.erp_purchase_po_visas,
 public.erp_purchase_po_visa_operations FROM PUBLIC,anon,authenticated;
GRANT SELECT,INSERT,UPDATE ON public.erp_purchase_po_visas,
 public.erp_purchase_po_visa_operations TO service_role;

CREATE OR REPLACE FUNCTION public.erp_purchase_po_visa_transaction(
 p_action text,p_operation_id text,p_acteur_id text,p_payload jsonb
) RETURNS jsonb
LANGUAGE plpgsql SECURITY INVOKER SET search_path=pg_catalog,public
AS $body$
DECLARE
 v_actor record; v_po public.commandes_achats%ROWTYPE;
 v_da public.erp_purchase_requests%ROWTYPE;
 v_visa public.erp_purchase_po_visas%ROWTYPE;
 v_operation public.erp_purchase_po_visa_operations%ROWTYPE;
 v_po_id text; v_hash text; v_result jsonb; v_visa_id text;
BEGIN
 IF p_action NOT IN ('PREPARE','VISA','REFUSE')
  OR p_operation_id IS NULL OR length(btrim(p_operation_id)) NOT BETWEEN 1 AND 128
  OR jsonb_typeof(p_payload)<>'object' OR p_acteur_id IS NULL
 THEN RAISE EXCEPTION 'Action de visa incorrecte' USING ERRCODE='22023'; END IF;

 SELECT user_id,role,actif INTO v_actor FROM public.users
 WHERE user_id=p_acteur_id FOR SHARE;
 IF NOT FOUND OR upper(btrim(coalesce(v_actor.actif,'')))
       NOT IN ('OUI','ACTIF','ACTIVE','TRUE','1','YES')
   OR (
      upper(btrim(coalesce(v_actor.role,''))) NOT IN ('ADMIN','ADMINISTRATEUR','SUPERADMIN')
      AND NOT EXISTS(
       SELECT 1 FROM public.permissions pr
       WHERE pr.role=v_actor.role AND lower(btrim(pr.module))='achats'
         AND upper(btrim(coalesce(pr.ecriture,''))) IN ('OUI','TRUE','1','YES')
      )
   )
 THEN RAISE EXCEPTION 'Acteur non autorisé' USING ERRCODE='42501'; END IF;

 PERFORM pg_advisory_xact_lock(hashtextextended('erp:visa:op:'||p_operation_id,0));
 SELECT * INTO v_operation FROM public.erp_purchase_po_visa_operations
 WHERE operation_id=p_operation_id FOR UPDATE;
 IF FOUND THEN
   IF v_operation.action IS DISTINCT FROM p_action
     OR v_operation.acteur_id IS DISTINCT FROM p_acteur_id
     OR v_operation.payload IS DISTINCT FROM p_payload THEN
      RAISE EXCEPTION 'Identifiant de visa réutilisé pour une autre action'
        USING ERRCODE='23505'; END IF;
   IF v_operation.resultat IS NULL THEN
      RAISE EXCEPTION 'Résultat de visa non confirmé' USING ERRCODE='23514';
   END IF;
   RETURN v_operation.resultat;
 END IF;
 INSERT INTO public.erp_purchase_po_visa_operations(
   operation_id,action,acteur_id,payload
 ) VALUES(p_operation_id,p_action,p_acteur_id,p_payload);

 v_po_id:=nullif(btrim(coalesce(p_payload->>'commande_achat_id','')),'');
 IF v_po_id IS NULL OR length(v_po_id)>200 THEN
   RAISE EXCEPTION 'Commande fournisseur manquante' USING ERRCODE='22023'; END IF;
 SELECT * INTO v_po FROM public.commandes_achats
 WHERE commande_achat_id=v_po_id FOR UPDATE;
 IF NOT FOUND OR v_po.statut<>'EN_ATTENTE' THEN
   RAISE EXCEPTION 'Visa impossible : BC absent ou déjà traité' USING ERRCODE='23514';
 END IF;
 IF EXISTS(SELECT 1 FROM public.bons_reception WHERE commande_achat_id=v_po_id) THEN
   RAISE EXCEPTION 'Visa rétrospectif interdit après réception' USING ERRCODE='23514';
 END IF;
 SELECT * INTO v_da FROM public.erp_purchase_requests
 WHERE commande_achat_id=v_po_id AND statut='COMMANDEE' FOR SHARE;
 IF NOT FOUND OR v_da.approbateur_id IS NULL
   OR v_da.approbateur_id=v_da.demandeur_id THEN
   RAISE EXCEPTION 'Absence de demande approuvée indépendamment'
     USING ERRCODE='23514';
 END IF;
 -- L'empreinte incorpore toutes les valeurs enregistrées, lignes triées.
 -- MD5 est un témoin d'intégrité interne non cryptographique, pas une signature.
 SELECT md5(to_jsonb(c)::text ||
     coalesce((SELECT jsonb_agg(to_jsonb(l) ORDER BY l.ligne_achat_id)::text
       FROM public.lignes_achats l
       WHERE l.commande_achat_id=c.commande_achat_id),'[]'))
 INTO v_hash FROM public.commandes_achats c WHERE c.commande_achat_id=v_po_id;
 IF v_hash IS NULL OR NOT EXISTS (
     SELECT 1 FROM public.lignes_achats WHERE commande_achat_id=v_po_id
 ) THEN RAISE EXCEPTION 'BC sans lignes vérifiables' USING ERRCODE='23514'; END IF;

 IF p_action='PREPARE' THEN
   IF v_da.demandeur_id<>p_acteur_id THEN
      RAISE EXCEPTION 'Préparation réservée au demandeur' USING ERRCODE='42501'; END IF;
   v_visa_id:='POV-'||gen_random_uuid()::text;
   INSERT INTO public.erp_purchase_po_visas(
       visa_id,commande_achat_id,demande_id,preparateur_id,empreinte_source
   ) VALUES(v_visa_id,v_po_id,v_da.demande_id,p_acteur_id,v_hash);
   v_result:=jsonb_build_object('visa_id',v_visa_id,
      'commande_achat_id',v_po_id,'statut','A_VISER');
 ELSE
   SELECT * INTO v_visa FROM public.erp_purchase_po_visas
   WHERE commande_achat_id=v_po_id FOR UPDATE;
   IF NOT FOUND OR v_visa.statut<>'A_VISER' OR
      v_visa.preparateur_id=p_acteur_id OR
      v_visa.empreinte_source IS DISTINCT FROM v_hash THEN
     RAISE EXCEPTION 'Visa impossible : séparation, statut ou source modifiée'
       USING ERRCODE='23514'; END IF;
   IF upper(btrim(coalesce(v_actor.role,'')))
      NOT IN ('ADMIN','ADMINISTRATEUR','SUPERADMIN') THEN
     RAISE EXCEPTION 'Visa réservé à un administrateur distinct'
       USING ERRCODE='42501'; END IF;
   IF p_action='REFUSE'
      AND length(btrim(coalesce(p_payload->>'motif',''))) NOT BETWEEN 10 AND 500 THEN
      RAISE EXCEPTION 'Refus exige un motif' USING ERRCODE='22023'; END IF;
   UPDATE public.erp_purchase_po_visas
      SET statut=CASE WHEN p_action='VISA' THEN 'VISE_INTERNE' ELSE 'REFUSE' END,
          validateur_id=p_acteur_id,
          motif=nullif(btrim(coalesce(p_payload->>'motif','')),''),
          decide_le=clock_timestamp()
   WHERE visa_id=v_visa.visa_id;
   v_result:=jsonb_build_object(
      'visa_id',v_visa.visa_id,'commande_achat_id',v_po_id,
      'statut',CASE WHEN p_action='VISA' THEN 'VISE_INTERNE' ELSE 'REFUSE' END);
 END IF;
 v_result:=v_result||jsonb_build_object(
    'operation_id',p_operation_id,
    'signature_effectuee',false,
    'transmission_fournisseur_effectuee',false,
    'paiement_autorise',false);
 UPDATE public.erp_purchase_po_visa_operations SET resultat=v_result
 WHERE operation_id=p_operation_id;
 RETURN v_result;
END $body$;

REVOKE ALL ON FUNCTION public.erp_purchase_po_visa_transaction(text,text,text,jsonb)
 FROM PUBLIC,anon,authenticated;
GRANT EXECUTE ON FUNCTION public.erp_purchase_po_visa_transaction(text,text,text,jsonb)
 TO service_role;
COMMIT;
