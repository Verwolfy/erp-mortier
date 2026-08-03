"""
Logique métier du module RH.
Gère les Employes et DemandesConges.
Conforme au schéma docs/schema_reference.md.
Lecture Supabase, Écriture hybride (Supabase + Google Sheets).
"""
import pandas as pd
from core.db_service import fetch_data, insert_hybrid
from core.utils import generate_unique_id, generate_technical_id


def get_employes() -> pd.DataFrame:
    """Récupère la liste des employés."""
    return pd.DataFrame(fetch_data("employes"))


def get_conges() -> pd.DataFrame:
    """Récupère l'historique des demandes de congés."""
    return pd.DataFrame(fetch_data("demandes_conges"))


def create_employe(nom: str, poste: str, service: str, manager_id: str, date_embauche: str) -> str:
    """
    Crée un nouvel employé avec un identifiant séquentiel.
    """
    df_emp = get_employes()
    exist_ids = df_emp["employe_id"].tolist() if not df_emp.empty else []

    emp_id = generate_unique_id("EMP", exist_ids)

    data_emp = {
        "employe_id": emp_id,
        "nom": nom,
        "poste": poste,
        "service": service,
        "manager_id": manager_id,
        "date_embauche": str(date_embauche),
        "actif": "OUI"
    }

    insert_hybrid("employes", data_emp)
    return emp_id


def create_demande_conge(employe_id: str, date_debut: str, date_fin: str, motif: str) -> str:
    """
    Enregistre une demande de congé avec un identifiant technique UUID.
    """
    conge_id = generate_technical_id("CNG")

    data_conge = {
        "demande_conge_id": conge_id,
        "employe_id": employe_id,
        "date_debut": str(date_debut),
        "date_fin": str(date_fin),
        "motif": motif,
        "statut": "EN_ATTENTE"
    }

    insert_hybrid("demandes_conges", data_conge)
    return conge_id