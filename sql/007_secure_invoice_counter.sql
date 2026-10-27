-- Migration 007 : sécurisation de la numérotation des factures
-- Réexécutable sans modifier les compteurs existants.

BEGIN;

REVOKE EXECUTE ON FUNCTION public.increment_compteur(text)
FROM PUBLIC, anon, authenticated;

GRANT EXECUTE ON FUNCTION public.increment_compteur(text)
TO service_role;

COMMIT;
