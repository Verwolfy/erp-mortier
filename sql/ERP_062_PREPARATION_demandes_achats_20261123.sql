-- ERP-062 — PRÉPARATION, NE PAS APPLIQUER AU PRINCIPAL SANS HOMOLOGATION.
-- Demande d'achat : brouillon -> soumise -> approuvée/refusée -> commandée.
-- Aucune écriture de stock, aucun paiement, aucune émission/notification fournisseur.
BEGIN;

CREATE TABLE IF NOT EXISTS public.erp_purchase_requests (
  demande_id text PRIMARY KEY,
  demandeur_id text NOT NULL REFERENCES public.users(user_id),
  motivation text NOT NULL CHECK (length(btrim(motivation)) BETWEEN 10 AND 1500),
  date_souhaitee date NOT NULL,
  statut text NOT NULL DEFAULT 'BROUILLON'
    CHECK (statut IN ('BROUILLON','SOUMISE','APPROUVEE','REFUSEE','COMMANDEE')),
  approbateur_id text REFERENCES public.users(user_id),
  decision_motif text,
  commande_achat_id text UNIQUE REFERENCES public.commandes_achats(commande_achat_id),
  cree_le timestamptz NOT NULL DEFAULT clock_timestamp(),
  soumis_le timestamptz,
  decide_le timestamptz,
  commande_le timestamptz,
  CONSTRAINT erp_da_separation CHECK (approbateur_id IS NULL OR approbateur_id<>demandeur_id),
  CONSTRAINT erp_da_link CHECK ((statut='COMMANDEE') = (commande_achat_id IS NOT NULL))
);
CREATE TABLE IF NOT EXISTS public.erp_purchase_request_lines (
  demande_id text NOT NULL REFERENCES public.erp_purchase_requests(demande_id) ON DELETE RESTRICT,
  mp_id text NOT NULL REFERENCES public.matieres_premieres(mp_id),
  unite_stock text NOT NULL CHECK (length(btrim(unite_stock)) BETWEEN 1 AND 40),
  quantite numeric NOT NULL CHECK (quantite>0 AND quantite<1000000000000000),
  PRIMARY KEY(demande_id,mp_id)
);
CREATE TABLE IF NOT EXISTS public.erp_purchase_request_operations (
  operation_id text PRIMARY KEY CHECK(length(btrim(operation_id)) BETWEEN 1 AND 128),
  action text NOT NULL CHECK(action IN ('CREATE','SUBMIT','APPROVE','REJECT','CONVERT')),
  acteur_id text NOT NULL REFERENCES public.users(user_id),
  request_payload jsonb NOT NULL,
  result_payload jsonb,
  cree_le timestamptz NOT NULL DEFAULT clock_timestamp()
);
CREATE TABLE IF NOT EXISTS public.erp_purchase_request_events (
  evenement_id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  demande_id text NOT NULL REFERENCES public.erp_purchase_requests(demande_id),
  operation_id text NOT NULL UNIQUE REFERENCES public.erp_purchase_request_operations(operation_id),
  acteur_id text NOT NULL REFERENCES public.users(user_id),
  action text NOT NULL,
  ancien_statut text,
  nouveau_statut text NOT NULL,
  commentaire text,
  cree_le timestamptz NOT NULL DEFAULT clock_timestamp()
);
CREATE INDEX IF NOT EXISTS erp_da_status_idx ON public.erp_purchase_requests(statut,cree_le DESC);

ALTER TABLE public.erp_purchase_requests ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.erp_purchase_request_lines ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.erp_purchase_request_operations ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.erp_purchase_request_events ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON public.erp_purchase_requests,public.erp_purchase_request_lines,
  public.erp_purchase_request_operations,public.erp_purchase_request_events
  FROM PUBLIC,anon,authenticated;
GRANT SELECT,INSERT,UPDATE ON public.erp_purchase_requests,
  public.erp_purchase_request_lines,public.erp_purchase_request_operations,
  public.erp_purchase_request_events TO service_role;
GRANT USAGE,SELECT ON SEQUENCE public.erp_purchase_request_events_evenement_id_seq
  TO service_role;

CREATE OR REPLACE FUNCTION public.erp_purchase_request_transaction(
 p_action text, p_operation_id text, p_acteur_id text, p_payload jsonb
) RETURNS jsonb LANGUAGE plpgsql SECURITY INVOKER
SET search_path=pg_catalog,public
AS $action$
DECLARE
 v_role text;
 v_da public.erp_purchase_requests%ROWTYPE;
 v_id text;
 v_saved record;
 v_result jsonb;
 v_rows jsonb;
 v_lines jsonb;
 v_line record;
 v_unit text;
 v_ok bool;
 v_po jsonb;
 v_old text;
 v_approved jsonb;
 v_actual jsonb;
 v_count integer:=0;
 v_date date;
BEGIN
 IF p_action NOT IN ('CREATE','SUBMIT','APPROVE','REJECT','CONVERT')
    OR p_operation_id IS NULL OR length(btrim(p_operation_id)) NOT BETWEEN 1 AND 128
    OR p_acteur_id IS NULL OR length(btrim(p_acteur_id)) NOT BETWEEN 1 AND 200
    OR jsonb_typeof(p_payload) IS DISTINCT FROM 'object' THEN
   RAISE EXCEPTION 'Action demande achat invalide' USING ERRCODE='22023';
 END IF;
 SELECT u.role INTO v_role FROM public.users u
 WHERE u.user_id=p_acteur_id
   AND upper(btrim(coalesce(u.actif,''))) IN ('OUI','ACTIF','ACTIVE','TRUE','1','YES')
 FOR SHARE;
 IF NOT FOUND OR (
   upper(btrim(coalesce(v_role,''))) NOT IN ('ADMIN','ADMINISTRATEUR','SUPERADMIN')
   AND NOT EXISTS (SELECT 1 FROM public.permissions pr
      WHERE pr.role=v_role AND lower(btrim(pr.module))='achats'
      AND upper(btrim(coalesce(pr.ecriture,''))) IN ('OUI','TRUE','1','YES'))
 ) THEN RAISE EXCEPTION 'Acteur Achats inactif ou non habilité' USING ERRCODE='42501'; END IF;

 -- Sérialise une tentative identique même avec deux sessions concurrentes.
 PERFORM pg_advisory_xact_lock(hashtextextended('erp:da:op:'||p_operation_id,0));
 SELECT action,acteur_id,request_payload,result_payload INTO v_saved
 FROM public.erp_purchase_request_operations WHERE operation_id=p_operation_id FOR UPDATE;
 IF FOUND THEN
   IF v_saved.action IS DISTINCT FROM p_action
      OR v_saved.acteur_id IS DISTINCT FROM p_acteur_id
      OR v_saved.request_payload IS DISTINCT FROM p_payload THEN
     RAISE EXCEPTION 'Identifiant opération utilisé avec des données différentes'
       USING ERRCODE='23505';
   END IF;
   IF v_saved.result_payload IS NULL THEN
      RAISE EXCEPTION 'Opération antérieure non confirmée' USING ERRCODE='23514';
   END IF;
   RETURN v_saved.result_payload;
 END IF;
 INSERT INTO public.erp_purchase_request_operations(operation_id,action,acteur_id,request_payload)
 VALUES(p_operation_id,p_action,p_acteur_id,p_payload);

 IF p_action='CREATE' THEN
   IF nullif(btrim(coalesce(p_payload->>'motivation','')),'') IS NULL
      OR length(btrim(p_payload->>'motivation')) NOT BETWEEN 10 AND 1500
      OR (p_payload->>'date_souhaitee') !~ '^[0-9]{4}-[0-9]{2}-[0-9]{2}$'
      OR jsonb_typeof(p_payload->'lignes')<>'array'
      OR jsonb_array_length(p_payload->'lignes') NOT BETWEEN 1 AND 100 THEN
      RAISE EXCEPTION 'Demande incomplète ou hors limites' USING ERRCODE='22023';
   END IF;
   v_date:=(p_payload->>'date_souhaitee')::date;
   IF to_char(v_date,'YYYY-MM-DD') <> p_payload->>'date_souhaitee' THEN
      RAISE EXCEPTION 'Date de besoin invalide' USING ERRCODE='22023'; END IF;
   v_id:='DA-'||gen_random_uuid()::text;
   INSERT INTO public.erp_purchase_requests(demande_id,demandeur_id,motivation,date_souhaitee)
   VALUES(v_id,p_acteur_id,btrim(p_payload->>'motivation'),v_date);
   FOR v_line IN
    SELECT * FROM jsonb_to_recordset(p_payload->'lignes')
    AS x(mp_id text,quantite numeric)
   LOOP
     IF v_line.mp_id IS NULL OR length(btrim(v_line.mp_id)) NOT BETWEEN 1 AND 200
        OR v_line.quantite IS NULL OR v_line.quantite::text IN ('NaN','Infinity','-Infinity')
        OR v_line.quantite<=0 OR v_line.quantite>=1000000000000000 THEN
        RAISE EXCEPTION 'Ligne de demande invalide' USING ERRCODE='22023'; END IF;
     SELECT unite_stock INTO v_unit FROM public.matieres_premieres
       WHERE mp_id=v_line.mp_id AND upper(btrim(coalesce(actif,'')))='OUI' FOR SHARE;
     IF NOT FOUND OR nullif(btrim(coalesce(v_unit,'')),'') IS NULL THEN
        RAISE EXCEPTION 'Matière inactive ou unité absente' USING ERRCODE='23514'; END IF;
     INSERT INTO public.erp_purchase_request_lines(demande_id,mp_id,unite_stock,quantite)
     VALUES(v_id,v_line.mp_id,v_unit,v_line.quantite);
     v_count:=v_count+1;
   END LOOP;
   IF v_count<>jsonb_array_length(p_payload->'lignes') THEN
      RAISE EXCEPTION 'Lignes de demande incohérentes' USING ERRCODE='23514'; END IF;
   v_old:=NULL;
   v_result:=jsonb_build_object('operation_id',p_operation_id,'demande_id',v_id,
       'statut','BROUILLON','lignes',v_count);
 ELSE
   v_id:=p_payload->>'demande_id';
   IF v_id IS NULL OR length(btrim(v_id)) NOT BETWEEN 1 AND 200 THEN
     RAISE EXCEPTION 'Référence demande absente' USING ERRCODE='22023'; END IF;
   SELECT * INTO v_da FROM public.erp_purchase_requests WHERE demande_id=v_id FOR UPDATE;
   IF NOT FOUND THEN RAISE EXCEPTION 'Demande introuvable' USING ERRCODE='23503'; END IF;
   v_old:=v_da.statut;

   IF p_action='SUBMIT' THEN
     IF v_da.statut<>'BROUILLON' OR v_da.demandeur_id<>p_acteur_id THEN
        RAISE EXCEPTION 'Soumission interdite' USING ERRCODE='23514'; END IF;
     UPDATE public.erp_purchase_requests SET statut='SOUMISE',soumis_le=clock_timestamp()
     WHERE demande_id=v_id;
     v_result:=jsonb_build_object('demande_id',v_id,'statut','SOUMISE');

   ELSIF p_action IN ('APPROVE','REJECT') THEN
     IF v_da.statut<>'SOUMISE' OR v_da.demandeur_id=p_acteur_id THEN
        RAISE EXCEPTION 'Double validation : approbateur distinct obligatoire'
          USING ERRCODE='23514'; END IF;
     IF p_action='REJECT'
        AND length(btrim(coalesce(p_payload->>'commentaire',''))) NOT BETWEEN 10 AND 1000
     THEN RAISE EXCEPTION 'Refus exige un motif documenté' USING ERRCODE='22023'; END IF;
     UPDATE public.erp_purchase_requests
     SET statut=CASE WHEN p_action='APPROVE' THEN 'APPROUVEE' ELSE 'REFUSEE' END,
         approbateur_id=p_acteur_id,decide_le=clock_timestamp(),
         decision_motif=nullif(btrim(coalesce(p_payload->>'commentaire','')),'')
     WHERE demande_id=v_id;
     v_result:=jsonb_build_object('demande_id',v_id,
         'statut',CASE WHEN p_action='APPROVE' THEN 'APPROUVEE' ELSE 'REFUSEE' END,
         'approbateur_id',p_acteur_id);

   ELSIF p_action='CONVERT' THEN
     IF v_da.statut<>'APPROUVEE' OR v_da.approbateur_id IS NULL
       OR v_da.demandeur_id=v_da.approbateur_id
     THEN RAISE EXCEPTION 'Commande réservée aux demandes approuvées'
       USING ERRCODE='23514'; END IF;
     IF p_payload->>'fournisseur_id' IS NULL OR
        length(btrim(p_payload->>'fournisseur_id')) NOT BETWEEN 1 AND 200 THEN
       RAISE EXCEPTION 'Fournisseur non renseigné' USING ERRCODE='22023'; END IF;
     PERFORM 1 FROM public.fournisseurs
       WHERE fournisseur_id=p_payload->>'fournisseur_id'
       AND upper(btrim(coalesce(actif,'')))='OUI' FOR SHARE;
     IF NOT FOUND THEN RAISE EXCEPTION 'Fournisseur absent ou inactif' USING ERRCODE='23514'; END IF;
     IF jsonb_typeof(p_payload->'lignes')<>'array'
       OR jsonb_array_length(p_payload->'lignes')<1
       OR jsonb_array_length(p_payload->'lignes')>100 THEN
       RAISE EXCEPTION 'Lignes commande requises' USING ERRCODE='22023'; END IF;
     -- Couverture intégrale de la demande approuvée, sans substitution ni surachat.
     SELECT jsonb_object_agg(mp_id,quantite ORDER BY mp_id) INTO v_approved
       FROM public.erp_purchase_request_lines WHERE demande_id=v_id;
     v_rows:='[]'::jsonb;
     FOR v_line IN SELECT * FROM jsonb_to_recordset(p_payload->'lignes')
        AS x(mp_id text,quantite numeric,prix_unitaire numeric)
     LOOP
       IF v_line.mp_id IS NULL OR v_line.quantite IS NULL
          OR v_line.prix_unitaire IS NULL
          OR v_line.quantite::text IN ('NaN','Infinity','-Infinity')
          OR v_line.prix_unitaire::text IN ('NaN','Infinity','-Infinity')
          OR v_line.quantite<=0 OR v_line.quantite>=1000000000000000
          OR v_line.prix_unitaire<0 OR v_line.prix_unitaire>=1000000000000000
          OR NOT (v_approved ? v_line.mp_id) THEN
           RAISE EXCEPTION 'Ligne BC absente de la demande ou invalide'
             USING ERRCODE='23514'; END IF;
       SELECT unite_stock INTO STRICT v_unit
         FROM public.erp_purchase_request_lines
         WHERE demande_id=v_id AND mp_id=v_line.mp_id;
       IF (SELECT upper(btrim(coalesce(actif,''))) FROM public.matieres_premieres
          WHERE mp_id=v_line.mp_id) IS DISTINCT FROM 'OUI' THEN
          RAISE EXCEPTION 'Matière devenue inactive' USING ERRCODE='23514'; END IF;
       v_rows:=v_rows||jsonb_build_array(jsonb_build_object(
         'ligne_achat_id','LAC-'||gen_random_uuid()::text,
         'mp_id',v_line.mp_id,'unite_cond',v_unit,
         'qte_cond',v_line.quantite,'qte_totale',v_line.quantite,
         'prix_unitaire',v_line.prix_unitaire,
         'total_devise',v_line.quantite*v_line.prix_unitaire));
       v_count:=v_count+1;
     END LOOP;
     SELECT jsonb_object_agg(mp_id,quantite ORDER BY mp_id) INTO v_actual
       FROM jsonb_to_recordset(p_payload->'lignes') AS x(mp_id text,quantite numeric);
     IF v_actual IS DISTINCT FROM v_approved OR
        v_count<>(SELECT count(*) FROM public.erp_purchase_request_lines WHERE demande_id=v_id)
     THEN RAISE EXCEPTION 'Quantités du BC différentes de la demande approuvée'
          USING ERRCODE='23514'; END IF;
     v_po:=public.erp_create_purchase_order(
        'DA-PO-'||p_operation_id,'CMA-DA-'||gen_random_uuid()::text,
        p_payload->>'fournisseur_id',p_payload->>'type_achat',
        p_payload->>'devise',(p_payload->>'taux_change')::numeric,
        coalesce(p_payload->>'mode_paiement',''),
        coalesce(p_payload->>'delai_paiement',''),
        coalesce(p_payload->>'date_voulue',''),v_rows);
     IF v_po->>'commande_achat_id' IS NULL THEN
       RAISE EXCEPTION 'BC non confirmé' USING ERRCODE='23514'; END IF;
     UPDATE public.erp_purchase_requests SET statut='COMMANDEE',
       commande_achat_id=v_po->>'commande_achat_id',commande_le=clock_timestamp()
     WHERE demande_id=v_id;
     v_result:=jsonb_build_object('demande_id',v_id,'statut','COMMANDEE',
         'commande_achat_id',v_po->>'commande_achat_id');
   END IF;
 END IF;

 UPDATE public.erp_purchase_request_operations SET result_payload=v_result
 WHERE operation_id=p_operation_id;
 INSERT INTO public.erp_purchase_request_events(demande_id,operation_id,acteur_id,
      action,ancien_statut,nouveau_statut,commentaire)
 VALUES(v_id,p_operation_id,p_acteur_id,p_action,v_old,v_result->>'statut',
        nullif(btrim(coalesce(p_payload->>'commentaire','')),''));
 RETURN v_result||jsonb_build_object('operation_id',p_operation_id);
END $action$;

REVOKE ALL ON FUNCTION public.erp_purchase_request_transaction(text,text,text,jsonb)
 FROM PUBLIC,anon,authenticated;
GRANT EXECUTE ON FUNCTION public.erp_purchase_request_transaction(text,text,text,jsonb)
 TO service_role;
COMMIT;
