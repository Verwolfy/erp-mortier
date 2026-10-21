"""Finance : comptes, règlements équilibrés et lettrages atomiques (Supabase).

Une RPC PostgreSQL assure chaque mutation en une seule transaction.
Un compte de contrepartie explicite est requis pour une écriture en partie double.
Migration SQL 006 requise sur un environnement de TEST avant mise en service.
"""
from __future__ import annotations

from datetime import date
from decimal import Decimal, InvalidOperation
from typing import Any
from uuid import uuid4

import pandas as pd

from core.db_service import check_server_permission, fetch_data
from modules.stocks.service import _stock_rpc_client

LIMIT = Decimal("1e15")
CENT = Decimal("0.01")


class FinanceOperationError(RuntimeError):
    """État RPC inconnu : reprendre avec le MÊME operation_id et même contenu."""

    def __init__(self, message: str, *, operation_id: str):
        super().__init__(message)
        self.operation_id = operation_id


def _text(value: Any, field: str, *, max_len: int = 200, optional: bool = False) -> str:
    if not isinstance(value, str):
        raise ValueError(f"{field} invalide")
    result = value.strip()
    if (not optional and not result) or len(result) > max_len:
        raise ValueError(f"{field} invalide")
    return result


def _amount(value: Any, field: str, *, allow_zero: bool = False,
            allow_negative: bool = False) -> Decimal:
    if isinstance(value, bool):
        raise ValueError(f"{field} invalide")
    raw = str(value)
    if len(raw) > 64:
        raise ValueError(f"{field} invalide")
    try:
        number = Decimal(raw)
    except (InvalidOperation, ValueError, TypeError) as exc:
        raise ValueError(f"{field} invalide") from exc
    if (not number.is_finite() or abs(number) >= LIMIT
            or (number < 0 and not allow_negative)
            or (number == 0 and not allow_zero)
            or number != number.quantize(CENT)):
        raise ValueError(f"{field} doit être un montant valide en centimes")
    return number


def _date_iso(value: Any, field: str) -> str:
    result = _text(value, field, max_len=10)
    try:
        parsed = date.fromisoformat(result)
    except (ValueError, TypeError) as exc:
        raise ValueError(f"{field} doit être AAAA-MM-JJ") from exc
    if parsed.isoformat() != result:
        raise ValueError(f"{field} doit être AAAA-MM-JJ")
    return result


def _rpc(action: str, payload: dict[str, Any], *, operation_id: str | None) -> dict:
    op_id = (_text(operation_id, "operation_id", max_len=128)
             if operation_id is not None else f"FIN-{uuid4()}")
    for table in ({"ACCOUNT": ("comptes",),
                   "PAYMENT": ("reglements", "ecritures_comptables"),
                   "ALLOCATE": ("lettrage", "reglements")}[action]):
        if check_server_permission(table) is not True:
            raise PermissionError("Droit d'écriture Finance refusé")
    try:
        response = _stock_rpc_client().rpc("erp_finance_transaction", {
            "p_action": action, "p_operation_id": op_id, "p_payload": payload,
        }).execute()
    except Exception as exc:
        raise FinanceOperationError(
            "Transaction non confirmée : vérifier Supabase et reprendre avec le MÊME operation_id",
            operation_id=op_id,
        ) from exc
    result = response.data
    required = {"ACCOUNT": "compte_id", "PAYMENT": "reglement_id", "ALLOCATE": "lettrage_id"}[action]
    if (not isinstance(result, dict) or result.get("operation_id") != op_id
            or result.get("action") != action
            or not isinstance(result.get(required), str) or not result[required]):
        raise FinanceOperationError("Réponse SQL non vérifiable", operation_id=op_id)
    return result


def get_comptes() -> pd.DataFrame:
    return pd.DataFrame(fetch_data("comptes"))


def get_reglements() -> pd.DataFrame:
    return pd.DataFrame(fetch_data("reglements"))


def get_lettrages() -> pd.DataFrame:
    return pd.DataFrame(fetch_data("lettrage"))


def get_ecritures_comptables() -> pd.DataFrame:
    """Écritures de trésorerie et contreparties, pas un grand livre général complet."""
    return pd.DataFrame(fetch_data("ecritures_comptables"))


def creer_compte(nom_compte: str, type_compte: str, numero_compte: str,
                 solde_initial: float, *, operation_id: str | None = None) -> str:
    payload = {
        "nom_compte": _text(nom_compte, "Nom compte"),
        "type_compte": _text(type_compte, "Type compte"),
        "numero_compte": _text(numero_compte, "Numéro compte"),
        "solde_initial": format(_amount(solde_initial, "Solde initial", allow_zero=True,
                                         allow_negative=True), "f"),
    }
    return _rpc("ACCOUNT", payload, operation_id=operation_id)["compte_id"]


def enregistrer_reglement(date_reglement: str, type_flux: str, partenaire_id: str,
                           compte_id: str, mode_paiement: str, reference_trace: str,
                           montant_total: float, *, contrepartie_compte_id: str | None = None,
                           operation_id: str | None = None) -> str:
    """Règlement + deux écritures équilibrées. Contrepartie obligatoire (nouveau)."""
    if type_flux not in ("ENCAISSEMENT", "DECAISSEMENT"):
        raise ValueError("Type de flux invalide")
    compte = _text(compte_id, "Compte de trésorerie")
    if contrepartie_compte_id is None:
        raise ValueError("Compte de contrepartie obligatoire pour la partie double")
    contrepartie = _text(contrepartie_compte_id, "Compte de contrepartie")
    if compte == contrepartie:
        raise ValueError("La trésorerie et la contrepartie doivent être deux comptes distincts")
    payload = {
        "date_reglement": _date_iso(date_reglement, "Date règlement"),
        "type_flux": type_flux,
        "partenaire_id": _text(partenaire_id, "Partenaire"),
        "compte_id": compte,
        "contrepartie_compte_id": contrepartie,
        "mode_paiement": _text(mode_paiement, "Mode paiement"),
        "reference_trace": _text(reference_trace, "Référence traçable", max_len=200),
        "montant_total": format(_amount(montant_total, "Montant règlement"), "f"),
    }
    return _rpc("PAYMENT", payload, operation_id=operation_id)["reglement_id"]


def enregistrer_lettrage(reglement_id: str, document_id: str,
                          type_document: str, montant_applique: float,
                          *, operation_id: str | None = None) -> str:
    """Affectation atomique, sans modifier le statut commercial de la facture."""
    if type_document not in ("FactureClient", "FactureFournisseur"):
        raise ValueError("Type document non pris en charge (avoirs exclus)")
    payload = {
        "reglement_id": _text(reglement_id, "Règlement"),
        "document_id": _text(document_id, "Document"),
        "type_document": type_document,
        "montant_applique": format(_amount(montant_applique, "Montant appliqué"), "f"),
    }
    return _rpc("ALLOCATE", payload, operation_id=operation_id)["lettrage_id"]
