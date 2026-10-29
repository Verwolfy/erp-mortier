-- ERP 025 : référentiel DES DOSSIERS d'exonération TVA client.
-- Règle métier Ventes : taux normal (paramètre daté, actuellement 19 %)
-- ou 0 % si une attestation CLIENT validée couvre le SKU et la date.
-- Aucune exonération attribuée par défaut ; aucune facture ni donnée créée.
-- Ne modifie ni la RPC de facturation ni le paramètre réduit historique.
BEGIN;

CREATE TABLE public.erp_exonerations_tva_clients (
    attestation_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    client_id text NOT NULL REFERENCES public.clients(client_id)
        ON UPDATE RESTRICT ON DELETE RESTRICT,
    reference_attestation text NOT NULL
        CHECK (length(btrim(reference_attestation)) BETWEEN 1 AND 200),
    autorite_emettrice text NOT NULL
        CHECK (length(btrim(autorite_emettrice)) BETWEEN 1 AND 200),
    justification text NOT NULL
        CHECK (length(btrim(justification)) BETWEEN 1 AND 2000),
    reference_piece_interne text NOT NULL
        CHECK (length(btrim(reference_piece_interne)) BETWEEN 1 AND 250),
    date_effet date NOT NULL,
    date_fin date NOT NULL,
    date_verification date,
    date_validation date,
    valide_par text,
    statut text NOT NULL DEFAULT 'A_VALIDER'
        CHECK (statut IN ('A_VALIDER', 'VALIDEE', 'REVOQUEE')),
    cree_le timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT erp_exo_client_dates
        CHECK (date_fin >= date_effet),
    CONSTRAINT erp_exo_client_validation
        CHECK (statut <> 'VALIDEE' OR (
            date_verification IS NOT NULL
            AND date_validation IS NOT NULL
            AND date_validation >= date_verification
            AND nullif(btrim(valide_par), '') IS NOT NULL
        )),
    CONSTRAINT erp_exo_client_reference_unique
        UNIQUE (client_id, reference_attestation)
);

CREATE TABLE public.erp_exonerations_tva_skus (
    attestation_id uuid NOT NULL
        REFERENCES public.erp_exonerations_tva_clients(attestation_id)
        ON UPDATE RESTRICT ON DELETE RESTRICT,
    sku_id text NOT NULL
        REFERENCES public.sku_conditionnement(sku_id)
        ON UPDATE RESTRICT ON DELETE RESTRICT,
    PRIMARY KEY (attestation_id, sku_id)
);

CREATE INDEX erp_exo_client_recherche_idx
    ON public.erp_exonerations_tva_clients (client_id, statut, date_effet, date_fin);
CREATE INDEX erp_exo_client_sku_recherche_idx
    ON public.erp_exonerations_tva_skus (sku_id, attestation_id);

-- Défense en profondeur : aucune politique permissive et aucun droit
-- navigateur. Seul le backend privilégié peut consulter les dossiers.
-- IMPORTANT : aucune attribution de droits d'écriture à service_role.
ALTER TABLE public.erp_exonerations_tva_clients ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.erp_exonerations_tva_skus ENABLE ROW LEVEL SECURITY;
REVOKE ALL PRIVILEGES ON TABLE public.erp_exonerations_tva_clients,
    public.erp_exonerations_tva_skus FROM PUBLIC, anon, authenticated, service_role;
GRANT SELECT ON TABLE public.erp_exonerations_tva_clients,
    public.erp_exonerations_tva_skus TO service_role;

DO $verify$
BEGIN
    IF NOT (SELECT relrowsecurity FROM pg_class
             WHERE oid = 'public.erp_exonerations_tva_clients'::regclass)
       OR NOT (SELECT relrowsecurity FROM pg_class
             WHERE oid = 'public.erp_exonerations_tva_skus'::regclass)
       OR has_table_privilege('anon', 'public.erp_exonerations_tva_clients', 'SELECT')
       OR has_table_privilege('authenticated', 'public.erp_exonerations_tva_clients', 'SELECT')
       OR has_table_privilege('anon', 'public.erp_exonerations_tva_skus', 'SELECT')
       OR has_table_privilege('authenticated', 'public.erp_exonerations_tva_skus', 'SELECT')
       OR NOT has_table_privilege('service_role', 'public.erp_exonerations_tva_clients', 'SELECT')
       OR NOT has_table_privilege('service_role', 'public.erp_exonerations_tva_skus', 'SELECT')
       OR has_table_privilege('service_role', 'public.erp_exonerations_tva_clients', 'INSERT')
       OR has_table_privilege('service_role', 'public.erp_exonerations_tva_skus', 'INSERT')
    THEN
        RAISE EXCEPTION 'ACL du registre exonérations non conforme';
    END IF;
END
$verify$;
COMMIT;
