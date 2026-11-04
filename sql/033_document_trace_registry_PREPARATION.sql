-- NEXTGEN ERP 033 — PROPOSITION NON APPLIQUÉE.
-- Migration préparatoire : revue de sécurité requise avant exécution.
-- Ni historique ni QR public : schéma privé, aucun GRANT supplémentaire.
-- Ne PAS exécuter sur production avant les tests RLS / transactionnels.
BEGIN;

-- Le schéma erp_private existe déjà dans la production, vérifié en lecture.
CREATE TABLE erp_private.erp_document_trace (
    trace_id text PRIMARY KEY
        CHECK (trace_id ~ '^NG-[A-F0-9]{32}$'),
    document_type text NOT NULL
        CHECK (length(btrim(document_type)) BETWEEN 2 AND 100),
    document_reference text NOT NULL DEFAULT ''
        CHECK (length(document_reference) <= 120),
    version_no integer NOT NULL DEFAULT 1 CHECK (version_no >= 1),
    statut text NOT NULL DEFAULT 'BROUILLON'
        CHECK (statut IN ('BROUILLON','A_VALIDER','VALIDE','ANNULE')),
    created_by text NOT NULL CHECK (length(btrim(created_by)) BETWEEN 1 AND 128),
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    payload_sha256 text NOT NULL CHECK (payload_sha256 ~ '^[a-f0-9]{64}$'),
    metadata jsonb NOT NULL DEFAULT '{}'::jsonb
        CHECK (jsonb_typeof(metadata) = 'object' AND pg_column_size(metadata) <= 8192),
    CONSTRAINT erp_document_trace_version UNIQUE (trace_id, version_no)
);

CREATE TABLE erp_private.erp_document_trace_event (
    event_id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    trace_id text NOT NULL
        REFERENCES erp_private.erp_document_trace(trace_id) ON DELETE RESTRICT,
    event_type text NOT NULL
        CHECK (event_type IN ('CREATION','EXPORT','SOUMISSION','VALIDATION','ANNULATION')),
    actor_id text NOT NULL CHECK (length(btrim(actor_id)) BETWEEN 1 AND 128),
    happened_at timestamptz NOT NULL DEFAULT now(),
    version_no integer NOT NULL CHECK (version_no >= 1),
    detail jsonb NOT NULL DEFAULT '{}'::jsonb
        CHECK (jsonb_typeof(detail) = 'object' AND pg_column_size(detail) <= 4096)
);
CREATE INDEX erp_document_trace_event_trace_date
    ON erp_private.erp_document_trace_event(trace_id, happened_at DESC);

ALTER TABLE erp_private.erp_document_trace ENABLE ROW LEVEL SECURITY;
ALTER TABLE erp_private.erp_document_trace_event ENABLE ROW LEVEL SECURITY;
ALTER TABLE erp_private.erp_document_trace FORCE ROW LEVEL SECURITY;
ALTER TABLE erp_private.erp_document_trace_event FORCE ROW LEVEL SECURITY;

-- AUCUNE POLICY et AUCUN GRANT : accès par défaut refusé à anon,
-- authenticated et service_role sans une couche serveur explicitement revue.
REVOKE ALL ON erp_private.erp_document_trace FROM PUBLIC, anon, authenticated, service_role;
REVOKE ALL ON erp_private.erp_document_trace_event FROM PUBLIC, anon, authenticated, service_role;
REVOKE ALL ON SEQUENCE erp_private.erp_document_trace_event_event_id_seq
    FROM PUBLIC, anon, authenticated, service_role;

COMMIT;

-- Points BLOQUANTS restant à définir AVANT application :
-- 1. Quelle identité serveur fiable associer à l'utilisateur ERP Streamlit ?
-- 2. Autorisation d'écriture contrôlée par un RPC + journaux immuables.
-- 3. Règles de rétention, suppression RGPD/secret commercial et RLS testées.
-- 4. Vérification QR publique éventuelle : projection minimale, pas de PII.
-- 5. Stratégie de versions : une ligne actuelle par trace_id ou historique dédié.
