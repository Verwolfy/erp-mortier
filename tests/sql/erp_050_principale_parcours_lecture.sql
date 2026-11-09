-- ERP-050 : matrices d'intégrité des parcours métier à partir des données SIM-ERP49.
-- Lecture seule, ne simule pas une authentification ni une navigation Streamlit.
-- Un resultat faux doit être analysé, pas ignoré pour afficher « succès ».
SELECT parcours, test_ok FROM (
SELECT 'CRM'::text AS parcours, (EXISTS(SELECT 1 FROM public.interactions i JOIN public.clients c USING(client_id) WHERE i.interaction_id='SIM-ERP49-INT-1' AND c.client_id='SIM-ERP49-CLI-BTP') AND EXISTS(SELECT 1 FROM public.pipeline WHERE opportunite_id='SIM-ERP49-OPP-1')) AS test_ok
UNION ALL
SELECT 'ACHATS'::text AS parcours, (EXISTS(SELECT 1 FROM public.commandes_achats a JOIN public.lignes_achats l USING(commande_achat_id) JOIN public.fournisseurs f USING(fournisseur_id) JOIN public.matieres_premieres m USING(mp_id) WHERE a.commande_achat_id='SIM-ERP49-CA-1')) AS test_ok
UNION ALL
SELECT 'VENTES'::text AS parcours, (EXISTS(SELECT 1 FROM public.devis d JOIN public.lignes_devis l USING(devis_id) JOIN public.sku_conditionnement s USING(sku_id) WHERE d.devis_id='SIM-ERP49-DEV-1') AND EXISTS(SELECT 1 FROM public.commandes_ventes c JOIN public.lignes_commande_ventes l USING(commande_vente_id) WHERE c.commande_vente_id='SIM-ERP49-CV-1')) AS test_ok
UNION ALL
SELECT 'PRODUCTION'::text AS parcours, (EXISTS(SELECT 1 FROM public.ordres_fabrication o JOIN public.recettes r USING(recette_id) JOIN public.produits p ON p.pf_id=o.pf_id AND p.pf_id=r.pf_id WHERE o.of_id='SIM-ERP49-OF-1' AND r.actif='NON' AND p.actif='NON')) AS test_ok
UNION ALL
SELECT 'STOCKS'::text AS parcours, (EXISTS(SELECT 1 FROM public.sku_conditionnement s JOIN public.produits p USING(pf_id) WHERE s.sku_id='SIM-ERP49-SKU-COLLE25' AND s.actif='NON' AND p.actif='NON')) AS test_ok
UNION ALL
SELECT 'PROJETS'::text AS parcours, (EXISTS(SELECT 1 FROM public.projets p JOIN public.taches t USING(projet_id) JOIN public.feuilles_de_temps h USING(tache_id) WHERE p.projet_id='SIM-ERP49-PROJ-1')) AS test_ok
UNION ALL
SELECT 'RH'::text AS parcours, (EXISTS(SELECT 1 FROM public.employes e JOIN public.demandes_conges c USING(employe_id) WHERE e.employe_id='SIM-ERP49-EMP-COM' AND e.actif='NON')) AS test_ok
UNION ALL
SELECT 'COUTS_ANALYTIQUES'::text AS parcours, (EXISTS(SELECT 1 FROM public.erp_cost_periods p JOIN public.erp_cost_pools pool USING(period_id) JOIN public.erp_cost_drivers d USING(period_id) WHERE p.period_id='SIM-ERP49-COST-P1' AND pool.statut='SIMULATION')) AS test_ok
UNION ALL
SELECT 'FINANCE_SCF_SANS_FAUX'::text AS parcours, ((SELECT count(*) FROM public.ecritures_comptables)=0 AND (SELECT count(*) FROM public.erp_sku_fiscalite WHERE statut='VALIDEE')=0) AS test_ok
UNION ALL
SELECT 'SITE_CATALOGUE'::text AS parcours, ((SELECT count(*) FROM public.site_produits)=50) AS test_ok
) AS controles ORDER BY parcours;
