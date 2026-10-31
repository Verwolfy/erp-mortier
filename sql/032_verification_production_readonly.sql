-- ERP 032 : contrôle de production en lecture seule.
-- Exécuter exclusivement contre Supabase PRODUCTION.
-- Ne crée ni ne modifie aucune facture, attestation ou permission.
SELECT
  (SELECT count(*) FROM pg_catalog.pg_trigger
   WHERE tgrelid = 'public.factures'::regclass
     AND tgname = 'erp_factures_garde_exonerations'
     AND tgenabled = 'O') = 1 AS garde_factures_active,
  (SELECT count(*) FROM pg_catalog.pg_trigger
   WHERE tgrelid = 'public.erp_exonerations_tva_clients'::regclass
     AND NOT tgisinternal AND tgenabled = 'O') >= 2 AS garde_attestation_active,
  has_function_privilege('anon',
    'public.erp_sale_transaction(text,text,jsonb)','EXECUTE') = false AS navigateur_anonyme_refuse,
  has_function_privilege('authenticated',
    'public.erp_sale_transaction(text,text,jsonb)','EXECUTE') = false AS navigateur_auth_refuse,
  has_function_privilege('service_role',
    'public.erp_sale_transaction(text,text,jsonb)','EXECUTE') AS serveur_autorise,
  (SELECT count(*) FROM public.erp_exonerations_tva_clients) AS dossiers_fiscaux,
  (SELECT count(*) FROM public.erp_exonerations_tva_validateurs WHERE actif) AS validateurs_fiscaux,
  (SELECT count(*) FROM public.factures) AS factures_existantes,
  (SELECT count(*) FROM public.factures WHERE statut='BROUILLON') AS brouillons_existants;
