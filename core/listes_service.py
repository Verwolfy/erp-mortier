"""
Service de gestion des listes de référence.
"""
import pandas as pd
import streamlit as st
from core.sheets_service import get_all_records

@st.cache_data(ttl=300, show_spinner=False)
def get_liste(liste_code: str, parent_code: str = None) -> list:
    """Récupère une liste de référence active."""
    df = pd.DataFrame(get_all_records("referentiels", "ListesReference"))
    if df.empty or "liste_code" not in df.columns:
        return []

    # CORRECTION : Le statut exact dans la base de données est "ACTIF", pas "OUI"
    mask = (df["liste_code"] == liste_code) & (df["actif"] == "ACTIF")
    if parent_code:
        mask &= (df["parent_code"] == parent_code)

    df_filtered = df[mask]

    if "ordre" in df_filtered.columns:
        df_filtered["ordre"] = pd.to_numeric(df_filtered["ordre"], errors="coerce").fillna(999)
        df_filtered = df_filtered.sort_values(by="ordre")

    return df_filtered.to_dict("records")

def liste_to_dict(liste_data: list) -> dict:
    """Retourne {valeur_code: valeur_libelle} pour peupler un selectbox avec format_func."""
    return {item["valeur_code"]: item.get("valeur_libelle", item["valeur_code"]) for item in liste_data}