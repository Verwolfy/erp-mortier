"""Consultation privée et non nominative des demandes NextGen depuis le CRM.

Strictement READ ONLY. Pas de détail de contact, de conversion, de logs PII
ni d'accès à la table tant qu'un drapeau serveur n'est pas activé.
"""
from __future__ import annotations

import uuid

import streamlit as st
from config.roles import has_permission
from core.db_service import get_supabase_client

MAX_ROWS = 100
_PUBLIC_COLUMNS = ("demande_id", "type_demande", "statut", "cree_le")
_KINDS = frozenset({"quote", "distributor"})
_STATUSES = frozenset({"nouveau", "en_cours", "clos"})
_ACTIVE = frozenset({"OUI", "TRUE", "1", "ACTIF", "ACTIVE", "YES"})


def inbox_enabled() -> bool:
    """Doit être explicitement true dans les secrets serveur Streamlit."""
    try:
        cfg = st.secrets.get("nextgen", {})
        return isinstance(cfg, dict) and cfg.get("crm_inbox_read_enabled") is True
    except Exception:
        return False


def _require_crm_read(client: object) -> None:
    state = st.session_state
    if state.get("authenticated") is not True:
        raise PermissionError("Session non authentifiée")
    account = state.get("user")
    user_id = account.get("user_id") if isinstance(account, dict) else None
    if not isinstance(user_id, str) or not user_id.strip():
        raise PermissionError("Session utilisateur invalide")
    # Relecture en base ; le rôle déclaré dans la session ne vaut pas autorité.
    users = (
        client.table("users")
        .select("user_id,role,actif")
        .eq("user_id", user_id)
        .limit(2)
        .execute()
        .data
    )
    if not isinstance(users, list) or len(users) != 1:
        raise PermissionError("Identité non confirmée")
    fresh = users[0]
    if not isinstance(fresh, dict) or fresh.get("user_id") != user_id:
        raise PermissionError("Identité incohérente")
    role = fresh.get("role")
    status = fresh.get("actif")
    if not isinstance(role, str) or not role.strip():
        raise PermissionError("Rôle non confirmé")
    if not (status is True or status == 1 or (
        isinstance(status, str) and status.strip().upper() in _ACTIVE
    )):
        raise PermissionError("Compte inactif")
    if not has_permission(role.strip(), "CRM", "lecture"):
        raise PermissionError("Habilitation CRM insuffisante")


def list_requests_readonly() -> tuple[list[dict[str, str]], bool]:
    """Max. 100 lignes visibles, exclusivement les quatre métadonnées autorisées.

    L'élément 101 sert à signaler une suite non affichée ; aucun chiffre affiché
    ne doit être interprété comme un total réel au-delà des lignes consultées.
    """
    if not inbox_enabled():
        raise PermissionError("Fonction désactivée")
    if st.session_state.get("authenticated") is not True:
        raise PermissionError("Session non authentifiée")
    client = get_supabase_client()
    _require_crm_read(client)
    result = (
        client.table("site_demandes")
        .select(",".join(_PUBLIC_COLUMNS))
        .order("cree_le", desc=True)
        .limit(MAX_ROWS + 1)
        .execute()
    )
    data = result.data
    if not isinstance(data, list) or len(data) > MAX_ROWS + 1:
        raise ValueError("Lecture CRM non conforme")
    validated = []
    for record in data:
        if not isinstance(record, dict) or set(record) != set(_PUBLIC_COLUMNS):
            raise ValueError("Champs CRM inattendus")
        if record["type_demande"] not in _KINDS or record["statut"] not in _STATUSES:
            raise ValueError("Valeur de statut non reconnue")
        try:
            uuid.UUID(str(record["demande_id"]))
        except (ValueError, TypeError, AttributeError):
            raise ValueError("Identifiant CRM invalide") from None
        if not isinstance(record["cree_le"], str) or len(record["cree_le"]) > 64:
            raise ValueError("Horodatage CRM invalide")
        validated.append({col: str(record[col]) for col in _PUBLIC_COLUMNS})
    more = len(validated) > MAX_ROWS
    return validated[:MAX_ROWS], more
