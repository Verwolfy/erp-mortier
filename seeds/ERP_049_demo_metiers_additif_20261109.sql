-- ERP-049 / Données de démonstration, Algérie - 2026-11-09.
-- DONNEES FICTIVES : non comptables, non fiscales, non juridiques.
-- Cible : Supabase principal en phase essais, jamais la base TEST inactive.
-- Additif et idempotent par identifiants fixes. Aucun effacement ou modification.
-- Exécuter dans une transaction et vérifier les comptes avant COMMIT.
-- NE PAS insérer manuellement des écritures, stocks, mouvements, pièces fiscales,
-- paiements, habilitations, logs, secrets, preuves juridiques ou consentements web.
-- Convention : préfixe SIM-ERP49- ; identifications explicites SIMULATION.

INSERT INTO public.employes (employe_id,nom,poste,service,actif)
VALUES
('SIM-ERP49-EMP-COM','SIMULATION - Conseiller commercial','Commercial de démonstration','Ventes','NON'),
('SIM-ERP49-EMP-ATELIER','SIMULATION - Technicien atelier','Planificateur de démonstration','Production','NON')
ON CONFLICT (employe_id) DO NOTHING;

INSERT INTO public.clients (client_id,nom,categorie_client,type_client,pays,wilaya,nom_contact,commercial_id,actif)
VALUES
('SIM-ERP49-CLI-BTP','SIMULATION - Entreprise pose de carrelage','PROFESSIONNEL','ENTREPRISE','Algérie','Alger','Contact fictif - sans identité réelle','SIM-ERP49-EMP-COM','NON'),
('SIM-ERP49-CLI-NEGOCE','SIMULATION - Négociant matériaux','DISTRIBUTEUR','ENTREPRISE','Algérie','Oran','Contact fictif - sans identité réelle','SIM-ERP49-EMP-COM','NON')
ON CONFLICT (client_id) DO NOTHING;

INSERT INTO public.fournisseurs (fournisseur_id,nom,categorie,type_entreprise,pays,wilaya,delai_appro_jours,actif)
VALUES
('SIM-ERP49-FOUR-LIANTS','SIMULATION - Fournisseur liants et charges','MATIERES_PREMIERES','ENTREPRISE','Algérie','Blida',7,'NON'),
('SIM-ERP49-FOUR-ADJ','SIMULATION - Fournisseur adjuvants','MATIERES_PREMIERES','ENTREPRISE','Algérie','Alger',14,'NON')
ON CONFLICT (fournisseur_id) DO NOTHING;

INSERT INTO public.matieres_premieres (mp_id,nom,categorie_mp,unite_stock,origine_pays,actif,stock_mini,stock_maxi,cmp_actuel)
VALUES
('SIM-ERP49-MP-CIMENT','SIMULATION - Liant cimentaire','LIANT','KG','Algérie','NON',0,0,0),
('SIM-ERP49-MP-SABLE','SIMULATION - Charge siliceuse','CHARGE','KG','Algérie','NON',0,0,0),
('SIM-ERP49-MP-POLYMERE','SIMULATION - Polymère redispersable','ADJUVANT','KG','Non renseigné','NON',0,0,0)
ON CONFLICT (mp_id) DO NOTHING;

INSERT INTO public.produits (pf_id,nom,categorie_pf,unite_production,actif)
VALUES
('SIM-ERP49-PF-COLLE','SIMULATION - Mortier-colle carrelage (prototype non commercial)','MORT_COLLE','KG','NON'),
('SIM-ERP49-PF-JOINT','SIMULATION - Mortier de jointoiement (prototype non commercial)','MORT_JOINTS','KG','NON')
ON CONFLICT (pf_id) DO NOTHING;

INSERT INTO public.sku_conditionnement
(sku_id,pf_id,format,poids_net,unite_vente,facteur_conversion,prix_vente_defaut,actif)
VALUES
('SIM-ERP49-SKU-COLLE25','SIM-ERP49-PF-COLLE','Sac 25 kg',25,'SAC',25,850,'NON'),
('SIM-ERP49-SKU-JOINT5','SIM-ERP49-PF-JOINT','Sac 5 kg',5,'SAC',5,250,'NON')
ON CONFLICT (sku_id) DO NOTHING;

-- Recettes uniquement pour tests de saisie ; NON validées pour fabrication.
INSERT INTO public.recettes
(recette_id,pf_id,version,rendement_unite,instructions,date_effet,actif)
VALUES
('SIM-ERP49-REC-COLLE','SIM-ERP49-PF-COLLE','SIMULATION-1',1000,
 'SIMULATION UNIQUEMENT - composition illustrative, ne pas fabriquer ni homologuer.',
 '2026-11-09','NON'),
('SIM-ERP49-REC-JOINT','SIM-ERP49-PF-JOINT','SIMULATION-1',500,
 'SIMULATION UNIQUEMENT - composition illustrative, ne pas fabriquer ni homologuer.',
 '2026-11-09','NON')
ON CONFLICT (recette_id) DO NOTHING;

INSERT INTO public.lignes_recette (ligne_recette_id,recette_id,mp_id,quantite_par_unite)
VALUES
('SIM-ERP49-LREC-C1','SIM-ERP49-REC-COLLE','SIM-ERP49-MP-CIMENT',0.35),
('SIM-ERP49-LREC-C2','SIM-ERP49-REC-COLLE','SIM-ERP49-MP-SABLE',0.62),
('SIM-ERP49-LREC-C3','SIM-ERP49-REC-COLLE','SIM-ERP49-MP-POLYMERE',0.03),
('SIM-ERP49-LREC-J1','SIM-ERP49-REC-JOINT','SIM-ERP49-MP-CIMENT',0.25),
('SIM-ERP49-LREC-J2','SIM-ERP49-REC-JOINT','SIM-ERP49-MP-SABLE',0.70),
('SIM-ERP49-LREC-J3','SIM-ERP49-REC-JOINT','SIM-ERP49-MP-POLYMERE',0.05)
ON CONFLICT (ligne_recette_id) DO NOTHING;

INSERT INTO public.pipeline (opportunite_id,prospect_nom,contact,statut,commercial_id,valeur_estimee,probabilite_pct,date_creation,date_derniere_action)
VALUES
('SIM-ERP49-OPP-1','SIMULATION - Projet de rénovation', 'Contact fictif','QUALIFICATION',
 'SIM-ERP49-EMP-COM',150000,30,'2026-11-09','2026-11-09')
ON CONFLICT (opportunite_id) DO NOTHING;

INSERT INTO public.interactions (interaction_id,client_id,date_creation,type_action,notes,date_rappel,statut_rappel)
VALUES
('SIM-ERP49-INT-1','SIM-ERP49-CLI-BTP','2026-11-09','APPEL',
 'SIMULATION - demande fictive de 40 sacs de mortier-colle, aucun client réel.',
 '2026-11-16','A_FAIRE')
ON CONFLICT (interaction_id) DO NOTHING;

INSERT INTO public.devis (devis_id,client_id,"date",validite,statut,commercial_id)
VALUES
('SIM-ERP49-DEV-1','SIM-ERP49-CLI-BTP','2026-11-09','2026-12-09',
 'BROUILLON','SIM-ERP49-EMP-COM')
ON CONFLICT (devis_id) DO NOTHING;

INSERT INTO public.lignes_devis (ligne_devis_id,devis_id,sku_id,quantite,prix_unitaire,remise_pct)
VALUES
('SIM-ERP49-LDEV-1','SIM-ERP49-DEV-1','SIM-ERP49-SKU-COLLE25',40,850,0)
ON CONFLICT (ligne_devis_id) DO NOTHING;

-- Commande commerciale SIMULATION, aucun brouillon de facture ni montant TVA.
INSERT INTO public.commandes_ventes (commande_vente_id,devis_id,client_id,"date",statut)
VALUES
('SIM-ERP49-CV-1','SIM-ERP49-DEV-1','SIM-ERP49-CLI-BTP','2026-11-09','EN_ATTENTE')
ON CONFLICT (commande_vente_id) DO NOTHING;

INSERT INTO public.lignes_commande_ventes
(ligne_commande_vente_id,commande_vente_id,sku_id,quantite,prix_unitaire)
VALUES
('SIM-ERP49-LCV-1','SIM-ERP49-CV-1','SIM-ERP49-SKU-COLLE25',40,850)
ON CONFLICT (ligne_commande_vente_id) DO NOTHING;

-- Achat fictif non réceptionné ; pas de mouvement de stock.
INSERT INTO public.commandes_achats
(commande_achat_id,date_commande,fournisseur_id,type_achat,devise,taux_change,
montant_total_devise,montant_total_local,mode_paiement,delai_paiement,date_voulue,statut)
VALUES
('SIM-ERP49-CA-1','2026-11-09','SIM-ERP49-FOUR-LIANTS','MATIERE_PREMIERE',
 'DZD',1,10000,10000,'VIREMENT','30 JOURS','2026-11-20','EN_ATTENTE')
ON CONFLICT (commande_achat_id) DO NOTHING;

INSERT INTO public.lignes_achats
(ligne_achat_id,commande_achat_id,mp_id,unite_cond,qte_cond,qte_totale,prix_unitaire,total_devise)
VALUES
('SIM-ERP49-LCA-1','SIM-ERP49-CA-1','SIM-ERP49-MP-CIMENT','KG',100,100,100,10000)
ON CONFLICT (ligne_achat_id) DO NOTHING;

-- OF uniquement PLANIFIÉ ; aucune consommation réelle ni stock de produits finis.
INSERT INTO public.ordres_fabrication
(of_id,pf_id,recette_id,sku_id,quantite_prevue,quantite_produite,
date_planification,statut,cout_total,notes)
VALUES
('SIM-ERP49-OF-1','SIM-ERP49-PF-COLLE','SIM-ERP49-REC-COLLE',
 'SIM-ERP49-SKU-COLLE25',40,0,'2026-11-10','PLANIFIE',0,
 'SIMULATION - OF non exécutable ; recette prototype non validée.')
ON CONFLICT (of_id) DO NOTHING;

INSERT INTO public.projets (projet_id,nom,client_id,date_debut,date_fin_prevue,statut)
VALUES
('SIM-ERP49-PROJ-1','SIMULATION - Chantier carrelage démonstration',
 'SIM-ERP49-CLI-BTP','2026-11-09','2026-12-20','PLANIFIE')
ON CONFLICT (projet_id) DO NOTHING;

INSERT INTO public.taches (tache_id,projet_id,assigne_a,statut,date_echeance)
VALUES
('SIM-ERP49-TACHE-1','SIM-ERP49-PROJ-1','SIM-ERP49-EMP-ATELIER',
 'A_FAIRE','2026-11-18')
ON CONFLICT (tache_id) DO NOTHING;

INSERT INTO public.feuilles_de_temps (feuille_temps_id,employe_id,tache_id,"date",heures)
VALUES
('SIM-ERP49-TEMPS-1','SIM-ERP49-EMP-ATELIER','SIM-ERP49-TACHE-1',
 '2026-11-09',2.5)
ON CONFLICT (feuille_temps_id) DO NOTHING;

INSERT INTO public.demandes_conges
(demande_conge_id,employe_id,date_debut,date_fin,motif,statut)
VALUES
('SIM-ERP49-CONGE-1','SIM-ERP49-EMP-COM','2026-12-14','2026-12-15',
 'SIMULATION - congé non réel','BROUILLON')
ON CONFLICT (demande_conge_id) DO NOTHING;

INSERT INTO public.grilles_tarifaires
(grille_id,client_id_ou_categorie,sku_id,prix_negocie,remise_pct,date_debut,date_fin)
VALUES
('SIM-ERP49-GRILLE-1','SIM-ERP49-CLI-BTP',
 'SIM-ERP49-SKU-COLLE25',800,0,'2026-11-09','2026-12-31')
ON CONFLICT (grille_id) DO NOTHING;

INSERT INTO public.contrats
(contrat_id,client_id,date_debut,date_fin,grille_tarifaire_id,renouvellement_auto,conditions,actif)
VALUES
('SIM-ERP49-CONTRAT-1','SIM-ERP49-CLI-BTP','2026-11-09','2026-12-31',
 'SIM-ERP49-GRILLE-1','NON',
 'SIMULATION - contrat fictif sans valeur juridique, sans signature.','NON')
ON CONFLICT (contrat_id) DO NOTHING;

INSERT INTO public.appels_offres
(ao_id,besoin_description,mp_id,date_limite,statut)
VALUES
('SIM-ERP49-AO-1','SIMULATION - consultation fournisseur pour liant cimentaire',
 'SIM-ERP49-MP-CIMENT','2026-11-25','BROUILLON')
ON CONFLICT (ao_id) DO NOTHING;

INSERT INTO public.reponses_appels_offres
(reponse_ao_id,ao_id,fournisseur_id,prix_propose,delai_propose,date_reponse)
VALUES
('SIM-ERP49-RAO-1','SIM-ERP49-AO-1','SIM-ERP49-FOUR-LIANTS',
 10000,'7 jours - SIMULATION','2026-11-09')
ON CONFLICT (reponse_ao_id) DO NOTHING;

-- Comptabilité analytique : simulation SANS pièce SCF, sans validation.
INSERT INTO public.erp_cost_periods (period_id,libelle,date_debut,date_fin,statut)
VALUES
('SIM-ERP49-COST-P1','SIMULATION - Novembre 2026',
 DATE '2026-11-01', DATE '2026-11-30','BROUILLON')
ON CONFLICT (period_id) DO NOTHING;

INSERT INTO public.erp_cost_pools
(pool_id,period_id,nature_code,base_imputation,montant_dzd,justificatif,statut)
VALUES
('SIM-ERP49-COST-POOL1','SIM-ERP49-COST-P1','ENERGIE','HOURS_MACHINE',
 12500,'SIMULATION - charge fictive, aucune pièce comptable opposable','SIMULATION')
ON CONFLICT (pool_id) DO NOTHING;

INSERT INTO public.erp_cost_drivers
(period_id,of_id,base_imputation,valeur,justificatif)
VALUES
('SIM-ERP49-COST-P1','SIM-ERP49-OF-1','HOURS_MACHINE',
 8,'SIMULATION - 8 heures machine fictives pour calcul test')
ON CONFLICT (period_id,of_id,base_imputation) DO NOTHING;

-- Marqueur strictement technique, aucun taux légal.
INSERT INTO public.parametres (cle,valeur)
VALUES ('SIM_ERP49_JEU_DE_TEST', '2026-11-09|simulation|sans portee fiscale ou juridique')
ON CONFLICT (cle) DO NOTHING;
