"""
Service de base de données hybride (Supabase + Google Sheets).
Lit depuis Supabase (SQL). Écrit dans Supabase ET Google Sheets (Dual-Write).
Le schéma est centralisé ici pour éviter les erreurs de frappe.
Intègre une piste d'audit automatique ET UN CONTRÔLE DE DROITS SERVEUR.
"""
import streamlit as st
from supabase import create_client, Client
from core.sheets_service import append_rows_batch, update_multiple_cells_by_id
from core.logger import log_error
from config.roles import has_permission

# ==========================================
# DICTIONNAIRE CENTRAL DU SCHÉMA DE DONNÉES
# ==========================================
SCHEMA_CONFIG = {
    # --- REFERENTIELS ---
    "fournisseurs": {"module": "referentiels", "sheet": "Fournisseurs", "cols": ["fournisseur_id", "nom", "categorie", "type_entreprise", "adresse", "gps", "pays", "wilaya", "rc", "nif", "nis", "nom_contact", "poste_contact", "email_contact", "mobile_contact", "email_entreprise", "site_web", "telephone_fixe", "delai_appro_jours", "actif"]},
    "matieres_premieres": {"module": "referentiels", "sheet": "MatieresPremieres", "cols": ["mp_id", "nom", "categorie_mp", "unite_stock", "origine_pays", "duree_peremption_jours", "fournisseurs_ids", "actif", "type_emballage", "poids_net", "cmp_actuel", "stock_mini", "stock_maxi", "hs_code", "taux_dedouanement", "lien_fiche_technique", "lien_fiche_securite"]},
    "produits": {"module": "referentiels", "sheet": "Produits", "cols": ["pf_id", "nom", "categorie_pf", "recette_id", "unite_production", "actif"]},
    "sku_conditionnement": {"module": "referentiels", "sheet": "SkuConditionnement", "cols": ["sku_id", "pf_id", "format", "emballage_mp_id", "poids_net", "unite_vente", "facteur_conversion", "prix_vente_defaut", "actif"]},
    "clients": {"module": "referentiels", "sheet": "Clients", "cols": ["client_id", "nom", "categorie_client", "type_client", "adresse", "gps", "pays", "wilaya", "rc", "nif", "nis", "nom_contact", "poste_contact", "email_contact", "mobile_contact", "email_entreprise", "site_web", "telephone_fixe", "commercial_id", "actif"]},
    "contrats": {"module": "referentiels", "sheet": "Contrats", "cols": ["contrat_id", "client_id", "date_debut", "date_fin", "grille_tarifaire_id", "renouvellement_auto", "conditions", "actif"]},
    "grilles_tarifaires": {"module": "referentiels", "sheet": "GrillesTarifaires", "cols": ["grille_id", "client_id_ou_categorie", "sku_id", "prix_negocie", "remise_pct", "date_debut", "date_fin"]},
    "parametres": {"module": "referentiels", "sheet": "Parametres", "cols": ["cle", "valeur"]},
    "users": {"module": "referentiels", "sheet": "Users", "cols": ["user_id", "nom", "login", "hash_mdp", "role", "actif"]},
    "permissions": {"module": "referentiels", "sheet": "Permissions", "cols": ["role", "module", "lecture", "ecriture"]},
    "compteurs": {"module": "referentiels", "sheet": "Compteurs", "cols": ["type_document", "prefixe", "annee", "dernier_numero"]},
    "listes_reference": {"module": "referentiels", "sheet": "ListesReference", "cols": ["liste_code", "parent_code", "valeur_code", "valeur_libelle", "ordre", "actif"]},

    # --- ACHATS ---
    "commandes_achats": {"module": "achats", "sheet": "CommandesAchats", "cols": ["commande_achat_id", "date_commande", "fournisseur_id", "type_achat", "devise", "taux_change", "montant_total_devise", "montant_total_local", "mode_paiement", "delai_paiement", "date_voulue", "statut"]},
    "lignes_achats": {"module": "achats", "sheet": "LignesAchats", "cols": ["ligne_achat_id", "commande_achat_id", "mp_id", "unite_cond", "qte_cond", "qte_totale", "prix_unitaire", "total_devise"]},
    "appels_offres": {"module": "achats", "sheet": "AppelsOffres", "cols": ["ao_id", "besoin_description", "mp_id", "date_limite", "statut"]},
    "reponses_appels_offres": {"module": "achats", "sheet": "ReponsesAppelsOffres", "cols": ["reponse_ao_id", "ao_id", "fournisseur_id", "prix_propose", "delai_propose", "date_reponse"]},
    "bons_reception": {"module": "achats", "sheet": "BonsReception", "cols": ["bon_reception_id", "commande_achat_id", "date_reception", "controle_conformite", "remarques"]},
    "factures_fournisseurs": {"module": "achats", "sheet": "FacturesFournisseurs", "cols": ["facture_fournisseur_id", "commande_achat_id", "fournisseur_id", "reference_facture_fournisseur", "date", "montant_ht", "taux_tva", "montant_tva", "montant_ttc", "statut_paiement"]},

    # --- STOCKS ---
    "mouvements": {"module": "stocks", "sheet": "Mouvements", "cols": ["mouvement_id", "date", "type_mouvement", "mp_id", "quantite", "reference", "lot_id", "prix_entree"]},
    "mouvements_pf": {"module": "stocks", "sheet": "MouvementsPf", "cols": ["mouvement_pf_id", "date", "type_mouvement", "sku_id", "quantite", "reference", "lot_id", "cout_unitaire"]},
    "lots": {"module": "stocks", "sheet": "Lots", "cols": ["lot_id", "item_id", "type_item", "date_creation", "date_peremption", "quantite_initiale", "quantite_restante", "statut"]},
    "stock_actuel": {"module": "stocks", "sheet": "StockActuel", "cols": ["mp_id", "quantite_disponible", "cmp_actuel", "derniere_maj"]},
    "stock_actuel_pf": {"module": "stocks", "sheet": "StockActuelPf", "cols": ["sku_id", "quantite_disponible", "cout_revient", "derniere_maj"]},

    # --- PRODUCTION ---
    "recettes": {"module": "production", "sheet": "Recettes", "cols": ["recette_id", "pf_id", "version", "rendement_unite", "instructions", "date_effet", "actif"]},
    "lignes_recette": {"module": "production", "sheet": "LignesRecette", "cols": ["ligne_recette_id", "recette_id", "mp_id", "quantite_par_unite"]},
    "ordres_fabrication": {"module": "production", "sheet": "OrdresFabrication", "cols": ["of_id", "pf_id", "recette_id", "sku_id", "quantite_prevue", "quantite_produite", "date_planification", "date_debut", "date_fin", "statut", "cout_total", "notes"]},
    "controle_qualite": {"module": "production", "sheet": "ControleQualite", "cols": ["qc_id", "of_id", "date", "conforme", "remarques", "controleur"]},

    # --- VENTES ---
    "devis": {"module": "ventes", "sheet": "Devis", "cols": ["devis_id", "client_id", "date", "validite", "statut", "commercial_id"]},
    "lignes_devis": {"module": "ventes", "sheet": "LignesDevis", "cols": ["ligne_devis_id", "devis_id", "sku_id", "quantite", "prix_unitaire", "remise_pct"]},
    "commandes_ventes": {"module": "ventes", "sheet": "CommandesVentes", "cols": ["commande_vente_id", "devis_id", "client_id", "date", "statut"]},
    "lignes_commande_ventes": {"module": "ventes", "sheet": "LignesCommandeVentes", "cols": ["ligne_commande_vente_id", "commande_vente_id", "sku_id", "quantite", "prix_unitaire"]},
    "bons_livraison": {"module": "ventes", "sheet": "BonsLivraison", "cols": ["bl_id", "commande_vente_id", "date", "transporteur", "zone", "statut"]},
    "factures": {"module": "ventes", "sheet": "Factures", "cols": ["facture_id", "commande_vente_id", "client_id", "date", "montant_ht", "taux_tva", "montant_tva", "montant_ttc", "montant_paye", "statut", "date_echeance", "montant_timbre", "type_facture", "facture_origine_id", "remise_globale"]},
    "lignes_facture": {"module": "ventes", "sheet": "LignesFacture", "cols": ["ligne_facture_id", "facture_id", "sku_id", "quantite", "prix_unitaire", "remise_ligne", "total_ligne_ht"]},

    # --- FINANCE ---
    "comptes": {"module": "finance", "sheet": "Comptes", "cols": ["compte_id", "nom_compte", "type_compte", "numero_compte", "solde_initial", "statut"]},
    "reglements": {"module": "finance", "sheet": "Reglements", "cols": ["reglement_id", "date_reglement", "type_flux", "partenaire_id", "compte_id", "mode_paiement", "reference_trace", "montant_total", "montant_alloue", "statut"]},
    "lettrage": {"module": "finance", "sheet": "Lettrage", "cols": ["lettrage_id", "date", "reglement_id", "document_id", "type_document", "montant_applique"]},

    # --- CRM ---
    "interactions": {"module": "crm", "sheet": "Interactions", "cols": ["interaction_id", "client_id", "date_creation", "type_action", "notes", "date_rappel", "statut_rappel"]},
    "pipeline": {"module": "crm", "sheet": "Pipeline", "cols": ["opportunite_id", "prospect_nom", "contact", "statut", "commercial_id", "valeur_estimee", "probabilite_pct", "date_creation", "date_derniere_action"]},

    # --- RH ---
    "employes": {"module": "rh", "sheet": "Employes", "cols": ["employe_id", "nom", "poste", "service", "manager_id", "date_embauche", "actif"]},
    "demandes_conges": {"module": "rh", "sheet": "DemandesConges", "cols": ["demande_conge_id", "employe_id", "date_debut", "date_fin", "motif", "statut"]},
    "projets": {"module": "rh", "sheet": "Projets", "cols": ["projet_id", "nom", "client_id", "date_debut", "date_fin_prevue", "statut"]},
    "taches": {"module": "rh", "sheet": "Taches", "cols": ["tache_id", "projet_id", "assigne_a", "statut", "date_echeance"]},
    "feuilles_de_temps": {"module": "rh", "sheet": "FeuillesDeTemps", "cols": ["feuille_temps_id", "employe_id", "tache_id", "date", "heures"]},

    # --- LOGS ---
    "audit_trail": {"module": "logs", "sheet": "AuditTrail", "cols": ["timestamp", "user_id", "module", "action", "detail"]},
    "erreurs": {"module": "logs", "sheet": "Erreurs", "cols": ["timestamp", "module", "message", "contexte"]},
}

@st.cache_resource
def get_supabase_client() -> Client:
    """Initialise et retourne le client Supabase en utilisant les secrets de Streamlit."""
    url = st.secrets["supabase"]["url"]
    key = st.secrets["supabase"]["key"]
    return create_client(url, key)

def check_server_permission(table_name: str) -> bool:
    """NOUVEAU : Vérifie côté serveur si l'utilisateur a le droit d'écriture sur le module cible."""
    if not hasattr(st, "session_state") or "user" not in st.session_state:
        return False

    if table_name not in SCHEMA_CONFIG:
        return False # Sécurité absolue : si table non configurée, on bloque.

    # Mapping spécifique pour faire le lien entre le nom du module DB et vos rôles
    module_cible = SCHEMA_CONFIG[table_name]["module"]
    if module_cible in ["referentiels", "logs"]:
        module_cible = "Administration"
    else:
        module_cible = module_cible.capitalize()

    user_role = st.session_state["user"].get("role", "")
    return has_permission(user_role, module_cible, "ecriture")

def log_action(action: str, table_name: str, details: str):
    """Enregistre silencieusement une trace d'action dans la table logs."""
    try:
        supabase = get_supabase_client()
        if not supabase:
            return
        user_id = st.session_state.get("user", {}).get("user_id", "SYSTEM") if hasattr(st, "session_state") else "SYSTEM"
        supabase.table("logs").insert({
            "user_id": user_id,
            "action": action,
            "table_name": table_name,
            "details": str(details)
        }).execute()
    except Exception as e:
        print(f"⚠️ Échec d'enregistrement du log : {e}")

def fetch_data(table_name: str) -> list:
    """Lit toutes les données d'une table Supabase."""
    supabase = get_supabase_client()
    try:
        response = supabase.table(table_name).select("*").execute()
        return response.data
    except Exception as e:
        log_error(f"Erreur de lecture Supabase sur la table {table_name}", str(e))
        return []

def insert_hybrid(table_name: str, data: dict):
    """
    Écrit la donnée dans Supabase et déduit la cible Google Sheets automatiquement.
    Intègre le contrôle de droits côté serveur.
    """
    if not check_server_permission(table_name):
        log_error("Accès Refusé", f"Tentative d'INSERT bloquée sur {table_name}")
        raise PermissionError(f"🔒 Sécurité Serveur : Droit d'écriture refusé pour la table '{table_name}'.")

    supabase = get_supabase_client()
    try:
        res = supabase.table(table_name).insert(data).execute()
        supa_data = res.data
    except Exception as e:
        log_error(f"Erreur d'insertion Supabase ({table_name})", str(e))
        return None

    if supa_data and table_name in SCHEMA_CONFIG:
        config = SCHEMA_CONFIG[table_name]
        try:
            ligne_sheets = [data.get(col, "") for col in config["cols"]]
            append_rows_batch(config["module"], config["sheet"], [ligne_sheets])
        except Exception as e:
            log_error(f"Désynchronisation Google Sheets pour {config['sheet']}", str(e))

    log_action("INSERT", table_name, f"ID/Data: {data}")
    return supa_data

def update_hybrid(table_name: str, id_col: str, target_id: str, updates: dict):
    """
    Met à jour la donnée dans Supabase et déduit la cible Google Sheets automatiquement.
    Intègre le contrôle de droits côté serveur.
    """
    if not check_server_permission(table_name):
        log_error("Accès Refusé", f"Tentative d'UPDATE bloquée sur {table_name}")
        raise PermissionError(f"🔒 Sécurité Serveur : Droit d'écriture refusé pour la table '{table_name}'.")

    supabase = get_supabase_client()
    try:
        res = supabase.table(table_name).update(updates).eq(id_col, target_id).execute()
        supa_data = res.data
    except Exception as e:
        log_error(f"Erreur de mise à jour Supabase ({table_name}, ID: {target_id})", str(e))
        return None

    if supa_data and table_name in SCHEMA_CONFIG:
        config = SCHEMA_CONFIG[table_name]
        try:
            update_multiple_cells_by_id(config["module"], config["sheet"], id_col, target_id, updates)
        except Exception as e:
            log_error(f"Désynchronisation Google Sheets pour {config['sheet']}", str(e))

    log_action("UPDATE", table_name, f"{id_col}={target_id} | Modifs: {updates}")
    return supa_data