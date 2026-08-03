"""
Service de base de données hybride (Supabase + Google Sheets).
Lit depuis Supabase (SQL). Écrit dans Supabase ET Google Sheets (Dual-Write).
"""
import streamlit as st
from supabase import create_client, Client
from core.sheets_service import append_rows_batch, update_multiple_cells_by_id


@st.cache_resource
def get_supabase_client() -> Client:
    """Initialise et retourne le client Supabase en utilisant les secrets de Streamlit."""
    url = st.secrets["supabase"]["url"]
    key = st.secrets["supabase"]["key"]
    return create_client(url, key)


supabase = get_supabase_client()


def fetch_data(table_name: str) -> list:
    """
    Lit toutes les données d'une table Supabase.
    Ultra-rapide, remplace les appels constants à l'API Google Sheets.
    """
    try:
        response = supabase.table(table_name).select("*").execute()
        return response.data
    except Exception as e:
        print(f"Erreur de lecture Supabase sur la table {table_name}: {e}")
        return []


def insert_hybrid(table_name: str, sheet_module: str, sheet_name: str, data: dict, columns_order: list):
    """
    Écrit la donnée dans Supabase. Si succès, sauvegarde dans Google Sheets.
    """
    try:
        # 1. Insertion dans Supabase
        res = supabase.table(table_name).insert(data).execute()

        # 2. Backup dans Google Sheets (format liste ordonnée selon le schéma)
        if res.data:
            ligne_sheets = [data.get(col, "") for col in columns_order]
            append_rows_batch(sheet_module, sheet_name, [ligne_sheets])

        return res.data
    except Exception as e:
        print(f"Erreur d'insertion hybride ({table_name}): {e}")
        return None


def update_hybrid(table_name: str, sheet_module: str, sheet_name: str, id_col: str, target_id: str, updates: dict):
    """
    Met à jour la donnée dans Supabase, puis dans Google Sheets.
    """
    try:
        # 1. Mise à jour Supabase
        res = supabase.table(table_name).update(updates).eq(id_col, target_id).execute()

        # 2. Backup Google Sheets
        if res.data:
            update_multiple_cells_by_id(sheet_module, sheet_name, id_col, target_id, updates)

        return res.data
    except Exception as e:
        print(f"Erreur de mise à jour hybride ({table_name}): {e}")
        return None