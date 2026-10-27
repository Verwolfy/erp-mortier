-- EXACT SQL APPLIED TO SUPABASE PRINCIPALE; do not reapply blindly.
-- Migration 20261027200803 erp_012_harden_principale_grants
DO $guard$
BEGIN
 IF EXISTS (SELECT 1 FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace
 WHERE n.nspname='public' AND c.relkind IN ('r','p') AND NOT c.relrowsecurity)
 THEN RAISE EXCEPTION 'ABORT: table without RLS'; END IF;
 IF EXISTS (SELECT 1 FROM pg_policies p WHERE p.schemaname='public' AND ('anon'=ANY(p.roles) OR 'authenticated'=ANY(p.roles) OR 'public'=ANY(p.roles)))
 THEN RAISE EXCEPTION 'ABORT: direct client RLS policies exist'; END IF;
END $guard$;
REVOKE ALL PRIVILEGES ON ALL TABLES IN SCHEMA public FROM anon, authenticated;
REVOKE ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public FROM anon, authenticated;
ALTER DEFAULT PRIVILEGES FOR ROLE postgres IN SCHEMA public REVOKE ALL ON TABLES FROM anon, authenticated;
ALTER DEFAULT PRIVILEGES FOR ROLE postgres IN SCHEMA public REVOKE ALL ON SEQUENCES FROM anon, authenticated;
ALTER DEFAULT PRIVILEGES FOR ROLE postgres IN SCHEMA public REVOKE ALL ON FUNCTIONS FROM anon, authenticated;
ALTER FUNCTION public.increment_compteur(text) SET search_path TO pg_catalog, public;
