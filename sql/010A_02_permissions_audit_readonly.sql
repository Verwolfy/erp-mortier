-- MIGRATION 010-A-02 : INVENTAIRE SQL EN LECTURE SEULE.
-- À exécuter dans SQL Editor du PROJET SUPABASE TEST, après vérification
-- visuelle du projet sélectionné. NE PAS appliquer comme migration DDL.
-- Les résultats ne prouvent ni l'identité de la clé utilisée côté Python,
-- ni les permissions métier implémentées par le code applicatif.
-- Requête SELECT unique, sans BEGIN/ROLLBACK pour conserver le résultat
-- dans SQL Editor ; exporter ce résultat en CSV pour le vérificateur local.
-- Pas de requête sur les données métier, pas d'écriture, pas d'appel RPC.
WITH
rpc_attendues(objet, signature) AS (
  VALUES
    ('erp_apply_stock_movement', 'public.erp_apply_stock_movement(text,text,text,text,numeric,numeric,text,text)'),
    ('erp_close_manufacturing_order', 'public.erp_close_manufacturing_order(text,text,text,text,numeric,text,numeric)'),
    ('erp_start_manufacturing_order', 'public.erp_start_manufacturing_order(text)'),
    ('erp_create_purchase_order', 'public.erp_create_purchase_order(text,text,text,text,text,numeric,text,text,text,jsonb)'),
    ('erp_receive_purchase_order', 'public.erp_receive_purchase_order(text,text,text,text,text,text,text,jsonb)'),
    ('erp_sale_transaction', 'public.erp_sale_transaction(text,text,jsonb)'),
    ('erp_finance_transaction', 'public.erp_finance_transaction(text,text,jsonb)'),
    ('erp_create_recipe', 'public.erp_create_recipe(text,text,text,numeric,text,text,jsonb)'),
    ('erp_create_manufacturing_order', 'public.erp_create_manufacturing_order(text,text,text,text,numeric,text,text)'),
    ('erp_create_sales_order', 'public.erp_create_sales_order(text,text,text,jsonb)'),
    ('increment_compteur', 'public.increment_compteur(text)')
),
fn AS (
  SELECT e.objet, e.signature, to_regprocedure(e.signature)::oid AS oid,
         p.prosecdef, p.proconfig, p.proowner
  FROM rpc_attendues e
  LEFT JOIN pg_catalog.pg_proc p ON p.oid = to_regprocedure(e.signature)::oid
),
rpc_resultats AS (
  SELECT 'RPC_ATTENDUE'::text AS categorie, objet,
    CASE
      WHEN oid IS NULL THEN 'BLOQUANT'
      WHEN COALESCE(has_function_privilege(to_regrole('anon'), oid, 'EXECUTE'),false)
        OR COALESCE(has_function_privilege(to_regrole('authenticated'), oid, 'EXECUTE'),false)
        THEN 'BLOQUANT'
      WHEN NOT COALESCE(has_function_privilege(to_regrole('service_role'), oid, 'EXECUTE'),false)
        THEN 'BLOQUANT'
      WHEN prosecdef OR NOT EXISTS (
        SELECT 1 FROM unnest(COALESCE(proconfig, ARRAY[]::text[])) cfg
        WHERE cfg LIKE 'search_path=%') THEN 'A_VERIFIER'
      ELSE 'OK'
    END AS statut,
    jsonb_build_object(
      'signature_attendue', signature,
      'presente', oid IS NOT NULL,
      'execute_anon', COALESCE(has_function_privilege(to_regrole('anon'), oid,'EXECUTE'),false),
      'execute_authenticated', COALESCE(has_function_privilege(to_regrole('authenticated'), oid,'EXECUTE'),false),
      'execute_service_role', COALESCE(has_function_privilege(to_regrole('service_role'), oid,'EXECUTE'),false),
      'security_definer', prosecdef,
      'configuration_fonction', proconfig
    )::text AS details
  FROM fn
),
tables_attendues(objet) AS (
  VALUES ('erp_stock_operations'),('erp_stock_outbox'),
         ('erp_of_closures'),('erp_of_outbox'),
         ('erp_purchase_operations'),('erp_purchase_outbox'),
         ('erp_sales_operations'),('erp_sales_outbox'),
         ('erp_finance_operations'),('erp_finance_outbox'),
         ('erp_production_creations'),('erp_sales_order_creations')
),
table_refs AS (
  SELECT t.objet, to_regclass(format('%I.%I', 'public',t.objet))::oid AS oid
  FROM tables_attendues t
),
tables_resultats AS (
  SELECT 'TABLE_TECHNIQUE'::text AS categorie, t.objet,
    CASE WHEN t.oid IS NULL THEN 'BLOQUANT'
      WHEN NOT c.relrowsecurity THEN 'BLOQUANT'
      WHEN COALESCE(has_table_privilege(to_regrole('anon'),t.oid,'SELECT'),false)
        OR COALESCE(has_table_privilege(to_regrole('anon'),t.oid,'INSERT'),false)
        OR COALESCE(has_table_privilege(to_regrole('anon'),t.oid,'UPDATE'),false)
        OR COALESCE(has_table_privilege(to_regrole('anon'),t.oid,'DELETE'),false)
        OR COALESCE(has_table_privilege(to_regrole('authenticated'),t.oid,'SELECT'),false)
        OR COALESCE(has_table_privilege(to_regrole('authenticated'),t.oid,'INSERT'),false)
        OR COALESCE(has_table_privilege(to_regrole('authenticated'),t.oid,'UPDATE'),false)
        OR COALESCE(has_table_privilege(to_regrole('authenticated'),t.oid,'DELETE'),false)
        THEN 'BLOQUANT'
      ELSE 'OK' END AS statut,
    jsonb_build_object('presente',t.oid IS NOT NULL,
                       'rls_active',c.relrowsecurity,
                       'force_rls',c.relforcerowsecurity,
                       'politiques',COALESCE(pol.nb,0),
                       'lecture_anon',COALESCE(has_table_privilege(to_regrole('anon'),t.oid,'SELECT'),false),
                       'lecture_authenticated',COALESCE(has_table_privilege(to_regrole('authenticated'),t.oid,'SELECT'),false))::text AS details
  FROM table_refs t
  LEFT JOIN pg_catalog.pg_class c ON c.oid=t.oid
  LEFT JOIN LATERAL (
    SELECT count(*) nb FROM pg_catalog.pg_policy p WHERE p.polrelid=t.oid
  ) pol ON true
),
metier_resultats AS (
  SELECT 'TABLE_METIER'::text AS categorie, c.relname::text AS objet,
    CASE
      WHEN NOT c.relrowsecurity THEN 'A_VERIFIER'
      WHEN COALESCE(has_table_privilege(to_regrole('anon'),c.oid,'INSERT'),false)
        OR COALESCE(has_table_privilege(to_regrole('anon'),c.oid,'UPDATE'),false)
        OR COALESCE(has_table_privilege(to_regrole('anon'),c.oid,'DELETE'),false)
        THEN 'A_VERIFIER'
      ELSE 'INFO' END AS statut,
    jsonb_build_object('rls_active',c.relrowsecurity,
                       'politiques', (SELECT count(*) FROM pg_catalog.pg_policy pol WHERE pol.polrelid=c.oid),
                       'lecture_anon',COALESCE(has_table_privilege(to_regrole('anon'),c.oid,'SELECT'),false),
                       'ecriture_anon',COALESCE(has_table_privilege(to_regrole('anon'),c.oid,'INSERT'),false)
                          OR COALESCE(has_table_privilege(to_regrole('anon'),c.oid,'UPDATE'),false)
                          OR COALESCE(has_table_privilege(to_regrole('anon'),c.oid,'DELETE'),false),
                       'lecture_authenticated',COALESCE(has_table_privilege(to_regrole('authenticated'),c.oid,'SELECT'),false),
                       'service_role_bypass_rls',true)::text AS details
  FROM pg_catalog.pg_class c
  JOIN pg_catalog.pg_namespace n ON n.oid=c.relnamespace
  WHERE n.nspname='public' AND c.relkind IN ('r','p')
    AND NOT EXISTS(SELECT 1 FROM tables_attendues t WHERE t.objet=c.relname)
),
fonction_inattendue AS (
  SELECT 'SURCHARGE_RPC'::text AS categorie,
         p.proname::text AS objet,
         'A_VERIFIER'::text AS statut,
         jsonb_build_object('signature_inattendue',p.oid::regprocedure::text,
                            'execute_anon',COALESCE(has_function_privilege(to_regrole('anon'),p.oid,'EXECUTE'),false),
                            'execute_authenticated',COALESCE(has_function_privilege(to_regrole('authenticated'),p.oid,'EXECUTE'),false),
                            'security_definer',p.prosecdef)::text AS details
  FROM pg_catalog.pg_proc p
  JOIN pg_catalog.pg_namespace n ON n.oid=p.pronamespace
  WHERE n.nspname='public'
    AND EXISTS(SELECT 1 FROM rpc_attendues e WHERE e.objet=p.proname)
    AND NOT EXISTS(SELECT 1 FROM fn f WHERE f.oid=p.oid)
),
schema_resultats AS (
  SELECT 'SCHEMA_PUBLIC'::text AS categorie, 'public'::text AS objet,
    CASE WHEN COALESCE(has_schema_privilege(to_regrole('anon'),'public','CREATE'),false)
               OR COALESCE(has_schema_privilege(to_regrole('authenticated'),'public','CREATE'),false)
       THEN 'BLOQUANT' ELSE 'OK' END AS statut,
    jsonb_build_object('anon_create',COALESCE(has_schema_privilege(to_regrole('anon'),'public','CREATE'),false),
                       'authenticated_create',COALESCE(has_schema_privilege(to_regrole('authenticated'),'public','CREATE'),false))::text AS details
),
rapport AS (
  SELECT * FROM rpc_resultats
  UNION ALL SELECT * FROM tables_resultats
  UNION ALL SELECT * FROM metier_resultats
  UNION ALL SELECT * FROM fonction_inattendue
  UNION ALL SELECT * FROM schema_resultats
)
SELECT categorie, objet, statut, details
FROM rapport
ORDER BY CASE statut WHEN 'BLOQUANT' THEN 0 WHEN 'A_VERIFIER' THEN 1 WHEN 'INFO' THEN 2 ELSE 3 END,
         categorie, objet;
