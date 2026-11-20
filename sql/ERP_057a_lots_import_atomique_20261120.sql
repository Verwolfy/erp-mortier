-- ERP-057A : snapshot de lots et import atomique de comptages (aucun mouvement de stock).
-- Compatible avec ERP-056. L'absence de référentiel dépôts interdit une
-- affectation fictive de quantités par emplacement.
BEGIN;

CREATE TABLE IF NOT EXISTS public.erp_inventaire_lots (
 inventaire_id text NOT NULL REFERENCES public.erp_inventaires(inventaire_id) ON DELETE RESTRICT,
 lot_id text NOT NULL,
 type_article text NOT NULL CHECK(type_article IN ('MP','PF')),
 article_id text NOT NULL,
 quantite_theorique numeric NOT NULL
   CHECK (quantite_theorique >= 0 AND quantite_theorique < 1000000000000000),
 statut_snapshot text,
 date_peremption_snapshot text,
 quantite_comptee numeric
   CHECK (quantite_comptee IS NULL OR (quantite_comptee >= 0 AND quantite_comptee < 1000000000000000)),
 compte_par text REFERENCES public.users(user_id),
 compte_le timestamptz,
 motif_ecart text CHECK (motif_ecart IS NULL OR length(motif_ecart) <= 600),
 PRIMARY KEY (inventaire_id, lot_id),
 FOREIGN KEY(inventaire_id,type_article,article_id)
   REFERENCES public.erp_inventaire_lignes(inventaire_id,type_article,article_id)
   DEFERRABLE INITIALLY DEFERRED,
 CONSTRAINT erp_inv_lot_count_metadata CHECK (
   (quantite_comptee IS NULL AND compte_par IS NULL AND compte_le IS NULL)
    OR (quantite_comptee IS NOT NULL AND compte_par IS NOT NULL AND compte_le IS NOT NULL)
 )
);
CREATE TABLE IF NOT EXISTS public.erp_inventaire_import_operations (
 operation_id text PRIMARY KEY CHECK (operation_id ~ '^INVIMP-[A-Za-z0-9-]{8,110}$'),
 inventaire_id text NOT NULL REFERENCES public.erp_inventaires(inventaire_id),
 acteur_id text NOT NULL REFERENCES public.users(user_id),
 payload jsonb NOT NULL,
 result_payload jsonb,
 cree_le timestamptz NOT NULL DEFAULT clock_timestamp()
);
ALTER TABLE public.erp_inventaire_import_operations ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON public.erp_inventaire_import_operations FROM PUBLIC,anon,authenticated;
GRANT SELECT,INSERT,UPDATE ON public.erp_inventaire_import_operations TO service_role;

CREATE INDEX IF NOT EXISTS erp_inv_lots_article_idx
 ON public.erp_inventaire_lots(inventaire_id,type_article,article_id);
ALTER TABLE public.erp_inventaire_lots ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON public.erp_inventaire_lots FROM PUBLIC,anon,authenticated;
GRANT SELECT,INSERT,UPDATE ON public.erp_inventaire_lots TO service_role;

-- Le trigger se déclenche dans la même transaction que la création ERP-056.
-- FK différée : les lignes article sont insérées ensuite par erp_inventory_create.
CREATE OR REPLACE FUNCTION public.erp_inventory_capture_lots()
RETURNS trigger LANGUAGE plpgsql SECURITY INVOKER
SET search_path=pg_catalog,public AS $body$
DECLARE v_count integer;
BEGIN
 INSERT INTO public.erp_inventaire_lots(
   inventaire_id,lot_id,type_article,article_id,quantite_theorique,
   statut_snapshot,date_peremption_snapshot
 )
 SELECT NEW.inventaire_id,l.lot_id,l.type_item,l.item_id,l.quantite_restante,
        l.statut,l.date_peremption
 FROM public.lots l
 WHERE l.type_item IN ('MP','PF')
   AND (NEW.categorie='TOUS' OR l.type_item=NEW.categorie);
 GET DIAGNOSTICS v_count=ROW_COUNT;
 IF v_count>5000 THEN
  RAISE EXCEPTION 'Inventaire : trop de lots photographiés' USING ERRCODE='22023';
 END IF;
 RETURN NEW;
END $body$;

DROP TRIGGER IF EXISTS erp_inv_capture_lots ON public.erp_inventaires;
CREATE TRIGGER erp_inv_capture_lots
AFTER INSERT ON public.erp_inventaires
FOR EACH ROW EXECUTE FUNCTION public.erp_inventory_capture_lots();

-- Lot réellement présent dans le snapshot ; n'ajoute ni ne corrige de lot.
CREATE OR REPLACE FUNCTION public.erp_inventory_count_lot(
 p_inventaire_id text,p_lot_id text,p_quantite numeric,p_motif text,p_acteur_id text
) RETURNS jsonb
LANGUAGE plpgsql SECURITY INVOKER
SET search_path=pg_catalog,public AS $body$
DECLARE v_header public.erp_inventaires%ROWTYPE;
        v_line public.erp_inventaire_lots%ROWTYPE;
BEGIN
 IF NOT public.erp_inventory_permission(p_acteur_id,true) THEN
   RAISE EXCEPTION 'Droit Stocks écriture non confirmé' USING ERRCODE='42501';
 END IF;
 IF p_lot_id IS NULL OR length(btrim(p_lot_id))=0 OR length(p_lot_id)>200
 OR p_quantite IS NULL OR p_quantite::text IN ('NaN','Infinity','-Infinity')
 OR p_quantite<0 OR p_quantite>=1000000000000000
 OR length(coalesce(p_motif,''))>600 THEN
   RAISE EXCEPTION 'Comptage de lot invalide' USING ERRCODE='22023';
 END IF;
 SELECT * INTO STRICT v_header FROM public.erp_inventaires
 WHERE inventaire_id=p_inventaire_id FOR UPDATE;
 IF v_header.statut<>'OUVERT' THEN
   RAISE EXCEPTION 'Campagne non ouverte' USING ERRCODE='23514';
 END IF;
 SELECT * INTO STRICT v_line FROM public.erp_inventaire_lots
 WHERE inventaire_id=p_inventaire_id AND lot_id=p_lot_id FOR UPDATE;
 IF p_quantite IS DISTINCT FROM v_line.quantite_theorique
  AND length(btrim(coalesce(p_motif,'')))<5 THEN
   RAISE EXCEPTION 'Motif obligatoire pour un écart de lot' USING ERRCODE='22023';
 END IF;
 UPDATE public.erp_inventaire_lots SET
   quantite_comptee=p_quantite,compte_par=p_acteur_id,
   compte_le=clock_timestamp(),motif_ecart=nullif(btrim(coalesce(p_motif,'')),'')
 WHERE inventaire_id=p_inventaire_id AND lot_id=p_lot_id;
 RETURN jsonb_build_object('inventaire_id',p_inventaire_id,'lot_id',p_lot_id,
   'quantite_theorique',v_line.quantite_theorique,'quantite_comptee',p_quantite,
   'ecart',p_quantite-v_line.quantite_theorique,'mouvements_stock_appliques',false);
END $body$;

-- Import Excel prévalidé côté client ET revérifié intégralement dans UNE RPC.
-- Aucun update avant validation complète ; l'erreur rollback toute la requête.
CREATE OR REPLACE FUNCTION public.erp_inventory_bulk_count(
 p_inventaire_id text,p_acteur_id text,p_rows jsonb,p_operation_id text
) RETURNS jsonb LANGUAGE plpgsql SECURITY INVOKER
SET search_path=pg_catalog,public AS $body$
DECLARE v_header public.erp_inventaires%ROWTYPE;
        v_item jsonb; v_kind text; v_id text; v_raw text; v_motif text;
        v_qty numeric; v_theoretical numeric; v_row_count integer;
        v_updated integer:=0; v_delta integer; v_key text; v_keys text[]:='{}';
        v_prior public.erp_inventaire_import_operations%ROWTYPE;
        v_result jsonb;
BEGIN
 IF NOT public.erp_inventory_permission(p_acteur_id,true) THEN
   RAISE EXCEPTION 'Droit Stocks écriture non confirmé' USING ERRCODE='42501';
 END IF;
 IF p_operation_id IS NULL OR p_operation_id !~ '^INVIMP-[A-Za-z0-9-]{8,110}$' THEN
   RAISE EXCEPTION 'Identifiant d import obligatoire' USING ERRCODE='22023';
 END IF;
 IF p_rows IS NULL OR jsonb_typeof(p_rows)<>'array' THEN
   RAISE EXCEPTION 'Import inventaire invalide' USING ERRCODE='22023';
 END IF;
 v_row_count:=jsonb_array_length(p_rows);
 IF v_row_count<1 OR v_row_count>500 THEN
   RAISE EXCEPTION 'Import limité à 1..500 lignes' USING ERRCODE='22023';
 END IF;
 -- Répétition sûre après timeout, y compris si campagne désormais SOUMIS.
 SELECT * INTO STRICT v_header FROM public.erp_inventaires
 WHERE inventaire_id=p_inventaire_id FOR UPDATE;
 INSERT INTO public.erp_inventaire_import_operations(
   operation_id,inventaire_id,acteur_id,payload
 ) VALUES(p_operation_id,p_inventaire_id,p_acteur_id,p_rows)
 ON CONFLICT(operation_id) DO NOTHING;
 SELECT * INTO STRICT v_prior FROM public.erp_inventaire_import_operations
 WHERE operation_id=p_operation_id FOR UPDATE;
 IF v_prior.inventaire_id IS DISTINCT FROM p_inventaire_id
   OR v_prior.acteur_id IS DISTINCT FROM p_acteur_id
   OR v_prior.payload IS DISTINCT FROM p_rows THEN
   RAISE EXCEPTION 'Identifiant d import réutilisé avec une demande différente' USING ERRCODE='23505';
 END IF;
 IF v_prior.result_payload IS NOT NULL THEN
   RETURN v_prior.result_payload;
 END IF;
 IF v_header.statut<>'OUVERT' THEN
   RAISE EXCEPTION 'Campagne non ouverte à l import' USING ERRCODE='23514';
 END IF;
 -- Première passe : aucune écriture.
 FOR v_item IN SELECT value FROM jsonb_array_elements(p_rows) LOOP
   IF jsonb_typeof(v_item)<>'object'
     OR (SELECT count(*) FROM jsonb_object_keys(v_item))<>4
     OR NOT (v_item ? 'type_article' AND v_item ? 'article_id'
       AND v_item ? 'quantite_comptee' AND v_item ? 'motif_ecart')
     OR jsonb_typeof(v_item->'type_article')<>'string'
     OR jsonb_typeof(v_item->'article_id')<>'string'
     OR jsonb_typeof(v_item->'quantite_comptee')<>'string'
     OR jsonb_typeof(v_item->'motif_ecart')<>'string'
   THEN RAISE EXCEPTION 'Colonnes de comptage invalides' USING ERRCODE='22023'; END IF;
   v_kind:=v_item->>'type_article'; v_id:=v_item->>'article_id';
   v_raw:=v_item->>'quantite_comptee'; v_motif:=btrim(v_item->>'motif_ecart');
   IF v_kind NOT IN ('MP','PF') OR v_id IS NULL OR length(v_id) NOT BETWEEN 1 AND 200
     OR length(v_raw) NOT BETWEEN 1 AND 45
     OR v_raw !~ '^(0|[1-9][0-9]*)(\.[0-9]+)?$'
     OR length(v_motif)>600 THEN
     RAISE EXCEPTION 'Article ou quantité invalide' USING ERRCODE='22023';
   END IF;
   v_qty:=v_raw::numeric;
   IF v_qty>=1000000000000000 THEN
     RAISE EXCEPTION 'Quantité trop grande' USING ERRCODE='22023';
   END IF;
   v_key:=v_kind||chr(31)||v_id;
   IF v_key=ANY(v_keys) THEN
     RAISE EXCEPTION 'Doublon d article dans le fichier' USING ERRCODE='23505';
   END IF;
   v_keys:=array_append(v_keys,v_key);
   SELECT quantite_theorique INTO v_theoretical
   FROM public.erp_inventaire_lignes
   WHERE inventaire_id=p_inventaire_id AND type_article=v_kind AND article_id=v_id;
   IF NOT FOUND THEN
     RAISE EXCEPTION 'Article absent du snapshot inventaire' USING ERRCODE='23503';
   END IF;
   IF v_qty IS DISTINCT FROM v_theoretical AND length(v_motif)<5 THEN
     RAISE EXCEPTION 'Motif obligatoire pour tout écart' USING ERRCODE='22023';
   END IF;
 END LOOP;
 -- Seconde passe : sérialisée par le verrou FOR UPDATE sur la campagne.
 FOR v_item IN SELECT value FROM jsonb_array_elements(p_rows) LOOP
   UPDATE public.erp_inventaire_lignes SET
      quantite_comptee=(v_item->>'quantite_comptee')::numeric,
      motif_ecart=nullif(btrim(v_item->>'motif_ecart'),''),
      compte_par=p_acteur_id,compte_le=clock_timestamp()
   WHERE inventaire_id=p_inventaire_id
     AND type_article=v_item->>'type_article'
     AND article_id=v_item->>'article_id';
   GET DIAGNOSTICS v_delta=ROW_COUNT;
   v_updated:=v_updated+v_delta;
 END LOOP;
 IF v_updated<>v_row_count THEN
   RAISE EXCEPTION 'Import partiel interdit' USING ERRCODE='23514';
 END IF;
 v_result:=jsonb_build_object('inventaire_id',p_inventaire_id,
   'operation_id',p_operation_id,
   'lignes_mises_a_jour',v_updated,'mouvements_stock_appliques',false);
 UPDATE public.erp_inventaire_import_operations
   SET result_payload=v_result WHERE operation_id=p_operation_id;
 RETURN v_result;
END $body$;

REVOKE ALL ON FUNCTION public.erp_inventory_capture_lots() FROM PUBLIC,anon,authenticated;
REVOKE ALL ON FUNCTION public.erp_inventory_count_lot(text,text,numeric,text,text) FROM PUBLIC,anon,authenticated;
REVOKE ALL ON FUNCTION public.erp_inventory_bulk_count(text,text,jsonb,text) FROM PUBLIC,anon,authenticated;
GRANT EXECUTE ON FUNCTION public.erp_inventory_count_lot(text,text,numeric,text,text) TO service_role;
GRANT EXECUTE ON FUNCTION public.erp_inventory_bulk_count(text,text,jsonb,text) TO service_role;

COMMIT;
