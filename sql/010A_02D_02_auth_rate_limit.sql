-- Migration 010-A-02D-02 : limitation partagee des connexions
-- Source : definitions et structure relevees sur Supabase TEST.
-- Ne pas executer sur PROD sans validation et autorisation distinctes.
-- A executer par le role postgres dans un environnement autorise.
--
-- Ne contient aucun secret extrait de TEST.
-- Le secret existant est conserve lors d'une nouvelle execution.
-- Aucun DROP, TRUNCATE ni suppression de donnees.

BEGIN;

-- 1. Secret propre a chaque environnement.

CREATE TABLE IF NOT EXISTS public.erp_auth_rate_secret (
    id integer NOT NULL PRIMARY KEY,
    secret_uuid uuid NOT NULL DEFAULT gen_random_uuid(),
    CONSTRAINT erp_auth_rate_secret_id_check
        CHECK (id = 1)
);

-- 2. Compteurs partages par empreinte de login.

CREATE TABLE IF NOT EXISTS public.erp_auth_rate_state (
    key_hash text NOT NULL PRIMARY KEY,
    failure_count integer NOT NULL DEFAULT 0,
    first_failure_at timestamptz,
    locked_until timestamptz,
    updated_at timestamptz NOT NULL DEFAULT clock_timestamp(),

    CONSTRAINT erp_auth_rate_state_failure_count_check
        CHECK (failure_count >= 0 AND failure_count <= 3),

    CONSTRAINT erp_auth_rate_state_key_hash_check
        CHECK (key_hash ~ '^[0-9a-f]{64}$')
);

-- 3. Jetons de tentatives de connexion.

CREATE TABLE IF NOT EXISTS public.erp_auth_attempt_tokens (
    token uuid NOT NULL DEFAULT gen_random_uuid() PRIMARY KEY,
    key_hash text NOT NULL
        REFERENCES public.erp_auth_rate_state(key_hash),
    created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    completed_at timestamptz,
    outcome text,

    CONSTRAINT erp_auth_attempt_tokens_outcome_check
        CHECK (
            outcome IN (
                'SUCCESS',
                'FAILURE',
                'BACKEND_ERROR',
                'EXPIRED'
            )
        )
);

CREATE INDEX IF NOT EXISTS erp_auth_attempt_tokens_pending_idx
ON public.erp_auth_attempt_tokens (key_hash, created_at)
WHERE completed_at IS NULL;

-- 4. Isolation des tables.

ALTER TABLE public.erp_auth_rate_secret
    ENABLE ROW LEVEL SECURITY;

ALTER TABLE public.erp_auth_rate_state
    ENABLE ROW LEVEL SECURITY;

ALTER TABLE public.erp_auth_attempt_tokens
    ENABLE ROW LEVEL SECURITY;

REVOKE ALL ON TABLE
    public.erp_auth_rate_secret,
    public.erp_auth_rate_state,
    public.erp_auth_attempt_tokens
FROM PUBLIC, anon, authenticated, service_role;

-- Generer le secret seulement s'il n'existe pas deja.
-- Aucun remplacement du secret existant.

INSERT INTO public.erp_auth_rate_secret (id)
VALUES (1)
ON CONFLICT (id) DO NOTHING;

-- 5. Debut d'une tentative.

CREATE OR REPLACE FUNCTION public.erp_auth_begin(p_login text)
RETURNS uuid
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path TO 'pg_catalog', 'pg_temp'
AS $function$
DECLARE
    v_secret uuid;
    v_hash text;
    v_token uuid;
    v_now timestamptz := clock_timestamp();
    v_locked timestamptz;
    v_first timestamptz;
BEGIN
    IF p_login IS NULL
       OR length(btrim(p_login)) = 0
       OR length(btrim(p_login)) > 128
    THEN
        RAISE EXCEPTION 'Identifiant invalide'
            USING ERRCODE = '22023';
    END IF;

    SELECT secret_uuid INTO v_secret
    FROM public.erp_auth_rate_secret
    WHERE id = 1;

    IF v_secret IS NULL THEN
        RAISE EXCEPTION 'Configuration de s?curit? absente';
    END IF;

    -- Conserver seulement une empreinte pseudonymisee du login.
    v_hash := encode(
        sha256(
            convert_to(
                v_secret::text || ':' || lower(btrim(p_login)),
                'UTF8'
            )
        ),
        'hex'
    );

    INSERT INTO public.erp_auth_rate_state(key_hash)
    VALUES (v_hash)
    ON CONFLICT (key_hash) DO NOTHING;

    PERFORM 1
    FROM public.erp_auth_rate_state
    WHERE key_hash = v_hash
    FOR UPDATE;

    SELECT locked_until, first_failure_at
    INTO v_locked, v_first
    FROM public.erp_auth_rate_state
    WHERE key_hash = v_hash;

    IF v_locked IS NOT NULL AND v_locked > v_now THEN
        RETURN NULL;
    END IF;

    IF (v_locked IS NOT NULL AND v_locked <= v_now)
       OR (
           v_first IS NOT NULL
           AND v_first <= v_now - interval '15 minutes'
       )
    THEN
        UPDATE public.erp_auth_rate_state
        SET failure_count = 0,
            first_failure_at = NULL,
            locked_until = NULL,
            updated_at = v_now
        WHERE key_hash = v_hash;
    END IF;

    UPDATE public.erp_auth_attempt_tokens
    SET completed_at = v_now,
        outcome = 'EXPIRED'
    WHERE key_hash = v_hash
      AND completed_at IS NULL
      AND created_at <= v_now - interval '60 seconds';

    IF EXISTS (
        SELECT 1
        FROM public.erp_auth_attempt_tokens
        WHERE key_hash = v_hash
          AND completed_at IS NULL
    ) THEN
        RETURN NULL;
    END IF;

    INSERT INTO public.erp_auth_attempt_tokens(key_hash)
    VALUES (v_hash)
    RETURNING token INTO v_token;

    RETURN v_token;
END;
$function$;

-- 6. Finalisation d'une tentative.

CREATE OR REPLACE FUNCTION public.erp_auth_finish(
    p_token uuid,
    p_outcome text
)
RETURNS boolean
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path TO 'pg_catalog', 'pg_temp'
AS $function$
DECLARE
    v_hash text;
    v_created timestamptz;
    v_completed timestamptz;
    v_now timestamptz := clock_timestamp();
BEGIN
    IF p_token IS NULL
       OR p_outcome IS NULL
       OR p_outcome NOT IN (
           'SUCCESS', 'FAILURE', 'BACKEND_ERROR'
       )
    THEN
        RAISE EXCEPTION 'Param?tres invalides'
            USING ERRCODE = '22023';
    END IF;

    SELECT key_hash INTO v_hash
    FROM public.erp_auth_attempt_tokens
    WHERE token = p_token;

    IF NOT FOUND THEN
        RETURN false;
    END IF;

    PERFORM 1
    FROM public.erp_auth_rate_state
    WHERE key_hash = v_hash
    FOR UPDATE;

    SELECT created_at, completed_at
    INTO v_created, v_completed
    FROM public.erp_auth_attempt_tokens
    WHERE token = p_token
    FOR UPDATE;

    IF NOT FOUND OR v_completed IS NOT NULL THEN
        RETURN false;
    END IF;

    IF v_created <= v_now - interval '60 seconds' THEN
        UPDATE public.erp_auth_attempt_tokens
        SET completed_at = v_now,
            outcome = 'EXPIRED'
        WHERE token = p_token;

        RETURN false;
    END IF;

    UPDATE public.erp_auth_attempt_tokens
    SET completed_at = v_now,
        outcome = p_outcome
    WHERE token = p_token;

    IF p_outcome = 'SUCCESS' THEN
        UPDATE public.erp_auth_rate_state
        SET failure_count = 0,
            first_failure_at = NULL,
            locked_until = NULL,
            updated_at = v_now
        WHERE key_hash = v_hash;

    ELSIF p_outcome = 'FAILURE' THEN
        UPDATE public.erp_auth_rate_state
        SET failure_count = LEAST(failure_count + 1, 3),
            first_failure_at = COALESCE(first_failure_at, v_now),
            locked_until = CASE
                WHEN failure_count >= 2
                THEN v_now + interval '180 seconds'
                ELSE NULL
            END,
            updated_at = v_now
        WHERE key_hash = v_hash;
    END IF;

    -- BACKEND_ERROR ne penalise pas l'utilisateur.
    RETURN true;
END;
$function$;

-- 7. Permissions explicites des deux fonctions.

REVOKE ALL ON FUNCTION public.erp_auth_begin(text)
FROM PUBLIC, anon, authenticated, service_role;

REVOKE ALL ON FUNCTION public.erp_auth_finish(uuid, text)
FROM PUBLIC, anon, authenticated, service_role;

GRANT EXECUTE ON FUNCTION public.erp_auth_begin(text)
TO service_role;

GRANT EXECUTE ON FUNCTION public.erp_auth_finish(uuid, text)
TO service_role;

COMMIT;
