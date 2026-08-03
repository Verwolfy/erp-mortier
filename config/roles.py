"""
Gestion des rôles et permissions.
Lit dynamiquement l'onglet Permissions du fichier ERP_Referentiels.
"""
import streamlit as st
from core.sheets_service import get_all_records

@st.cache_data(ttl=300, show_spinner=False)
def get_permissions_data():
    """Récupère et met en cache la table des permissions."""
    return get_all_records("referentiels", "Permissions")

def has_permission(role: str, module: str, perm_type: str) -> bool:
    """
    Vérifie si un rôle possède une permission spécifique sur un module.
    perm_type doit être "lecture" ou "ecriture".
    """
    if not role or not module:
        return False

    permissions = get_permissions_data()
    for row in permissions:
        if str(row.get("role", "")) == role and str(row.get("module", "")) == module:
            valeur_perm = str(row.get(perm_type, "")).upper()
            return valeur_perm == "OUI" or valeur_perm == "TRUE" or valeur_perm == "1"

    return False

def get_allowed_modules(role: str) -> list:
    """
    Retourne la liste des modules auxquels le rôle a accès en lecture.
    """
    if not role:
        return []

    permissions = get_permissions_data()
    allowed = []
    for row in permissions:
        if str(row.get("role", "")) == role:
            lecture = str(row.get("lecture", "")).upper()
            if lecture in ["OUI", "TRUE", "1"]:
                allowed.append(str(row.get("module", "")))

    return allowed