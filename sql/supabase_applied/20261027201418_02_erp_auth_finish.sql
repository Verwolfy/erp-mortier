-- Segment de la migration Supabase appliquee 20261027201418 (erp_013_security_tables_and_rpc).
-- Ne pas executer isolement; revoir l'ensemble des 6 segments avant reutilisation.
CREATE OR REPLACE FUNCTION public.erp_auth_finish(p_token uuid, p_outcome text)
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
        RAISE EXCEPTION 'Paramètres invalides'
            USING ERRCODE = '22023';
    END IF;

    SELECT key_hash INTO v_hash
    FROM public.erp_auth_attempt_tokens
    WHERE token = p_token;

    IF NOT FOUND THEN
        RETURN false;
    END IF;

    -- Même ordre de verrouillage que erp_auth_begin.
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

    -- BACKEND_ERROR ne pénalise pas l'utilisateur.
    RETURN true;
END;
$function$;
REVOKE ALL PRIVILEGES ON FUNCTION public.erp_auth_finish(p_token uuid, p_outcome text) FROM PUBLIC,anon,authenticated,service_role;
GRANT EXECUTE ON FUNCTION public.erp_auth_finish(p_token uuid, p_outcome text) TO service_role;
