-- Contrôle strict et sans écriture du jeu complet de 80 lignes, dérivé
-- de 55 prédicats exacts du rollback combiné versionné.
-- Toute divergence bloque le contrôle ; aucun DELETE exécuté.
WITH controle AS (
SELECT 1 AS ligne, 'mouvements_pf'::text AS table_nom, 1 AS attendu, (SELECT count(*) FROM public.mouvements_pf WHERE mouvement_pf_id='DEMO26_MVP2' AND reference='DEMO26_STOCK_INITIAL') AS observe
UNION ALL
SELECT 2 AS ligne, 'mouvements'::text AS table_nom, 1 AS attendu, (SELECT count(*) FROM public.mouvements WHERE mouvement_id='DEMO26_MV2' AND reference='DEMO26_STOCK_INITIAL') AS observe
UNION ALL
SELECT 3 AS ligne, 'paie_lignes_v2'::text AS table_nom, 1 AS attendu, (SELECT count(*) FROM public.paie_lignes_v2 WHERE ligne_id IN (-260001)) AS observe
UNION ALL
SELECT 4 AS ligne, 'scf_lignes'::text AS table_nom, 2 AS attendu, (SELECT count(*) FROM public.scf_lignes WHERE ligne_id IN (-260002,-260003)) AS observe
UNION ALL
SELECT 5 AS ligne, 'scf_pieces'::text AS table_nom, 1 AS attendu, (SELECT count(*) FROM public.scf_pieces WHERE piece_id IN ('90000000-0026-4026-8026-000000000002')) AS observe
UNION ALL
SELECT 6 AS ligne, 'scf_plan_comptes'::text AS table_nom, 2 AS attendu, (SELECT count(*) FROM public.scf_plan_comptes WHERE numero_compte IN ('41199926','70199926')) AS observe
UNION ALL
SELECT 7 AS ligne, 'scf_journaux'::text AS table_nom, 1 AS attendu, (SELECT count(*) FROM public.scf_journaux WHERE code_journal IN ('DEMO26_JRN')) AS observe
UNION ALL
SELECT 8 AS ligne, 'scf_exercices'::text AS table_nom, 1 AS attendu, (SELECT count(*) FROM public.scf_exercices WHERE exercice_id IN ('DEMO26_SCF2026')) AS observe
UNION ALL
SELECT 9 AS ligne, 'paie_bulletins_v2'::text AS table_nom, 1 AS attendu, (SELECT count(*) FROM public.paie_bulletins_v2 WHERE bulletin_id IN ('90000000-0026-4026-8026-000000000001')) AS observe
UNION ALL
SELECT 10 AS ligne, 'paie_periodes_v2'::text AS table_nom, 1 AS attendu, (SELECT count(*) FROM public.paie_periodes_v2 WHERE periode_id IN ('DEMO26_PER11')) AS observe
UNION ALL
SELECT 11 AS ligne, 'erp_sku_fiscalite'::text AS table_nom, 2 AS attendu, (SELECT count(*) FROM public.erp_sku_fiscalite WHERE sku_id IN ('DEMO26_SKU1','DEMO26_SKU2') AND date_effet='2026-11-01') AS observe
UNION ALL
SELECT 12 AS ligne, 'mouvements_pf'::text AS table_nom, 1 AS attendu, (SELECT count(*) FROM public.mouvements_pf WHERE mouvement_pf_id IN ('DEMO26_MVP1')) AS observe
UNION ALL
SELECT 13 AS ligne, 'mouvements'::text AS table_nom, 1 AS attendu, (SELECT count(*) FROM public.mouvements WHERE mouvement_id IN ('DEMO26_MV1')) AS observe
UNION ALL
SELECT 14 AS ligne, 'reponses_appels_offres'::text AS table_nom, 1 AS attendu, (SELECT count(*) FROM public.reponses_appels_offres WHERE reponse_ao_id IN ('DEMO26_RAO1')) AS observe
UNION ALL
SELECT 15 AS ligne, 'appels_offres'::text AS table_nom, 1 AS attendu, (SELECT count(*) FROM public.appels_offres WHERE ao_id IN ('DEMO26_AO1')) AS observe
UNION ALL
SELECT 16 AS ligne, 'fiches_de_paie'::text AS table_nom, 1 AS attendu, (SELECT count(*) FROM public.fiches_de_paie WHERE fiche_paie_id IN ('DEMO26_FP1')) AS observe
UNION ALL
SELECT 17 AS ligne, 'feuilles_de_temps'::text AS table_nom, 1 AS attendu, (SELECT count(*) FROM public.feuilles_de_temps WHERE feuille_temps_id IN ('DEMO26_FT1')) AS observe
UNION ALL
SELECT 18 AS ligne, 'demandes_conges'::text AS table_nom, 1 AS attendu, (SELECT count(*) FROM public.demandes_conges WHERE demande_conge_id IN ('DEMO26_CONGE1')) AS observe
UNION ALL
SELECT 19 AS ligne, 'taches'::text AS table_nom, 1 AS attendu, (SELECT count(*) FROM public.taches WHERE tache_id IN ('DEMO26_TASK1')) AS observe
UNION ALL
SELECT 20 AS ligne, 'projets'::text AS table_nom, 1 AS attendu, (SELECT count(*) FROM public.projets WHERE projet_id IN ('DEMO26_PRJ1')) AS observe
UNION ALL
SELECT 21 AS ligne, 'lettrage'::text AS table_nom, 1 AS attendu, (SELECT count(*) FROM public.lettrage WHERE lettrage_id IN ('DEMO26_LET1')) AS observe
UNION ALL
SELECT 22 AS ligne, 'reglements'::text AS table_nom, 2 AS attendu, (SELECT count(*) FROM public.reglements WHERE reglement_id IN ('DEMO26_RG1','DEMO26_RG2')) AS observe
UNION ALL
SELECT 23 AS ligne, 'controle_qualite'::text AS table_nom, 1 AS attendu, (SELECT count(*) FROM public.controle_qualite WHERE qc_id IN ('DEMO26_QC1')) AS observe
UNION ALL
SELECT 24 AS ligne, 'consommations_of'::text AS table_nom, 1 AS attendu, (SELECT count(*) FROM public.consommations_of WHERE consommation_id IN ('DEMO26_CONS1')) AS observe
UNION ALL
SELECT 25 AS ligne, 'ordres_fabrication'::text AS table_nom, 2 AS attendu, (SELECT count(*) FROM public.ordres_fabrication WHERE of_id IN ('DEMO26_OF1','DEMO26_OF2')) AS observe
UNION ALL
SELECT 26 AS ligne, 'lignes_factures_fournisseurs'::text AS table_nom, 1 AS attendu, (SELECT count(*) FROM public.lignes_factures_fournisseurs WHERE ligne_ff_id IN ('DEMO26_LFF1')) AS observe
UNION ALL
SELECT 27 AS ligne, 'factures_fournisseurs'::text AS table_nom, 1 AS attendu, (SELECT count(*) FROM public.factures_fournisseurs WHERE facture_fournisseur_id IN ('DEMO26_FF1')) AS observe
UNION ALL
SELECT 28 AS ligne, 'lignes_bons_reception'::text AS table_nom, 1 AS attendu, (SELECT count(*) FROM public.lignes_bons_reception WHERE ligne_br_id IN ('DEMO26_LBR1')) AS observe
UNION ALL
SELECT 29 AS ligne, 'bons_reception'::text AS table_nom, 1 AS attendu, (SELECT count(*) FROM public.bons_reception WHERE bon_reception_id IN ('DEMO26_BR1')) AS observe
UNION ALL
SELECT 30 AS ligne, 'lignes_achats'::text AS table_nom, 1 AS attendu, (SELECT count(*) FROM public.lignes_achats WHERE ligne_achat_id IN ('DEMO26_LCA1')) AS observe
UNION ALL
SELECT 31 AS ligne, 'commandes_achats'::text AS table_nom, 2 AS attendu, (SELECT count(*) FROM public.commandes_achats WHERE commande_achat_id IN ('DEMO26_CA1','DEMO26_CA2')) AS observe
UNION ALL
SELECT 32 AS ligne, 'lignes_facture'::text AS table_nom, 2 AS attendu, (SELECT count(*) FROM public.lignes_facture WHERE ligne_facture_id IN ('DEMO26_LF1','DEMO26_LF2')) AS observe
UNION ALL
SELECT 33 AS ligne, 'factures'::text AS table_nom, 2 AS attendu, (SELECT count(*) FROM public.factures WHERE facture_id IN ('DEMO26_FAC1','DEMO26_FAC2')) AS observe
UNION ALL
SELECT 34 AS ligne, 'lignes_bons_livraison'::text AS table_nom, 1 AS attendu, (SELECT count(*) FROM public.lignes_bons_livraison WHERE ligne_bl_id IN ('DEMO26_LBL1')) AS observe
UNION ALL
SELECT 35 AS ligne, 'bons_livraison'::text AS table_nom, 1 AS attendu, (SELECT count(*) FROM public.bons_livraison WHERE bl_id IN ('DEMO26_BL1')) AS observe
UNION ALL
SELECT 36 AS ligne, 'lignes_commande_ventes'::text AS table_nom, 2 AS attendu, (SELECT count(*) FROM public.lignes_commande_ventes WHERE ligne_commande_vente_id IN ('DEMO26_LCV1','DEMO26_LCV2')) AS observe
UNION ALL
SELECT 37 AS ligne, 'commandes_ventes'::text AS table_nom, 2 AS attendu, (SELECT count(*) FROM public.commandes_ventes WHERE commande_vente_id IN ('DEMO26_CV1','DEMO26_CV2')) AS observe
UNION ALL
SELECT 38 AS ligne, 'lignes_devis'::text AS table_nom, 1 AS attendu, (SELECT count(*) FROM public.lignes_devis WHERE ligne_devis_id IN ('DEMO26_LD1')) AS observe
UNION ALL
SELECT 39 AS ligne, 'devis'::text AS table_nom, 1 AS attendu, (SELECT count(*) FROM public.devis WHERE devis_id IN ('DEMO26_DEV1')) AS observe
UNION ALL
SELECT 40 AS ligne, 'contrats'::text AS table_nom, 1 AS attendu, (SELECT count(*) FROM public.contrats WHERE contrat_id IN ('DEMO26_CTR1')) AS observe
UNION ALL
SELECT 41 AS ligne, 'grilles_tarifaires'::text AS table_nom, 1 AS attendu, (SELECT count(*) FROM public.grilles_tarifaires WHERE grille_id IN ('DEMO26_GR1')) AS observe
UNION ALL
SELECT 42 AS ligne, 'interactions'::text AS table_nom, 2 AS attendu, (SELECT count(*) FROM public.interactions WHERE interaction_id IN ('DEMO26_INT1','DEMO26_INT2')) AS observe
UNION ALL
SELECT 43 AS ligne, 'pipeline'::text AS table_nom, 3 AS attendu, (SELECT count(*) FROM public.pipeline WHERE opportunite_id IN ('DEMO26_OP1','DEMO26_OP2','DEMO26_OP3')) AS observe
UNION ALL
SELECT 44 AS ligne, 'comptes'::text AS table_nom, 2 AS attendu, (SELECT count(*) FROM public.comptes WHERE compte_id IN ('DEMO26_BANK','DEMO26_CASH')) AS observe
UNION ALL
SELECT 45 AS ligne, 'lots'::text AS table_nom, 2 AS attendu, (SELECT count(*) FROM public.lots WHERE lot_id IN ('DEMO26_LOT1','DEMO26_LOT2')) AS observe
UNION ALL
SELECT 46 AS ligne, 'stock_actuel_pf'::text AS table_nom, 2 AS attendu, (SELECT count(*) FROM public.stock_actuel_pf WHERE sku_id IN ('DEMO26_SKU1','DEMO26_SKU2')) AS observe
UNION ALL
SELECT 47 AS ligne, 'stock_actuel'::text AS table_nom, 2 AS attendu, (SELECT count(*) FROM public.stock_actuel WHERE mp_id IN ('DEMO26_MP1','DEMO26_MP2')) AS observe
UNION ALL
SELECT 48 AS ligne, 'sku_conditionnement'::text AS table_nom, 2 AS attendu, (SELECT count(*) FROM public.sku_conditionnement WHERE sku_id IN ('DEMO26_SKU1','DEMO26_SKU2')) AS observe
UNION ALL
SELECT 49 AS ligne, 'lignes_recette'::text AS table_nom, 2 AS attendu, (SELECT count(*) FROM public.lignes_recette WHERE ligne_recette_id IN ('DEMO26_LR1','DEMO26_LR2')) AS observe
UNION ALL
SELECT 50 AS ligne, 'recettes'::text AS table_nom, 2 AS attendu, (SELECT count(*) FROM public.recettes WHERE recette_id IN ('DEMO26_REC1','DEMO26_REC2')) AS observe
UNION ALL
SELECT 51 AS ligne, 'produits'::text AS table_nom, 2 AS attendu, (SELECT count(*) FROM public.produits WHERE pf_id IN ('DEMO26_PF1','DEMO26_PF2')) AS observe
UNION ALL
SELECT 52 AS ligne, 'matieres_premieres'::text AS table_nom, 2 AS attendu, (SELECT count(*) FROM public.matieres_premieres WHERE mp_id IN ('DEMO26_MP1','DEMO26_MP2')) AS observe
UNION ALL
SELECT 53 AS ligne, 'employes'::text AS table_nom, 2 AS attendu, (SELECT count(*) FROM public.employes WHERE employe_id IN ('DEMO26_EMP1','DEMO26_EMP2')) AS observe
UNION ALL
SELECT 54 AS ligne, 'fournisseurs'::text AS table_nom, 2 AS attendu, (SELECT count(*) FROM public.fournisseurs WHERE fournisseur_id IN ('DEMO26_FOU1','DEMO26_FOU2')) AS observe
UNION ALL
SELECT 55 AS ligne, 'clients'::text AS table_nom, 2 AS attendu, (SELECT count(*) FROM public.clients WHERE client_id IN ('DEMO26_CLI1','DEMO26_CLI2')) AS observe
), bilan AS (
  SELECT count(*) nombre_predicats, count(DISTINCT table_nom) nombre_tables,
         sum(attendu) total_attendu, sum(observe) total_present,
         count(*) FILTER (WHERE attendu <> observe) anomalies
  FROM controle
)
SELECT CASE WHEN nombre_predicats = 55 AND nombre_tables = 53
                AND total_attendu = 80 AND total_present = 80 AND anomalies = 0
            THEN 'CONTROLE_80_LIGNES_OK'
            ELSE 'ECART_DEMO_A_ANALYSER' END AS resultat,
       nombre_predicats, nombre_tables, total_attendu, total_present, anomalies
FROM bilan;
