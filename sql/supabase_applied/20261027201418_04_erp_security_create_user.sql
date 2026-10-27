-- Segment de la migration Supabase appliquee 20261027201418 (erp_013_security_tables_and_rpc).
-- Ne pas executer isolement; revoir l'ensemble des 6 segments avant reutilisation.
CREATE OR REPLACE FUNCTION public.erp_security_create_user(p_actor_id text, p_operation_id uuid, p_user_id text, p_nom text, p_login text, p_hash_mdp text, p_role text)
 RETURNS text
 LANGUAGE plpgsql
 SECURITY DEFINER
 SET search_path TO 'pg_catalog', 'pg_temp'
AS $function$
DECLARE
  v_role text := upper(btrim(coalesce(p_role, '')));
BEGIN
  -- Le verrou empêche une révocation simultanée pendant l'acte.
  PERFORM 1 FROM public.erp_security_authorities a
    JOIN public.users u ON u.user_id = a.user_id
    WHERE a.user_id = p_actor_id AND a.habilitation = 'SECURITY_MANAGER'
      AND a.actif IS TRUE AND a.retire_le IS NULL
      AND upper(btrim(coalesce(u.actif, ''))) IN ('OUI', 'TRUE', 'YES', '1')
    FOR SHARE OF a, u;
  IF NOT FOUND THEN RAISE EXCEPTION 'Gestion de securite non autorisee' USING ERRCODE = '42501'; END IF;
  IF v_role NOT IN ('ACHATS','COMMERCIAL','CRM','FINANCE','LECTURE_SEULE',
                    'MAGASINIER','PRODUCTION','QUALITE','RH','STOCKS','VENTES') THEN
    RAISE EXCEPTION 'Role cible non autorise' USING ERRCODE = '42501';
  END IF;
  IF nullif(btrim(coalesce(p_user_id, '')), '') IS NULL
     OR nullif(btrim(coalesce(p_nom, '')), '') IS NULL
     OR nullif(btrim(coalesce(p_login, '')), '') IS NULL
     OR p_operation_id IS NULL THEN
    RAISE EXCEPTION 'Parametres utilisateur invalides' USING ERRCODE = '22023';
  END IF;
  IF p_hash_mdp IS NULL OR p_hash_mdp !~ '^\$2[aby]\$[0-9][0-9]\$' THEN
    RAISE EXCEPTION 'Empreinte de mot de passe invalide' USING ERRCODE = '22023';
  END IF;
  INSERT INTO public.erp_security_operations(operation_id, action, acteur_id, cible)
    VALUES (p_operation_id, 'CREER_UTILISATEUR', p_actor_id, p_user_id);
  INSERT INTO public.users(user_id, nom, login, hash_mdp, role, actif)
    VALUES (p_user_id, btrim(p_nom), btrim(p_login), p_hash_mdp, v_role, 'OUI');
  INSERT INTO public.audit_trail ("timestamp", user_id, module, action, detail)
    VALUES (to_char(now() AT TIME ZONE 'UTC', 'YYYY-MM-DD"T"HH24:MI:SS"Z"'),
            p_actor_id, 'Securite', 'CREER_UTILISATEUR',
            'operation_id=' || p_operation_id::text || '; cible=' || p_user_id);
  RETURN p_user_id;
END;
$function$;
REVOKE ALL PRIVILEGES ON FUNCTION public.erp_security_create_user(p_actor_id text, p_operation_id uuid, p_user_id text, p_nom text, p_login text, p_hash_mdp text, p_role text) FROM PUBLIC,anon,authenticated,service_role;
GRANT EXECUTE ON FUNCTION public.erp_security_create_user(p_actor_id text, p_operation_id uuid, p_user_id text, p_nom text, p_login text, p_hash_mdp text, p_role text) TO service_role;
