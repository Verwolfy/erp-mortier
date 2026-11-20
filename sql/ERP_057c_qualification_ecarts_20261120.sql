-- ERP-057C : qualification documentaire des écarts, sans régularisation.
BEGIN;
ALTER TABLE public.erp_inventaire_lignes
 ADD COLUMN IF NOT EXISTS nature_ecart text NOT NULL DEFAULT 'NON_QUALIFIE'
 CHECK(nature_ecart IN (
   'NON_QUALIFIE','PERTE','CASSE','PERIME','RETOUR_CLIENT','ERREUR_COMPTAGE','AUTRE'
 ));
ALTER TABLE public.erp_inventaire_lignes
 ADD COLUMN IF NOT EXISTS qualifie_par text REFERENCES public.users(user_id);
ALTER TABLE public.erp_inventaire_lignes
 ADD COLUMN IF NOT EXISTS qualifie_le timestamptz;
ALTER TABLE public.erp_inventaire_lignes
 ADD COLUMN IF NOT EXISTS qualification_note text CHECK(
    qualification_note IS NULL OR length(qualification_note)<=600
 );

-- Un nouveau comptage ou un import modifiant la quantité annule toute
-- qualification antérieure, empêchant une cause obsolète de persister.
CREATE OR REPLACE FUNCTION public.erp_inventory_invalidate_nature()
RETURNS trigger LANGUAGE plpgsql SECURITY INVOKER
SET search_path=pg_catalog,public AS $body$
BEGIN
 IF NEW.quantite_comptee IS DISTINCT FROM OLD.quantite_comptee THEN
  NEW.nature_ecart='NON_QUALIFIE';
  NEW.qualifie_par=NULL;
  NEW.qualifie_le=NULL;
  NEW.qualification_note=NULL;
 END IF;
 RETURN NEW;
END $body$;
DROP TRIGGER IF EXISTS erp_inv_reset_nature ON public.erp_inventaire_lignes;
CREATE TRIGGER erp_inv_reset_nature
BEFORE UPDATE OF quantite_comptee ON public.erp_inventaire_lignes
FOR EACH ROW EXECUTE FUNCTION public.erp_inventory_invalidate_nature();

CREATE OR REPLACE FUNCTION public.erp_inventory_classify_difference(
 p_inventaire_id text,p_type_article text,p_article_id text,
 p_nature text,p_commentaire text,p_acteur_id text
) RETURNS jsonb LANGUAGE plpgsql SECURITY INVOKER
SET search_path=pg_catalog,public AS $body$
DECLARE v_inv public.erp_inventaires%ROWTYPE;
        v_line public.erp_inventaire_lignes%ROWTYPE;
        v_delta numeric;
BEGIN
 IF NOT public.erp_inventory_permission(p_acteur_id,true) THEN
  RAISE EXCEPTION 'Droit Stocks écriture non confirmé' USING ERRCODE='42501';
 END IF;
 IF p_type_article NOT IN ('MP','PF')
 OR p_nature NOT IN ('PERTE','CASSE','PERIME','RETOUR_CLIENT','ERREUR_COMPTAGE','AUTRE')
 OR length(btrim(coalesce(p_commentaire,''))) NOT BETWEEN 10 AND 600 THEN
  RAISE EXCEPTION 'Qualification incomplète' USING ERRCODE='22023';
 END IF;
 SELECT * INTO STRICT v_inv FROM public.erp_inventaires
 WHERE inventaire_id=p_inventaire_id FOR UPDATE;
 IF v_inv.statut<>'OUVERT' THEN
  RAISE EXCEPTION 'Qualification réservée à une campagne ouverte' USING ERRCODE='23514';
 END IF;
 SELECT * INTO STRICT v_line FROM public.erp_inventaire_lignes
 WHERE inventaire_id=p_inventaire_id
   AND type_article=p_type_article AND article_id=p_article_id FOR UPDATE;
 IF v_line.quantite_comptee IS NULL THEN
  RAISE EXCEPTION 'Comptage physique préalable obligatoire' USING ERRCODE='23514';
 END IF;
 v_delta:=v_line.quantite_comptee-v_line.quantite_theorique;
 IF v_delta=0 THEN
  RAISE EXCEPTION 'Aucun écart à qualifier' USING ERRCODE='23514';
 END IF;
 IF (p_nature IN ('PERTE','CASSE','PERIME') AND v_delta>0)
 OR (p_nature='RETOUR_CLIENT' AND v_delta<0) THEN
  RAISE EXCEPTION 'Nature non cohérente avec le signe de l écart' USING ERRCODE='22023';
 END IF;
 UPDATE public.erp_inventaire_lignes SET
   nature_ecart=p_nature,qualifie_par=p_acteur_id,
   qualifie_le=clock_timestamp(),qualification_note=btrim(p_commentaire)
 WHERE inventaire_id=p_inventaire_id
   AND type_article=p_type_article AND article_id=p_article_id;
 RETURN jsonb_build_object('inventaire_id',p_inventaire_id,
   'type_article',p_type_article,'article_id',p_article_id,
   'nature',p_nature,'ecart',v_delta,'mouvements_stock_appliques',false);
END $body$;

REVOKE ALL ON FUNCTION public.erp_inventory_invalidate_nature()
 FROM PUBLIC,anon,authenticated;
REVOKE ALL ON FUNCTION public.erp_inventory_classify_difference(text,text,text,text,text,text)
 FROM PUBLIC,anon,authenticated;
GRANT EXECUTE ON FUNCTION public.erp_inventory_classify_difference(text,text,text,text,text,text)
 TO service_role;
COMMIT;
