-- Segment de la migration Supabase appliquee 20261027201418 (erp_013_security_tables_and_rpc).
-- Ne pas executer isolement; revoir l'ensemble des 6 segments avant reutilisation.
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
        RAISE EXCEPTION 'Configuration de sécurité absente';
    END IF;

    -- Ne stocker que l'empreinte pseudonymisée du login.
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

    -- Verrouillage atomique du compteur partagé.
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

    -- Réinitialisation après expiration du blocage
    -- ou après 15 minutes depuis le premier échec.
    IF (v_locked IS NOT NULL AND v_locked <= v_now)
       OR (v_first IS NOT NULL
           AND v_first <= v_now - interval '15 minutes')
    THEN
        UPDATE public.erp_auth_rate_state
        SET failure_count = 0,
            first_failure_at = NULL,
            locked_until = NULL,
            updated_at = v_now
        WHERE key_hash = v_hash;
    END IF;

    -- Expirer les tentatives abandonnées.
    UPDATE public.erp_auth_attempt_tokens
    SET completed_at = v_now,
        outcome = 'EXPIRED'
    WHERE key_hash = v_hash
      AND completed_at IS NULL
      AND created_at <= v_now - interval '60 seconds';

    -- Une seule tentative simultanée par identifiant.
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
REVOKE ALL PRIVILEGES ON FUNCTION public.erp_auth_begin(p_login text) FROM PUBLIC,anon,authenticated,service_role;
GRANT EXECUTE ON FUNCTION public.erp_auth_begin(p_login text) TO service_role;
