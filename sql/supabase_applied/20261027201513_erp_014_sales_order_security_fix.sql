-- EXACT SQL APPLIED TO SUPABASE PRINCIPALE; do not reapply blindly.
-- Migration 20261027201513 erp_014_sales_order_security_fix
DO $guard$
BEGIN
 IF NOT EXISTS(SELECT 1 FROM pg_proc WHERE oid='public.erp_create_sales_order(text,text,text,jsonb)'::regprocedure AND NOT prosecdef)
 THEN RAISE EXCEPTION 'Safety stop: sales function already changed'; END IF;
 IF has_function_privilege('anon','public.erp_create_sales_order(text,text,text,jsonb)','EXECUTE') OR has_function_privilege('authenticated','public.erp_create_sales_order(text,text,text,jsonb)','EXECUTE')
 THEN RAISE EXCEPTION 'Safety stop: sales function exposed to client roles'; END IF;
END $guard$;
ALTER FUNCTION public.erp_create_sales_order(text,text,text,jsonb) SECURITY DEFINER;
ALTER FUNCTION public.erp_create_sales_order(text,text,text,jsonb) SET search_path TO pg_catalog, pg_temp;
REVOKE ALL PRIVILEGES ON FUNCTION public.erp_create_sales_order(text,text,text,jsonb) FROM PUBLIC, anon, authenticated;
GRANT EXECUTE ON FUNCTION public.erp_create_sales_order(text,text,text,jsonb) TO service_role;
