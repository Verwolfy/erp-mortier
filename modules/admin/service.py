"""
Logique métier de l'Administration : Clients, Fournisseurs, Matières Premières, Produits et SKU.
Hybride : Lecture sur Supabase, Écriture Supabase + Backup Google Sheets.
Respect strict du schéma docs/schema_reference.md.
"""
import pandas as pd
import streamlit as st
from core.db_service import fetch_data, insert_hybrid, update_hybrid
from core.utils import generate_unique_id

# Petit mapping local uniquement pour faire le lien entre l'UI et la lecture
READ_MAPPING = {
    "Fournisseurs": "fournisseurs",
    "MatieresPremieres": "matieres_premieres",
    "Produits": "produits",
    "SkuConditionnement": "sku_conditionnement",
    "Clients": "clients"
}

@st.cache_data(ttl=60, show_spinner=False)
def get_dataframe(sheet_name: str, only_active=False) -> pd.DataFrame:
    """Récupère les données depuis Supabase (SQL) pour une rapidité maximale."""
    table_name = READ_MAPPING.get(sheet_name)
    if not table_name:
        return pd.DataFrame()

    data = fetch_data(table_name)
    df = pd.DataFrame(data)

    if only_active and not df.empty and "actif" in df.columns:
        df = df[df["actif"] == "OUI"]
    return df

def sauvegarder_modifications(sheet_name: str, id_col: str, df_original: pd.DataFrame, changes: dict) -> bool:
    """Applique les modifications d'un data_editor vers Supabase + Google Sheets."""
    table_name = READ_MAPPING.get(sheet_name)
    try:
        for row_idx_str, col_changes in changes.items():
            row_idx = int(row_idx_str)
            target_id = str(df_original.iloc[row_idx][id_col])
            updates_dict = {col: str(val) for col, val in col_changes.items()}

            # Mise à jour ultra-simplifiée !
            update_hybrid(table_name, id_col, target_id, updates_dict)
        return True
    except Exception as e:
        print(f"Erreur lors de la sauvegarde sur {sheet_name} : {e}")
        return False

# --- FOURNISSEURS ---
def add_fournisseur(data: dict):
    df = get_dataframe("Fournisseurs")
    exist_ids = df["fournisseur_id"].tolist() if not df.empty else []

    data["fournisseur_id"] = generate_unique_id("FRN", exist_ids)
    data["actif"] = "OUI"

    insert_hybrid("fournisseurs", data)

# --- MATIERES PREMIERES ---
def add_matiere_premiere(data: dict):
    df = get_dataframe("MatieresPremieres")
    exist_ids = df["mp_id"].tolist() if not df.empty else []

    data["mp_id"] = generate_unique_id("MP", exist_ids)
    data["actif"] = "OUI"
    data["cmp_actuel"] = 0.0

    insert_hybrid("matieres_premieres", data)

# --- PRODUITS FINIS ---
def add_produit(data: dict):
    df = get_dataframe("Produits")
    exist_ids = df["pf_id"].tolist() if not df.empty else []

    data["pf_id"] = generate_unique_id("PF", exist_ids)
    data["actif"] = "OUI"

    insert_hybrid("produits", data)

# --- SKU CONDITIONNEMENT ---
def add_sku(data: dict):
    df = get_dataframe("SkuConditionnement")
    exist_ids = df["sku_id"].tolist() if not df.empty else []

    data["sku_id"] = generate_unique_id("SKU", exist_ids)
    data["actif"] = "OUI"

    insert_hybrid("sku_conditionnement", data)

# --- CLIENTS ---
def add_client(data: dict):
    df = get_dataframe("Clients")
    exist_ids = df["client_id"].tolist() if not df.empty else []

    data["client_id"] = generate_unique_id("CLI", exist_ids)
    data["actif"] = "OUI"

    insert_hybrid("clients", data)