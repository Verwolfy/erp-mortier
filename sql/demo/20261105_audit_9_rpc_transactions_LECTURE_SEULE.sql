-- Lecture seule : contrat des 9 RPC métier et privilèges d'exécution.
-- Refuse une fonction manquante, une signature divergente, un accès public.
WITH attendu(nom,signature) AS (
  VALUES ('erp_close_manufacturing_order','p_of_id text, p_conforme text, p_remarques text, p_controleur text, p_quantite_produite numeric, p_emballage_mp_id text, p_emballage_consomme numeric'),
    ('erp_create_manufacturing_order','p_operation_id text, p_pf_id text, p_recette_id text, p_sku_id text, p_quantite_prevue numeric, p_date_planification text, p_notes text'),
    ('erp_create_purchase_order','p_operation_id text, p_order_id text, p_fournisseur_id text, p_type_achat text, p_devise text, p_taux_change numeric, p_mode_paiement text, p_delai_paiement text, p_date_voulue text, p_lines jsonb'),
    ('erp_create_recipe','p_operation_id text, p_pf_id text, p_version text, p_rendement_unite numeric, p_instructions text, p_date_effet text, p_lignes jsonb'),
    ('erp_create_sales_order','p_operation_id text, p_client_id text, p_date text, p_lignes jsonb'),
    ('erp_finance_transaction','p_action text, p_operation_id text, p_payload jsonb'),
    ('erp_receive_purchase_order','p_operation_id text, p_br_id text, p_commande_achat_id text, p_date_reception text, p_controle_conformite text, p_remarques text, p_date_peremption text, p_lines jsonb'),
    ('erp_sale_transaction','p_action text, p_operation_id text, p_payload jsonb'),
    ('erp_start_manufacturing_order','p_of_id text')
), trouve AS (
 SELECT a.nom, a.signature, count(p.oid) AS nombre,
        coalesce(bool_and(pg_get_function_identity_arguments(p.oid)=a.signature),false) AS signature_ok,
        coalesce(bool_and(has_function_privilege('service_role',p.oid,'EXECUTE')),false) AS service_ok,
        coalesce(bool_or(has_function_privilege('anon',p.oid,'EXECUTE')),false) AS acces_anon,
        coalesce(bool_or(has_function_privilege('authenticated',p.oid,'EXECUTE')),false) AS acces_auth,
        coalesce(bool_and(p.prosecdef=false),false) AS invoker_ok,
        coalesce(bool_and('search_path=pg_catalog, public'=ANY(p.proconfig)),false) AS path_ok
 FROM attendu a
 LEFT JOIN pg_proc p ON p.proname=a.nom
 AND p.pronamespace='public'::regnamespace
 GROUP BY a.nom,a.signature
)
SELECT nom, CASE WHEN nombre=1 AND signature_ok AND service_ok AND NOT acces_anon AND NOT acces_auth AND invoker_ok AND path_ok THEN 'OK' ELSE 'ECART' END AS resultat,
       nombre,signature_ok,service_ok,acces_anon,acces_auth,invoker_ok,path_ok
FROM trouve ORDER BY nom;
