"""Accusés *internes* d'encaissement, non fiscaux.

L'opération et l'identifiant sont conservés pour pouvoir réessayer sans
créer de doublon après une coupure de réseau. Les droits sont revalidés
en amont via la couche de permissions de l'ERP.
"""
from __future__ import annotations

from uuid import uuid4
from typing import Any

from core.db_service import check_server_permission
from modules.stocks.service import _stock_rpc_client


class RecuOperationIncertaine(RuntimeError):
    """Reprendre avec le même operation_id ; émission SQL peut être effectuée."""

    def __init__(self, operation_id: str):
        super().__init__(
            "État de l'accusé interne inconnu. Réessayer avec le même operation_id."
        )
        self.operation_id = operation_id


def _identifiant(value: Any, champ: str, max_length: int = 200) -> str:
    if not isinstance(value, str) or not value.strip() or len(value.strip()) > max_length:
        raise ValueError(f"{champ} invalide")
    return value.strip()


def emettre_recu_interne(
    reglement_id: str,
    *,
    operation_id: str | None = None,
) -> dict[str, str]:
    """N'émet ni quittance légale, ni écriture comptable, ni taxe.

    Les appels repris après timeout sont sûrs si l'operation_id est inchangé.
    """
    ident = _identifiant(reglement_id, "Règlement")
    op = _identifiant(
        operation_id if operation_id is not None else "RECUI-" + uuid4().hex,
        "Identifiant d'opération", max_length=128
    )
    import re
    if not re.fullmatch(r"RECUI-[A-Za-z0-9-]{8,120}", op):
        raise ValueError("Identifiant de reprise invalide")
    if check_server_permission("reglements") is not True:
        raise PermissionError("Émission de reçu interne interdite")
    try:
        response = _stock_rpc_client().rpc(
            "erp_emettre_recu_interne",
            {"p_operation_id": op, "p_reglement_id": ident},
        ).execute()
    except Exception as exc:
        raise RecuOperationIncertaine(op) from exc
    value = response.data
    if (not isinstance(value, dict) or value.get("operation_id") != op
            or value.get("reglement_id") != ident
            or value.get("statut") != "INTERNE_NON_FISCAL"
            or value.get("timbre_statut") != "NON_CALCULE"
            or not isinstance(value.get("recu_id"), str)
            or not value["recu_id"].startswith("RINT-")):
        raise RecuOperationIncertaine(op)
    return value
