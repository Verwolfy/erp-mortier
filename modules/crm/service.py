"""
Logique métier du module CRM.
Gère le Pipeline (opportunités) et les Interactions.
Conforme au schéma docs/schema_reference.md.
Lecture Supabase, Écriture hybride (Supabase + Google Sheets).
"""
import pandas as pd
from core.db_service import fetch_data, insert_hybrid
from core.utils import generate_unique_id, generate_technical_id, get_local_now

def get_pipeline() -> pd.DataFrame:
    """Récupère toutes les opportunités du pipeline."""
    return pd.DataFrame(fetch_data("pipeline"))

def get_interactions() -> pd.DataFrame:
    """Récupère l'historique des interactions CRM."""
    return pd.DataFrame(fetch_data("interactions"))

def create_opportunite(prospect_nom: str, contact: str, statut: str, commercial_id: str, valeur_estimee: float, probabilite_pct: float):
    """
    Crée une nouvelle opportunité dans le Pipeline.
    """
    df_pipe = get_pipeline()
    exist_ids = df_pipe["opportunite_id"].tolist() if not df_pipe.empty else []

    opp_id = generate_unique_id("OPP", exist_ids)
    date_jour = get_local_now().strftime("%Y-%m-%d")

    data_opp = {
        "opportunite_id": opp_id,
        "prospect_nom": prospect_nom,
        "contact": contact,
        "statut": statut,
        "commercial_id": commercial_id,
        "valeur_estimee": valeur_estimee,
        "probabilite_pct": probabilite_pct,
        "date_creation": date_jour,
        "date_derniere_action": date_jour
    }
    cols_opp = ["opportunite_id", "prospect_nom", "contact", "statut", "commercial_id", "valeur_estimee", "probabilite_pct", "date_creation", "date_derniere_action"]

    insert_hybrid("pipeline", "crm", "Pipeline", data_opp, cols_opp)
    return opp_id

def create_interaction(client_id: str, type_action: str, notes: str, date_rappel: str):
    """
    Enregistre une nouvelle interaction avec un client ou prospect.
    """
    int_id = generate_technical_id("INT")
    date_creation = get_local_now().strftime("%Y-%m-%d %H:%M")

    data_int = {
        "interaction_id": int_id,
        "client_id": client_id,
        "date_creation": date_creation,
        "type_action": type_action,
        "notes": notes,
        "date_rappel": date_rappel,
        "statut_rappel": "EN_ATTENTE"
    }
    cols_int = ["interaction_id", "client_id", "date_creation", "type_action", "notes", "date_rappel", "statut_rappel"]

    insert_hybrid("interactions", "crm", "Interactions", data_int, cols_int)
    return int_id