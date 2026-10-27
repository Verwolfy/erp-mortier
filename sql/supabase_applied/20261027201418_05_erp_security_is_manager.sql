-- Segment de la migration Supabase appliquee 20261027201418 (erp_013_security_tables_and_rpc).
-- Ne pas executer isolement; revoir l'ensemble des 6 segments avant reutilisation.
CREATE OR REPLACE FUNCTION public.erp_security_is_manager(p_actor_id text)
 RETURNS boolean
 LANGUAGE sql
 STABLE SECURITY DEFINER
 SET search_path TO 'pg_catalog', 'pg_temp'
AS $function$
  SELECT EXISTS (
    SELECT 1 FROM public.users u
    JOIN public.erp_security_authorities a ON a.user_id = u.user_id
    WHERE u.user_id = p_actor_id
      AND upper(btrim(coalesce(u.actif, ''))) IN ('OUI', 'TRUE', 'YES', '1')
      AND a.habilitation = 'SECURITY_MANAGER' AND a.actif IS TRUE
      AND a.retire_le IS NULL
  );
$function$;
REVOKE ALL PRIVILEGES ON FUNCTION public.erp_security_is_manager(p_actor_id text) FROM PUBLIC,anon,authenticated,service_role;
GRANT EXECUTE ON FUNCTION public.erp_security_is_manager(p_actor_id text) TO service_role;
