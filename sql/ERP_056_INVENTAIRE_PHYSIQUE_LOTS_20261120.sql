-- ERP-056 — Inventaire physique par lot, piste d'audit et ajustements sous approbation.
-- Schéma additif : aucune mutation des stocks historiques lors de l'installation.
-- APIs SERVICE_ROLE UNIQUEMENT, SECURITY INVOKER et RLS sans politiques client.
BEGIN;

CREATE TABLE public.erp_inventory_campaigns (
    inventory_id text PRIMARY KEY CHECK (length(inventory_id) BETWEEN 8 AND 128),
    item_type text NOT NULL CHECK (item_type IN ('MP','PF')),
    item_id text NOT NULL,
    area_label text NOT NULL,
    reason text NOT NULL,
    status text NOT NULL DEFAULT 'OUVERT'
        CHECK (status IN ('OUVERT','SOUMIS','APPROUVE','APPLIQUE','ANNULE')),
    source_quantity numeric NOT NULL CHECK (source_quantity >= 0 AND source_quantity < 1e15),
    source_unit_cost numeric CHECK (source_unit_cost >= 0 AND source_unit_cost < 1e15),
    source_movement_count bigint NOT NULL CHECK (source_movement_count >= 0),
    created_by text NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    submitted_by text, submitted_at timestamptz,
    approved_by text, approved_at timestamptz, approval_reason text,
    applied_by text, applied_at timestamptz, applied_operation_id text UNIQUE,
    result_payload jsonb,
    CHECK (length(item_id) BETWEEN 1 AND 200),
    CHECK (length(area_label) BETWEEN 1 AND 120),
    CHECK (length(reason) BETWEEN 1 AND 500)
);
CREATE UNIQUE INDEX erp_inventory_one_open_per_item
  ON public.erp_inventory_campaigns(item_type,item_id)
  WHERE status IN ('OUVERT','SOUMIS','APPROUVE');

CREATE TABLE public.erp_inventory_lines (
    inventory_id text NOT NULL REFERENCES public.erp_inventory_campaigns(inventory_id),
    lot_id text NOT NULL,
    expected_quantity numeric NOT NULL CHECK (expected_quantity >= 0 AND expected_quantity < 1e15),
    counted_quantity numeric CHECK (counted_quantity >= 0 AND counted_quantity < 1e15),
    counted_by text,
    counted_at timestamptz,
    count_note text,
    PRIMARY KEY (inventory_id,lot_id)
);

CREATE TABLE public.erp_inventory_events (
    event_id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    inventory_id text NOT NULL REFERENCES public.erp_inventory_campaigns(inventory_id),
    operation_id text NOT NULL UNIQUE,
    action text NOT NULL CHECK(action IN ('COUNT','SUBMIT','APPROVE','APPLY')),
    actor_id text NOT NULL,
    request_payload jsonb NOT NULL,
    result_payload jsonb NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now()
);

ALTER TABLE public.erp_inventory_campaigns ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.erp_inventory_lines ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.erp_inventory_events ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON public.erp_inventory_campaigns, public.erp_inventory_lines,
    public.erp_inventory_events FROM PUBLIC, anon, authenticated;
GRANT SELECT, INSERT, UPDATE ON public.erp_inventory_campaigns,
    public.erp_inventory_lines, public.erp_inventory_events TO service_role;
GRANT USAGE, SELECT ON SEQUENCE public.erp_inventory_events_event_id_seq TO service_role;

-- Contrôle à chaque commande avec le rôle ERP réellement actif en base.
CREATE FUNCTION public.erp_inventory_actor_allowed(p_actor_id text)
RETURNS boolean LANGUAGE sql SECURITY INVOKER
SET search_path=pg_catalog,public
AS $func$
    SELECT EXISTS (
        SELECT 1 FROM public.users u
        WHERE u.user_id=p_actor_id AND u.actif='OUI' AND
        (
            upper(btrim(u.role)) IN ('ADMIN','ADMINISTRATEUR','SUPERADMIN')
            OR EXISTS (
                SELECT 1 FROM public.permissions p
                WHERE upper(btrim(p.role))=upper(btrim(u.role))
                  AND upper(btrim(p.module))='STOCKS'
                  AND p.ecriture='OUI'
            )
        )
    );
$func$;

CREATE FUNCTION public.erp_inventory_start(
 p_inventory_id text, p_actor_id text, p_item_type text,
 p_item_id text, p_area_label text, p_reason text
) RETURNS jsonb LANGUAGE plpgsql SECURITY INVOKER
SET search_path=pg_catalog,public
AS $func$
DECLARE
 v_prior public.erp_inventory_campaigns%ROWTYPE;
 v_qty numeric; v_cost numeric; v_lots_qty numeric;
 v_lots_count integer; v_mov_count bigint; v_out jsonb;
BEGIN
 IF NOT public.erp_inventory_actor_allowed(p_actor_id) THEN
    RAISE EXCEPTION 'Accès inventaire refusé' USING ERRCODE='42501';
 END IF;
 IF p_inventory_id IS NULL OR length(p_inventory_id) NOT BETWEEN 8 AND 128
    OR p_inventory_id !~ '^INV-[A-Za-z0-9_-]+$'
    OR p_item_type IS NULL OR p_item_type NOT IN ('MP','PF')
    OR p_item_id IS NULL OR length(btrim(p_item_id)) NOT BETWEEN 1 AND 200
    OR p_area_label IS NULL OR length(btrim(p_area_label)) NOT BETWEEN 1 AND 120
    OR p_reason IS NULL OR length(btrim(p_reason)) NOT BETWEEN 1 AND 500 THEN
    RAISE EXCEPTION 'Identifiants, localisation ou motif invalides' USING ERRCODE='22023';
 END IF;
 -- Même verrou que erp_apply_stock_movement pour éviter un snapshot concurrent.
 PERFORM pg_advisory_xact_lock(
    hashtextextended('ERP_STOCK:'||p_item_type||':'||p_item_id,0));
 SELECT * INTO v_prior FROM public.erp_inventory_campaigns
  WHERE inventory_id=p_inventory_id FOR UPDATE;
 IF FOUND THEN
    IF v_prior.item_type<>p_item_type OR v_prior.item_id<>p_item_id
       OR v_prior.area_label<>btrim(p_area_label)
       OR v_prior.reason<>btrim(p_reason)
       OR v_prior.created_by<>p_actor_id THEN
       RAISE EXCEPTION 'Identifiant inventaire déjà utilisé autrement' USING ERRCODE='23505';
    END IF;
    RETURN jsonb_build_object('inventory_id',p_inventory_id,'status',v_prior.status,
        'reused',true);
 END IF;
 IF p_item_type='MP' THEN
    PERFORM 1 FROM public.matieres_premieres WHERE mp_id=p_item_id;
    IF NOT FOUND THEN RAISE EXCEPTION 'MP inconnue' USING ERRCODE='23503'; END IF;
    SELECT quantite_disponible,cmp_actuel INTO v_qty,v_cost
      FROM public.stock_actuel WHERE mp_id=p_item_id FOR UPDATE;
    SELECT count(*) INTO v_mov_count FROM public.mouvements WHERE mp_id=p_item_id;
 ELSE
    PERFORM 1 FROM public.sku_conditionnement WHERE sku_id=p_item_id;
    IF NOT FOUND THEN RAISE EXCEPTION 'SKU inconnu' USING ERRCODE='23503'; END IF;
    SELECT quantite_disponible,cout_revient INTO v_qty,v_cost
      FROM public.stock_actuel_pf WHERE sku_id=p_item_id FOR UPDATE;
    SELECT count(*) INTO v_mov_count FROM public.mouvements_pf WHERE sku_id=p_item_id;
 END IF;
 v_qty:=coalesce(v_qty,0);
 IF v_qty<0 OR v_qty>=1e15 OR v_qty::text IN ('NaN','Infinity','-Infinity')
    OR (v_cost IS NOT NULL AND
       (v_cost<0 OR v_cost>=1e15 OR v_cost::text IN ('NaN','Infinity','-Infinity'))) THEN
     RAISE EXCEPTION 'Stock ou PMP invalides' USING ERRCODE='23514';
 END IF;
 SELECT count(*),coalesce(sum(quantite_restante),0)
    INTO v_lots_count,v_lots_qty
    FROM public.lots
    WHERE item_id=p_item_id AND type_item=p_item_type
      AND quantite_restante>0 AND statut='ACTIF';
 -- Ne pas inventer de lot, et ne pas effacer un stock orphelin par comptage.
 IF v_lots_count=0 OR v_qty<>v_lots_qty OR EXISTS(
    SELECT 1 FROM public.lots
    WHERE item_id=p_item_id AND type_item=p_item_type
      AND (quantite_restante<0 OR
           (quantite_restante>0 AND statut<>'ACTIF'))
 ) THEN
    RAISE EXCEPTION 'Incohérence stock global/lots : réconciliation préalable obligatoire'
        USING ERRCODE='23514';
 END IF;
 INSERT INTO public.erp_inventory_campaigns(
  inventory_id,item_type,item_id,area_label,reason,source_quantity,
  source_unit_cost,source_movement_count,created_by)
 VALUES(p_inventory_id,p_item_type,p_item_id,btrim(p_area_label),btrim(p_reason),
        v_qty,v_cost,v_mov_count,p_actor_id);
 INSERT INTO public.erp_inventory_lines(inventory_id,lot_id,expected_quantity)
 SELECT p_inventory_id,lot_id,quantite_restante FROM public.lots
 WHERE item_id=p_item_id AND type_item=p_item_type
   AND quantite_restante>0 AND statut='ACTIF';
 v_out:=jsonb_build_object('inventory_id',p_inventory_id,'status','OUVERT',
     'lot_count',v_lots_count,'theoretical_quantity',v_qty);
 RETURN v_out;
END;
$func$;

CREATE FUNCTION public.erp_inventory_command(
 p_operation_id text, p_actor_id text, p_inventory_id text, p_action text,
 p_lot_id text DEFAULT NULL, p_count numeric DEFAULT NULL,
 p_note text DEFAULT NULL
) RETURNS jsonb LANGUAGE plpgsql SECURITY INVOKER
SET search_path=pg_catalog,public
AS $func$
DECLARE
 v_inv public.erp_inventory_campaigns%ROWTYPE;
 v_prev public.erp_inventory_events%ROWTYPE;
 v_request jsonb; v_result jsonb;
 v_unfilled integer; v_delta numeric; v_qty numeric; v_cost numeric;
 v_count bigint; v_lot record; v_old_qty numeric; v_new_qty numeric;
 v_changes integer:=0; v_total_delta numeric:=0; v_row_count integer;
 v_reference text; v_movement_id text;
BEGIN
 IF NOT public.erp_inventory_actor_allowed(p_actor_id) THEN
    RAISE EXCEPTION 'Accès inventaire refusé' USING ERRCODE='42501';
 END IF;
 IF p_operation_id IS NULL OR length(btrim(p_operation_id)) NOT BETWEEN 8 AND 128
    OR p_inventory_id IS NULL OR length(p_inventory_id) NOT BETWEEN 8 AND 128
    OR p_action IS NULL OR p_action NOT IN ('COUNT','SUBMIT','APPROVE','APPLY')
    OR p_note IS NOT NULL AND length(p_note)>500 THEN
    RAISE EXCEPTION 'Commande inventaire invalide' USING ERRCODE='22023';
 END IF;
 v_request:=jsonb_build_object('action',p_action,'inventory_id',p_inventory_id,
     'lot_id',p_lot_id,'count',p_count,'note',p_note,'actor',p_actor_id);
 SELECT * INTO v_prev FROM public.erp_inventory_events
     WHERE operation_id=p_operation_id FOR UPDATE;
 IF FOUND THEN
    IF v_prev.request_payload IS DISTINCT FROM v_request THEN
       RAISE EXCEPTION 'Operation_id réutilisé pour une autre commande'
         USING ERRCODE='23505';
    END IF;
    RETURN v_prev.result_payload;
 END IF;
 SELECT * INTO v_inv FROM public.erp_inventory_campaigns
  WHERE inventory_id=p_inventory_id FOR UPDATE;
 IF NOT FOUND THEN RAISE EXCEPTION 'Inventaire inconnu' USING ERRCODE='23503'; END IF;
 IF p_action='COUNT' THEN
    IF v_inv.status<>'OUVERT' OR p_lot_id IS NULL
       OR length(btrim(p_lot_id))=0 OR length(p_lot_id)>200
       OR p_count IS NULL OR p_count<0 OR p_count>=1e15
       OR p_count::text IN ('NaN','Infinity','-Infinity') THEN
       RAISE EXCEPTION 'Comptage invalide ou inventaire verrouillé' USING ERRCODE='23514';
    END IF;
    UPDATE public.erp_inventory_lines SET counted_quantity=p_count,
       counted_by=p_actor_id,counted_at=now(),count_note=p_note
     WHERE inventory_id=p_inventory_id AND lot_id=p_lot_id;
    GET DIAGNOSTICS v_row_count=ROW_COUNT;
    IF v_row_count<>1 THEN
       RAISE EXCEPTION 'Lot hors inventaire' USING ERRCODE='23503';
    END IF;
    v_result:=jsonb_build_object('inventory_id',p_inventory_id,
       'lot_id',p_lot_id,'counted',p_count,'status','OUVERT');
 ELSIF p_action='SUBMIT' THEN
    IF v_inv.status<>'OUVERT' THEN
       RAISE EXCEPTION 'Inventaire non ouvert' USING ERRCODE='23514';
    END IF;
    SELECT count(*) INTO v_unfilled FROM public.erp_inventory_lines
      WHERE inventory_id=p_inventory_id AND counted_quantity IS NULL;
    IF v_unfilled>0 THEN
       RAISE EXCEPTION 'Comptages manquants' USING ERRCODE='23514';
    END IF;
    UPDATE public.erp_inventory_campaigns SET
      status='SOUMIS',submitted_by=p_actor_id,submitted_at=now()
      WHERE inventory_id=p_inventory_id;
    v_result:=jsonb_build_object('inventory_id',p_inventory_id,'status','SOUMIS');
 ELSIF p_action='APPROVE' THEN
    IF v_inv.status<>'SOUMIS' OR v_inv.created_by=p_actor_id
       OR v_inv.submitted_by=p_actor_id
       OR EXISTS(SELECT 1 FROM public.erp_inventory_lines
                 WHERE inventory_id=p_inventory_id AND counted_by=p_actor_id)
       OR p_note IS NULL OR length(btrim(p_note))<12 THEN
       RAISE EXCEPTION 'Approbation indépendante et justification requises'
         USING ERRCODE='42501';
    END IF;
    UPDATE public.erp_inventory_campaigns SET
      status='APPROUVE',approved_by=p_actor_id,approved_at=now(),
      approval_reason=btrim(p_note)
      WHERE inventory_id=p_inventory_id;
    v_result:=jsonb_build_object('inventory_id',p_inventory_id,'status','APPROUVE');
 ELSE
    IF v_inv.status<>'APPROUVE' OR v_inv.approved_by IS NULL
       OR v_inv.approved_by<>p_actor_id THEN
       RAISE EXCEPTION 'Application réservée à l approbateur confirmé'
          USING ERRCODE='42501';
    END IF;
    PERFORM pg_advisory_xact_lock(
       hashtextextended('ERP_STOCK:'||v_inv.item_type||':'||v_inv.item_id,0));
    IF v_inv.item_type='MP' THEN
       SELECT quantite_disponible,cmp_actuel INTO v_qty,v_cost
        FROM public.stock_actuel WHERE mp_id=v_inv.item_id FOR UPDATE;
       SELECT count(*) INTO v_count FROM public.mouvements WHERE mp_id=v_inv.item_id;
    ELSE
       SELECT quantite_disponible,cout_revient INTO v_qty,v_cost
        FROM public.stock_actuel_pf WHERE sku_id=v_inv.item_id FOR UPDATE;
       SELECT count(*) INTO v_count FROM public.mouvements_pf WHERE sku_id=v_inv.item_id;
    END IF;
    IF v_qty IS DISTINCT FROM v_inv.source_quantity
       OR v_cost IS DISTINCT FROM v_inv.source_unit_cost
       OR v_count<>v_inv.source_movement_count
       OR (SELECT count(*) FROM public.lots
           WHERE type_item=v_inv.item_type AND item_id=v_inv.item_id
             AND statut='ACTIF' AND quantite_restante>0)
          <> (SELECT count(*) FROM public.erp_inventory_lines
              WHERE inventory_id=p_inventory_id) THEN
       RAISE EXCEPTION 'Stock modifié depuis ouverture : nouveau comptage requis'
          USING ERRCODE='40001';
    END IF;
    IF EXISTS(
      SELECT 1 FROM public.erp_inventory_lines i
      LEFT JOIN public.lots l ON l.lot_id=i.lot_id
      WHERE i.inventory_id=p_inventory_id
        AND (l.type_item IS DISTINCT FROM v_inv.item_type
         OR l.item_id IS DISTINCT FROM v_inv.item_id
         OR l.quantite_restante IS DISTINCT FROM i.expected_quantity
         OR l.statut IS DISTINCT FROM 'ACTIF'
         OR i.counted_quantity IS NULL)
    ) THEN
       RAISE EXCEPTION 'Lots modifiés ou comptage incomplet : appliquer interdit'
          USING ERRCODE='40001';
    END IF;
    SELECT coalesce(sum(counted_quantity-expected_quantity),0)
      INTO v_total_delta FROM public.erp_inventory_lines
      WHERE inventory_id=p_inventory_id;
    IF v_total_delta<>0 AND
        (v_cost IS NULL OR v_cost<=0 OR v_cost>=1e15
         OR v_cost::text IN ('NaN','Infinity','-Infinity')) THEN
        RAISE EXCEPTION 'PMP documenté obligatoire pour régulariser'
           USING ERRCODE='23514';
    END IF;
    v_new_qty:=v_qty+v_total_delta;
    IF v_new_qty<0 OR v_new_qty>=1e15 THEN
       RAISE EXCEPTION 'Stock corrigé hors limites' USING ERRCODE='23514';
    END IF;
    v_reference:='INVENTAIRE:'||p_inventory_id;
    FOR v_lot IN
      SELECT i.lot_id,i.expected_quantity,i.counted_quantity,
             l.quantite_restante
      FROM public.erp_inventory_lines i
      JOIN public.lots l ON l.lot_id=i.lot_id
      WHERE i.inventory_id=p_inventory_id
      ORDER BY i.lot_id FOR UPDATE OF l
    LOOP
      v_delta:=v_lot.counted_quantity-v_lot.expected_quantity;
      CONTINUE WHEN v_delta=0;
      UPDATE public.lots SET quantite_restante=v_lot.counted_quantity,
        statut=CASE WHEN v_lot.counted_quantity=0 THEN 'EPUISE' ELSE 'ACTIF' END
        WHERE lot_id=v_lot.lot_id;
      IF v_inv.item_type='MP' THEN
        v_movement_id:='INV-M-'||gen_random_uuid()::text;
        INSERT INTO public.mouvements
         (mouvement_id,date,type_mouvement,mp_id,quantite,reference,lot_id,prix_entree)
        VALUES(v_movement_id,to_char(now() AT TIME ZONE 'UTC','YYYY-MM-DD HH24:MI:SS'),
          CASE WHEN v_delta>0 THEN 'ENTREE' ELSE 'SORTIE' END,
          v_inv.item_id,abs(v_delta),v_reference,v_lot.lot_id,v_cost);
      ELSE
        v_movement_id:='INV-P-'||gen_random_uuid()::text;
        INSERT INTO public.mouvements_pf
         (mouvement_pf_id,date,type_mouvement,sku_id,quantite,reference,lot_id,cout_unitaire)
        VALUES(v_movement_id,to_char(now() AT TIME ZONE 'UTC','YYYY-MM-DD HH24:MI:SS'),
          CASE WHEN v_delta>0 THEN 'ENTREE' ELSE 'SORTIE' END,
          v_inv.item_id,abs(v_delta),v_reference,v_lot.lot_id,v_cost);
      END IF;
      v_changes:=v_changes+1;
    END LOOP;
    IF v_inv.item_type='MP' THEN
       UPDATE public.stock_actuel SET
         quantite_disponible=v_new_qty,
         derniere_maj=to_char(now() AT TIME ZONE 'UTC','YYYY-MM-DD HH24:MI:SS')
       WHERE mp_id=v_inv.item_id;
    ELSE
       UPDATE public.stock_actuel_pf SET
         quantite_disponible=v_new_qty,
         derniere_maj=to_char(now() AT TIME ZONE 'UTC','YYYY-MM-DD HH24:MI:SS')
       WHERE sku_id=v_inv.item_id;
    END IF;
    v_result:=jsonb_build_object('inventory_id',p_inventory_id,'status','APPLIQUE',
       'movement_count',v_changes,'delta',v_total_delta,
       'stock_final',v_new_qty,'requires_scf_review',v_changes>0);
    UPDATE public.erp_inventory_campaigns SET
      status='APPLIQUE',applied_by=p_actor_id,applied_at=now(),
      applied_operation_id=p_operation_id,result_payload=v_result
      WHERE inventory_id=p_inventory_id;
 END IF;
 INSERT INTO public.erp_inventory_events
   (inventory_id,operation_id,action,actor_id,request_payload,result_payload)
 VALUES(p_inventory_id,p_operation_id,p_action,p_actor_id,v_request,v_result);
 RETURN v_result;
END;
$func$;

REVOKE ALL ON FUNCTION public.erp_inventory_actor_allowed(text) FROM PUBLIC,anon,authenticated;
REVOKE ALL ON FUNCTION public.erp_inventory_start(text,text,text,text,text,text) FROM PUBLIC,anon,authenticated;
REVOKE ALL ON FUNCTION public.erp_inventory_command(text,text,text,text,text,numeric,text) FROM PUBLIC,anon,authenticated;
GRANT EXECUTE ON FUNCTION public.erp_inventory_actor_allowed(text) TO service_role;
GRANT EXECUTE ON FUNCTION public.erp_inventory_start(text,text,text,text,text,text) TO service_role;
GRANT EXECUTE ON FUNCTION public.erp_inventory_command(text,text,text,text,text,numeric,text) TO service_role;

COMMIT;
