-- 010-A-02D-01 : à appliquer UNIQUEMENT sur erp-mortier-test, après contrôle.
-- Programme TEST ffuhbmcfyexsbjwhryvj. Environnement non vérifiable par SQL seul.
-- Le backend Streamlit vérifie la session et transmet p_actor_id.
-- Le secret service_role doit être isolé côté serveur (un acteur tenant la clé pourrait usurper p_actor_id).
-- REV 2 : supprime dans la même transaction les anciens droits d'écriture directe
-- de service_role sur les tables de sécurité, conservant leur lecture côté serveur.
-- IMPORTANT : l'identité de la cible TEST ne peut pas être prouvée par SQL seul.
BEGIN;
SET LOCAL search_path = pg_catalog, pg_temp;
SET LOCAL lock_timeout = '10s';
SET LOCAL statement_timeout = '30s';

DO $preflight$
BEGIN
  IF to_regclass('public.erp_security_authorities') IS NULL THEN
    RAISE EXCEPTION 'Habilitations absentes : exécuter et vérifier bootstrap TEST';
  END IF;
  IF (SELECT count(*) FROM public.erp_security_authorities
      WHERE actif IS TRUE AND habilitation = 'SECURITY_MANAGER') <> 1 THEN
    RAISE EXCEPTION 'Initialisation : attendu un seul SECURITY_MANAGER actif sur TEST';
  END IF;
END
$preflight$;

CREATE TABLE IF NOT EXISTS public.erp_security_operations (
  operation_id uuid PRIMARY KEY,
  action text NOT NULL,
  acteur_id text NOT NULL,
  cible text NOT NULL,
  cree_le timestamptz NOT NULL DEFAULT now()
);
ALTER TABLE public.erp_security_operations ENABLE ROW LEVEL SECURITY;
REVOKE ALL PRIVILEGES ON TABLE public.erp_security_operations FROM PUBLIC, anon, authenticated, service_role;

CREATE OR REPLACE FUNCTION public.erp_security_is_manager(p_actor_id text)
RETURNS boolean
LANGUAGE sql STABLE SECURITY DEFINER
SET search_path = pg_catalog, pg_temp
AS $body$
  SELECT EXISTS (
    SELECT 1 FROM public.users u
    JOIN public.erp_security_authorities a ON a.user_id = u.user_id
    WHERE u.user_id = p_actor_id
      AND upper(btrim(coalesce(u.actif, ''))) IN ('OUI', 'TRUE', 'YES', '1')
      AND a.habilitation = 'SECURITY_MANAGER' AND a.actif IS TRUE
      AND a.retire_le IS NULL
  );
$body$;
REVOKE ALL PRIVILEGES ON FUNCTION public.erp_security_is_manager(text)
  FROM PUBLIC, anon, authenticated, service_role;
GRANT EXECUTE ON FUNCTION public.erp_security_is_manager(text) TO service_role;

CREATE OR REPLACE FUNCTION public.erp_security_create_user(
  p_actor_id text, p_operation_id uuid, p_user_id text, p_nom text,
  p_login text, p_hash_mdp text, p_role text
) RETURNS text
LANGUAGE plpgsql SECURITY DEFINER
SET search_path = pg_catalog, pg_temp
AS $body$
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
$body$;
REVOKE ALL PRIVILEGES ON FUNCTION public.erp_security_create_user(text,uuid,text,text,text,text,text)
  FROM PUBLIC, anon, authenticated, service_role;
GRANT EXECUTE ON FUNCTION public.erp_security_create_user(text,uuid,text,text,text,text,text) TO service_role;

CREATE OR REPLACE FUNCTION public.erp_security_add_permission(
  p_actor_id text, p_operation_id uuid, p_role text,
  p_module text, p_lecture text, p_ecriture text
) RETURNS boolean
LANGUAGE plpgsql SECURITY DEFINER
SET search_path = pg_catalog, pg_temp
AS $body$
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
$body$;
REVOKE ALL PRIVILEGES ON FUNCTION public.erp_security_add_permission(text,uuid,text,text,text,text)
  FROM PUBLIC, anon, authenticated, service_role;
GRANT EXECUTE ON FUNCTION public.erp_security_add_permission(text,uuid,text,text,text,text) TO service_role;

-- 010-A-02C avait ouvert INSERT direct sur ces deux tables.
-- SECURITY DEFINER continue d'écrire en tant que propriétaire postgres ;
-- toute écriture via la clé service_role doit désormais passer par la RPC auditée.
-- SELECT reste autorisé pour l'authentification et les écrans de gestion.
REVOKE INSERT, UPDATE, DELETE ON TABLE public.users, public.permissions FROM service_role;

DO $postflight$
BEGIN
  IF has_table_privilege('anon','public.erp_security_operations','SELECT')
     OR has_table_privilege('authenticated','public.erp_security_operations','SELECT')
     OR has_table_privilege('service_role','public.erp_security_operations','SELECT')
     OR has_function_privilege('anon','public.erp_security_is_manager(text)','EXECUTE')
     OR has_function_privilege('authenticated','public.erp_security_is_manager(text)','EXECUTE')
     OR NOT has_function_privilege('service_role','public.erp_security_create_user(text,uuid,text,text,text,text,text)','EXECUTE')
     OR NOT has_function_privilege('service_role','public.erp_security_add_permission(text,uuid,text,text,text,text)','EXECUTE')
     OR NOT has_function_privilege('service_role','public.erp_security_is_manager(text)','EXECUTE')
     OR NOT has_table_privilege('service_role','public.users','SELECT')
     OR NOT has_table_privilege('service_role','public.permissions','SELECT')
     OR has_table_privilege('service_role','public.users','INSERT')
     OR has_table_privilege('service_role','public.users','UPDATE')
     OR has_table_privilege('service_role','public.users','DELETE')
     OR has_table_privilege('service_role','public.permissions','INSERT')
     OR has_table_privilege('service_role','public.permissions','UPDATE')
     OR has_table_privilege('service_role','public.permissions','DELETE') THEN
    RAISE EXCEPTION 'Postcontrole des droits invalide';
  END IF;
END;
$postflight$;
COMMIT;
