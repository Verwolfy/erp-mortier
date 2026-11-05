-- Lot indépendant SIM26 : scénario de simulation uniquement, pas de pièces réelles.
-- Référentiels fiscaux et authentification inchangés.
BEGIN;
DO $g$ BEGIN
IF EXISTS(SELECT 1 FROM public.clients WHERE client_id='SIM26_CLI')
OR EXISTS(SELECT 1 FROM public.factures WHERE facture_id='SIM26_INV')
OR EXISTS(SELECT 1 FROM public.commandes_achats WHERE commande_achat_id='SIM26_PO')
THEN RAISE EXCEPTION 'Lot SIM26 déjà présent'; END IF;
END $g$;
INSERT INTO public.fournisseurs (fournisseur_id,nom,categorie,actif) VALUES ('SIM26_FOU','[FICTIF] Fournisseur cycle intégré','MATIERES','OUI');
INSERT INTO public.clients (client_id,nom,categorie_client,actif,email_contact) VALUES ('SIM26_CLI','[FICTIF] Client cycle intégré','PRO','OUI','simulation@example.invalid');
INSERT INTO public.matieres_premieres (mp_id,nom,categorie_mp,unite_stock,cmp_actuel,stock_mini,stock_maxi,actif) VALUES ('SIM26_MP','[FICTIF] Liant de simulation','Granulat','kg',10,0,2000,'OUI');
INSERT INTO public.produits (pf_id,nom,categorie_pf,unite_production,actif) VALUES ('SIM26_PF','[FICTIF] Produit fini simulé','Mortier','kg','OUI');
INSERT INTO public.sku_conditionnement (sku_id,pf_id,format,poids_net,unite_vente,facteur_conversion,prix_vente_defaut,actif) VALUES ('SIM26_SKU','SIM26_PF','[FICTIF] Sac de simulation',10,'SAC',10,200,'OUI');
INSERT INTO public.comptes (compte_id,nom_compte,type_compte,solde_initial,statut) VALUES ('SIM26_BANK','[FICTIF] Compte cycle intégré','Banque',0,'ACTIF');
INSERT INTO public.commandes_achats (commande_achat_id,date_commande,fournisseur_id,type_achat,devise,taux_change,montant_total_devise,montant_total_local,date_voulue,statut) VALUES ('SIM26_PO','2026-10-13','SIM26_FOU','MP','DZD',1,1000,1000,'2026-10-15','RECEPTIONNE');
INSERT INTO public.lignes_achats (ligne_achat_id,commande_achat_id,mp_id,unite_cond,qte_cond,qte_totale,prix_unitaire,total_devise) VALUES ('SIM26_POL','SIM26_PO','SIM26_MP','kg',100,100,10,1000);
INSERT INTO public.bons_reception (bon_reception_id,commande_achat_id,date_reception,controle_conformite,remarques) VALUES ('SIM26_GR','SIM26_PO','2026-10-15','OUI','[FICTIF] Réception simulée 100 kg');
INSERT INTO public.lots (lot_id,item_id,type_item,date_creation,date_peremption,quantite_initiale,quantite_restante,statut) VALUES ('SIM26_LOT_MP','SIM26_MP','MP','2026-10-15','2027-10-15',100,0,'EPUISE');
INSERT INTO public.lignes_bons_reception (ligne_br_id,bon_reception_id,mp_id,quantite_recue,lot_attribue_id) VALUES ('SIM26_GRL','SIM26_GR','SIM26_MP',100,'SIM26_LOT_MP');
INSERT INTO public.stock_actuel (mp_id,quantite_disponible,cmp_actuel,derniere_maj) VALUES ('SIM26_MP',0,10,'2026-10-18');
INSERT INTO public.mouvements (mouvement_id,date,type_mouvement,mp_id,quantite,reference,lot_id,prix_entree) VALUES ('SIM26_MV_IN','2026-10-15','ENTREE','SIM26_MP',100,'SIM26_GR','SIM26_LOT_MP',10);
INSERT INTO public.recettes (recette_id,pf_id,version,rendement_unite,instructions,date_effet,actif) VALUES ('SIM26_REC','SIM26_PF','SIMUL-V1',10,'[FICTIF] Ne jamais fabriquer physiquement','2026-10-16','OUI');
INSERT INTO public.lignes_recette (ligne_recette_id,recette_id,mp_id,quantite_par_unite) VALUES ('SIM26_RECL','SIM26_REC','SIM26_MP',10);
INSERT INTO public.ordres_fabrication (of_id,pf_id,recette_id,sku_id,quantite_prevue,quantite_produite,date_planification,date_debut,date_fin,statut,cout_total,notes) VALUES ('SIM26_OF','SIM26_PF','SIM26_REC','SIM26_SKU',10,10,'2026-10-17','2026-10-17','2026-10-18','TERMINE',1000,'[FICTIF] OF terminé, contrôle qualité positif');
INSERT INTO public.consommations_of (consommation_id,of_id,mp_id,lot_id,quantite_consommee) VALUES ('SIM26_CONS','SIM26_OF','SIM26_MP','SIM26_LOT_MP',100);
INSERT INTO public.mouvements (mouvement_id,date,type_mouvement,mp_id,quantite,reference,lot_id) VALUES ('SIM26_MV_OUT','2026-10-17','SORTIE','SIM26_MP',100,'SIM26_OF','SIM26_LOT_MP');
INSERT INTO public.controle_qualite (qc_id,of_id,date,conforme,remarques,controleur) VALUES ('SIM26_QC','SIM26_OF','2026-10-18','OUI','[FICTIF] Lot conforme pour essai logiciel','SIMULATION');
INSERT INTO public.lots (lot_id,item_id,type_item,date_creation,date_peremption,quantite_initiale,quantite_restante,statut) VALUES ('SIM26_LOT_PF','SIM26_SKU','PF','2026-10-18','2027-10-18',10,0,'EPUISE');
INSERT INTO public.stock_actuel_pf (sku_id,quantite_disponible,cout_revient,derniere_maj) VALUES ('SIM26_SKU',0,100,'2026-10-25');
INSERT INTO public.mouvements_pf (mouvement_pf_id,date,type_mouvement,sku_id,quantite,reference,lot_id,cout_unitaire) VALUES ('SIM26_PF_IN','2026-10-18','ENTREE','SIM26_SKU',10,'SIM26_OF','SIM26_LOT_PF',100);
INSERT INTO public.devis (devis_id,client_id,date,validite,statut) VALUES ('SIM26_DEV','SIM26_CLI','2026-10-19','2026-10-31','ACCEPTE');
INSERT INTO public.lignes_devis (ligne_devis_id,devis_id,sku_id,quantite,prix_unitaire,remise_pct) VALUES ('SIM26_DEVL','SIM26_DEV','SIM26_SKU',10,200,0);
INSERT INTO public.commandes_ventes (commande_vente_id,devis_id,client_id,date,statut) VALUES ('SIM26_SO','SIM26_DEV','SIM26_CLI','2026-10-20','TERMINE');
INSERT INTO public.lignes_commande_ventes (ligne_commande_vente_id,commande_vente_id,sku_id,quantite,prix_unitaire) VALUES ('SIM26_SOL','SIM26_SO','SIM26_SKU',10,200);
INSERT INTO public.bons_livraison (bl_id,commande_vente_id,date,transporteur,zone,statut) VALUES ('SIM26_DN','SIM26_SO','2026-10-22','[FICTIF] Logistique','SIMULATION','EXPEDIE');
INSERT INTO public.lignes_bons_livraison (ligne_bl_id,bl_id,sku_id,quantite_livree,lot_id) VALUES ('SIM26_DNL','SIM26_DN','SIM26_SKU',10,'SIM26_LOT_PF');
INSERT INTO public.mouvements_pf (mouvement_pf_id,date,type_mouvement,sku_id,quantite,reference,lot_id,cout_unitaire) VALUES ('SIM26_PF_OUT','2026-10-22','SORTIE','SIM26_SKU',10,'SIM26_DN','SIM26_LOT_PF',100);
INSERT INTO public.factures (facture_id,commande_vente_id,client_id,date,montant_ht,taux_tva,montant_tva,montant_ttc,montant_paye,statut,date_echeance,montant_timbre,type_facture,remise_globale) VALUES ('SIM26_INV','SIM26_SO','SIM26_CLI','2026-10-23',2000,0.19,380,2380,2380,'VALIDE','2026-11-15',0,'FactureClient',0);
INSERT INTO public.lignes_facture (ligne_facture_id,facture_id,sku_id,quantite,prix_unitaire,remise_ligne,total_ligne_ht) VALUES ('SIM26_INVL','SIM26_INV','SIM26_SKU',10,200,0,2000);
INSERT INTO public.reglements (reglement_id,date_reglement,type_flux,partenaire_id,compte_id,mode_paiement,reference_trace,montant_total,montant_alloue,statut) VALUES ('SIM26_PAY','2026-10-24','ENCAISSEMENT','SIM26_CLI','SIM26_BANK','VIREMENT','SIM26_TRACE',2380,2380,'VALIDE');
INSERT INTO public.lettrage (lettrage_id,date,reglement_id,document_id,type_document,montant_applique) VALUES ('SIM26_MATCH','2026-10-24','SIM26_PAY','SIM26_INV','FactureClient',2380);
INSERT INTO public.factures_fournisseurs (facture_fournisseur_id,commande_achat_id,fournisseur_id,reference_facture_fournisseur,date,montant_ht,taux_tva,montant_tva,montant_ttc,statut_paiement) VALUES ('SIM26_BILL','SIM26_PO','SIM26_FOU','[FICTIF] SIM26','2026-10-16',1000,0,0,1000,'BROUILLON');
INSERT INTO public.lignes_factures_fournisseurs (ligne_ff_id,facture_fournisseur_id,mp_id_ou_service,quantite,prix_unitaire,taux_tva,total_ht) VALUES ('SIM26_BILLL','SIM26_BILL','SIM26_MP',100,10,0,1000);
INSERT INTO public.pipeline (opportunite_id,prospect_nom,statut,valeur_estimee,probabilite_pct,date_creation,date_derniere_action) VALUES ('SIM26_OPP','[FICTIF] Client cycle intégré','Gagné',2000,100,'2026-10-19','2026-10-24');
INSERT INTO public.interactions (interaction_id,client_id,date_creation,type_action,notes,statut_rappel) VALUES ('SIM26_CALL','SIM26_CLI','2026-10-19','APPEL','[FICTIF] Accord client test','TERMINE');
INSERT INTO public.projets (projet_id,nom,client_id,date_debut,date_fin_prevue,statut) VALUES ('SIM26_PROJ','[FICTIF] Projet démonstration cycle','SIM26_CLI','2026-10-13','2026-10-25','TERMINE');
INSERT INTO public.taches (tache_id,projet_id,statut,date_echeance) VALUES ('SIM26_TASK','SIM26_PROJ','TERMINE','2026-10-25');
INSERT INTO public.feuilles_de_temps (feuille_temps_id,employe_id,tache_id,date,heures) VALUES ('SIM26_TIME','DEMO26_EMP1','SIM26_TASK','2026-10-21',2);
COMMIT;
