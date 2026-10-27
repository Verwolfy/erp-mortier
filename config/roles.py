"""Autorisations ERP fondées sur Supabase (source de vérité unique).

Le cache court ne sert qu'au menu. Une autorisation d'écriture passe toujours
par une lecture fraîche de PostgreSQL, puis par les contrôles du service métier.
"""
from __future__ import annotations

import logging

import streamlit as st

_LOG = logging.getLogger(__name__)
_ADMIN_ROLES = frozenset({"ADMIN", "ADMINISTRATEUR", "SUPERADMIN"})
_MODULES_ADMIN = [
    "Administration", "Achats", "Stocks", "Production", "Ventes",
    "CRM", "Finance", "RH", "Dashboards",
]
_VALID_PERMISSIONS = frozenset({"lecture", "ecriture"})
_TRUE_VALUES = frozenset({"OUI", "TRUE", "1", "YES"})


def _norm(value: object) -> str:
    return str(value or "").strip().upper()


def _enabled(value: object) -> bool:
    if value is True or value == 1:
        return True
    return _norm(value) in _TRUE_VALUES


def _permission_rows(role: str | None = None) -> list[dict]:
    """Lit les permissions directement dans Supabase, sans dépendre de Sheets.

    L'import local évite la dépendance circulaire : db_service importe roles.
    En cas de panne de Supabase, aucune autorisation n'est accordée.
    """
    try:
        from core.db_service import get_supabase_client

        query = (get_supabase_client()
                 .table("permissions")
                 .select("role,module,lecture,ecriture"))
        if role is not None:
            # Filtre SQL pour éviter une récupération générale à chaque écriture.
            # Une comparaison exacte est refaite plus bas, car ILIKE admet des jokers.
            query = query.ilike("role", role.strip())
        # Une matrice RBAC dépassant 1 000 entrées doit être paginée et auditée.
        rows = query.limit(1000).execute().data or []
        if not isinstance(rows, list) or len(rows) >= 1000:
            _LOG.warning("Matrice de permissions invalide ou potentiellement tronquée")
            return []
        return [row for row in rows if isinstance(row, dict)]
    except Exception as exc:
        _LOG.warning("Consultation des permissions impossible (%s)", type(exc).__name__)
        return []


def get_permissions_data() -> list[dict]:
    """Snapshot court pour les affichages ; ne jamais l'utiliser pour autoriser une écriture."""
    return _permission_rows()


def has_permission(role: str, module: str, perm_type: str) -> bool:
    """Contrôle frais et fail-closed des autorisations de lecture/écriture.

    Les rôles d'administration conservent leur convention historique.
    L'identité réelle de l'administrateur doit être vérifiée dans db_service.
    """
    if not isinstance(role, str) or not isinstance(module, str):
        return False
    if perm_type not in _VALID_PERMISSIONS:
        return False
    role_key, module_key = _norm(role), _norm(module)
    if not role_key or not module_key:
        return False
    if role_key in _ADMIN_ROLES:
        return True

    matched = [row for row in _permission_rows(role) if
               _norm(row.get("role")) == role_key and
               _norm(row.get("module")) == module_key]
    # En cas de droits contradictoires/doublonnés, on refuse par défaut.
    return len(matched) == 1 and _enabled(matched[0].get(perm_type))


def get_allowed_modules(role: str) -> list[str]:
    """Modules visibles dans le menu ; le contrôle à l'écriture reste indépendant."""
    if not isinstance(role, str) or not role.strip():
        return []
    role_key = _norm(role)
    if role_key in _ADMIN_ROLES:
        return _MODULES_ADMIN.copy()

    # Les lignes contradictoires ne doivent pas produire une autorisation implicite.
    matches: dict[str, list[dict]] = {}
    for row in get_permissions_data():
        if _norm(row.get("role")) == role_key and _norm(row.get("module")):
            matches.setdefault(_norm(row["module"]), []).append(row)
    return [str(rows[0]["module"]).strip() for rows in matches.values()
            if len(rows) == 1 and _enabled(rows[0].get("lecture"))]
