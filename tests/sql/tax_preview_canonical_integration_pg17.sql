-- Après ERP-044 puis ERP-045 : tests uniquement sur PostgreSQL 17 jetable.
BEGIN;
CREATE FUNCTION pg_temp.expect_reject(label text, statement text)
RETURNS void LANGUAGE plpgsql AS $assert$
DECLARE refused boolean := false;
BEGIN
  BEGIN
    EXECUTE statement;
  EXCEPTION WHEN OTHERS THEN
    refused := true;
  END;
  IF NOT refused THEN
    RAISE EXCEPTION 'Refus attendu non appliqué: %', label;
  END IF;
END;
$assert$;

DO $verify$
DECLARE answer jsonb;
BEGIN
  answer := public.erp_tax_preview_classified(
    '[{"sku_id":"SKU-SIM-N","montant_ht":"100.00"},{"sku_id":"SKU-SIM-R","montant_ht":"50.00"}]'::jsonb,
    '2026-11-09', false);
  IF answer->>'montant_ht' IS DISTINCT FROM '150.00'
     OR answer->>'montant_tva' IS DISTINCT FROM '23.50'
     OR answer->>'montant_ttc' IS DISTINCT FROM '173.50'
     OR answer->'lignes'->0->>'code_tva' IS DISTINCT FROM 'TVA_TAUX_NORMAL'
     OR answer->'lignes'->1->>'code_tva' IS DISTINCT FROM 'TVA_TAUX_REDUIT'
     OR answer->'lignes'->0->>'source_classification' IS DISTINCT FROM 'PREUVE-FICTIVE' THEN
      RAISE EXCEPTION 'TAX V2 lecture canonique incorrecte: %',answer;
  END IF;
  IF has_table_privilege('service_role','public.erp_sku_tva_qualifications','INSERT')
     OR NOT has_table_privilege('service_role','public.erp_sku_fiscalite','SELECT')
     OR has_function_privilege('anon','public.erp_tax_preview_classified(jsonb,date,boolean)','EXECUTE')
     OR has_function_privilege('authenticated','public.erp_tax_preview_classified(jsonb,date,boolean)','EXECUTE') THEN
    RAISE EXCEPTION 'ERP-045 : privilèges incohérents';
  END IF;
END;
$verify$;

SET LOCAL ROLE service_role;
DO $role$
DECLARE answer jsonb;
BEGIN
 answer := public.erp_tax_preview_classified(
   '[{"sku_id":"SKU-SIM-N","montant_ht":"10.00"}]'::jsonb,
   '2026-11-09',false);
 IF answer->>'montant_tva' IS DISTINCT FROM '2.00' THEN
     RAISE EXCEPTION 'ERP-045 : mauvais calcul sous service_role';
 END IF;
END;
$role$;
RESET ROLE;

SELECT pg_temp.expect_reject('classe en attente', $sql$
 SELECT public.erp_tax_preview_classified(
 '[{"sku_id":"SKU-SIM-UNVERIFIE","montant_ht":"1.00"}]'::jsonb,'2026-11-09',false)
$sql$);
SELECT pg_temp.expect_reject('exonération non couverte', $sql$
 SELECT public.erp_tax_preview_classified(
 '[{"sku_id":"SKU-SIM-EXO","montant_ht":"1.00"}]'::jsonb,'2026-11-09',false)
$sql$);
SELECT pg_temp.expect_reject('SKU inactif', $sql$
 SELECT public.erp_tax_preview_classified(
 '[{"sku_id":"SKU-SIM-INACTIF","montant_ht":"1.00"}]'::jsonb,'2026-11-09',false)
$sql$);
SELECT pg_temp.expect_reject('timbre espèces', $sql$
 SELECT public.erp_tax_preview_classified(
 '[{"sku_id":"SKU-SIM-N","montant_ht":"1.00"}]'::jsonb,'2026-11-09',true)
$sql$);

-- Chevauchement d'une qualification non VALIDEE : refus malgré une valeur validée.
INSERT INTO public.erp_sku_fiscalite(
sku_id,date_effet,categorie_tva,code_parametre,statut
) VALUES('SKU-SIM-N','2026-08-01',NULL,NULL,'A_VALIDER');
SELECT pg_temp.expect_reject('ancien référentiel chevauchant non validé', $sql$
 SELECT public.erp_tax_preview_classified(
 '[{"sku_id":"SKU-SIM-N","montant_ht":"100.00"}]'::jsonb,'2026-11-09',false)
$sql$);

-- Si une entrée pilote contradictoire apparaissait, la RPC doit l'ignorer.
INSERT INTO public.erp_sku_tva_qualifications(
sku_id,code_tva,date_effet,statut,source_classification,
date_verification,valide_par,date_validation)
VALUES('SKU-SIM-R','TVA_TAUX_NORMAL','2026-01-01','confirmee',
       'SIMULATION-OBSOLÈTE','2026-01-01','TEST','2026-01-01');
DO $ignore$
DECLARE answer jsonb;
BEGIN
 answer := public.erp_tax_preview_classified(
   '[{"sku_id":"SKU-SIM-R","montant_ht":"100.00","code_tva":"TVA_TAUX_NORMAL"}]'::jsonb,
   '2026-11-09',false);
 IF answer->>'montant_tva' IS DISTINCT FROM '7.00'
    OR answer->'lignes'->0->>'code_tva' IS DISTINCT FROM 'TVA_TAUX_REDUIT' THEN
      RAISE EXCEPTION 'ERP-045 : source obsolète a influencé le calcul';
 END IF;
END;
$ignore$;

ROLLBACK;
