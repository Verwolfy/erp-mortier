-- ERP-050 : recette RPC NEGATIVE de la principale en phase essais.
-- 8 cas de refus métier + ACL 16 RPC ; aucune modification durable.
-- Sans GRANT, sans changement de RLS, sans qualification fiscale inventée.
-- Toutes les écritures expérimentales sont ANNULÉES par ROLLBACK.
-- Exécution autorisée seulement via le connecteur SQL de la principale,
-- jamais sur la base Supabase TEST (doit rester INACTIVE).
BEGIN;
SET LOCAL lock_timeout='3s';
SET LOCAL statement_timeout='20s';
SET LOCAL ROLE service_role;
CREATE TEMP TABLE erp050_rejets (
  scenario text PRIMARY KEY, resultat text NOT NULL, sqlstate_observe text NOT NULL
) ON COMMIT DROP;
DO $erp50$
DECLARE
  c record; result jsonb; observed text; diagnostic text;
  acl_count integer;
BEGIN
  SELECT count(*) INTO acl_count
    FROM pg_catalog.pg_proc p
    JOIN pg_catalog.pg_namespace n ON n.oid=p.pronamespace
   WHERE n.nspname='public'
     AND p.proname=ANY(ARRAY[
       'erp_create_purchase_order','erp_receive_purchase_order','erp_create_recipe',
       'erp_create_manufacturing_order','erp_start_manufacturing_order',
       'erp_close_manufacturing_order','erp_create_sales_order','erp_sale_transaction',
       'erp_finance_transaction','erp_apply_stock_movement',
       'erp_tax_preview_classified','erp_tva_sku_readiness','erp_cost_validate_period',
       'erp_cost_period_audit','erp_cost_export_validated','erp_cost_document_pool_atomic'
     ])
     AND NOT has_function_privilege('anon',p.oid,'EXECUTE')
     AND NOT has_function_privilege('authenticated',p.oid,'EXECUTE')
     AND has_function_privilege('service_role',p.oid,'EXECUTE');
  IF acl_count <> 16 THEN
    RAISE EXCEPTION 'ERP-050 : permissions RPC non conformes, %/16',acl_count
      USING ERRCODE='23514';
  END IF;
  INSERT INTO erp050_rejets VALUES ('ACL_RPC_16','REFUS_ANON_ET_AUTHENTICATED','OK');
  FOR c IN SELECT * FROM (VALUES
    ('TVA_SKU_SANS_FICHE', '23514',
     'SELECT public.erp_tax_preview_classified(jsonb_build_array(jsonb_build_object(''sku_id'',(SELECT sku_id FROM public.erp_tva_sku_readiness(DATE ''2026-11-09'') WHERE etat_technique=''SANS_FICHE'' ORDER BY sku_id LIMIT 1),''montant_ht'',''100.00'')), DATE ''2026-11-09'',false)'),
    ('FACTURE_SKU_INACTIF', '23503',
     'SELECT public.erp_sale_transaction(''DRAFT'',''SIM-ERP50-INV-RB'',jsonb_build_object(''client_id'',''SIM-ERP49-CLI-BTP'',''date_echeance'',''2026-12-01'',''remise_globale'',''0'',''paiement_especes'',false,''type_facture'',''FactureClient'',''facture_origine_id'','''',''montant_ht'',''850'',''montant_tva'',''161.50'',''montant_timbre'',''0'',''montant_ttc'',''1011.50'',''lignes'',jsonb_build_array(jsonb_build_object(''sku_id'',''SIM-ERP49-SKU-COLLE25'',''quantite'',''1'',''prix_unitaire'',''850'',''remise_ligne'',''0'',''total_ligne_ht'',''850''))))'),
    ('FACTURE_ABSENTE', '23503',
     'SELECT public.erp_sale_transaction(''VALIDATE'',''SIM-ERP50-VALID-RB'',''{"facture_id":"SIM-ERP50-NOT-FOUND"}''::jsonb)'),
    ('LIVRAISON_SKU_INACTIF', '23503',
     'SELECT public.erp_sale_transaction(''SHIP'',''SIM-ERP50-SHIP-RB'',''{"commande_vente_id":"SIM-ERP49-CV-1","transporteur":"SIM","zone":"SIM","lignes":[{"sku_id":"SIM-ERP49-SKU-COLLE25","quantite_livree":"1"}]}''::jsonb)'),
    ('FABRICATION_PRODUIT_INACTIF', '23503',
     'SELECT public.erp_create_manufacturing_order(''SIM-ERP50-OF-OP'',''SIM-ERP49-PF-COLLE'',''SIM-ERP49-REC-COLLE'',''SIM-ERP49-SKU-COLLE25'',40,''2026-11-09'',''SIMULATION-ROLLBACK'')'),
    ('STOCK_INSUFFISANT', '23514',
     'SELECT public.erp_apply_stock_movement(''SIM-ERP50-STOCK-NONE'',''PF'',''SORTIE'',''SIM-ERP49-SKU-COLLE25'',1,NULL,''SIMULATION-ROLLBACK'',NULL)'),
    ('COUT_SCF_NON_JUSTIFIE', '23514',
     'SELECT public.erp_cost_validate_period(''SIM-ERP49-COST-P1'')'),
    ('REGLEMENT_INVALIDE', '22023',
     'SELECT public.erp_finance_transaction(''PAYMENT'',''SIM-ERP50-FINANCE-RB'',''{}''::jsonb)')
  ) AS scenarios(nom, code_attendu, requete)
  LOOP
    observed := 'ACCEPTE';
    diagnostic := '';
    BEGIN
      EXECUTE c.requete INTO result;
    EXCEPTION WHEN OTHERS THEN
      GET STACKED DIAGNOSTICS observed=RETURNED_SQLSTATE, diagnostic=MESSAGE_TEXT;
    END;
    IF observed IS DISTINCT FROM c.code_attendu THEN
      RAISE EXCEPTION 'ERP-050 scenario % : SQLSTATE %, attendu %, detail %',
        c.nom,observed,c.code_attendu,left(diagnostic,110)
        USING ERRCODE='23514';
    END IF;
    INSERT INTO erp050_rejets VALUES (c.nom,'REFUS_CONFIRME',observed);
  END LOOP;
END
$erp50$;
RESET ROLE;
SELECT * FROM erp050_rejets ORDER BY scenario;
ROLLBACK;
