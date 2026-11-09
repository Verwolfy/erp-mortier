-- ERP SECURITY-01 : audit de la surface publique, exclusivement lecture seule.
-- RLS sans policy peut exprimer un refus d'accès intentionnel.
-- Ce diagnostic décrit les droits effectifs SQL et ne certifie pas toute l'application.
WITH relations AS (
  SELECT c.oid, c.relkind, c.relrowsecurity, c.reloptions,
         has_table_privilege('anon', c.oid, 'SELECT') AS anon_select,
         has_table_privilege('anon', c.oid, 'INSERT') AS anon_insert,
         has_table_privilege('authenticated', c.oid, 'SELECT') AS auth_select,
         has_table_privilege('authenticated', c.oid, 'INSERT') AS auth_insert,
         has_table_privilege('service_role', c.oid, 'SELECT') AS service_select,
         (SELECT count(*) FROM pg_policy pol WHERE pol.polrelid = c.oid) AS policy_count
  FROM pg_class c
  JOIN pg_namespace n ON n.oid = c.relnamespace
  WHERE n.nspname = 'public'
    AND c.relkind IN ('r', 'p', 'v', 'm')
), fonctions AS (
  SELECT p.oid, p.prosecdef, p.proconfig, p.prorettype,
         has_function_privilege('anon', p.oid, 'EXECUTE') AS anon_execute,
         has_function_privilege('authenticated', p.oid, 'EXECUTE') AS auth_execute
  FROM pg_proc p
  JOIN pg_namespace n ON n.oid = p.pronamespace
  WHERE n.nspname = 'public'
)
SELECT
  (SELECT count(*) FROM relations) AS relations_publiques,
  (SELECT count(*) FROM relations WHERE relkind IN ('r','p')) AS tables_publiques,
  (SELECT count(*) FROM relations WHERE relrowsecurity) AS tables_rls,
  (SELECT count(*) FROM relations WHERE relrowsecurity AND policy_count = 0) AS tables_rls_sans_policy,
  (SELECT count(*) FROM relations WHERE relkind IN ('v','m')) AS vues,
  (SELECT count(*) FROM relations WHERE relkind = 'v'
      AND NOT coalesce('security_invoker=true' = ANY(reloptions), false)) AS vues_sans_security_invoker,
  (SELECT count(*) FROM relations WHERE relkind IN ('v','m') AND NOT service_select) AS vues_sans_service_select,
  (SELECT count(*) FROM relations WHERE anon_select OR auth_select) AS relations_select_client,
  (SELECT count(*) FROM relations WHERE anon_insert OR auth_insert) AS relations_insert_client,
  (SELECT count(*) FROM fonctions) AS fonctions_publiques,
  (SELECT count(*) FROM fonctions WHERE anon_execute OR auth_execute) AS fonctions_executables_client,
  (SELECT count(*) FROM fonctions WHERE (anon_execute OR auth_execute)
      AND prorettype <> 'pg_catalog.trigger'::regtype) AS fonctions_clients_hors_trigger,
  (SELECT count(*) FROM fonctions WHERE prosecdef) AS fonctions_security_definer,
  (SELECT count(*) FROM fonctions WHERE prosecdef AND (anon_execute OR auth_execute)) AS definer_executables_client,
  (SELECT count(*) FROM fonctions WHERE prosecdef
      AND NOT (coalesce(array_to_string(proconfig, ','), '') LIKE '%search_path%')) AS definer_sans_search_path;
