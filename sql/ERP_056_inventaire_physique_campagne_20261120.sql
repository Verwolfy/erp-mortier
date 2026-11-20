-- ERP-056 : inventaires physiques MP/PF. Création et comptages sans écriture de stock.
-- Supabase principal ; service_role serveur seulement ; utilisateur ERP contrôlé en base.
BEGIN;

CREATE TABLE IF NOT EXISTS public.erp_inventaires (
  inventaire_id text PRIMARY KEY,
  categorie text NOT NULL CHECK (categorie IN ('MP','PF','TOUS')),
  libelle text NOT NULL CHECK(length(btrim(libelle)) BETWEEN 3 AND 160),
  statut text NOT NULL DEFAULT 'OUVERT'
      CHECK(statut IN ('OUVERT','SOUMIS','SANS_ECART','ECARTS_A_QUALIFIER')),
  date_snapshot timestamptz NOT NULL DEFAULT clock_timestamp(),
  createur_id text NOT NULL REFERENCES public.users(user_id),
  soumis_par text REFERENCES public.users(user_id),
  soumis_le timestamptz,
  valide_par text REFERENCES public.users(user_id),
  valide_le timestamptz,
  commentaire_validation text,
  CONSTRAINT erp_inv_id_format CHECK(inventaire_id ~ '^INV-[A-Za-z0-9-]{8,110}$'),
  CONSTRAINT erp_inv_approbateur_distinct CHECK(valide_par IS NULL OR valide_par <> createur_id)
);

CREATE TABLE IF NOT EXISTS public.erp_inventaire_lignes (
  inventaire_id text NOT NULL REFERENCES public.erp_inventaires(inventaire_id) ON DELETE RESTRICT,
  type_article text NOT NULL CHECK(type_article IN ('MP','PF')),
  article_id text NOT NULL,
  quantite_theorique numeric NOT NULL CHECK(quantite_theorique >= 0 AND quantite_theorique < 1000000000000000),
  pmp_snapshot numeric CHECK(pmp_snapshot IS NULL OR (pmp_snapshot >= 0 AND pmp_snapshot < 1000000000000000)),
  quantite_comptee numeric CHECK(quantite_comptee IS NULL OR (quantite_comptee >= 0 AND quantite_comptee < 1000000000000000)),
  compte_par text REFERENCES public.users(user_id),
  compte_le timestamptz,
  motif_ecart text,
  PRIMARY KEY (inventaire_id, type_article, article_id),
  CONSTRAINT erp_inv_count_metadata CHECK(
    (quantite_comptee IS NULL AND compte_par IS NULL AND compte_le IS NULL)
    OR (quantite_comptee IS NOT NULL AND compte_par IS NOT NULL AND compte_le IS NOT NULL)
  ),
  CONSTRAINT erp_inv_motif_taille CHECK(motif_ecart IS NULL OR length(motif_ecart)<=600)
);

CREATE INDEX IF NOT EXISTS erp_inventaires_date_idx ON public.erp_inventaires(date_snapshot DESC);
CREATE INDEX IF NOT EXISTS erp_inventaire_lignes_type_idx ON public.erp_inventaire_lignes(type_article,article_id);
ALTER TABLE public.erp_inventaires ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.erp_inventaire_lignes ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON public.erp_inventaires,public.erp_inventaire_lignes FROM PUBLIC,anon,authenticated;
GRANT SELECT,INSERT,UPDATE ON public.erp_inventaires,public.erp_inventaire_lignes TO service_role;

CREATE OR REPLACE FUNCTION public.erp_inventory_permission(p_user text,p_write boolean)
RETURNS boolean LANGUAGE sql SECURITY INVOKER STABLE SET search_path=pg_catalog,public
AS $$
 SELECT EXISTS (
  SELECT 1 FROM public.users u
  WHERE u.user_id=p_user
    AND upper(btrim(coalesce(u.actif,''))) IN ('OUI','TRUE','1','ACTIF','ACTIVE','YES')
    AND (upper(btrim(u.role)) IN ('ADMIN','ADMINISTRATEUR','SUPERADMIN')
     OR EXISTS (
       SELECT 1 FROM public.permissions p
       WHERE upper(btrim(p.role))=upper(btrim(u.role))
         AND upper(btrim(p.module))='STOCKS'
         AND upper(btrim(coalesce(p.lecture,''))) IN ('OUI','TRUE','1','YES')
         AND (NOT p_write OR upper(btrim(coalesce(p.ecriture,''))) IN ('OUI','TRUE','1','YES'))
         AND (SELECT count(*) FROM public.permissions pp
              WHERE upper(btrim(pp.role))=upper(btrim(u.role))
                AND upper(btrim(pp.module))='STOCKS')=1
     ))
 )
$$;

CREATE OR REPLACE FUNCTION public.erp_inventory_create(
 p_inventaire_id text,p_categorie text,p_libelle text,p_acteur_id text
) RETURNS jsonb LANGUAGE plpgsql SECURITY INVOKER SET search_path=pg_catalog,public AS $$
DECLARE v_n int; v_preexisting public.erp_inventaires%ROWTYPE;
BEGIN
 IF NOT public.erp_inventory_permission(p_acteur_id,true)
    THEN RAISE EXCEPTION 'Droit Stocks écriture non confirmé' USING ERRCODE='42501'; END IF;
 IF p_inventaire_id IS NULL OR p_inventaire_id !~ '^INV-[A-Za-z0-9-]{8,110}$'
    OR p_categorie NOT IN ('MP','PF','TOUS') OR length(btrim(coalesce(p_libelle,''))) NOT BETWEEN 3 AND 160
    THEN RAISE EXCEPTION 'Paramètres de campagne incorrects' USING ERRCODE='22023'; END IF;
 -- Idempotence : un même identifiant avec une charge différente est interdit.
 SELECT * INTO v_preexisting FROM public.erp_inventaires WHERE inventaire_id=p_inventaire_id FOR UPDATE;
 IF FOUND THEN
  IF v_preexisting.categorie<>p_categorie OR v_preexisting.libelle<>btrim(p_libelle)
     OR v_preexisting.createur_id<>p_acteur_id THEN
   RAISE EXCEPTION 'Identifiant inventaire réutilisé avec une autre demande' USING ERRCODE='23505';
  END IF;
  RETURN jsonb_build_object('inventaire_id',p_inventaire_id,'statut',v_preexisting.statut,
    'lignes',(SELECT count(*) FROM public.erp_inventaire_lignes WHERE inventaire_id=p_inventaire_id));
 END IF;
 INSERT INTO public.erp_inventaires(inventaire_id,categorie,libelle,createur_id)
 VALUES(p_inventaire_id,p_categorie,btrim(p_libelle),p_acteur_id);
 IF p_categorie IN ('MP','TOUS') THEN
  INSERT INTO public.erp_inventaire_lignes(inventaire_id,type_article,article_id,quantite_theorique,pmp_snapshot)
  SELECT p_inventaire_id,'MP',s.mp_id,s.quantite_disponible,s.cmp_actuel
    FROM public.stock_actuel s ORDER BY s.mp_id;
 END IF;
 IF p_categorie IN ('PF','TOUS') THEN
  INSERT INTO public.erp_inventaire_lignes(inventaire_id,type_article,article_id,quantite_theorique,pmp_snapshot)
  SELECT p_inventaire_id,'PF',s.sku_id,s.quantite_disponible,s.cout_revient
    FROM public.stock_actuel_pf s ORDER BY s.sku_id;
 END IF;
 SELECT count(*) INTO v_n FROM public.erp_inventaire_lignes WHERE inventaire_id=p_inventaire_id;
 IF v_n=0 OR v_n>5000 THEN
   RAISE EXCEPTION 'Référentiel de stock vide ou trop volumineux' USING ERRCODE='22023';
 END IF;
 RETURN jsonb_build_object('inventaire_id',p_inventaire_id,'statut','OUVERT','lignes',v_n);
END $$;

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
 UPDATE public.erp_inventaire_lignes SET quantite_comptee=p_quantite, compte_par=p_acteur_id,
    compte_le=clock_timestamp(),motif_ecart=nullif(btrim(coalesce(p_motif,'')),'')
  WHERE inventaire_id=p_inventaire_id AND type_article=p_type_article AND article_id=p_article_id;
 RETURN jsonb_build_object('inventaire_id',p_inventaire_id,'article_id',p_article_id,
    'type_article',p_type_article,'quantite_theorique',v_old.quantite_theorique,
    'quantite_comptee',p_quantite,'ecart',p_quantite-v_old.quantite_theorique);
END $$;

CREATE OR REPLACE FUNCTION public.erp_inventory_submit(
 p_inventaire_id text,p_acteur_id text
) RETURNS jsonb LANGUAGE plpgsql SECURITY INVOKER SET search_path=pg_catalog,public AS $$
DECLARE v_inv public.erp_inventaires%ROWTYPE; v_remaining int;
BEGIN
 IF NOT public.erp_inventory_permission(p_acteur_id,true)
 THEN RAISE EXCEPTION 'Droit Stocks écriture non confirmé' USING ERRCODE='42501'; END IF;
 SELECT * INTO STRICT v_inv FROM public.erp_inventaires WHERE inventaire_id=p_inventaire_id FOR UPDATE;
 IF v_inv.statut='SOUMIS' AND v_inv.soumis_par=p_acteur_id THEN
  RETURN jsonb_build_object('statut','SOUMIS','inventaire_id',p_inventaire_id);
 END IF;
 IF v_inv.statut<>'OUVERT' THEN RAISE EXCEPTION 'Campagne déjà soumise ou validée' USING ERRCODE='23514'; END IF;
 SELECT count(*) INTO v_remaining FROM public.erp_inventaire_lignes
 WHERE inventaire_id=p_inventaire_id AND quantite_comptee IS NULL;
 IF v_remaining>0 THEN RAISE EXCEPTION 'Comptage incomplet : % lignes',v_remaining USING ERRCODE='23514'; END IF;
 UPDATE public.erp_inventaires SET statut='SOUMIS',soumis_par=p_acteur_id,
   soumis_le=clock_timestamp() WHERE inventaire_id=p_inventaire_id;
 RETURN jsonb_build_object('statut','SOUMIS','inventaire_id',p_inventaire_id);
END $$;

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
 IF v_inv.statut<>'SOUMIS' OR v_inv.createur_id=p_acteur_id OR v_inv.soumis_par=p_acteur_id THEN
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

-- Aucun appel navigateur direct aux fonctions : seulement serveur service_role.
REVOKE ALL ON FUNCTION public.erp_inventory_permission(text,boolean) FROM PUBLIC,anon,authenticated;
REVOKE ALL ON FUNCTION public.erp_inventory_create(text,text,text,text) FROM PUBLIC,anon,authenticated;
REVOKE ALL ON FUNCTION public.erp_inventory_count(text,text,text,numeric,text,text) FROM PUBLIC,anon,authenticated;
REVOKE ALL ON FUNCTION public.erp_inventory_submit(text,text) FROM PUBLIC,anon,authenticated;
REVOKE ALL ON FUNCTION public.erp_inventory_approve(text,text,text) FROM PUBLIC,anon,authenticated;
GRANT EXECUTE ON FUNCTION public.erp_inventory_permission(text,boolean) TO service_role;
GRANT EXECUTE ON FUNCTION public.erp_inventory_create(text,text,text,text) TO service_role;
GRANT EXECUTE ON FUNCTION public.erp_inventory_count(text,text,text,numeric,text,text) TO service_role;
GRANT EXECUTE ON FUNCTION public.erp_inventory_submit(text,text) TO service_role;
GRANT EXECUTE ON FUNCTION public.erp_inventory_approve(text,text,text) TO service_role;
COMMIT;
