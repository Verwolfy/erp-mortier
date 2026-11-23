"""ERP-062 : demandes d'achat, approbation et transformation en BC.

Fonctionnalité préparée, désactivée par défaut et NON DEPLOYEE en SQL principal.
Les mutations passent par UNE RPC atomique, avec le même operation_id en reprise.
"""
from __future__ import annotations

from datetime import date
from decimal import Decimal, InvalidOperation
from uuid import uuid4
from typing import Any

import streamlit as st

from core.db_service import check_server_permission, check_server_read_permission
from modules.stocks.service import _stock_rpc_client

ACTIONS = frozenset({"CREATE", "SUBMIT", "APPROVE", "REJECT", "CONVERT"})


class PurchaseRequestError(RuntimeError):
    """Résultat incertain après RPC ; conserver cet identifiant sans en créer un autre."""

    def __init__(self, operation_id: str):
        super().__init__("Demande d'achat non confirmée : vérifier le journal avant reprise")
        self.operation_id = operation_id


def _actor(*, writing: bool = True) -> str:
    permission = check_server_permission if writing else check_server_read_permission
    if permission("commandes_achats") is not True:
        raise PermissionError("Droits Achats non vérifiables")
    if st.session_state.get("authenticated") is not True:
        raise PermissionError("Session expirée")
    user = st.session_state.get("user")
    if not isinstance(user, dict):
        raise PermissionError("Identité absente")
    actor = user.get("user_id")
    if not isinstance(actor, str) or not 1 <= len(actor.strip()) <= 200:
        raise PermissionError("Identité non vérifiable")
    return actor.strip()


def _quantity(raw: Any, *, zero: bool = False) -> str:
    if isinstance(raw, bool):
        raise ValueError("Quantité invalide")
    try:
        number = Decimal(str(raw))
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise ValueError("Quantité invalide") from exc
    if not number.is_finite() or number >= Decimal("1e15") or (
        number < 0 if zero else number <= 0
    ):
        raise ValueError("Quantité hors limites")
    return str(number)


def _text(raw: Any, label: str, *, maximum: int = 200, minimum: int = 1) -> str:
    if not isinstance(raw, str) or not minimum <= len(raw.strip()) <= maximum:
        raise ValueError(f"{label} invalide")
    return raw.strip()


def _date(raw: str) -> str:
    raw = _text(raw, "Date", maximum=10, minimum=10)
    try:
        if date.fromisoformat(raw).isoformat() != raw:
            raise ValueError("Date invalide")
    except ValueError as exc:
        raise ValueError("Date au format AAAA-MM-JJ attendue") from exc
    return raw


def create_request_payload(motivation: str, date_souhaitee: str,
                           lines: list[dict]) -> dict:
    justification = _text(motivation, "Motivation", maximum=1500, minimum=10)
    desired = _date(date_souhaitee)
    if not isinstance(lines, list) or not 1 <= len(lines) <= 100:
        raise ValueError("1 à 100 matières requises")
    parsed, unique = [], set()
    for line in lines:
        if not isinstance(line, dict):
            raise ValueError("Ligne incorrecte")
        mp_id = _text(line.get("mp_id"), "Matière")
        if mp_id in unique:
            raise ValueError("Une matière ne peut figurer deux fois")
        unique.add(mp_id)
        parsed.append({"mp_id": mp_id,
                       "quantite": _quantity(line.get("quantite"))})
    return {"motivation": justification, "date_souhaitee": desired, "lignes": parsed}


def convert_request_payload(demande_id: str, fournisseur_id: str,
                            lines: list[dict], date_voulue: str, *,
                            type_achat: str = "Matière Première",
                            mode_paiement: str = "Virement",
                            delai_paiement: str = "30 jours") -> dict:
    if not isinstance(lines, list) or not 1 <= len(lines) <= 100:
        raise ValueError("Lignes de commande requises")
    parsed, unique = [], set()
    for row in lines:
        if not isinstance(row, dict):
            raise ValueError("Ligne de commande incorrecte")
        mp = _text(row.get("mp_id"), "Matière")
        if mp in unique:
            raise ValueError("Matière en double")
        unique.add(mp)
        parsed.append({
            "mp_id": mp,
            "quantite": _quantity(row.get("quantite")),
            "prix_unitaire": _quantity(row.get("prix_unitaire"), zero=True),
        })
    return {
        "demande_id": _text(demande_id, "Demande"),
        "fournisseur_id": _text(fournisseur_id, "Fournisseur"),
        "type_achat": _text(type_achat, "Type achat"),
        "devise": "DZD", "taux_change": 1,
        "mode_paiement": _text(mode_paiement, "Paiement"),
        "delai_paiement": _text(delai_paiement, "Délai"),
        "date_voulue": _date(date_voulue),
        "lignes": parsed,
    }


def purchase_request_action(action: str, payload: dict, *,
                            operation_id: str | None = None) -> dict:
    """Une seule RPC; jamais de saisies directes dans les quatre tables."""
    if action not in ACTIONS or not isinstance(payload, dict):
        raise ValueError("Action demande invalide")
    op_id = _text(operation_id or f"DA-UI-{uuid4().hex}", "Opération",
                  maximum=128)
    actor = _actor(writing=True)
    if action != "CREATE":
        _text(payload.get("demande_id"), "Demande")
    try:
        response = _stock_rpc_client().rpc("erp_purchase_request_transaction", {
            "p_action": action,
            "p_operation_id": op_id,
            "p_acteur_id": actor,
            "p_payload": payload,
        }).execute()
    except Exception as exc:
        raise PurchaseRequestError(op_id) from exc
    result = response.data
    if not isinstance(result, dict) or result.get("operation_id") != op_id:
        raise PurchaseRequestError(op_id)
    if not isinstance(result.get("demande_id"), str):
        raise PurchaseRequestError(op_id)
    if result.get("statut") not in {
        "BROUILLON", "SOUMISE", "APPROUVEE", "REFUSEE", "COMMANDEE"
    }:
        raise PurchaseRequestError(op_id)
    if result["statut"] == "COMMANDEE" and not isinstance(
        result.get("commande_achat_id"), str
    ):
        raise PurchaseRequestError(op_id)
    return result


def list_purchase_requests() -> list[dict]:
    _actor(writing=False)
    try:
        result = (_stock_rpc_client().table("erp_purchase_requests")
                  .select("demande_id,demandeur_id,motivation,date_souhaitee,"
                          "statut,approbateur_id,decision_motif,commande_achat_id,cree_le")
                  .order("cree_le", desc=True).limit(201).execute())
    except Exception as exc:
        raise RuntimeError("Registre des demandes indisponible") from exc
    rows = result.data
    if not isinstance(rows, list) or any(not isinstance(row, dict) for row in rows):
        raise RuntimeError("Registre des demandes non vérifiable")
    if len(rows) > 200:
        raise RuntimeError("Plus de 200 demandes : pagination obligatoire")
    return rows


def purchase_request_lines(demande_id: str) -> list[dict]:
    _actor(writing=False)
    ref = _text(demande_id, "Demande")
    try:
        result = (_stock_rpc_client().table("erp_purchase_request_lines")
                  .select("mp_id,unite_stock,quantite")
                  .eq("demande_id", ref).limit(101).execute())
    except Exception as exc:
        raise RuntimeError("Lignes de demande indisponibles") from exc
    rows = result.data
    if not isinstance(rows, list) or not rows or len(rows) > 100:
        raise RuntimeError("Lignes de demande incomplètes")
    return rows
