-- Exécution UNIQUEMENT sur une base PostgreSQL 17 éphémère de GitHub Actions.
-- Ce test ne contacte ni Supabase ni les clients ERP.
BEGIN;

INSERT INTO public.erp_sku_tva_qualifications(
    sku_id, code_tva, date_effet, date_fin, statut,
    source_classification, date_verification, valide_par, date_validation
) VALUES
('SKU-SIM-N','TVA_TAUX_NORMAL','2026-01-01',NULL,'confirmee',
 'QUALIFICATION-FICTIVE','2026-01-02','AUDITEUR-FICTIF','2026-01-03'),
('SKU-SIM-R','TVA_TAUX_REDUIT','2026-01-01',NULL,'a_confirmer',
 'QUALIFICATION-FICTIVE',NULL,NULL,NULL),
('SKU-SIM-INACTIF','TVA_TAUX_NORMAL','2026-01-01',NULL,'confirmee',
 'QUALIFICATION-FICTIVE','2026-01-02','AUDITEUR-FICTIF','2026-01-03'),
('SKU-SIM-UNVERIFIE','TVA_TAUX_NORMAL','2026-01-01',NULL,'a_confirmer',
 'QUALIFICATION-FICTIVE',NULL,NULL,NULL);

-- Une qualification non validée peut être homologuée, mais devient immuable.
UPDATE public.erp_sku_tva_qualifications
SET statut = 'confirmee', date_verification='2026-01-02',
    valide_par='AUDITEUR-FICTIF', date_validation='2026-01-03'
WHERE sku_id='SKU-SIM-R';

CREATE FUNCTION pg_temp.expect_reject(case_name text, statement text)
RETURNS void LANGUAGE plpgsql AS $assert$
DECLARE
    was_rejected boolean := false;
BEGIN
    BEGIN
        EXECUTE statement;
    EXCEPTION WHEN OTHERS THEN
        was_rejected := true;
    END;
    IF NOT was_rejected THEN
        RAISE EXCEPTION 'Protection SQL absente: %', case_name;
    END IF;
END;
$assert$;

DO $verify$
DECLARE
    outcome jsonb;
BEGIN
    outcome := public.erp_tax_preview_classified(
        '[{"sku_id":"SKU-SIM-N","montant_ht":"100.00"},{"sku_id":"SKU-SIM-R","montant_ht":"50.00"}]'::jsonb,
        '2026-11-09'::date, false
    );
    IF outcome->>'montant_ht' IS DISTINCT FROM '150.00'
        OR outcome->>'montant_tva' IS DISTINCT FROM '23.50'
        OR outcome->>'montant_ttc' IS DISTINCT FROM '173.50'
        OR outcome->>'montant_timbre' IS DISTINCT FROM '0.00'
        OR outcome->>'statut' IS DISTINCT FROM 'CALCUL_ISOLE_NON_COMPTABILISE'
        OR jsonb_array_length(outcome->'lignes') <> 2 THEN
        RAISE EXCEPTION 'Parité de calcul TVA fictive invalide : %', outcome;
    END IF;
    -- Le JSON client essaie d'imposer un taux réduit : le serveur doit l'ignorer.
    outcome := public.erp_tax_preview_classified(
        '[{"sku_id":"SKU-SIM-N","montant_ht":"100.00","code_tva":"TVA_TAUX_REDUIT","classification_verifiee":true}]'::jsonb,
        '2026-11-09'::date, false
    );
    IF outcome->>'montant_tva' IS DISTINCT FROM '20.00'
       OR outcome->'lignes'->0->>'code_tva' IS DISTINCT FROM 'TVA_TAUX_NORMAL' THEN
       RAISE EXCEPTION 'Auto-classification client acceptée : %', outcome;
    END IF;
    IF has_table_privilege('anon', 'public.erp_sku_tva_qualifications', 'SELECT')
       OR has_table_privilege('authenticated', 'public.erp_sku_tva_qualifications', 'SELECT')
       OR has_function_privilege('anon', 'public.erp_tax_preview_classified(jsonb,date,boolean)', 'EXECUTE')
       OR has_function_privilege('authenticated', 'public.erp_tax_preview_classified(jsonb,date,boolean)', 'EXECUTE') THEN
       RAISE EXCEPTION 'Accès public non autorisé au référentiel TVA';
    END IF;
END;
$verify$;

-- Appel vérifié sous le rôle interne service_role, sans élévation SECURITY DEFINER.
SET ROLE service_role;
DO $role$
DECLARE v jsonb;
BEGIN
    v := public.erp_tax_preview_classified(
       '[{"sku_id":"SKU-SIM-N","montant_ht":"10.00"}]'::jsonb,
       '2026-11-09'::date, false
    );
    IF v->>'montant_tva' IS DISTINCT FROM '2.00' THEN
       RAISE EXCEPTION 'Accès interne ou calcul invalide';
    END IF;
END;
$role$;
RESET ROLE;

SELECT pg_temp.expect_reject('timbre espèces', $case$
    SELECT public.erp_tax_preview_classified(
      '[{"sku_id":"SKU-SIM-N","montant_ht":"100.00"}]'::jsonb,
      '2026-11-09', true)
$case$);

SELECT pg_temp.expect_reject('date hors registre', $case$
    SELECT public.erp_tax_preview_classified(
      '[{"sku_id":"SKU-SIM-N","montant_ht":"100.00"}]'::jsonb,
      '2025-11-09', false)
$case$);

SELECT pg_temp.expect_reject('SKU inactif', $case$
    SELECT public.erp_tax_preview_classified(
      '[{"sku_id":"SKU-SIM-INACTIF","montant_ht":"100.00"}]'::jsonb,
      '2026-11-09', false)
$case$);

SELECT pg_temp.expect_reject('qualification non confirmée', $case$
    SELECT public.erp_tax_preview_classified(
      '[{"sku_id":"SKU-SIM-UNVERIFIE","montant_ht":"100.00"}]'::jsonb,
      '2026-11-09', false)
$case$);

SELECT pg_temp.expect_reject('montant sous forme nombre JSON', $case$
    SELECT public.erp_tax_preview_classified(
      '[{"sku_id":"SKU-SIM-N","montant_ht":100.00}]'::jsonb,
      '2026-11-09', false)
$case$);

SELECT pg_temp.expect_reject('montant non monétaire', $case$
    SELECT public.erp_tax_preview_classified(
      '[{"sku_id":"SKU-SIM-N","montant_ht":"100.001"}]'::jsonb,
      '2026-11-09', false)
$case$);

SELECT pg_temp.expect_reject('SKU dupliqué', $case$
    SELECT public.erp_tax_preview_classified(
      '[{"sku_id":"SKU-SIM-N","montant_ht":"1.00"},{"sku_id":"SKU-SIM-N","montant_ht":"2.00"}]'::jsonb,
      '2026-11-09', false)
$case$);

SELECT pg_temp.expect_reject('qualification confirmée immuable', $case$
    UPDATE public.erp_sku_tva_qualifications
    SET code_tva = 'TVA_TAUX_REDUIT' WHERE sku_id='SKU-SIM-N'
$case$);

SELECT pg_temp.expect_reject('historique non supprimable', $case$
    DELETE FROM public.erp_sku_tva_qualifications WHERE sku_id='SKU-SIM-N'
$case$);

-- Une version provisoire applicable rend la qualification contradictoire.
INSERT INTO public.erp_sku_tva_qualifications(
    sku_id,code_tva,date_effet,statut,source_classification
) VALUES ('SKU-SIM-N','TVA_TAUX_NORMAL','2026-09-01',
          'a_confirmer','QUALIFICATION-EN-ATTENTE');
SELECT pg_temp.expect_reject('qualification chevauchante', $case$
    SELECT public.erp_tax_preview_classified(
      '[{"sku_id":"SKU-SIM-N","montant_ht":"100.00"}]'::jsonb,
      '2026-11-09', false)
$case$);

-- Un taux réglementaire concurrent doit également bloquer.
INSERT INTO public.parametres_reglementaires(
    code, valeur, unite, statut_juridique, niveau_confiance,
    date_effet, source, date_verification
) VALUES ('TVA_TAUX_REDUIT',0.08,'fraction','a_confirmer',
          'RECOUPEE','2026-09-01','FICTIF-NON-VALIDE','2026-09-02');
SELECT pg_temp.expect_reject('taux non confirmé chevauchant', $case$
    SELECT public.erp_tax_preview_classified(
      '[{"sku_id":"SKU-SIM-R","montant_ht":"100.00"}]'::jsonb,
      '2026-11-09', false)
$case$);

ROLLBACK;
