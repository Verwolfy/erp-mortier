-- Segment de la migration Supabase appliquee 20261027201418 (erp_013_security_tables_and_rpc).
-- Ne pas executer isolement; revoir l'ensemble des 6 segments avant reutilisation.
CREATE OR REPLACE FUNCTION public.erp_security_add_permission(p_actor_id text, p_operation_id uuid, p_role text, p_module text, p_lecture text, p_ecriture text)
 RETURNS boolean
 LANGUAGE plpgsql
 SECURITY DEFINER
 SET search_path TO 'pg_catalog', 'pg_temp'
AS $function$
DECLARE
  v_role text := upper(btrim(coalesce(p_role, '')));
BEGIN
  PERFORM 1 FROM public.erp_security_authorities a
    JOIN public.users u ON u.user_id = a.user_id
    WHERE a.user_id = p_actor_id AND a.habilitation = 'SECURITY_MANAGER'
      AND a.actif IS TRUE AND a.retire_le IS NULL
      AND upper(btrim(coalesce(u.actif, ''))) IN ('OUI', 'TRUE', 'YES', '1')
    FOR SHARE OF a, u;
  IF NOT FOUND THEN RAISE EXCEPTION 'Gestion de securite non autorisee' USING ERRCODE = '42501'; END IF;
  IF v_role NOT IN ('ACHATS','COMMERCIAL','CRM','FINANCE','LECTURE_SEULE',
                    'MAGASINIER','PRODUCTION','QUALITE','RH','STOCKS','VENTES')
     OR p_module NOT IN ('Achats','Stocks','Production','Ventes','Finance','CRM',
                         'RH','Dashboards','Logs') THEN
    RAISE EXCEPTION 'Role ou module cible non autorise' USING ERRCODE = '42501';
  END IF;
  IF p_lecture NOT IN ('OUI','NON') OR p_ecriture NOT IN ('OUI','NON')
     OR p_operation_id IS NULL THEN
    RAISE EXCEPTION 'Valeurs de permission invalides' USING ERRCODE = '22023';
  END IF;
  -- Empêche les doublons concurrents sans ajouter d'index sur la table historique.
  PERFORM pg_catalog.pg_advisory_xact_lock(pg_catalog.hashtext(v_role || ':' || p_module));
  IF EXISTS (SELECT 1 FROM public.permissions
             WHERE upper(btrim(role)) = v_role AND module = p_module) THEN
    RAISE EXCEPTION 'Permission de ce role et module deja presente' USING ERRCODE = '23505';
  END IF;
  INSERT INTO public.erp_security_operations(operation_id, action, acteur_id, cible)
    VALUES (p_operation_id, 'AJOUTER_PERMISSION', p_actor_id, v_role || '/' || p_module);
  INSERT INTO public.permissions(role,module,lecture,ecriture)
    VALUES (v_role,p_module,p_lecture,p_ecriture);
  INSERT INTO public.audit_trail ("timestamp", user_id, module, action, detail)
    VALUES (to_char(now() AT TIME ZONE 'UTC', 'YYYY-MM-DD"T"HH24:MI:SS"Z"'),
            p_actor_id, 'Securite', 'AJOUTER_PERMISSION',
            'operation_id=' || p_operation_id::text || '; role=' || v_role || '; module=' || p_module);
  RETURN TRUE;
END;
$function$;
REVOKE ALL PRIVILEGES ON FUNCTION public.erp_security_add_permission(p_actor_id text, p_operation_id uuid, p_role text, p_module text, p_lecture text, p_ecriture text) FROM PUBLIC,anon,authenticated,service_role;
GRANT EXECUTE ON FUNCTION public.erp_security_add_permission(p_actor_id text, p_operation_id uuid, p_role text, p_module text, p_lecture text, p_ecriture text) TO service_role;
