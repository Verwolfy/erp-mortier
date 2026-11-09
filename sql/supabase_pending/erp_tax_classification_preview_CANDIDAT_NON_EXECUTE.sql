-- CANDIDAT NON EXÉCUTÉ, pas une migration appliquée.
-- ERP TAX-V2 : qualification des SKU et prévisualisation SQL isolée, à tester sur TEST.
-- AUCUNE exécution en production tant que la classification n'est pas homologuée,
-- que le TEST est inactif et que la transaction erp_sale_transaction n'est pas adaptée.
-- Le calcul n'écrit aucune facture, aucune ligne, aucun journal.
BEGIN;

CREATE TABLE IF NOT EXISTS public.erp_sku_tva_qualifications (
    qualification_id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    sku_id text NOT NULL REFERENCES public.sku_conditionnement(sku_id),
    code_tva text NOT NULL CHECK (code_tva IN ('TVA_TAUX_NORMAL', 'TVA_TAUX_REDUIT')),
    date_effet date NOT NULL,
    date_fin date,
    statut text NOT NULL DEFAULT 'a_confirmer'
        CHECK (statut IN ('a_confirmer', 'confirmee', 'rejetee')),
    source_classification text NOT NULL,
    date_verification date,
    valide_par text,
    date_validation date,
    cree_le timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT erp_sku_tva_qualification_dates
        CHECK (date_fin IS NULL OR date_fin >= date_effet),
    CONSTRAINT erp_sku_tva_qualification_homologation
        CHECK (statut <> 'confirmee' OR (
            nullif(btrim(source_classification), '') IS NOT NULL
            AND date_verification IS NOT NULL
            AND nullif(btrim(valide_par), '') IS NOT NULL
            AND date_validation IS NOT NULL
        ))
);
ALTER TABLE public.erp_sku_tva_qualifications ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON TABLE public.erp_sku_tva_qualifications FROM PUBLIC, anon, authenticated;
GRANT SELECT, INSERT, UPDATE ON TABLE public.erp_sku_tva_qualifications TO service_role;
REVOKE ALL ON SEQUENCE public.erp_sku_tva_qualifications_qualification_id_seq FROM PUBLIC, anon, authenticated;
GRANT USAGE ON SEQUENCE public.erp_sku_tva_qualifications_qualification_id_seq TO service_role;

CREATE OR REPLACE FUNCTION public.erp_tax_preview_classified(
    p_lines jsonb, p_date date, p_cash boolean DEFAULT false
) RETURNS jsonb
LANGUAGE plpgsql STABLE SECURITY INVOKER
SET search_path = pg_catalog, public
AS $erp_tax_preview$
DECLARE
    v_line jsonb;
    v_sku text;
    v_seen text[] := ARRAY[]::text[];
    v_amount numeric;
    v_code text;
    v_qual_source text;
    v_qual_date date;
    v_qual_count bigint;
    v_qual_invalid bigint;
    v_rate numeric;
    v_rate_source text;
    v_rate_date date;
    v_rate_count bigint;
    v_rate_invalid bigint;
    v_line_tax numeric;
    v_ht numeric := 0;
    v_tva numeric := 0;
    v_details jsonb := '[]'::jsonb;
BEGIN
    IF p_date IS NULL OR p_cash IS DISTINCT FROM false
       OR p_lines IS NULL OR jsonb_typeof(p_lines) <> 'array'
       OR jsonb_array_length(p_lines) NOT BETWEEN 1 AND 500 THEN
        RAISE EXCEPTION 'Simulation fiscale: entrée ou timbre non pris en charge'
            USING ERRCODE = '22023';
    END IF;
    FOR v_line IN SELECT value FROM jsonb_array_elements(p_lines)
    LOOP
        IF jsonb_typeof(v_line) <> 'object'
           OR jsonb_typeof(v_line->'sku_id') <> 'string'
           OR jsonb_typeof(v_line->'montant_ht') <> 'string'
           OR (v_line->>'montant_ht') !~ '^[0-9]{1,15}(\\.[0-9]{1,2})?$' THEN
            RAISE EXCEPTION 'Ligne fiscale ou montant décimal invalide'
                USING ERRCODE = '22023';
        END IF;
        v_sku := btrim(v_line->>'sku_id');
        IF v_sku = '' OR length(v_sku) > 200 OR v_sku = ANY(v_seen) THEN
            RAISE EXCEPTION 'SKU fiscal absent ou dupliqué'
                USING ERRCODE = '23514';
        END IF;
        v_seen := array_append(v_seen, v_sku);
        v_amount := (v_line->>'montant_ht')::numeric;
        IF v_amount >= 1000000000000000 THEN
            RAISE EXCEPTION 'Assiette fiscale hors limites'
                USING ERRCODE = '23514';
        END IF;

        -- Le statut de qualification doit venir d'une table serveur, jamais du JSON client.
        -- Compter TOUTES les versions applicables, y compris les versions non validées.
        SELECT count(*), max(code_tva), max(source_classification),
               max(date_verification),
               count(*) FILTER (WHERE (statut = 'confirmee'
                   AND nullif(btrim(source_classification), '') IS NOT NULL
                   AND date_verification IS NOT NULL
                   AND nullif(btrim(valide_par), '') IS NOT NULL
                   AND date_validation IS NOT NULL) IS NOT TRUE)
          INTO v_qual_count, v_code, v_qual_source, v_qual_date, v_qual_invalid
          FROM public.erp_sku_tva_qualifications
          WHERE sku_id = v_sku AND date_effet <= p_date
            AND (date_fin IS NULL OR date_fin >= p_date);
        IF v_qual_count <> 1 OR v_qual_invalid <> 0
           OR v_code NOT IN ('TVA_TAUX_NORMAL', 'TVA_TAUX_REDUIT') THEN
            RAISE EXCEPTION 'SKU sans qualification fiscale unique et confirmée'
                USING ERRCODE = '23514';
        END IF;

        -- La source de taux reste public.parametres_reglementaires.
        -- Absence, chevauchement, projet ou unité incohérente : refuser.
        SELECT count(*), max(valeur), max(source), max(date_verification),
               count(*) FILTER (WHERE (
                   statut_juridique = 'en_vigueur'
                   AND niveau_confiance = 'CONFIRMEE'
                   AND unite = 'fraction'
                   AND valeur IS NOT NULL
                   AND valeur BETWEEN 0 AND 1
                   AND nullif(btrim(source), '') IS NOT NULL
                   AND date_verification IS NOT NULL) IS NOT TRUE)
          INTO v_rate_count, v_rate, v_rate_source, v_rate_date, v_rate_invalid
          FROM public.parametres_reglementaires
          WHERE code = v_code AND date_effet <= p_date
            AND (date_fin IS NULL OR date_fin >= p_date);
        IF v_rate_count <> 1 OR v_rate_invalid <> 0 OR v_rate IS NULL THEN
            RAISE EXCEPTION 'Taux TVA absent, ambigu ou non vérifié'
                USING ERRCODE = '23514';
        END IF;
        v_line_tax := round(v_amount * v_rate, 2);
        v_ht := v_ht + v_amount;
        v_tva := v_tva + v_line_tax;
        IF v_ht + v_tva >= 1000000000000000 THEN
            RAISE EXCEPTION 'Montant total fiscal hors limites'
                USING ERRCODE = '23514';
        END IF;
        v_details := v_details || jsonb_build_array(jsonb_build_object(
            'sku_id', v_sku,
            'montant_ht', to_char(v_amount, 'FM9999999999999990.00'),
            'code_tva', v_code,
            'taux_tva', v_rate::text,
            'montant_tva', to_char(v_line_tax, 'FM9999999999999990.00'),
            'source_classification', v_qual_source,
            'date_verification_classification', v_qual_date::text,
            'source_taux', v_rate_source,
            'date_verification_taux', v_rate_date::text
        ));
    END LOOP;
    RETURN jsonb_build_object(
        'date_facture', p_date::text,
        'montant_ht', to_char(v_ht, 'FM9999999999999990.00'),
        'montant_tva', to_char(v_tva, 'FM9999999999999990.00'),
        'montant_timbre', '0.00',
        'montant_ttc', to_char(v_ht + v_tva, 'FM9999999999999990.00'),
        'lignes', v_details,
        'statut', 'CALCUL_ISOLE_NON_COMPTABILISE'
    );
END;
$erp_tax_preview$;
REVOKE ALL ON FUNCTION public.erp_tax_preview_classified(jsonb,date,boolean)
    FROM PUBLIC, anon, authenticated;
GRANT EXECUTE ON FUNCTION public.erp_tax_preview_classified(jsonb,date,boolean)
    TO service_role;
COMMIT;
