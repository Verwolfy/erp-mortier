-- Lecture seule : à lancer sur une copie / instance TEST pour préparer la migration.
SELECT table_name
FROM information_schema.tables
WHERE table_schema='public' AND table_name IN
('factures','lignes_facture','compteurs','bons_livraison','lignes_bons_livraison',
 'commandes_ventes','lignes_commande_ventes','stock_actuel_pf','lots','erp_stock_operations')
ORDER BY table_name;

SELECT type_document,prefixe,annee,dernier_numero
FROM public.compteurs WHERE type_document IN ('FactureClient','FactureAvoir');

SELECT f.statut,count(*) AS nombre FROM public.factures f GROUP BY f.statut ORDER BY f.statut;

-- Repérer les livraisons éventuellement liées à des commandes absentes.
SELECT b.bl_id,b.commande_vente_id FROM public.bons_livraison b
LEFT JOIN public.commandes_ventes c ON c.commande_vente_id=b.commande_vente_id
WHERE c.commande_vente_id IS NULL;
