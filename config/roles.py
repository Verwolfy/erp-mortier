"""
Gestion des rôles et permissions.
Lit dynamiquement la table Permissions (avec fallback Supabase et bypass Admin).
"""
import streamlit as st
from core.sheets_service import get_all_records

@st.cache_data(ttl=300, show_spinner=False)
def get_permissions_data():
    """Récupère et met en cache la table des permissions depuis Google Sheets."""
    try:
        return get_all_records("referentiels", "Permissions")
    except Exception:
        return []

def has_permission(role: str, module: str, perm_type: str) -> bool:
    """
    Vérifie si un rôle possède une permission spécifique sur un module.
    Insensible à la casse + Bypass automatique pour les Administrateurs.
    """
    if not role or not module:
        return False

    role_clean = str(role).strip().upper()
    module_clean = str(module).strip().upper()

    # 1. Bypass automatique pour les rôles d'administration
    if role_clean in ["ADMIN", "ADMINISTRATEUR", "SUPERADMIN"]:
        return True

    # 2. Lecture des permissions (Google Sheets puis Supabase en secours)
    permissions = get_permissions_data()
    if not permissions:
        try:
            from core.db_service import fetch_data
            permissions = fetch_data("permissions")
        except Exception:
            permissions = []

    # 3. Vérification des droits (comparaison insensible à la casse)
    for row in permissions:
        r_row = str(row.get("role", "")).strip().upper()
        m_row = str(row.get("module", "")).strip().upper()

        if r_row == role_clean and m_row == module_clean:
            valeur_perm = str(row.get(perm_type, "")).strip().upper()
            return valeur_perm in ["OUI", "TRUE", "1"]

    return False

def get_allowed_modules(role: str) -> list:
    """
    Retourne la liste des modules auxquels le rôle a accès en lecture.
    """
    if not role:
        return []

    role_clean = str(role).strip().upper()
    if role_clean in ["ADMIN", "ADMINISTRATEUR", "SUPERADMIN"]:
        return ["Administration", "Achats", "Stocks", "Production", "Ventes", "CRM", "Finance", "RH", "Dashboards"]

    permissions = get_permissions_data()
    if not permissions:
        try:
            from core.db_service import fetch_data
            permissions = fetch_data("permissions")
        except Exception:
            permissions = []

    allowed = []
    for row in permissions:
        r_row = str(row.get("role", "")).strip().upper()
        if r_row == role_clean:
            lecture = str(row.get("lecture", "")).strip().upper()
            if lecture in ["OUI", "TRUE", "1"]:
                allowed.append(str(row.get("module", "")))

    return allowed