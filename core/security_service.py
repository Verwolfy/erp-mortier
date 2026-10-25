"""Gestion des habilitations : session serveur + RPC auditée sur PostgreSQL.

Aucune autorité n'est dérivée du rôle ADMIN ou de la permission métier.
La clé service_role doit rester secrète côté Streamlit, jamais dans le navigateur.
"""
import logging
import uuid

import streamlit as st

from core.db_service import get_supabase_client

_LOG = logging.getLogger(__name__)
# Doit rester aligné avec la liste autorisée côté SQL 010A_02D_01.
STANDARD_ROLES = (
    "ACHATS", "COMMERCIAL", "CRM", "FINANCE", "LECTURE_SEULE",
    "MAGASINIER", "PRODUCTION", "QUALITE", "RH", "STOCKS", "VENTES",
)
STANDARD_MODULES = (
    "Achats", "Stocks", "Production", "Ventes", "Finance", "CRM", "RH",
    "Dashboards", "Logs",
)


def _actor_id() -> str:
    state = st.session_state
    if state.get("authenticated") is not True:
        raise PermissionError("Session non authentifiee")
    user = state.get("user")
    actor = user.get("user_id") if isinstance(user, dict) else None
    if not isinstance(actor, str) or not actor.strip():
        raise PermissionError("Identite utilisateur invalide")
    return actor.strip()


def is_security_manager() -> bool:
    """Vérification RPC non cachée ; toute erreur refuse l'accès."""
    try:
        actor = _actor_id()
        response = get_supabase_client().rpc(
            "erp_security_is_manager", {"p_actor_id": actor}
        ).execute()
        return response.data is True
    except Exception as exc:
        _LOG.warning("Verification SECURITY_MANAGER indisponible (%s)", type(exc).__name__)
        return False


def require_security_manager() -> str:
    actor = _actor_id()
    if not is_security_manager():
        raise PermissionError("Habilitation SECURITY_MANAGER requise")
    return actor


def create_user_secure(user_id: str, nom: str, login: str,
                       hash_mdp: str, role: str) -> str:
    actor = require_security_manager()
    if not isinstance(role, str) or role not in STANDARD_ROLES:
        raise PermissionError("Role cible non autorise")
    response = get_supabase_client().rpc("erp_security_create_user", {
        "p_actor_id": actor, "p_operation_id": str(uuid.uuid4()),
        "p_user_id": user_id, "p_nom": nom, "p_login": login,
        "p_hash_mdp": hash_mdp, "p_role": role,
    }).execute()
    if response.data != user_id:
        raise RuntimeError("Creation utilisateur non confirmee ; controler TEST")
    return user_id


def add_permission_secure(role: str, module: str, lecture: str,
                          ecriture: str) -> bool:
    actor = require_security_manager()
    if role not in STANDARD_ROLES or module not in STANDARD_MODULES:
        raise PermissionError("Attribution de droits non autorisee")
    if lecture not in {"OUI", "NON"} or ecriture not in {"OUI", "NON"}:
        raise ValueError("Valeur de permission invalide")
    response = get_supabase_client().rpc("erp_security_add_permission", {
        "p_actor_id": actor, "p_operation_id": str(uuid.uuid4()),
        "p_role": role, "p_module": module,
        "p_lecture": lecture, "p_ecriture": ecriture,
    }).execute()
    if response.data is not True:
        raise RuntimeError("Permission non confirmee ; controler TEST")
    return True
