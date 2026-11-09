-- ERP-049 : contrôles de cohérence du jeu DEMO sur Supabase principal (lecture seule).
-- Doit renvoyer uniquement true. Ce test ne prouve pas la conformité fiscale.
SELECT
    (SELECT count(*)=2 FROM public.clients WHERE client_id LIKE 'SIM-ERP49-%') AS clients_ok,
    (SELECT count(*)=2 FROM public.fournisseurs WHERE fournisseur_id LIKE 'SIM-ERP49-%') AS fournisseurs_ok,
    (SELECT count(*)=3 FROM public.matieres_premieres WHERE mp_id LIKE 'SIM-ERP49-%') AS mp_ok,
    (SELECT count(*)=2 FROM public.produits WHERE pf_id LIKE 'SIM-ERP49-%' AND actif='NON') AS produits_inactifs_ok,
    (SELECT count(*)=2 FROM public.sku_conditionnement WHERE sku_id LIKE 'SIM-ERP49-%' AND actif='NON') AS sku_inactifs_ok,
    (SELECT count(*)=2 FROM public.recettes WHERE recette_id LIKE 'SIM-ERP49-%' AND actif='NON') AS recettes_inactives_ok,
    (SELECT count(*)=6 FROM public.lignes_recette WHERE ligne_recette_id LIKE 'SIM-ERP49-%') AS lignes_recettes_ok,
    (SELECT count(*)=1 FROM public.commandes_ventes v
       JOIN public.lignes_commande_ventes l USING (commande_vente_id)
      WHERE v.commande_vente_id='SIM-ERP49-CV-1' AND v.client_id='SIM-ERP49-CLI-BTP'
        AND l.sku_id='SIM-ERP49-SKU-COLLE25' AND l.quantite=40) AS commande_vente_liee_ok,
    (SELECT count(*)=1 FROM public.commandes_achats a
       JOIN public.lignes_achats l USING (commande_achat_id)
      WHERE a.commande_achat_id='SIM-ERP49-CA-1' AND a.fournisseur_id='SIM-ERP49-FOUR-LIANTS'
        AND l.mp_id='SIM-ERP49-MP-CIMENT') AS commande_achat_liee_ok,
    (SELECT count(*)=1 FROM public.erp_cost_pools
      WHERE pool_id='SIM-ERP49-COST-POOL1' AND statut='SIMULATION') AS cout_sans_preuve_simulation_ok,
    (SELECT count(*)=1 FROM public.erp_cost_drivers
      WHERE period_id='SIM-ERP49-COST-P1' AND of_id='SIM-ERP49-OF-1' AND valeur=8) AS inducteur_ok,
    (SELECT count(*)=0 FROM public.factures WHERE facture_id LIKE 'SIM-ERP49-%') AS pas_de_facture_factice_ok,
    (SELECT count(*)=0 FROM public.reglements WHERE reglement_id LIKE 'SIM-ERP49-%') AS pas_de_reglement_factice_ok,
    (SELECT count(*)=0 FROM public.scf_pieces WHERE piece_id LIKE 'SIM-ERP49-%') AS pas_de_piece_scf_factice_ok,
    (SELECT count(*)=0 FROM public.erp_sku_fiscalite
      WHERE sku_id LIKE 'SIM-ERP49-%') AS pas_de_qualification_fiscale_inventee_ok;
