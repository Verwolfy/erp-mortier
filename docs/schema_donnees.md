# PLAN DE RECONSTRUCTION COMPLÈTE — ERP Mortier, Adjuvants & Peinture

**Statut :** document de référence unique et figé (source de vérité). Toute reconstruction doit s'appuyer exclusivement sur les noms exacts définis ici — fichiers, onglets, colonnes, préfixes d'identifiants, listes de choix. Aucun nom ne doit être inventé ou renommé en cours de route.

---

## 1. Architecture globale et Règles de Nommage

**Convention de nommage figée, sans exception :**
- **Noms d'onglets** : `PascalCase`, sans underscore, sans accent (ex. `MatieresPremieres`).
- **Noms de colonnes** : `snake_case`, sans accent, tout en minuscules (ex. `stock_mini`).
- **Noms de fichiers Google Sheets** : `ERP_<Domaine>` (ex. `ERP_Referentiels`).
- **Listes de référence (`liste_code`)** : **Strictement en `PascalCase`** (ex: `CategorieClient`, `Pays`, `Wilaya`, `CategorieMP`, `UniteMesure`). Toute ancienne notation en majuscules avec underscores est abandonnée.
- **Statut actif** : S'écrit universellement `"OUI"` ou `"NON"` dans toute la base de données (y compris pour les listes de références).

---

## 2. Schéma de données — fichiers, onglets et colonnes

### 2.1 `ERP_Referentiels` *(module_name = `"referentiels"`)*

| Onglet | Colonnes (dans cet ordre exact) |
|---|---|
| `Fournisseurs` | `fournisseur_id, nom, categorie, type_entreprise, adresse, gps, pays, wilaya, rc, nif, nis, nom_contact, poste_contact, email_contact, mobile_contact, email_entreprise, site_web, telephone_fixe, delai_appro_jours, actif` |
| `MatieresPremieres` | `mp_id, nom, categorie_mp, unite_stock, origine_pays, duree_peremption_jours, fournisseurs_ids, actif, type_emballage, poids_net, cmp_actuel, stock_mini, stock_maxi, hs_code, taux_dedouanement, lien_fiche_technique, lien_fiche_securite` |
| `Produits` | `pf_id, nom, categorie_pf, recette_id, unite_production, actif` |
| `SkuConditionnement` | `sku_id, pf_id, format, emballage_mp_id, poids_net, unite_vente, facteur_conversion, prix_vente_defaut, actif` |
| `Clients` | `client_id, nom, categorie_client, type_client, adresse, gps, pays, wilaya, rc, nif, nis, nom_contact, poste_contact, email_contact, mobile_contact, email_entreprise, site_web, telephone_fixe, commercial_id, actif` |
| `Contrats` | `contrat_id, client_id, date_debut, date_fin, grille_tarifaire_id, renouvellement_auto, conditions, actif` |
| `GrillesTarifaires` | `grille_id, client_id_ou_categorie, sku_id, prix_negocie, remise_pct, date_debut, date_fin` |
| `Parametres` | `cle, valeur` |
| `Users` | `user_id, nom, login, hash_mdp, role, actif` |
| `Permissions` | `role, module, lecture, ecriture` |
| `Compteurs` | `type_document, prefixe, annee, dernier_numero` |
| `ListesReference` | `liste_code, parent_code, valeur_code, valeur_libelle, ordre, actif` |

### 2.2 `ERP_Achats` *(module_name = `"achats"`)*

| Onglet | Colonnes |
|---|---|
| `CommandesAchats` | `commande_achat_id, date_commande, fournisseur_id, type_achat, devise, taux_change, montant_total_devise, montant_total_local, mode_paiement, delai_paiement, date_voulue, statut` |
| `LignesAchats` | `ligne_achat_id, commande_achat_id, mp_id, unite_cond, qte_cond, qte_totale, prix_unitaire, total_devise` |
| `AppelsOffres` | `ao_id, besoin_description, mp_id, date_limite, statut` |
| `ReponsesAppelsOffres` | `reponse_ao_id, ao_id, fournisseur_id, prix_propose, delai_propose, date_reponse` |
| `BonsReception` | `bon_reception_id, commande_achat_id, date_reception, controle_conformite, remarques` |
| `FacturesFournisseurs` | `facture_fournisseur_id, commande_achat_id, fournisseur_id, reference_facture_fournisseur, date, montant_ht, taux_tva, montant_tva, montant_ttc, statut_paiement` |

### 2.3 `ERP_Stocks` *(module_name = `"stocks"`)*

| Onglet | Colonnes |
|---|---|
| `Mouvements` | `mouvement_id, date, type_mouvement, mp_id, quantite, reference, lot_id, prix_entree` |
| `MouvementsPf` | `mouvement_pf_id, date, type_mouvement, sku_id, quantite, reference, lot_id, cout_unitaire` |
| `Lots` | `lot_id, item_id, type_item, date_creation, date_peremption, quantite_initiale, quantite_restante, statut` |
| `StockActuel` | `mp_id, quantite_disponible, cmp_actuel, derniere_maj` |
| `StockActuelPf` | `sku_id, quantite_disponible, cout_revient, derniere_maj` |

### 2.4 `ERP_Production` *(module_name = `"production"`)*

| Onglet | Colonnes |
|---|---|
| `Recettes` | `recette_id, pf_id, version, rendement_unite, instructions, date_effet, actif` |
| `LignesRecette` | `ligne_recette_id, recette_id, mp_id, quantite_par_unite` |
| `OrdresFabrication` | `of_id, pf_id, recette_id, sku_id, quantite_prevue, quantite_produite, date_planification, date_debut, date_fin, statut, cout_total, notes` |
| `ControleQualite` | `qc_id, of_id, date, conforme, remarques, controleur` |

### 2.5 `ERP_Ventes` *(module_name = `"ventes"`)*

| Onglet | Colonnes |
|---|---|
| `Devis` | `devis_id, client_id, date, validite, statut, commercial_id` |
| `LignesDevis` | `ligne_devis_id, devis_id, sku_id, quantite, prix_unitaire, remise_pct` |
| `CommandesVentes` | `commande_vente_id, devis_id, client_id, date, statut` |
| `LignesCommandeVentes` | `ligne_commande_vente_id, commande_vente_id, sku_id, quantite, prix_unitaire` |
| `BonsLivraison` | `bl_id, commande_vente_id, date, transporteur, zone, statut` |
| `Factures` | `facture_id, commande_vente_id, client_id, date, montant_ht, taux_tva, montant_tva, montant_ttc, montant_paye, statut, date_echeance, montant_timbre, type_facture, facture_origine_id, remise_globale` |
| `LignesFacture` | `ligne_facture_id, facture_id, sku_id, quantite, prix_unitaire, remise_ligne, total_ligne_ht` |

### 2.6 `ERP_Finance` *(module_name = `"finance"`)*

| Onglet | Colonnes |
|---|---|
| `Comptes` | `compte_id, nom_compte, type_compte, numero_compte, solde_initial, statut` |
| `Reglements` | `reglement_id, date_reglement, type_flux, partenaire_id, compte_id, mode_paiement, reference_trace, montant_total, montant_alloue, statut` |
| `Lettrage` | `lettrage_id, date, reglement_id, document_id, type_document, montant_applique` |

### 2.7 `ERP_Crm` *(module_name = `"crm"`)*

| Onglet | Colonnes |
|---|---|
| `Interactions` | `interaction_id, client_id, date_creation, type_action, notes, date_rappel, statut_rappel` |
| `Pipeline` | `opportunite_id, prospect_nom, contact, statut, commercial_id, valeur_estimee, probabilite_pct, date_creation, date_derniere_action` |

### 2.8 `ERP_Rh` *(module_name = `"rh"`)*

| Onglet | Colonnes |
|---|---|
| `Employes` | `employe_id, nom, poste, service, manager_id, date_embauche, actif` |
| `DemandesConges` | `demande_conge_id, employe_id, date_debut, date_fin, motif, statut` |
| `Projets` | `projet_id, nom, client_id, date_debut, date_fin_prevue, statut` |
| `Taches` | `tache_id, projet_id, assigne_a, statut, date_echeance` |
| `FeuillesDeTemps` | `feuille_temps_id, employe_id, tache_id, date, heures` |

### 2.9 `ERP_Logs` *(module_name = `"logs"`)*

| Onglet | Colonnes |
|---|---|
| `AuditTrail` | `timestamp, user_id, module, action, detail` |
| `Erreurs` | `timestamp, module, message, contexte` |

---

## 3. Listes de référence et menus déroulants

Une seule table `ListesReference` (dans `ERP_Referentiels`) pilote tous les menus déroulants.
La cascade Pays→Wilaya utilise le format `parent_code = f"Pays:{code_pays_selectionne}"`.

**Valeurs Fallbacks (de secours) validées :**
- `Pays` : DZ, FR, CN, TR, ES, IT, DE, AE, EG, TN, MA, LY, MR, Autre
- `Wilaya` : 01 à 58
- `CategorieClient` : PARTICULIER, PRO_BTP, REVENDEUR, NEGOCE, PROMOTEUR, ENTREPRISE_CONSTRUCTION, MARCHE_PUBLIC, EXPORT
- `UniteMesure` : Kg, Litre, Sac, Palette, Unité, Fût, Seau, Tonne
- `CategorieMP` : LIANT, GRANULAT, ADJUVANT_CHIMIQUE, RESINE_LIANT_POLYMERE, PIGMENT_COLORANT, SOLVANT, ADDITIF_PEINTURE, FIBRE, **EMBALLAGE_CONSOMMABLE**
- `CategoriePF` : ENDUIT_MONOCOUCHE, ENDUIT_PAREMENT, MORTIER_SCELLEMENT, MORTIER_REPARATION, CHAPE_FLUIDE_AUTONIVELANTE, RAGREAGE_AUTOLISSANT, CIMENT_COLLE, MORTIER_BATARD, MORTIER_REFRACTAIRE, MORTIER_JOINT_ASSISE, SUPERPLASTIFIANT, PLASTIFIANT_REDUCTEUR_EAU, PEINTURE_BATIMENT_INTERIEUR, PEINTURE_FACADE_EXTERIEUR, VERNIS
- `HSCode` : 2523.10, 2523.21, 2523.29, 2523.30, 2523.90, 2521.00, 3824.40, 3824.50, 3208, 3209, 3210, 3206, 6810

---

## 4. Gouvernance des identifiants (Préfixes stricts)

| Catégorie | Préfixe Séquentiel (PREFIXE-0001) |
|---|---|
| Référentiels | Fournisseurs (`FRN`), MatieresPremieres (`MP`), Produits (`PF`), Sku (`SKU`), Clients (`CLI`), Contrats (`CTR`), Users (`USR`) |
| Achats | CommandesAchats (`CMA`), AppelsOffres (`AO`), BonsReception (`BR`) |
| Production | Recettes (`REC`), OrdresFabrication (`OF`) |
| Ventes | Devis (`DEV`), CommandesVentes (`CDV`), BonsLivraison (`BL`), Factures (`FAC-AAAA-XXXXXX` compteur légal) |
| Finance / RH | Comptes (`CPT`), Employes (`EMP`), Projets (`PRJ`) |

| Catégorie | Préfixe Technique UUID (PREFIXE-uuid) |
|---|---|
| Lignes | LignesAchats (`LAC`), LignesRecette (`LRC`), LignesFacture (`LFA`) |
| Mouvements | Mouvements (`MOUV`), MouvementsPf (`MOUVPF`), Lots (`LOT`), ControleQualite (`QC`) |
| Trésorerie | Reglements (`REGF`), Lettrage (`LET`) |
| CRM / RH | Interactions (`INT`), DemandesConges (`CNG`), Taches (`TCH`), FeuillesDeTemps (`FDT`), ReponsesAppelsOffres (`RAO`) |