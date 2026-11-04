-- NEXTGEN ERP 033 — PROPOSITION NON APPLIQUÉE.
-- Conception du registre QR privé : historique multiversion, aucun accès API.
-- Aucune politique de validation/rôle implicite : activation BLOQUÉE en production.
-- ATTENTION : fichier préparatoire, ne pas inclure dans des déploiements SQL automatiques.
BEGIN;

-- Dépendance existante vérifiée par requête information_schema en lecture seule :
-- erp_private existe déjà. Les utilisateurs ERP sont dans public.users
-- (user_id text), sans identité auth.users présumée.
CREATE TABLE erp_private.erp_document_trace (
    trace_id text PRIMARY KEY CHECK (trace_id ~ '^NG-[A-F0-9]{32}$'),
    document_type text NOT NULL CHECK (length(btrim(document_type)) BETWEEN 2 AND 100),
    document_reference text NOT NULL DEFAULT '' CHECK (length(document_reference) <= 120),
    current_version integer NOT NULL DEFAULT 1 CHECK (current_version >= 1),
    statut text NOT NULL DEFAULT 'BROUILLON'
        CHECK (statut IN ('BROUILLON','A_VALIDER','VALIDE','ANNULE')),
    created_by text NOT NULL REFERENCES public.users(user_id) ON DELETE RESTRICT,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now()
);

-- Chaque version possède sa propre empreinte : la clé est composite.
-- La création d'une version future DOIT être atomique avec current_version
-- et l'événement correspondant via un RPC serveur encore non implémenté.
CREATE TABLE erp_private.erp_document_trace_version (
    trace_id text NOT NULL REFERENCES erp_private.erp_document_trace(trace_id)
        ON DELETE RESTRICT,
    version_no integer NOT NULL CHECK (version_no >= 1),
    payload_sha256 text NOT NULL CHECK (payload_sha256 ~ '^[a-f0-9]{64}$'),
    recorded_by text NOT NULL REFERENCES public.users(user_id) ON DELETE RESTRICT,
    recorded_at timestamptz NOT NULL DEFAULT now(),
    metadata jsonb NOT NULL DEFAULT '{}'::jsonb
        CHECK (jsonb_typeof(metadata) = 'object' AND pg_column_size(metadata) <= 8192),
    PRIMARY KEY (trace_id, version_no)
);

-- Les événements référencent une version effective, jamais un numéro libre.
CREATE TABLE erp_private.erp_document_trace_event (
    event_id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    trace_id text NOT NULL,
    version_no integer NOT NULL,
    event_type text NOT NULL
        CHECK (event_type IN ('CREATION','EXPORT','SOUMISSION','VALIDATION','ANNULATION')),
    actor_id text NOT NULL REFERENCES public.users(user_id) ON DELETE RESTRICT,
    happened_at timestamptz NOT NULL DEFAULT now(),
    detail jsonb NOT NULL DEFAULT '{}'::jsonb
        CHECK (jsonb_typeof(detail) = 'object' AND pg_column_size(detail) <= 4096),
    FOREIGN KEY (trace_id, version_no)
        REFERENCES erp_private.erp_document_trace_version(trace_id, version_no)
        ON DELETE RESTRICT
);
CREATE INDEX erp_document_trace_event_trace_date
    ON erp_private.erp_document_trace_event(trace_id, happened_at DESC);

-- Défense supplémentaire contre altération d'un historique existant.
-- Fonctions invoker privées ; aucun privilège d'exécution élevé exposé.
CREATE FUNCTION erp_private.erp_document_trace_immutable()
RETURNS trigger LANGUAGE plpgsql SECURITY INVOKER
SET search_path = pg_catalog
AS $$
BEGIN
    RAISE EXCEPTION 'Historique documentaire immuable'
        USING ERRCODE = '23514';
END;
$$;

CREATE TRIGGER erp_document_trace_version_immutable
BEFORE UPDATE OR DELETE ON erp_private.erp_document_trace_version
FOR EACH ROW EXECUTE FUNCTION erp_private.erp_document_trace_immutable();

CREATE TRIGGER erp_document_trace_event_immutable
BEFORE UPDATE OR DELETE ON erp_private.erp_document_trace_event
FOR EACH ROW EXECUTE FUNCTION erp_private.erp_document_trace_immutable();

ALTER TABLE erp_private.erp_document_trace ENABLE ROW LEVEL SECURITY;
ALTER TABLE erp_private.erp_document_trace_version ENABLE ROW LEVEL SECURITY;
ALTER TABLE erp_private.erp_document_trace_event ENABLE ROW LEVEL SECURITY;
ALTER TABLE erp_private.erp_document_trace FORCE ROW LEVEL SECURITY;
ALTER TABLE erp_private.erp_document_trace_version FORCE ROW LEVEL SECURITY;
ALTER TABLE erp_private.erp_document_trace_event FORCE ROW LEVEL SECURITY;

-- Aucun GRANT aux rôles API. Aucune politique ajoutée tant que l'identité
-- serveur et l'autorisation de chaque transition ne sont pas homologuées.
REVOKE ALL ON erp_private.erp_document_trace
    FROM PUBLIC, anon, authenticated, service_role;
REVOKE ALL ON erp_private.erp_document_trace_version
    FROM PUBLIC, anon, authenticated, service_role;
REVOKE ALL ON erp_private.erp_document_trace_event
    FROM PUBLIC, anon, authenticated, service_role;
REVOKE ALL ON SEQUENCE erp_private.erp_document_trace_event_event_id_seq
    FROM PUBLIC, anon, authenticated, service_role;
REVOKE ALL ON FUNCTION erp_private.erp_document_trace_immutable()
    FROM PUBLIC, anon, authenticated, service_role;

COMMIT;

-- BLOQUANTS AVANT ACTIVATION :
-- - Authentifier et réévaluer les droits de chaque acteur public.users côté serveur.
-- - RPC transactionnel, contrôles d'état, version atomique et concurrents.
-- - Test SQL réel des refus UPDATE/DELETE et de toutes les politiques RLS.
-- - Vérification des liens entre current_version et version existante.
-- - Rétention, confidentialité des métadonnées et projection QR publique minimale.
-- - Approbation explicite avant toute DDL/RLS/GRANT sur production.
