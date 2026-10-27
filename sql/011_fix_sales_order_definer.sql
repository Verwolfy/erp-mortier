-- Migration 011 : correction des privileges de creation
-- des commandes clients.
-- TEST uniquement avant toute autorisation de bascule.
-- Aucun changement des GRANT ou politiques RLS.

BEGIN;

DO $guard$
BEGIN
    IF (
        SELECT pg_get_userbyid(proowner)
        FROM pg_proc
        WHERE oid = to_regprocedure(
            'public.erp_create_sales_order(text,text,text,jsonb)'
        )
    ) IS DISTINCT FROM 'postgres' THEN
        RAISE EXCEPTION 'Proprietaire RPC non conforme';
    END IF;

    IF has_function_privilege(
        'anon',
        'public.erp_create_sales_order(text,text,text,jsonb)',
        'EXECUTE'
    )
    OR has_function_privilege(
        'authenticated',
        'public.erp_create_sales_order(text,text,text,jsonb)',
        'EXECUTE'
    )
    OR NOT has_function_privilege(
        'service_role',
        'public.erp_create_sales_order(text,text,text,jsonb)',
        'EXECUTE'
    ) THEN
        RAISE EXCEPTION 'Permissions RPC non conformes';
    END IF;

    IF to_regprocedure('pg_catalog.gen_random_uuid()')
        IS NULL THEN
        RAISE EXCEPTION 'gen_random_uuid non disponible dans pg_catalog';
    END IF;
END;
$guard$;

ALTER FUNCTION public.erp_create_sales_order(
    text, text, text, jsonb
) SECURITY DEFINER;

ALTER FUNCTION public.erp_create_sales_order(
    text, text, text, jsonb
) SET search_path TO pg_catalog, pg_temp;

COMMIT;