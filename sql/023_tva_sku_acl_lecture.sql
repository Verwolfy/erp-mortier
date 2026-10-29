-- ERP 023 : harmonisation explicite des ACL du registre TVA SKU.
-- PROD accorde par défaut des privilèges serveur plus larges qu'en TEST.
-- La qualification reste volontairement en lecture seule pour l'application.
BEGIN;
REVOKE ALL PRIVILEGES ON TABLE public.erp_sku_fiscalite FROM service_role;
GRANT SELECT ON TABLE public.erp_sku_fiscalite TO service_role;
-- Aucun droit accordé à anon/authenticated. RLS reste activée.
DO $verify$
BEGIN
    IF NOT (SELECT relrowsecurity
             FROM pg_class WHERE oid='public.erp_sku_fiscalite'::regclass)
       OR NOT has_table_privilege('service_role','public.erp_sku_fiscalite','SELECT')
       OR has_table_privilege('service_role','public.erp_sku_fiscalite','INSERT')
       OR has_table_privilege('service_role','public.erp_sku_fiscalite','UPDATE')
       OR has_table_privilege('service_role','public.erp_sku_fiscalite','DELETE')
       OR has_table_privilege('service_role','public.erp_sku_fiscalite','TRUNCATE')
       OR has_table_privilege('service_role','public.erp_sku_fiscalite','REFERENCES')
       OR has_table_privilege('service_role','public.erp_sku_fiscalite','TRIGGER')
       OR has_table_privilege('anon','public.erp_sku_fiscalite','SELECT')
       OR has_table_privilege('authenticated','public.erp_sku_fiscalite','SELECT')
    THEN
        RAISE EXCEPTION 'ACL TVA SKU non conforme, transaction annulée';
    END IF;
END
$verify$;
COMMIT;
