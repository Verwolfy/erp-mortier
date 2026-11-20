-- ERP-057D : justification obligatoire aussi dans la RPC comptage unitaire.
BEGIN;
CREATE OR REPLACE FUNCTION public.erp_inventory_count(
 p_inventaire_id text,p_type_article text,p_article_id text,
 p_quantite numeric,p_motif text,p_acteur_id text
) RETURNS jsonb LANGUAGE plpgsql SECURITY INVOKER SET search_path=pg_catalog,public AS $$
DECLARE v_inv public.erp_inventaires%ROWTYPE; v_old public.erp_inventaire_lignes%ROWTYPE;
BEGIN
 IF NOT public.erp_inventory_permission(p_acteur_id,true)
 THEN RAISE EXCEPTION 'Droit Stocks écriture non confirmé' USING ERRCODE='42501'; END IF;
 IF p_type_article NOT IN ('MP','PF') OR p_quantite IS NULL
    OR p_quantite::text IN ('NaN','Infinity','-Infinity') OR p_quantite<0 OR p_quantite>=1000000000000000
    OR p_article_id IS NULL OR length(p_article_id)>200
    OR length(coalesce(p_motif,''))>600 THEN
   RAISE EXCEPTION 'Comptage invalide' USING ERRCODE='22023';
 END IF;
 SELECT * INTO STRICT v_inv FROM public.erp_inventaires WHERE inventaire_id=p_inventaire_id FOR UPDATE;
 IF v_inv.statut<>'OUVERT' THEN RAISE EXCEPTION 'Campagne fermée au comptage' USING ERRCODE='23514'; END IF;
 SELECT * INTO STRICT v_old FROM public.erp_inventaire_lignes
  WHERE inventaire_id=p_inventaire_id AND type_article=p_type_article AND article_id=p_article_id FOR UPDATE;
 -- Un second comptage d'une même ligne est permis, uniquement avant soumission.
 IF p_quantite IS DISTINCT FROM v_old.quantite_theorique
   AND length(btrim(coalesce(p_motif,'')))<5 THEN
   RAISE EXCEPTION 'Justification obligatoire pour un écart de comptage'
     USING ERRCODE='22023';
 END IF;
 UPDATE public.erp_inventaire_lignes SET quantite_comptee=p_quantite, compte_par=p_acteur_id,
    compte_le=clock_timestamp(),motif_ecart=nullif(btrim(coalesce(p_motif,'')),'')
  WHERE inventaire_id=p_inventaire_id AND type_article=p_type_article AND article_id=p_article_id;
 RETURN jsonb_build_object('inventaire_id',p_inventaire_id,'article_id',p_article_id,
    'type_article',p_type_article,'quantite_theorique',v_old.quantite_theorique,
    'quantite_comptee',p_quantite,'ecart',p_quantite-v_old.quantite_theorique);
END $$;
REVOKE ALL ON FUNCTION public.erp_inventory_count(text,text,text,numeric,text,text) FROM PUBLIC,anon,authenticated;
GRANT EXECUTE ON FUNCTION public.erp_inventory_count(text,text,text,numeric,text,text) TO service_role;
COMMIT;
