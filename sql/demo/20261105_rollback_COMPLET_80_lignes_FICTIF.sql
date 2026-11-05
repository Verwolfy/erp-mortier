-- RETOUR A L'ETAT AVANT LA DEMO ERP DU 2026-11-05 : 80 LIGNES FICTIVES.
-- N'affecte pas les autres lignes, ne restaure pas les mutations tierces.
-- Si une nouvelle dépendance FK existe, toute la transaction doit échouer.
-- Aucun CASCADE. Ne pas exécuter pendant des tests ERP encore actifs.
BEGIN;
-- Lot complémentaire (2 mouvements d'ouverture)
DELETE FROM public.mouvements_pf WHERE mouvement_pf_id='DEMO26_MVP2' AND reference='DEMO26_STOCK_INITIAL';
DELETE FROM public.mouvements WHERE mouvement_id='DEMO26_MV2' AND reference='DEMO26_STOCK_INITIAL';
-- Lot initial (78 lignes / 53 tables)
DELETE FROM public.paie_lignes_v2 WHERE ligne_id IN (-260001);
DELETE FROM public.scf_lignes WHERE ligne_id IN (-260002,-260003);
DELETE FROM public.scf_pieces WHERE piece_id IN ('90000000-0026-4026-8026-000000000002');
DELETE FROM public.scf_plan_comptes WHERE numero_compte IN ('41199926','70199926');
DELETE FROM public.scf_journaux WHERE code_journal IN ('DEMO26_JRN');
DELETE FROM public.scf_exercices WHERE exercice_id IN ('DEMO26_SCF2026');
DELETE FROM public.paie_bulletins_v2 WHERE bulletin_id IN ('90000000-0026-4026-8026-000000000001');
DELETE FROM public.paie_periodes_v2 WHERE periode_id IN ('DEMO26_PER11');
DELETE FROM public.erp_sku_fiscalite WHERE sku_id IN ('DEMO26_SKU1','DEMO26_SKU2') AND date_effet='2026-11-01';
DELETE FROM public.mouvements_pf WHERE mouvement_pf_id IN ('DEMO26_MVP1');
DELETE FROM public.mouvements WHERE mouvement_id IN ('DEMO26_MV1');
DELETE FROM public.reponses_appels_offres WHERE reponse_ao_id IN ('DEMO26_RAO1');
DELETE FROM public.appels_offres WHERE ao_id IN ('DEMO26_AO1');
DELETE FROM public.fiches_de_paie WHERE fiche_paie_id IN ('DEMO26_FP1');
DELETE FROM public.feuilles_de_temps WHERE feuille_temps_id IN ('DEMO26_FT1');
DELETE FROM public.demandes_conges WHERE demande_conge_id IN ('DEMO26_CONGE1');
DELETE FROM public.taches WHERE tache_id IN ('DEMO26_TASK1');
DELETE FROM public.projets WHERE projet_id IN ('DEMO26_PRJ1');
DELETE FROM public.lettrage WHERE lettrage_id IN ('DEMO26_LET1');
DELETE FROM public.reglements WHERE reglement_id IN ('DEMO26_RG1','DEMO26_RG2');
DELETE FROM public.controle_qualite WHERE qc_id IN ('DEMO26_QC1');
DELETE FROM public.consommations_of WHERE consommation_id IN ('DEMO26_CONS1');
DELETE FROM public.ordres_fabrication WHERE of_id IN ('DEMO26_OF1','DEMO26_OF2');
DELETE FROM public.lignes_factures_fournisseurs WHERE ligne_ff_id IN ('DEMO26_LFF1');
DELETE FROM public.factures_fournisseurs WHERE facture_fournisseur_id IN ('DEMO26_FF1');
DELETE FROM public.lignes_bons_reception WHERE ligne_br_id IN ('DEMO26_LBR1');
DELETE FROM public.bons_reception WHERE bon_reception_id IN ('DEMO26_BR1');
DELETE FROM public.lignes_achats WHERE ligne_achat_id IN ('DEMO26_LCA1');
DELETE FROM public.commandes_achats WHERE commande_achat_id IN ('DEMO26_CA1','DEMO26_CA2');
DELETE FROM public.lignes_facture WHERE ligne_facture_id IN ('DEMO26_LF1','DEMO26_LF2');
DELETE FROM public.factures WHERE facture_id IN ('DEMO26_FAC1','DEMO26_FAC2');
DELETE FROM public.lignes_bons_livraison WHERE ligne_bl_id IN ('DEMO26_LBL1');
DELETE FROM public.bons_livraison WHERE bl_id IN ('DEMO26_BL1');
DELETE FROM public.lignes_commande_ventes WHERE ligne_commande_vente_id IN ('DEMO26_LCV1','DEMO26_LCV2');
DELETE FROM public.commandes_ventes WHERE commande_vente_id IN ('DEMO26_CV1','DEMO26_CV2');
DELETE FROM public.lignes_devis WHERE ligne_devis_id IN ('DEMO26_LD1');
DELETE FROM public.devis WHERE devis_id IN ('DEMO26_DEV1');
DELETE FROM public.contrats WHERE contrat_id IN ('DEMO26_CTR1');
DELETE FROM public.grilles_tarifaires WHERE grille_id IN ('DEMO26_GR1');
DELETE FROM public.interactions WHERE interaction_id IN ('DEMO26_INT1','DEMO26_INT2');
DELETE FROM public.pipeline WHERE opportunite_id IN ('DEMO26_OP1','DEMO26_OP2','DEMO26_OP3');
DELETE FROM public.comptes WHERE compte_id IN ('DEMO26_BANK','DEMO26_CASH');
DELETE FROM public.lots WHERE lot_id IN ('DEMO26_LOT1','DEMO26_LOT2');
DELETE FROM public.stock_actuel_pf WHERE sku_id IN ('DEMO26_SKU1','DEMO26_SKU2');
DELETE FROM public.stock_actuel WHERE mp_id IN ('DEMO26_MP1','DEMO26_MP2');
DELETE FROM public.sku_conditionnement WHERE sku_id IN ('DEMO26_SKU1','DEMO26_SKU2');
DELETE FROM public.lignes_recette WHERE ligne_recette_id IN ('DEMO26_LR1','DEMO26_LR2');
DELETE FROM public.recettes WHERE recette_id IN ('DEMO26_REC1','DEMO26_REC2');
DELETE FROM public.produits WHERE pf_id IN ('DEMO26_PF1','DEMO26_PF2');
DELETE FROM public.matieres_premieres WHERE mp_id IN ('DEMO26_MP1','DEMO26_MP2');
DELETE FROM public.employes WHERE employe_id IN ('DEMO26_EMP1','DEMO26_EMP2');
DELETE FROM public.fournisseurs WHERE fournisseur_id IN ('DEMO26_FOU1','DEMO26_FOU2');
DELETE FROM public.clients WHERE client_id IN ('DEMO26_CLI1','DEMO26_CLI2');
COMMIT;
