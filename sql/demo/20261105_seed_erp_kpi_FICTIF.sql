-- DEMO ERP 2026-11-05 : 100% FICTIF. Ne pas utiliser dans déclarations.
-- Identifiants déterministes et rollback symétrique; aucune modification des lignes préexistantes.
BEGIN;
DO $guard$ BEGIN
IF EXISTS(SELECT 1 FROM public.clients WHERE client_id IN ('DEMO26_CLI1','DEMO26_CLI2')) THEN RAISE EXCEPTION 'DEMO collision: clients'; END IF;
IF EXISTS(SELECT 1 FROM public.fournisseurs WHERE fournisseur_id IN ('DEMO26_FOU1','DEMO26_FOU2')) THEN RAISE EXCEPTION 'DEMO collision: fournisseurs'; END IF;
IF EXISTS(SELECT 1 FROM public.employes WHERE employe_id IN ('DEMO26_EMP1','DEMO26_EMP2')) THEN RAISE EXCEPTION 'DEMO collision: employes'; END IF;
IF EXISTS(SELECT 1 FROM public.matieres_premieres WHERE mp_id IN ('DEMO26_MP1','DEMO26_MP2')) THEN RAISE EXCEPTION 'DEMO collision: matieres_premieres'; END IF;
IF EXISTS(SELECT 1 FROM public.produits WHERE pf_id IN ('DEMO26_PF1','DEMO26_PF2')) THEN RAISE EXCEPTION 'DEMO collision: produits'; END IF;
IF EXISTS(SELECT 1 FROM public.recettes WHERE recette_id IN ('DEMO26_REC1','DEMO26_REC2')) THEN RAISE EXCEPTION 'DEMO collision: recettes'; END IF;
IF EXISTS(SELECT 1 FROM public.lignes_recette WHERE ligne_recette_id IN ('DEMO26_LR1','DEMO26_LR2')) THEN RAISE EXCEPTION 'DEMO collision: lignes_recette'; END IF;
IF EXISTS(SELECT 1 FROM public.sku_conditionnement WHERE sku_id IN ('DEMO26_SKU1','DEMO26_SKU2')) THEN RAISE EXCEPTION 'DEMO collision: sku_conditionnement'; END IF;
IF EXISTS(SELECT 1 FROM public.stock_actuel WHERE mp_id IN ('DEMO26_MP1','DEMO26_MP2')) THEN RAISE EXCEPTION 'DEMO collision: stock_actuel'; END IF;
IF EXISTS(SELECT 1 FROM public.stock_actuel_pf WHERE sku_id IN ('DEMO26_SKU1','DEMO26_SKU2')) THEN RAISE EXCEPTION 'DEMO collision: stock_actuel_pf'; END IF;
IF EXISTS(SELECT 1 FROM public.lots WHERE lot_id IN ('DEMO26_LOT1','DEMO26_LOT2')) THEN RAISE EXCEPTION 'DEMO collision: lots'; END IF;
IF EXISTS(SELECT 1 FROM public.comptes WHERE compte_id IN ('DEMO26_BANK','DEMO26_CASH')) THEN RAISE EXCEPTION 'DEMO collision: comptes'; END IF;
IF EXISTS(SELECT 1 FROM public.pipeline WHERE opportunite_id IN ('DEMO26_OP1','DEMO26_OP2','DEMO26_OP3')) THEN RAISE EXCEPTION 'DEMO collision: pipeline'; END IF;
IF EXISTS(SELECT 1 FROM public.interactions WHERE interaction_id IN ('DEMO26_INT1','DEMO26_INT2')) THEN RAISE EXCEPTION 'DEMO collision: interactions'; END IF;
IF EXISTS(SELECT 1 FROM public.grilles_tarifaires WHERE grille_id IN ('DEMO26_GR1')) THEN RAISE EXCEPTION 'DEMO collision: grilles_tarifaires'; END IF;
IF EXISTS(SELECT 1 FROM public.contrats WHERE contrat_id IN ('DEMO26_CTR1')) THEN RAISE EXCEPTION 'DEMO collision: contrats'; END IF;
IF EXISTS(SELECT 1 FROM public.devis WHERE devis_id IN ('DEMO26_DEV1')) THEN RAISE EXCEPTION 'DEMO collision: devis'; END IF;
IF EXISTS(SELECT 1 FROM public.lignes_devis WHERE ligne_devis_id IN ('DEMO26_LD1')) THEN RAISE EXCEPTION 'DEMO collision: lignes_devis'; END IF;
IF EXISTS(SELECT 1 FROM public.commandes_ventes WHERE commande_vente_id IN ('DEMO26_CV1','DEMO26_CV2')) THEN RAISE EXCEPTION 'DEMO collision: commandes_ventes'; END IF;
IF EXISTS(SELECT 1 FROM public.lignes_commande_ventes WHERE ligne_commande_vente_id IN ('DEMO26_LCV1','DEMO26_LCV2')) THEN RAISE EXCEPTION 'DEMO collision: lignes_commande_ventes'; END IF;
IF EXISTS(SELECT 1 FROM public.bons_livraison WHERE bl_id IN ('DEMO26_BL1')) THEN RAISE EXCEPTION 'DEMO collision: bons_livraison'; END IF;
IF EXISTS(SELECT 1 FROM public.lignes_bons_livraison WHERE ligne_bl_id IN ('DEMO26_LBL1')) THEN RAISE EXCEPTION 'DEMO collision: lignes_bons_livraison'; END IF;
IF EXISTS(SELECT 1 FROM public.factures WHERE facture_id IN ('DEMO26_FAC1','DEMO26_FAC2')) THEN RAISE EXCEPTION 'DEMO collision: factures'; END IF;
IF EXISTS(SELECT 1 FROM public.lignes_facture WHERE ligne_facture_id IN ('DEMO26_LF1','DEMO26_LF2')) THEN RAISE EXCEPTION 'DEMO collision: lignes_facture'; END IF;
IF EXISTS(SELECT 1 FROM public.commandes_achats WHERE commande_achat_id IN ('DEMO26_CA1','DEMO26_CA2')) THEN RAISE EXCEPTION 'DEMO collision: commandes_achats'; END IF;
IF EXISTS(SELECT 1 FROM public.lignes_achats WHERE ligne_achat_id IN ('DEMO26_LCA1')) THEN RAISE EXCEPTION 'DEMO collision: lignes_achats'; END IF;
IF EXISTS(SELECT 1 FROM public.bons_reception WHERE bon_reception_id IN ('DEMO26_BR1')) THEN RAISE EXCEPTION 'DEMO collision: bons_reception'; END IF;
IF EXISTS(SELECT 1 FROM public.lignes_bons_reception WHERE ligne_br_id IN ('DEMO26_LBR1')) THEN RAISE EXCEPTION 'DEMO collision: lignes_bons_reception'; END IF;
IF EXISTS(SELECT 1 FROM public.factures_fournisseurs WHERE facture_fournisseur_id IN ('DEMO26_FF1')) THEN RAISE EXCEPTION 'DEMO collision: factures_fournisseurs'; END IF;
IF EXISTS(SELECT 1 FROM public.lignes_factures_fournisseurs WHERE ligne_ff_id IN ('DEMO26_LFF1')) THEN RAISE EXCEPTION 'DEMO collision: lignes_factures_fournisseurs'; END IF;
IF EXISTS(SELECT 1 FROM public.ordres_fabrication WHERE of_id IN ('DEMO26_OF1','DEMO26_OF2')) THEN RAISE EXCEPTION 'DEMO collision: ordres_fabrication'; END IF;
IF EXISTS(SELECT 1 FROM public.consommations_of WHERE consommation_id IN ('DEMO26_CONS1')) THEN RAISE EXCEPTION 'DEMO collision: consommations_of'; END IF;
IF EXISTS(SELECT 1 FROM public.controle_qualite WHERE qc_id IN ('DEMO26_QC1')) THEN RAISE EXCEPTION 'DEMO collision: controle_qualite'; END IF;
IF EXISTS(SELECT 1 FROM public.reglements WHERE reglement_id IN ('DEMO26_RG1','DEMO26_RG2')) THEN RAISE EXCEPTION 'DEMO collision: reglements'; END IF;
IF EXISTS(SELECT 1 FROM public.lettrage WHERE lettrage_id IN ('DEMO26_LET1')) THEN RAISE EXCEPTION 'DEMO collision: lettrage'; END IF;
IF EXISTS(SELECT 1 FROM public.projets WHERE projet_id IN ('DEMO26_PRJ1')) THEN RAISE EXCEPTION 'DEMO collision: projets'; END IF;
IF EXISTS(SELECT 1 FROM public.taches WHERE tache_id IN ('DEMO26_TASK1')) THEN RAISE EXCEPTION 'DEMO collision: taches'; END IF;
IF EXISTS(SELECT 1 FROM public.demandes_conges WHERE demande_conge_id IN ('DEMO26_CONGE1')) THEN RAISE EXCEPTION 'DEMO collision: demandes_conges'; END IF;
IF EXISTS(SELECT 1 FROM public.feuilles_de_temps WHERE feuille_temps_id IN ('DEMO26_FT1')) THEN RAISE EXCEPTION 'DEMO collision: feuilles_de_temps'; END IF;
IF EXISTS(SELECT 1 FROM public.fiches_de_paie WHERE fiche_paie_id IN ('DEMO26_FP1')) THEN RAISE EXCEPTION 'DEMO collision: fiches_de_paie'; END IF;
IF EXISTS(SELECT 1 FROM public.appels_offres WHERE ao_id IN ('DEMO26_AO1')) THEN RAISE EXCEPTION 'DEMO collision: appels_offres'; END IF;
IF EXISTS(SELECT 1 FROM public.reponses_appels_offres WHERE reponse_ao_id IN ('DEMO26_RAO1')) THEN RAISE EXCEPTION 'DEMO collision: reponses_appels_offres'; END IF;
IF EXISTS(SELECT 1 FROM public.mouvements WHERE mouvement_id IN ('DEMO26_MV1')) THEN RAISE EXCEPTION 'DEMO collision: mouvements'; END IF;
IF EXISTS(SELECT 1 FROM public.mouvements_pf WHERE mouvement_pf_id IN ('DEMO26_MVP1')) THEN RAISE EXCEPTION 'DEMO collision: mouvements_pf'; END IF;
IF EXISTS(SELECT 1 FROM public.erp_sku_fiscalite WHERE sku_id IN ('DEMO26_SKU1','DEMO26_SKU2') AND date_effet='2026-11-01') THEN RAISE EXCEPTION 'DEMO collision: erp_sku_fiscalite'; END IF;
IF EXISTS(SELECT 1 FROM public.paie_periodes_v2 WHERE periode_id IN ('DEMO26_PER11')) THEN RAISE EXCEPTION 'DEMO collision: paie_periodes_v2'; END IF;
IF EXISTS(SELECT 1 FROM public.paie_bulletins_v2 WHERE bulletin_id IN ('90000000-0026-4026-8026-000000000001')) THEN RAISE EXCEPTION 'DEMO collision: paie_bulletins_v2'; END IF;
IF EXISTS(SELECT 1 FROM public.scf_exercices WHERE exercice_id IN ('DEMO26_SCF2026')) THEN RAISE EXCEPTION 'DEMO collision: scf_exercices'; END IF;
IF EXISTS(SELECT 1 FROM public.scf_journaux WHERE code_journal IN ('DEMO26_JRN')) THEN RAISE EXCEPTION 'DEMO collision: scf_journaux'; END IF;
IF EXISTS(SELECT 1 FROM public.scf_plan_comptes WHERE numero_compte IN ('41199926','70199926')) THEN RAISE EXCEPTION 'DEMO collision: scf_plan_comptes'; END IF;
IF EXISTS(SELECT 1 FROM public.scf_pieces WHERE piece_id IN ('90000000-0026-4026-8026-000000000002')) THEN RAISE EXCEPTION 'DEMO collision: scf_pieces'; END IF;
IF EXISTS(SELECT 1 FROM public.scf_lignes WHERE ligne_id IN (-260002,-260003)) THEN RAISE EXCEPTION 'DEMO collision: scf_lignes'; END IF;
IF EXISTS(SELECT 1 FROM public.paie_lignes_v2 WHERE ligne_id IN (-260001)) THEN RAISE EXCEPTION 'DEMO collision: paie_lignes_v2'; END IF;
END $guard$;
INSERT INTO public.clients (client_id,nom,categorie_client,actif,wilaya) VALUES
('DEMO26_CLI1','[FICTIF] Client travaux','Entreprise','OUI','Bouira'),
('DEMO26_CLI2','[FICTIF] Distributeur','Distributeur','OUI','Alger');
INSERT INTO public.fournisseurs (fournisseur_id,nom,categorie,actif) VALUES
('DEMO26_FOU1','[FICTIF] Fournisseur matières','MATIERES','OUI'),
('DEMO26_FOU2','[FICTIF] Fournisseur maintenance','SERVICES OPEX','OUI');
INSERT INTO public.employes (employe_id,nom,poste,service,actif) VALUES
('DEMO26_EMP1','[FICTIF] Technicien','Technicien','Production','OUI'),
('DEMO26_EMP2','[FICTIF] Commercial','Commercial','Ventes','OUI');
INSERT INTO public.matieres_premieres (mp_id,nom,categorie_mp,unite_stock,stock_mini,stock_maxi,cmp_actuel,actif) VALUES
('DEMO26_MP1','[FICTIF] Poudre test','Granulat','kg',500,4000,80,'OUI'),
('DEMO26_MP2','[FICTIF] Résine test','Resine','kg',80,600,250,'OUI');
INSERT INTO public.produits (pf_id,nom,categorie_pf,unite_production,actif) VALUES
('DEMO26_PF1','[FICTIF] Mortier test','Mortier','kg','OUI'),
('DEMO26_PF2','[FICTIF] Revêtement test','Peinture','kg','OUI');
INSERT INTO public.recettes (recette_id,pf_id,version,rendement_unite,instructions,date_effet) VALUES
('DEMO26_REC1','DEMO26_PF1','DEMO',1000,'FICTIF - ne pas fabriquer','2026-11-01'),
('DEMO26_REC2','DEMO26_PF2','DEMO',500,'FICTIF - ne pas fabriquer','2026-11-01');
INSERT INTO public.lignes_recette (ligne_recette_id,recette_id,mp_id,quantite_par_unite) VALUES
('DEMO26_LR1','DEMO26_REC1','DEMO26_MP1',0.8),
('DEMO26_LR2','DEMO26_REC2','DEMO26_MP2',0.4);
INSERT INTO public.sku_conditionnement (sku_id,pf_id,format,poids_net,unite_vente,facteur_conversion,prix_vente_defaut,actif) VALUES
('DEMO26_SKU1','DEMO26_PF1','[FICTIF] Sac 25kg',25,'SAC',25,1800,'OUI'),
('DEMO26_SKU2','DEMO26_PF2','[FICTIF] Seau 5kg',5,'SEAU',5,2500,'OUI');
INSERT INTO public.stock_actuel (mp_id,quantite_disponible,cmp_actuel,derniere_maj) VALUES
('DEMO26_MP1',100,80,'2026-11-05'),
('DEMO26_MP2',220,250,'2026-11-05');
INSERT INTO public.stock_actuel_pf (sku_id,quantite_disponible,cout_revient,derniere_maj) VALUES
('DEMO26_SKU1',180,1000,'2026-11-05'),
('DEMO26_SKU2',60,1500,'2026-11-05');
INSERT INTO public.lots (lot_id,item_id,type_item,date_creation,date_peremption,quantite_initiale,quantite_restante,statut) VALUES
('DEMO26_LOT1','DEMO26_MP1','MP','2026-10-20','2026-11-20',100,100,'DISPONIBLE'),
('DEMO26_LOT2','DEMO26_SKU1','PF','2026-10-20','2027-10-20',180,180,'DISPONIBLE');
INSERT INTO public.comptes (compte_id,nom_compte,type_compte,numero_compte,solde_initial,statut) VALUES
('DEMO26_BANK','[FICTIF] Banque','Banque','FICTIF',1000000,'ACTIF'),
('DEMO26_CASH','[FICTIF] Caisse','Caisse','FICTIF',25000,'ACTIF');
INSERT INTO public.pipeline (opportunite_id,prospect_nom,statut,commercial_id,valeur_estimee,probabilite_pct,date_creation) VALUES
('DEMO26_OP1','[FICTIF] Prospect ouvert','En Négociation','DEMO26_EMP2',500000,60,'2026-11-02'),
('DEMO26_OP2','[FICTIF] Prospect gagné','Gagné','DEMO26_EMP2',200000,100,'2026-11-03'),
('DEMO26_OP3','[FICTIF] Prospect perdu','Perdu','DEMO26_EMP2',85000,0,'2026-11-03');
INSERT INTO public.interactions (interaction_id,client_id,date_creation,type_action,notes) VALUES
('DEMO26_INT1','DEMO26_CLI1','2026-11-04','APPEL','FICTIF - simulation'),
('DEMO26_INT2','DEMO26_CLI2','2026-11-04','VISITE','FICTIF - simulation');
INSERT INTO public.grilles_tarifaires (grille_id,client_id_ou_categorie,sku_id,prix_negocie,remise_pct,date_debut,date_fin) VALUES
('DEMO26_GR1','DEMO26_CLI1','DEMO26_SKU1',1600,5,'2026-11-01','2026-12-31');
INSERT INTO public.contrats (contrat_id,client_id,date_debut,date_fin,grille_tarifaire_id,conditions,actif) VALUES
('DEMO26_CTR1','DEMO26_CLI1','2026-11-01','2027-10-31','DEMO26_GR1','FICTIF - pas de contrat réel','OUI');
INSERT INTO public.devis (devis_id,client_id,date,validite,statut,commercial_id) VALUES
('DEMO26_DEV1','DEMO26_CLI1','2026-11-01','2026-12-01','ACCEPTE','DEMO26_EMP2');
INSERT INTO public.lignes_devis (ligne_devis_id,devis_id,sku_id,quantite,prix_unitaire,remise_pct) VALUES
('DEMO26_LD1','DEMO26_DEV1','DEMO26_SKU1',10,1600,0);
INSERT INTO public.commandes_ventes (commande_vente_id,devis_id,client_id,date,statut) VALUES
('DEMO26_CV1','DEMO26_DEV1','DEMO26_CLI1','2026-11-01','EN_COURS'),
('DEMO26_CV2',NULL,'DEMO26_CLI2','2026-09-01','TERMINE');
INSERT INTO public.lignes_commande_ventes (ligne_commande_vente_id,commande_vente_id,sku_id,quantite,prix_unitaire) VALUES
('DEMO26_LCV1','DEMO26_CV1','DEMO26_SKU1',10,1600),
('DEMO26_LCV2','DEMO26_CV2','DEMO26_SKU2',4,2500);
INSERT INTO public.bons_livraison (bl_id,commande_vente_id,date,transporteur,statut) VALUES
('DEMO26_BL1','DEMO26_CV1','2026-11-03','[FICTIF] Livraison','LIVRE');
INSERT INTO public.lignes_bons_livraison (ligne_bl_id,bl_id,sku_id,quantite_livree,lot_id) VALUES
('DEMO26_LBL1','DEMO26_BL1','DEMO26_SKU1',10,'DEMO26_LOT2');
INSERT INTO public.factures (facture_id,commande_vente_id,client_id,date,type_facture,statut,montant_ht,taux_tva,montant_tva,montant_ttc,montant_paye,montant_timbre,date_echeance) VALUES
('DEMO26_FAC1','DEMO26_CV1','DEMO26_CLI1','2026-11-03','FactureClient','VALIDE',16000,(select valeur from public.parametres_reglementaires where code='TVA_TAUX_NORMAL' and statut_juridique='en_vigueur' and date_effet<='2026-11-01' order by date_effet desc limit 1),16000*(select valeur from public.parametres_reglementaires where code='TVA_TAUX_NORMAL' and statut_juridique='en_vigueur' and date_effet<='2026-11-01' order by date_effet desc limit 1),16000*(1+(select valeur from public.parametres_reglementaires where code='TVA_TAUX_NORMAL' and statut_juridique='en_vigueur' and date_effet<='2026-11-01' order by date_effet desc limit 1)),3000,0,'2026-11-30'),
('DEMO26_FAC2','DEMO26_CV2','DEMO26_CLI2','2026-09-01','FactureClient','VALIDE',10000,(select valeur from public.parametres_reglementaires where code='TVA_TAUX_NORMAL' and statut_juridique='en_vigueur' and date_effet<='2026-11-01' order by date_effet desc limit 1),10000*(select valeur from public.parametres_reglementaires where code='TVA_TAUX_NORMAL' and statut_juridique='en_vigueur' and date_effet<='2026-11-01' order by date_effet desc limit 1),10000*(1+(select valeur from public.parametres_reglementaires where code='TVA_TAUX_NORMAL' and statut_juridique='en_vigueur' and date_effet<='2026-11-01' order by date_effet desc limit 1)),0,0,'2026-09-30');
INSERT INTO public.lignes_facture (ligne_facture_id,facture_id,sku_id,quantite,prix_unitaire,remise_ligne,total_ligne_ht) VALUES
('DEMO26_LF1','DEMO26_FAC1','DEMO26_SKU1',10,1600,0,16000),
('DEMO26_LF2','DEMO26_FAC2','DEMO26_SKU2',4,2500,0,10000);
INSERT INTO public.commandes_achats (commande_achat_id,date_commande,fournisseur_id,type_achat,devise,taux_change,montant_total_devise,montant_total_local,date_voulue,statut) VALUES
('DEMO26_CA1','2026-11-02','DEMO26_FOU1','MP','DZD',1,80000,80000,'2026-11-15','EN_ATTENTE'),
('DEMO26_CA2','2026-09-20','DEMO26_FOU2','SERVICE','DZD',1,5000,5000,'2026-10-01','EN_ATTENTE');
INSERT INTO public.lignes_achats (ligne_achat_id,commande_achat_id,mp_id,unite_cond,qte_cond,qte_totale,prix_unitaire,total_devise) VALUES
('DEMO26_LCA1','DEMO26_CA1','DEMO26_MP1','kg',1000,1000,80,80000);
INSERT INTO public.bons_reception (bon_reception_id,commande_achat_id,date_reception,controle_conformite,remarques) VALUES
('DEMO26_BR1','DEMO26_CA1','2026-11-04','OUI','FICTIF - test');
INSERT INTO public.lignes_bons_reception (ligne_br_id,bon_reception_id,mp_id,quantite_recue,lot_attribue_id) VALUES
('DEMO26_LBR1','DEMO26_BR1','DEMO26_MP1',100,'DEMO26_LOT1');
INSERT INTO public.factures_fournisseurs (facture_fournisseur_id,commande_achat_id,fournisseur_id,reference_facture_fournisseur,date,montant_ht,statut_paiement) VALUES
('DEMO26_FF1','DEMO26_CA1','DEMO26_FOU1','FICTIF-NON-FISCAL','2026-11-04',80000,'BROUILLON');
INSERT INTO public.lignes_factures_fournisseurs (ligne_ff_id,facture_fournisseur_id,mp_id_ou_service,quantite,prix_unitaire,total_ht) VALUES
('DEMO26_LFF1','DEMO26_FF1','DEMO26_MP1',1000,80,80000);
INSERT INTO public.ordres_fabrication (of_id,pf_id,recette_id,sku_id,quantite_prevue,quantite_produite,date_planification,statut,notes) VALUES
('DEMO26_OF1','DEMO26_PF1','DEMO26_REC1','DEMO26_SKU1',500,200,'2026-11-02','EN_COURS','FICTIF - simulation'),
('DEMO26_OF2','DEMO26_PF2','DEMO26_REC2','DEMO26_SKU2',100,0,'2026-11-04','PLANIFIE','FICTIF - simulation');
INSERT INTO public.consommations_of (consommation_id,of_id,mp_id,lot_id,quantite_consommee) VALUES
('DEMO26_CONS1','DEMO26_OF1','DEMO26_MP1','DEMO26_LOT1',60);
INSERT INTO public.controle_qualite (qc_id,of_id,date,conforme,remarques) VALUES
('DEMO26_QC1','DEMO26_OF1','2026-11-04','NON','FICTIF - rejet simulé');
INSERT INTO public.reglements (reglement_id,date_reglement,type_flux,partenaire_id,compte_id,mode_paiement,reference_trace,montant_total,montant_alloue,statut) VALUES
('DEMO26_RG1','2026-11-04','ENCAISSEMENT','DEMO26_CLI1','DEMO26_BANK','VIREMENT','FICTIF-01',3000,3000,'VALIDE'),
('DEMO26_RG2','2026-11-04','DECAISSEMENT','DEMO26_FOU2','DEMO26_BANK','VIREMENT','FICTIF-02',5000,0,'VALIDE');
INSERT INTO public.lettrage (lettrage_id,date,reglement_id,document_id,type_document,montant_applique) VALUES
('DEMO26_LET1','2026-11-04','DEMO26_RG1','DEMO26_FAC1','FactureClient',3000);
INSERT INTO public.projets (projet_id,nom,client_id,date_debut,date_fin_prevue,statut) VALUES
('DEMO26_PRJ1','[FICTIF] Chantier test','DEMO26_CLI1','2026-11-01','2027-01-31','EN_COURS');
INSERT INTO public.taches (tache_id,projet_id,assigne_a,statut,date_echeance) VALUES
('DEMO26_TASK1','DEMO26_PRJ1','DEMO26_EMP1','EN_COURS','2026-11-15');
INSERT INTO public.demandes_conges (demande_conge_id,employe_id,date_debut,date_fin,motif,statut) VALUES
('DEMO26_CONGE1','DEMO26_EMP1','2026-12-01','2026-12-05','FICTIF - RH','EN_ATTENTE');
INSERT INTO public.feuilles_de_temps (feuille_temps_id,employe_id,tache_id,date,heures) VALUES
('DEMO26_FT1','DEMO26_EMP1','DEMO26_TASK1','2026-11-04',7);
INSERT INTO public.fiches_de_paie (fiche_paie_id,employe_id,mois,annee,salaire_base,primes,retenues,net_a_payer,statut_paiement) VALUES
('DEMO26_FP1','DEMO26_EMP1',11,2026,50000,0,0,50000,'BROUILLON');
INSERT INTO public.appels_offres (ao_id,besoin_description,mp_id,date_limite,statut) VALUES
('DEMO26_AO1','FICTIF - achat test','DEMO26_MP1','2026-12-01','OUVERT');
INSERT INTO public.reponses_appels_offres (reponse_ao_id,ao_id,fournisseur_id,prix_propose,delai_propose,date_reponse) VALUES
('DEMO26_RAO1','DEMO26_AO1','DEMO26_FOU1',80,'7 jours','2026-11-04');
INSERT INTO public.mouvements (mouvement_id,date,type_mouvement,mp_id,quantite,reference,lot_id,prix_entree) VALUES
('DEMO26_MV1','2026-11-04','ENTREE','DEMO26_MP1',100,'DEMO26_BR1','DEMO26_LOT1',80);
INSERT INTO public.mouvements_pf (mouvement_pf_id,date,type_mouvement,sku_id,quantite,reference,lot_id,cout_unitaire) VALUES
('DEMO26_MVP1','2026-11-04','ENTREE','DEMO26_SKU1',180,'DEMO26_OF1','DEMO26_LOT2',1000);
INSERT INTO public.erp_sku_fiscalite (sku_id,date_effet,statut,justification) VALUES
('DEMO26_SKU1','2026-11-01','A_VALIDER','FICTIF - pas de qualification légale'),
('DEMO26_SKU2','2026-11-01','A_VALIDER','FICTIF - pas de qualification légale');
INSERT INTO public.paie_periodes_v2 (periode_id,annee,mois,statut) VALUES
('DEMO26_PER11',2026,11,'OUVERTE');
INSERT INTO public.paie_bulletins_v2 (bulletin_id,employe_id,periode_id,date_paie,salaire_brut,assiette_sociale,assiette_irg,cotisation_salarie,cotisation_employeur,irg,autres_retenues,net_a_payer,preuve_calcul,statut) VALUES
('90000000-0026-4026-8026-000000000001','DEMO26_EMP1','DEMO26_PER11','2026-11-05',50000,50000,50000,0,0,0,0,50000,'{"simulation":true,"taux_non_valides":true}'::jsonb,'PREPARE');
INSERT INTO public.scf_exercices (exercice_id,date_debut,date_fin,statut) VALUES
('DEMO26_SCF2026','2026-01-01','2026-12-31','OUVERT');
INSERT INTO public.scf_journaux (code_journal,libelle) VALUES
('DEMO26_JRN','[FICTIF] Journal test');
INSERT INTO public.scf_plan_comptes (numero_compte,libelle,actif,mouvementable) VALUES
('41199926','[FICTIF] Client test',TRUE,TRUE),
('70199926','[FICTIF] Vente test',TRUE,TRUE);
INSERT INTO public.scf_pieces (piece_id,exercice_id,code_journal,reference,document_source,date_ecriture,libelle,statut) VALUES
('90000000-0026-4026-8026-000000000002','DEMO26_SCF2026','DEMO26_JRN','DEMO26_PIECE1','DEMO26_FAC1','2026-11-04','FICTIF - pièce brouillon','BROUILLON');
INSERT INTO public.scf_lignes (ligne_id,piece_id,numero,compte,debit,credit) OVERRIDING SYSTEM VALUE VALUES
(-260002,'90000000-0026-4026-8026-000000000002',1,'41199926',1000,0),
(-260003,'90000000-0026-4026-8026-000000000002',2,'70199926',0,1000);
INSERT INTO public.paie_lignes_v2 (ligne_id,bulletin_id,numero,code,libelle,nature,montant) OVERRIDING SYSTEM VALUE VALUES
(-260001,'90000000-0026-4026-8026-000000000001',1,'SIM_BRUT','FICTIF - non validé','GAIN',50000);
COMMIT;
