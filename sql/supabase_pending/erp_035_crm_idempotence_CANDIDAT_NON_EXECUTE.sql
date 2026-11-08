-- SEC-CRM-03 — CANDIDAT POUR TEST ISOLE UNIQUEMENT — NON APPLIQUE
-- STOP: NE JAMAIS EXECUTER SUR wenydirqtmkywbxbxfal (PRODUCTION).
-- Ce fichier n'est PAS une migration automatique. Revue + TEST actif requis.
-- PostgreSQL 17 / Supabase. Aucune configuration de deployment ne le charge.
-- DDL a valider en TEST; toutes les modifications sont dans une transaction.
BEGIN;

CREATE SCHEMA IF NOT EXISTS erp_crm_private;
REVOKE ALL ON SCHEMA erp_crm_private FROM PUBLIC, anon, authenticated;

CREATE TABLE IF NOT EXISTS erp_crm_private.operation_receipts (
    operation_id uuid PRIMARY KEY,
    kind text NOT NULL CHECK (kind IN ('opportunite', 'interaction')),
    actor_id text NOT NULL,
    request_payload jsonb NOT NULL CHECK (jsonb_typeof(request_payload) = 'object'),
    document_id text NOT NULL,
    created_at timestamptz NOT NULL DEFAULT transaction_timestamp(),
    UNIQUE (kind, document_id)
);
ALTER TABLE erp_crm_private.operation_receipts ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON erp_crm_private.operation_receipts FROM PUBLIC, anon, authenticated, service_role;

-- L'owner devra etre postgres (ou autre role controle). La fonction utilise
-- l'acces serveur service_role seulement, jamais anon/authenticated.
CREATE OR REPLACE FUNCTION public.erp_crm_create_idempotent(
    p_operation_id uuid,
    p_actor_id text,
    p_kind text,
    p_payload jsonb
) RETURNS jsonb
LANGUAGE plpgsql
VOLATILE
SECURITY DEFINER
SET search_path = ''
AS $$
DECLARE
    v_role text;
    v_active text;
    v_perm_count integer := 0;
    v_perm_enabled integer := 0;
    v_document_id text;
    v_new boolean := false;
    v_receipt erp_crm_private.operation_receipts%ROWTYPE;
    v_num_val numeric;
    v_prob_val numeric;
BEGIN
    IF p_operation_id IS NULL OR p_actor_id IS NULL OR
       length(trim(p_actor_id)) = 0 OR length(p_actor_id) > 128 OR
       p_kind NOT IN ('opportunite', 'interaction') OR p_kind IS NULL OR
       p_payload IS NULL OR jsonb_typeof(p_payload) <> 'object' OR
       octet_length(p_payload::text) > 8192
    THEN
        RAISE EXCEPTION 'CRM_INPUT_INVALID' USING ERRCODE = '22023';
    END IF;

    -- Revalidation a CHAQUE tentative, y compris lors d'un replay.
    -- Le backend Streamlit seul peut invoquer cette fonction via service_role.
    SELECT u.role, u.actif
      INTO v_role, v_active
      FROM public.users AS u
     WHERE u.user_id = p_actor_id
     FOR SHARE;
    IF NOT FOUND OR v_role IS NULL OR
       upper(trim(coalesce(v_active, ''))) NOT IN
          ('OUI', 'TRUE', '1', 'YES', 'ACTIF', 'ACTIVE')
    THEN
        RAISE EXCEPTION 'CRM_ACCESS_DENIED' USING ERRCODE = '42501';
    END IF;

    IF upper(trim(v_role)) NOT IN ('ADMIN', 'ADMINISTRATEUR', 'SUPERADMIN') THEN
        SELECT count(*),
               count(*) FILTER (WHERE upper(trim(coalesce(p.ecriture, '')))
                                      IN ('OUI', 'TRUE', '1', 'YES'))
          INTO v_perm_count, v_perm_enabled
          FROM public.permissions AS p
         WHERE upper(trim(p.role)) = upper(trim(v_role))
           AND upper(trim(p.module)) = 'CRM';
        IF v_perm_count <> 1 OR v_perm_enabled <> 1 THEN
            RAISE EXCEPTION 'CRM_ACCESS_DENIED' USING ERRCODE = '42501';
        END IF;
    END IF;

    -- Validation stricte AVANT l'inscription dans le registre.
    IF p_kind = 'opportunite' THEN
        IF (p_payload - ARRAY['prospect_nom','contact','statut',
                'commercial_id','valeur_estimee','probabilite_pct']) <> '{}'::jsonb
           OR jsonb_typeof(p_payload->'prospect_nom') <> 'string'
           OR length(trim(p_payload->>'prospect_nom')) NOT BETWEEN 1 AND 200
           OR jsonb_typeof(p_payload->'statut') <> 'string'
           OR (p_payload->>'statut') NOT IN
                ('Nouveau','Contacté','En Négociation','Gagné','Perdu')
           OR jsonb_typeof(p_payload->'contact') <> 'string'
           OR length(p_payload->>'contact') > 400
           OR jsonb_typeof(p_payload->'commercial_id') <> 'string'
           OR length(p_payload->>'commercial_id') > 128
           OR jsonb_typeof(p_payload->'valeur_estimee') <> 'number'
           OR jsonb_typeof(p_payload->'probabilite_pct') <> 'number'
        THEN
            RAISE EXCEPTION 'CRM_PAYLOAD_INVALID' USING ERRCODE = '22023';
        END IF;
        v_num_val := (p_payload->>'valeur_estimee')::numeric;
        v_prob_val := (p_payload->>'probabilite_pct')::numeric;
        IF v_num_val < 0 OR v_num_val >= 1e15 OR
           v_prob_val < 0 OR v_prob_val > 100 THEN
            RAISE EXCEPTION 'CRM_PAYLOAD_INVALID' USING ERRCODE = '22023';
        END IF;
    ELSE
        IF (p_payload - ARRAY['client_id','type_action','notes','date_rappel'])
                 <> '{}'::jsonb
           OR jsonb_typeof(p_payload->'client_id') <> 'string'
           OR length(trim(p_payload->>'client_id')) NOT BETWEEN 1 AND 128
           OR jsonb_typeof(p_payload->'type_action') <> 'string'
           OR length(trim(p_payload->>'type_action')) NOT BETWEEN 1 AND 100
           OR jsonb_typeof(p_payload->'notes') <> 'string'
           OR length(p_payload->>'notes') > 4000
           OR jsonb_typeof(p_payload->'date_rappel') <> 'string'
           OR length(p_payload->>'date_rappel') > 10
        THEN
            RAISE EXCEPTION 'CRM_PAYLOAD_INVALID' USING ERRCODE = '22023';
        END IF;
        -- Rejeter les dates non canoniques et les valeurs hors calendrier.
        IF (p_payload->>'date_rappel') <> '' THEN
            IF (p_payload->>'date_rappel') !~ '^\\d{4}-\\d{2}-\\d{2}$' OR
               to_char((p_payload->>'date_rappel')::date, 'YYYY-MM-DD')
                    <> (p_payload->>'date_rappel') THEN
                RAISE EXCEPTION 'CRM_PAYLOAD_INVALID' USING ERRCODE = '22023';
            END IF;
        END IF;
        IF NOT EXISTS (
            SELECT 1 FROM public.clients AS c
             WHERE c.client_id = (p_payload->>'client_id')
               AND upper(trim(coalesce(c.actif, ''))) IN
                    ('OUI', 'TRUE', '1', 'YES', 'ACTIF', 'ACTIVE')
        ) THEN
            RAISE EXCEPTION 'CRM_CLIENT_UNAVAILABLE' USING ERRCODE = '22023';
        END IF;
    END IF;

    -- Une premiere tentative reserve operation_id + document_id.
    -- ON CONFLICT et PK UNIQUE serialisent les appels concurrents :
    -- le perdant attend le commit/rollback du gagnant.
    v_document_id := CASE p_kind
        WHEN 'opportunite' THEN 'OPP-' ELSE 'INT-' END
        || upper(replace(pg_catalog.gen_random_uuid()::text, '-', ''));
    INSERT INTO erp_crm_private.operation_receipts (
        operation_id, kind, actor_id, request_payload, document_id
    ) VALUES (
        p_operation_id, p_kind, p_actor_id, p_payload, v_document_id
    ) ON CONFLICT (operation_id) DO NOTHING;
    v_new := FOUND;

    SELECT * INTO STRICT v_receipt
      FROM erp_crm_private.operation_receipts
     WHERE operation_id = p_operation_id
     FOR UPDATE;

    IF v_receipt.kind <> p_kind OR v_receipt.actor_id <> p_actor_id
       OR v_receipt.request_payload <> p_payload THEN
        RAISE EXCEPTION 'CRM_OPERATION_CONFLICT' USING ERRCODE = '22023';
    END IF;
    v_document_id := v_receipt.document_id;

    IF v_new THEN
        IF p_kind = 'opportunite' THEN
            INSERT INTO public.pipeline (
                opportunite_id, prospect_nom, contact, statut, commercial_id,
                valeur_estimee, probabilite_pct, date_creation, date_derniere_action
            ) VALUES (
                v_document_id, p_payload->>'prospect_nom', p_payload->>'contact',
                p_payload->>'statut', p_payload->>'commercial_id',
                v_num_val, v_prob_val,
                to_char(transaction_timestamp(), 'YYYY-MM-DD'),
                to_char(transaction_timestamp(), 'YYYY-MM-DD')
            );
        ELSE
            INSERT INTO public.interactions (
                interaction_id, client_id, date_creation, type_action,
                notes, date_rappel, statut_rappel
            ) VALUES (
                v_document_id, p_payload->>'client_id',
                to_char(transaction_timestamp(), 'YYYY-MM-DD HH24:MI'),
                p_payload->>'type_action', p_payload->>'notes',
                p_payload->>'date_rappel', 'EN_ATTENTE'
            );
        END IF;
    END IF;

    -- Un registre sans document est INVALIDE, meme au replay.
    IF p_kind = 'opportunite' THEN
        IF NOT EXISTS (SELECT 1 FROM public.pipeline
                        WHERE opportunite_id = v_document_id) THEN
            RAISE EXCEPTION 'CRM_RECEIPT_ORPHAN' USING ERRCODE = '23514';
        END IF;
    ELSE
        IF NOT EXISTS (SELECT 1 FROM public.interactions
                        WHERE interaction_id = v_document_id) THEN
            RAISE EXCEPTION 'CRM_RECEIPT_ORPHAN' USING ERRCODE = '23514';
        END IF;
    END IF;

    RETURN jsonb_build_object(
        'operation_id', p_operation_id::text,
        'document_id', v_document_id,
        'kind', p_kind,
        'replayed', NOT v_new
    );
END;
$$;

REVOKE ALL ON FUNCTION public.erp_crm_create_idempotent(uuid,text,text,jsonb)
  FROM PUBLIC, anon, authenticated;
GRANT EXECUTE ON FUNCTION public.erp_crm_create_idempotent(uuid,text,text,jsonb)
  TO service_role;
COMMIT;

-- VERIFICATION EXCLUSIVEMENT EN TEST :
-- SELECT has_function_privilege('anon',
--    'public.erp_crm_create_idempotent(uuid,text,text,jsonb)','EXECUTE') = false;
-- SELECT has_function_privilege('authenticated',
--    'public.erp_crm_create_idempotent(uuid,text,text,jsonb)','EXECUTE') = false;
-- SELECT has_function_privilege('service_role',
--    'public.erp_crm_create_idempotent(uuid,text,text,jsonb)','EXECUTE') = true;
-- TESTER : timeout apres commit, p_operation_id rejoue avec payload identique/
-- different, appels concurrents, rollback sur erreur, role revoque et
-- interaction pour client inactif. Aucun test d'ecriture sur la PROD.
