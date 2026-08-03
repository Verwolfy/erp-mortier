"""
Logique métier de l'Administration : Clients, Fournisseurs, Matières Premières, Produits et SKU.
Hybride : Lecture sur Supabase, Écriture Supabase + Backup Google Sheets.
Respect strict du schéma docs/schema_reference.md.
"""
import pandas as pd
import streamlit as st
from core.db_service import fetch_data, insert_hybrid, update_hybrid
from core.utils import generate_unique_id

# Dictionnaire de correspondance : Nom de l'onglet Sheets -> Nom de la table SQL
TABLE_MAPPING = {
    "Fournisseurs": "fournisseurs",
    "MatieresPremieres": "matieres_premieres",
    "Produits": "produits",
    "SkuConditionnement": "sku_conditionnement",
    "Clients": "clients"
}

@st.cache_data(ttl=60, show_spinner=False)
def get_dataframe(sheet_name: str, only_active=False) -> pd.DataFrame:
    """Récupère les données depuis Supabase (SQL) pour une rapidité maximale."""
    table_name = TABLE_MAPPING.get(sheet_name)
    if not table_name:
        return pd.DataFrame()

    data = fetch_data(table_name)
    df = pd.DataFrame(data)

    if only_active and not df.empty and "actif" in df.columns:
        df = df[df["actif"] == "OUI"]
    return df

def sauvegarder_modifications(sheet_name: str, id_col: str, df_original: pd.DataFrame, changes: dict) -> bool:
    """
    Applique les modifications d'un data_editor vers Supabase + Google Sheets.
    """
    table_name = TABLE_MAPPING.get(sheet_name)
    try:
        for row_idx_str, col_changes in changes.items():
            row_idx = int(row_idx_str)
            target_id = str(df_original.iloc[row_idx][id_col])
            updates_dict = {col: str(val) for col, val in col_changes.items()}

            # Mise à jour hybride (Dual-Write)
            update_hybrid(
                table_name=table_name,
                sheet_module="referentiels",
                sheet_name=sheet_name,
                id_col=id_col,
                target_id=target_id,
                updates=updates_dict
            )
        return True
    except Exception as e:
        print(f"Erreur lors de la sauvegarde sur {sheet_name} : {e}")
        return False

# --- FOURNISSEURS ---
def add_fournisseur(data: dict):
    df = get_dataframe("Fournisseurs")
    exist_ids = df["fournisseur_id"].tolist() if not df.empty else []
    new_id = generate_unique_id("FRN", exist_ids)

    colonnes = ["fournisseur_id", "nom", "categorie", "type_entreprise", "adresse", "gps", "pays", "wilaya", "rc", "nif", "nis", "nom_contact", "poste_contact", "email_contact", "mobile_contact", "email_entreprise", "site_web", "telephone_fixe", "delai_appro_jours", "actif"]

    data["fournisseur_id"] = new_id
    data["actif"] = "OUI"

    insert_hybrid(
        table_name="fournisseurs",
        sheet_module="referentiels",
        sheet_name="Fournisseurs",
        data=data,
        columns_order=colonnes
    )

# --- MATIERES PREMIERES ---
def add_matiere_premiere(data: dict):
    df = get_dataframe("MatieresPremieres")
    exist_ids = df["mp_id"].tolist() if not df.empty else []
    new_id = generate_unique_id("MP", exist_ids)

    colonnes = ["mp_id", "nom", "categorie_mp", "unite_stock", "origine_pays", "duree_peremption_jours", "fournisseurs_ids", "actif", "type_emballage", "poids_net", "cmp_actuel", "stock_mini", "stock_maxi", "hs_code", "taux_dedouanement", "lien_fiche_technique", "lien_fiche_securite"]

    data["mp_id"] = new_id
    data["actif"] = "OUI"
    data["cmp_actuel"] = 0.0

    insert_hybrid(
        table_name="matieres_premieres",
        sheet_module="referentiels",
        sheet_name="MatieresPremieres",
        data=data,
        columns_order=colonnes
    )

# --- PRODUITS FINIS ---
def add_produit(data: dict):
    df = get_dataframe("Produits")
    exist_ids = df["pf_id"].tolist() if not df.empty else []
    new_id = generate_unique_id("PF", exist_ids)

    colonnes = ["pf_id", "nom", "categorie_pf", "recette_id", "unite_production", "actif"]

    data["pf_id"] = new_id
    data["actif"] = "OUI"

    insert_hybrid(
        table_name="produits",
        sheet_module="referentiels",
        sheet_name="Produits",
        data=data,
        columns_order=colonnes
    )

# --- SKU CONDITIONNEMENT ---
def add_sku(data: dict):
    df = get_dataframe("SkuConditionnement")
    exist_ids = df["sku_id"].tolist() if not df.empty else []
    new_id = generate_unique_id("SKU", exist_ids)

    colonnes = ["sku_id", "pf_id", "format", "emballage_mp_id", "poids_net", "unite_vente", "facteur_conversion", "prix_vente_defaut", "actif"]

    data["sku_id"] = new_id
    data["actif"] = "OUI"

    insert_hybrid(
        table_name="sku_conditionnement",
        sheet_module="referentiels",
        sheet_name="SkuConditionnement",
        data=data,
        columns_order=colonnes
    )

# --- CLIENTS ---
def add_client(data: dict):
    df = get_dataframe("Clients")
    exist_ids = df["client_id"].tolist() if not df.empty else []
    new_id = generate_unique_id("CLI", exist_ids)

    colonnes = ["client_id", "nom", "categorie_client", "type_client", "adresse", "gps", "pays", "wilaya", "rc", "nif", "nis", "nom_contact", "poste_contact", "email_contact", "mobile_contact", "email_entreprise", "site_web", "telephone_fixe", "commercial_id", "actif"]

    data["client_id"] = new_id
    data["actif"] = "OUI"

    insert_hybrid(
        table_name="clients",
        sheet_module="referentiels",
        sheet_name="Clients",
        data=data,
        columns_order=colonnes
    )