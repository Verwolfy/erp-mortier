-- ERP-056C : interdire l'approbation par un utilisateur ayant effectué le comptage.
BEGIN;
CREATE OR REPLACE FUNCTION public.erp_inventory_approve(
 p_inventaire_id text,p_acteur_id text,p_commentaire text
) RETURNS jsonb LANGUAGE plpgsql SECURITY INVOKER SET search_path=pg_catalog,public AS $$
DECLARE v_inv public.erp_inventaires%ROWTYPE; v_changed int; v_differences int; v_status text;
BEGIN
 IF NOT public.erp_inventory_permission(p_acteur_id,true) OR NOT EXISTS(
  SELECT 1 FROM public.users WHERE user_id=p_acteur_id
  AND upper(btrim(role)) IN ('ADMIN','ADMINISTRATEUR','SUPERADMIN')
 ) THEN RAISE EXCEPTION 'Validation réservée à un administrateur Stocks habilité' USING ERRCODE='42501'; END IF;
 IF length(btrim(coalesce(p_commentaire,'')))<10 OR length(p_commentaire)>600
 THEN RAISE EXCEPTION 'Justification de validation obligatoire' USING ERRCODE='22023'; END IF;
 SELECT * INTO STRICT v_inv FROM public.erp_inventaires WHERE inventaire_id=p_inventaire_id FOR UPDATE;
 IF v_inv.statut<>'SOUMIS' OR v_inv.createur_id=p_acteur_id
    OR v_inv.soumis_par=p_acteur_id
    OR EXISTS (
      SELECT 1 FROM public.erp_inventaire_lignes l
      WHERE l.inventaire_id=p_inventaire_id AND l.compte_par=p_acteur_id
    ) THEN
  RAISE EXCEPTION 'Double validation indépendante et campagne soumise requises' USING ERRCODE='23514';
 END IF;
 -- Aucun stock ne doit avoir changé depuis le snapshot : ne pas valider
 -- sur des quantités/couts devenus obsolètes.
 SELECT count(*) INTO v_changed FROM public.erp_inventaire_lignes l
 LEFT JOIN public.stock_actuel mp ON l.type_article='MP' AND mp.mp_id=l.article_id
 LEFT JOIN public.stock_actuel_pf pf ON l.type_article='PF' AND pf.sku_id=l.article_id
 WHERE l.inventaire_id=p_inventaire_id AND
  ((l.type_article='MP' AND (mp.mp_id IS NULL OR mp.quantite_disponible IS DISTINCT FROM l.quantite_theorique
     OR mp.cmp_actuel IS DISTINCT FROM l.pmp_snapshot))
    OR (l.type_article='PF' AND (pf.sku_id IS NULL OR pf.quantite_disponible IS DISTINCT FROM l.quantite_theorique
     OR pf.cout_revient IS DISTINCT FROM l.pmp_snapshot)));
 -- Un participant au comptage ne peut signer son propre contrôle.
 -- Les nouvelles lignes entrées dans le référentiel après photographie
 -- doivent également invalider l'approbation, même si toutes les anciennes
 -- références sont inchangées.
 IF (v_inv.categorie IN ('MP','TOUS') AND
     (SELECT count(*) FROM public.stock_actuel) <>
     (SELECT count(*) FROM public.erp_inventaire_lignes
      WHERE inventaire_id=p_inventaire_id AND type_article='MP'))
    OR (v_inv.categorie IN ('PF','TOUS') AND
     (SELECT count(*) FROM public.stock_actuel_pf) <>
     (SELECT count(*) FROM public.erp_inventaire_lignes
      WHERE inventaire_id=p_inventaire_id AND type_article='PF')) THEN
  RAISE EXCEPTION 'Référentiel modifié depuis la photographie' USING ERRCODE='40001';
 END IF;
 IF v_changed>0 THEN RAISE EXCEPTION 'Stock modifié depuis photographie : % références',v_changed USING ERRCODE='40001'; END IF;
 SELECT count(*) INTO v_differences FROM public.erp_inventaire_lignes
 WHERE inventaire_id=p_inventaire_id AND quantite_comptee IS DISTINCT FROM quantite_theorique;
 v_status:=CASE WHEN v_differences=0 THEN 'SANS_ECART' ELSE 'ECARTS_A_QUALIFIER' END;
 UPDATE public.erp_inventaires SET statut=v_status,valide_par=p_acteur_id,
    valide_le=clock_timestamp(),commentaire_validation=btrim(p_commentaire)
 WHERE inventaire_id=p_inventaire_id;
 RETURN jsonb_build_object('inventaire_id',p_inventaire_id,'statut',v_status,
   'ecarts',v_differences,'mouvements_stock_appliques',false);
END $$;

REVOKE ALL ON FUNCTION public.erp_inventory_approve(text,text,text) FROM PUBLIC,anon,authenticated;
GRANT EXECUTE ON FUNCTION public.erp_inventory_approve(text,text,text) TO service_role;
COMMIT;
