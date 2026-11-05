-- Audit métier SIM26 sans écriture. Un résultat KO doit bloquer la validation.
-- Les pièces sont fictives et ne prouvent pas l'exécution UI des RPC.
WITH controles(nom, ok) AS (
VALUES
('achat_100_kg', (SELECT count(*)=1 AND min(qte_totale)=100 AND min(prix_unitaire)=10 FROM public.lignes_achats WHERE commande_achat_id='SIM26_PO')),
('achat_recu', (SELECT statut='RECEPTIONNE' FROM public.commandes_achats WHERE commande_achat_id='SIM26_PO')),
('reception_100_kg', (SELECT coalesce(sum(quantite_recue),0)=100 FROM public.lignes_bons_reception WHERE bon_reception_id='SIM26_GR')),
('reception_et_achat_lies', (SELECT b.commande_achat_id='SIM26_PO' FROM public.bons_reception b WHERE b.bon_reception_id='SIM26_GR')),
('recette_10_kg_unite', (SELECT count(*)=1 AND min(quantite_par_unite)=10 FROM public.lignes_recette WHERE recette_id='SIM26_REC')),
('of_termine_10_unites', (SELECT quantite_prevue=10 AND quantite_produite=10 AND statut='TERMINE' AND recette_id='SIM26_REC' FROM public.ordres_fabrication WHERE of_id='SIM26_OF')),
('consommation_100_kg', (SELECT coalesce(sum(quantite_consommee),0)=100 FROM public.consommations_of WHERE of_id='SIM26_OF')),
('controle_qualite_conforme', (SELECT count(*)=1 AND bool_and(conforme='OUI') FROM public.controle_qualite WHERE of_id='SIM26_OF')),
('stock_mp_equilibre', (SELECT s.quantite_disponible=coalesce((SELECT sum(CASE WHEN type_mouvement='ENTREE' THEN quantite WHEN type_mouvement='SORTIE' THEN -quantite ELSE 0 END) FROM public.mouvements WHERE mp_id='SIM26_MP'),0) AND s.quantite_disponible=0 FROM public.stock_actuel s WHERE s.mp_id='SIM26_MP')),
('stock_pf_equilibre', (SELECT s.quantite_disponible=coalesce((SELECT sum(CASE WHEN type_mouvement='ENTREE' THEN quantite WHEN type_mouvement='SORTIE' THEN -quantite ELSE 0 END) FROM public.mouvements_pf WHERE sku_id='SIM26_SKU'),0) AND s.quantite_disponible=0 FROM public.stock_actuel_pf s WHERE s.sku_id='SIM26_SKU')),
('devis_commande_lies', (SELECT count(*)=1 AND bool_and(c.devis_id='SIM26_DEV' AND c.client_id='SIM26_CLI' AND c.statut='TERMINE') FROM public.commandes_ventes c WHERE c.commande_vente_id='SIM26_SO')),
('livraison_10_unites', (SELECT b.statut='EXPEDIE' AND b.commande_vente_id='SIM26_SO' AND (SELECT coalesce(sum(quantite_livree),0) FROM public.lignes_bons_livraison WHERE bl_id=b.bl_id)=10 FROM public.bons_livraison b WHERE b.bl_id='SIM26_DN')),
('facture_client_validee', (SELECT f.commande_vente_id='SIM26_SO' AND f.client_id='SIM26_CLI' AND f.statut='VALIDE' AND f.montant_ht=2000 AND f.montant_ttc=2380 AND f.montant_paye=2380 FROM public.factures f WHERE f.facture_id='SIM26_INV')),
('paiement_client_valide', (SELECT r.statut='VALIDE' AND r.type_flux='ENCAISSEMENT' AND r.partenaire_id='SIM26_CLI' AND r.montant_total=2380 AND r.montant_alloue=2380 FROM public.reglements r WHERE r.reglement_id='SIM26_PAY')),
('lettrage_facture_integral', (SELECT count(*)=1 AND min(document_id)='SIM26_INV' AND coalesce(sum(montant_applique),0)=2380 FROM public.lettrage WHERE reglement_id='SIM26_PAY')),
('facture_fournisseur_brouillon', (SELECT ff.statut_paiement='BROUILLON' AND ff.commande_achat_id='SIM26_PO' AND ff.montant_ttc=1000 FROM public.factures_fournisseurs ff WHERE ff.facture_fournisseur_id='SIM26_BILL')),
('tracabilite_achat_vers_vente', (SELECT count(*)=1 FROM public.lignes_facture lf JOIN public.factures f ON f.facture_id=lf.facture_id JOIN public.lignes_commande_ventes lc ON lc.commande_vente_id=f.commande_vente_id AND lc.sku_id=lf.sku_id JOIN public.sku_conditionnement sk ON sk.sku_id=lf.sku_id JOIN public.ordres_fabrication ofa ON ofa.sku_id=sk.sku_id JOIN public.lignes_recette lr ON lr.recette_id=ofa.recette_id JOIN public.lignes_achats la ON la.mp_id=lr.mp_id JOIN public.commandes_achats ca ON ca.commande_achat_id=la.commande_achat_id WHERE f.facture_id='SIM26_INV' AND ca.commande_achat_id='SIM26_PO'))
)
SELECT nom, CASE WHEN ok IS TRUE THEN 'OK' ELSE 'ECART' END AS resultat FROM controles ORDER BY nom;
