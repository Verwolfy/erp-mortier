-- ERP 028 : savoir si l'acteur connecté peut contrôler une exonération.
-- Lecture d'habilitation seulement ; n'attribue aucun validateur, n'écrit aucune donnée.
BEGIN;
CREATE FUNCTION public.erp_exoneration_tva_is_validator(p_actor_id text)
RETURNS boolean
LANGUAGE sql STABLE SECURITY DEFINER
SET search_path = pg_catalog, pg_temp
AS $fn$
 SELECT EXISTS (
   SELECT 1
   FROM public.users u
   JOIN public.erp_security_authorities a ON a.user_id=u.user_id
   JOIN public.erp_exonerations_tva_validateurs v ON v.user_id=u.user_id
   WHERE u.user_id=p_actor_id
     AND upper(btrim(coalesce(u.actif,''))) IN ('OUI','TRUE','YES','1')
     AND a.habilitation='SECURITY_MANAGER'
     AND a.actif IS TRUE AND a.retire_le IS NULL
     AND v.actif IS TRUE
 );
$fn$;
REVOKE ALL PRIVILEGES ON FUNCTION
 public.erp_exoneration_tva_is_validator(text)
 FROM PUBLIC,anon,authenticated,service_role;
GRANT EXECUTE ON FUNCTION
 public.erp_exoneration_tva_is_validator(text) TO service_role;
DO $verify$
BEGIN
  IF has_function_privilege(
     'anon','public.erp_exoneration_tva_is_validator(text)','EXECUTE')
   OR has_function_privilege(
     'authenticated','public.erp_exoneration_tva_is_validator(text)','EXECUTE')
   OR NOT has_function_privilege(
     'service_role','public.erp_exoneration_tva_is_validator(text)','EXECUTE')
  THEN RAISE EXCEPTION 'Habilitation lecteur fiscal exposée à tort'; END IF;
END;
$verify$;
COMMIT;
