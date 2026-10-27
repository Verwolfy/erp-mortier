-- Segment de la migration Supabase appliquee 20261027201418 (erp_013_security_tables_and_rpc).
-- Ne pas executer isolement; revoir l'ensemble des 6 segments avant reutilisation.
DO $preflight$
BEGIN
 IF EXISTS (SELECT 1 FROM (VALUES
 ('erp_auth_rate_secret'),('erp_auth_rate_state'),('erp_auth_attempt_tokens'),
 ('erp_security_authorities'),('erp_security_operations')) n(name)
 WHERE to_regclass('public.'||n.name) IS NOT NULL)
 THEN RAISE EXCEPTION 'Safety stop: security table already exists'; END IF;
 IF NOT EXISTS(SELECT 1 FROM public.users WHERE user_id='USR-0001' AND upper(btrim(coalesce(role,'')))='ADMIN' AND upper(btrim(coalesce(actif,'')))='OUI')
 THEN RAISE EXCEPTION 'Safety stop: target ADMIN USR-0001 not active'; END IF;
END $preflight$;

CREATE TABLE public.erp_auth_rate_secret (
 id integer NOT NULL PRIMARY KEY,
 secret_uuid uuid NOT NULL DEFAULT pg_catalog.gen_random_uuid(),
 CONSTRAINT erp_auth_rate_secret_id_check CHECK(id=1)
);
CREATE TABLE public.erp_auth_rate_state (
 key_hash text NOT NULL PRIMARY KEY,
 failure_count integer NOT NULL DEFAULT 0,
 first_failure_at timestamptz,
 locked_until timestamptz,
 updated_at timestamptz NOT NULL DEFAULT pg_catalog.clock_timestamp(),
 CONSTRAINT erp_auth_rate_state_failure_count_check CHECK(failure_count>=0 AND failure_count<=3),
 CONSTRAINT erp_auth_rate_state_key_hash_check CHECK(key_hash ~ '^[0-9a-f]{64}$')
);
CREATE TABLE public.erp_auth_attempt_tokens (
 token uuid NOT NULL DEFAULT pg_catalog.gen_random_uuid() PRIMARY KEY,
 key_hash text NOT NULL REFERENCES public.erp_auth_rate_state(key_hash),
 created_at timestamptz NOT NULL DEFAULT pg_catalog.clock_timestamp(),
 completed_at timestamptz,
 outcome text,
 CONSTRAINT erp_auth_attempt_tokens_outcome_check CHECK(outcome IN ('SUCCESS','FAILURE','BACKEND_ERROR','EXPIRED'))
);
CREATE INDEX erp_auth_attempt_tokens_pending_idx ON public.erp_auth_attempt_tokens (key_hash,created_at) WHERE completed_at IS NULL;
CREATE TABLE public.erp_security_authorities (
 user_id text NOT NULL PRIMARY KEY REFERENCES public.users(user_id) ON DELETE RESTRICT,
 habilitation text NOT NULL DEFAULT 'SECURITY_MANAGER',
 actif boolean NOT NULL DEFAULT TRUE,
 attribue_par text NOT NULL DEFAULT 'SYSTEM_MIGRATION_010A_02D_01',
 attribue_le timestamptz NOT NULL DEFAULT pg_catalog.now(),
 retire_le timestamptz,
 CONSTRAINT erp_security_authorities_habilitation_check CHECK(habilitation='SECURITY_MANAGER'),
 CONSTRAINT erp_security_authorities_active_ck CHECK(actif OR retire_le IS NOT NULL),
 CONSTRAINT erp_security_authorities_dates_ck CHECK(retire_le IS NULL OR retire_le>=attribue_le)
);
CREATE TABLE public.erp_security_operations (
 operation_id uuid NOT NULL PRIMARY KEY,
 action text NOT NULL,
 acteur_id text NOT NULL,
 cible text NOT NULL,
 cree_le timestamptz NOT NULL DEFAULT pg_catalog.now()
);
ALTER TABLE public.erp_auth_rate_secret ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.erp_auth_rate_state ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.erp_auth_attempt_tokens ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.erp_security_authorities ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.erp_security_operations ENABLE ROW LEVEL SECURITY;
REVOKE ALL PRIVILEGES ON TABLE public.erp_auth_rate_secret, public.erp_auth_rate_state,public.erp_auth_attempt_tokens,public.erp_security_authorities,public.erp_security_operations FROM PUBLIC,anon,authenticated,service_role;
INSERT INTO public.erp_auth_rate_secret(id) VALUES(1);
INSERT INTO public.erp_security_authorities(user_id,habilitation,actif,attribue_par) VALUES('USR-0001','SECURITY_MANAGER',true,'SYSTEM_MIGRATION_010A_02D_01');
