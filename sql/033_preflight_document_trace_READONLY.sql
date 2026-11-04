-- NEXTGEN 033 — PREFLIGHT LECTURE SEULE (aucune mutation).
-- Exécution possible sur production pour audit, sans appliquer 033.
-- Des résultats faux doivent BLOQUER l'activation du registre.
SELECT
  EXISTS (
    SELECT 1 FROM information_schema.schemata
    WHERE schema_name = 'erp_private'
  ) AS schema_prive_existe,
  NOT EXISTS (
    SELECT 1 FROM information_schema.tables
    WHERE table_schema = 'public'
      AND table_name IN ('erp_document_trace', 'erp_document_trace_event')
  ) AS aucune_table_qr_exposee,
  EXISTS (
    SELECT 1 FROM information_schema.tables
    WHERE table_schema = 'erp_private'
      AND table_name = 'erp_document_trace'
  ) AS registre_deja_present,
  EXISTS (
    SELECT 1 FROM information_schema.tables
    WHERE table_schema = 'erp_private'
      AND table_name = 'erp_document_trace_event'
  ) AS evenements_deja_presents;

-- Contrôler les privilèges du schéma privé sans accéder aux données.
SELECT
  has_schema_privilege('anon', 'erp_private', 'USAGE') AS anon_peut_utiliser_schema,
  has_schema_privilege('authenticated', 'erp_private', 'USAGE') AS auth_peut_utiliser_schema,
  has_schema_privilege('service_role', 'erp_private', 'USAGE') AS service_peut_utiliser_schema;

-- Après déploiement UNIQUEMENT, vérifier également l'absence de GRANT
-- direct, RLS activée/forcée, identité authentifiée, l'audit append-only et
-- les politiques testées contre plusieurs rôles. Ne rien inférer ici.
