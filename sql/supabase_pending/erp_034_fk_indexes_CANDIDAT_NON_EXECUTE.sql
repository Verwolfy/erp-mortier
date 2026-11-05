-- ERP 034 — proposition d'index complémentaires pour clés étrangères.
-- STATUT : CANDIDAT NON EXECUTE. Vérifié par analyse du schéma principal le 2026-11-05.
-- Chaque CREATE INDEX CONCURRENTLY doit être exécuté hors transaction, séparément.
-- Ne pas lancer automatiquement sans test de charge, contrôle des index existants,
-- relecture du plan et validation de l'impact sur les écritures.
-- L'ajout d'index ne modifie ni les données ni les droits RLS.
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_cq_of_id ON public.controle_qualite (of_id);
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_conges_employe_id ON public.demandes_conges (employe_id);
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_exo_clients_cree_par ON public.erp_exonerations_tva_clients (cree_par);
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_exo_events_acteur ON public.erp_exonerations_tva_evenements (acteur_metier);
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_exo_ops_acteur ON public.erp_exonerations_tva_operations (acteur_id);
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_exo_ops_attestation ON public.erp_exonerations_tva_operations (attestation_id);
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_fact_fourn_commande ON public.factures_fournisseurs (commande_achat_id);
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_lettrage_reglement ON public.lettrage (reglement_id);
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_lignes_achats_commande ON public.lignes_achats (commande_achat_id);
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_lcv_commande ON public.lignes_commande_ventes (commande_vente_id);
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_lignes_devis_devis ON public.lignes_devis (devis_id);
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_lignes_facture_facture ON public.lignes_facture (facture_id);
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_lignes_recette_recette ON public.lignes_recette (recette_id);
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_of_recette ON public.ordres_fabrication (recette_id);
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_sku_conditionnement_pf ON public.sku_conditionnement (pf_id);
