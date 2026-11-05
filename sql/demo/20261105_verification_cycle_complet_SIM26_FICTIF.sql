-- Lecture seule et vérification de la chaîne fictive intégrée.
WITH exact AS (SELECT 'feuilles_de_temps' AS table_nom, (SELECT count(*) FROM public.feuilles_de_temps WHERE feuille_temps_id='SIM26_TIME') AS n
UNION ALL
SELECT 'taches' AS table_nom, (SELECT count(*) FROM public.taches WHERE tache_id='SIM26_TASK') AS n
UNION ALL
SELECT 'projets' AS table_nom, (SELECT count(*) FROM public.projets WHERE projet_id='SIM26_PROJ') AS n
UNION ALL
SELECT 'interactions' AS table_nom, (SELECT count(*) FROM public.interactions WHERE interaction_id='SIM26_CALL') AS n
UNION ALL
SELECT 'pipeline' AS table_nom, (SELECT count(*) FROM public.pipeline WHERE opportunite_id='SIM26_OPP') AS n
UNION ALL
SELECT 'lignes_factures_fournisseurs' AS table_nom, (SELECT count(*) FROM public.lignes_factures_fournisseurs WHERE ligne_ff_id='SIM26_BILLL') AS n
UNION ALL
SELECT 'factures_fournisseurs' AS table_nom, (SELECT count(*) FROM public.factures_fournisseurs WHERE facture_fournisseur_id='SIM26_BILL') AS n
UNION ALL
SELECT 'lettrage' AS table_nom, (SELECT count(*) FROM public.lettrage WHERE lettrage_id='SIM26_MATCH') AS n
UNION ALL
SELECT 'reglements' AS table_nom, (SELECT count(*) FROM public.reglements WHERE reglement_id='SIM26_PAY') AS n
UNION ALL
SELECT 'lignes_facture' AS table_nom, (SELECT count(*) FROM public.lignes_facture WHERE ligne_facture_id='SIM26_INVL') AS n
UNION ALL
SELECT 'factures' AS table_nom, (SELECT count(*) FROM public.factures WHERE facture_id='SIM26_INV') AS n
UNION ALL
SELECT 'mouvements_pf' AS table_nom, (SELECT count(*) FROM public.mouvements_pf WHERE mouvement_pf_id='SIM26_PF_OUT') AS n
UNION ALL
SELECT 'lignes_bons_livraison' AS table_nom, (SELECT count(*) FROM public.lignes_bons_livraison WHERE ligne_bl_id='SIM26_DNL') AS n
UNION ALL
SELECT 'bons_livraison' AS table_nom, (SELECT count(*) FROM public.bons_livraison WHERE bl_id='SIM26_DN') AS n
UNION ALL
SELECT 'lignes_commande_ventes' AS table_nom, (SELECT count(*) FROM public.lignes_commande_ventes WHERE ligne_commande_vente_id='SIM26_SOL') AS n
UNION ALL
SELECT 'commandes_ventes' AS table_nom, (SELECT count(*) FROM public.commandes_ventes WHERE commande_vente_id='SIM26_SO') AS n
UNION ALL
SELECT 'lignes_devis' AS table_nom, (SELECT count(*) FROM public.lignes_devis WHERE ligne_devis_id='SIM26_DEVL') AS n
UNION ALL
SELECT 'devis' AS table_nom, (SELECT count(*) FROM public.devis WHERE devis_id='SIM26_DEV') AS n
UNION ALL
SELECT 'mouvements_pf' AS table_nom, (SELECT count(*) FROM public.mouvements_pf WHERE mouvement_pf_id='SIM26_PF_IN') AS n
UNION ALL
SELECT 'stock_actuel_pf' AS table_nom, (SELECT count(*) FROM public.stock_actuel_pf WHERE sku_id='SIM26_SKU') AS n
UNION ALL
SELECT 'lots' AS table_nom, (SELECT count(*) FROM public.lots WHERE lot_id='SIM26_LOT_PF') AS n
UNION ALL
SELECT 'controle_qualite' AS table_nom, (SELECT count(*) FROM public.controle_qualite WHERE qc_id='SIM26_QC') AS n
UNION ALL
SELECT 'mouvements' AS table_nom, (SELECT count(*) FROM public.mouvements WHERE mouvement_id='SIM26_MV_OUT') AS n
UNION ALL
SELECT 'consommations_of' AS table_nom, (SELECT count(*) FROM public.consommations_of WHERE consommation_id='SIM26_CONS') AS n
UNION ALL
SELECT 'ordres_fabrication' AS table_nom, (SELECT count(*) FROM public.ordres_fabrication WHERE of_id='SIM26_OF') AS n
UNION ALL
SELECT 'lignes_recette' AS table_nom, (SELECT count(*) FROM public.lignes_recette WHERE ligne_recette_id='SIM26_RECL') AS n
UNION ALL
SELECT 'recettes' AS table_nom, (SELECT count(*) FROM public.recettes WHERE recette_id='SIM26_REC') AS n
UNION ALL
SELECT 'mouvements' AS table_nom, (SELECT count(*) FROM public.mouvements WHERE mouvement_id='SIM26_MV_IN') AS n
UNION ALL
SELECT 'stock_actuel' AS table_nom, (SELECT count(*) FROM public.stock_actuel WHERE mp_id='SIM26_MP') AS n
UNION ALL
SELECT 'lignes_bons_reception' AS table_nom, (SELECT count(*) FROM public.lignes_bons_reception WHERE ligne_br_id='SIM26_GRL') AS n
UNION ALL
SELECT 'lots' AS table_nom, (SELECT count(*) FROM public.lots WHERE lot_id='SIM26_LOT_MP') AS n
UNION ALL
SELECT 'bons_reception' AS table_nom, (SELECT count(*) FROM public.bons_reception WHERE bon_reception_id='SIM26_GR') AS n
UNION ALL
SELECT 'lignes_achats' AS table_nom, (SELECT count(*) FROM public.lignes_achats WHERE ligne_achat_id='SIM26_POL') AS n
UNION ALL
SELECT 'commandes_achats' AS table_nom, (SELECT count(*) FROM public.commandes_achats WHERE commande_achat_id='SIM26_PO') AS n
UNION ALL
SELECT 'comptes' AS table_nom, (SELECT count(*) FROM public.comptes WHERE compte_id='SIM26_BANK') AS n
UNION ALL
SELECT 'sku_conditionnement' AS table_nom, (SELECT count(*) FROM public.sku_conditionnement WHERE sku_id='SIM26_SKU') AS n
UNION ALL
SELECT 'produits' AS table_nom, (SELECT count(*) FROM public.produits WHERE pf_id='SIM26_PF') AS n
UNION ALL
SELECT 'matieres_premieres' AS table_nom, (SELECT count(*) FROM public.matieres_premieres WHERE mp_id='SIM26_MP') AS n
UNION ALL
SELECT 'clients' AS table_nom, (SELECT count(*) FROM public.clients WHERE client_id='SIM26_CLI') AS n
UNION ALL
SELECT 'fournisseurs' AS table_nom, (SELECT count(*) FROM public.fournisseurs WHERE fournisseur_id='SIM26_FOU') AS n),
mp AS (SELECT s.quantite_disponible stock,
  (SELECT COALESCE(SUM(CASE WHEN type_mouvement='ENTREE' THEN quantite WHEN type_mouvement='SORTIE' THEN -quantite ELSE 0 END),0) FROM public.mouvements WHERE mp_id='SIM26_MP') net
  FROM public.stock_actuel s WHERE mp_id='SIM26_MP'),
pf AS (SELECT s.quantite_disponible stock,
  (SELECT COALESCE(SUM(CASE WHEN type_mouvement='ENTREE' THEN quantite WHEN type_mouvement='SORTIE' THEN -quantite ELSE 0 END),0) FROM public.mouvements_pf WHERE sku_id='SIM26_SKU') net
  FROM public.stock_actuel_pf s WHERE sku_id='SIM26_SKU')
SELECT
  (SELECT count(*) FROM exact) AS id_checks,
  (SELECT count(DISTINCT table_nom) FROM exact) AS tables_checked,
  (SELECT sum(n) FROM exact) AS inserted_rows,
  (SELECT count(*) FROM exact WHERE n<>1) AS invalid_ids,
  (SELECT stock FROM mp) AS mp_stock,
  (SELECT net FROM mp) AS mp_net_movement,
  (SELECT stock FROM pf) AS pf_stock,
  (SELECT net FROM pf) AS pf_net_movement,
  (SELECT sum(quantite_recue) FROM public.lignes_bons_reception WHERE bon_reception_id='SIM26_GR') AS received_mp,
  (SELECT sum(quantite_consommee) FROM public.consommations_of WHERE of_id='SIM26_OF') AS consumed_mp,
  (SELECT quantite_produite FROM public.ordres_fabrication WHERE of_id='SIM26_OF') AS produced_pf,
  (SELECT sum(quantite_livree) FROM public.lignes_bons_livraison WHERE bl_id='SIM26_DN') AS delivered_pf,
  (SELECT conforme FROM public.controle_qualite WHERE of_id='SIM26_OF') AS qc,
  (SELECT montant_ttc FROM public.factures WHERE facture_id='SIM26_INV') AS invoice_total,
  (SELECT montant_paye FROM public.factures WHERE facture_id='SIM26_INV') AS paid_amount,
  (SELECT sum(montant_applique) FROM public.lettrage WHERE document_id='SIM26_INV') AS allocated,
  (SELECT montant_total FROM public.reglements WHERE reglement_id='SIM26_PAY') AS settlement_total,
  (SELECT statut FROM public.commandes_achats WHERE commande_achat_id='SIM26_PO') AS statut_reception_achat,
  (SELECT statut FROM public.commandes_ventes WHERE commande_vente_id='SIM26_SO') AS statut_commande_client,
  (SELECT statut FROM public.bons_livraison WHERE bl_id='SIM26_DN') AS statut_livraison;
