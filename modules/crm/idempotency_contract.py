"""Contrat client FUTUR de la RPC CRM idempotente — non activé en production.

Aucun accès réseau, aucune écriture, aucun remplacement d'insert_hybrid.
Ce module prépare un format stable pour des tests en environnement TEST isolé.
"""
from __future__ import annotations

from datetime import date
from decimal import Decimal, InvalidOperation
from math import isfinite
from typing import Any
from uuid import UUID, uuid4

_KINDS = frozenset({"opportunite", "interaction"})
_OPPORTUNITY_FIELDS = frozenset({
    "prospect_nom", "contact", "statut", "commercial_id",
    "valeur_estimee", "probabilite_pct",
})
_INTERACTION_FIELDS = frozenset({
    "client_id", "type_action", "notes", "date_rappel",
})
_STATUSES = frozenset({"Nouveau", "Contacté", "En Négociation", "Gagné", "Perdu"})


class CRMResponseUncertain(RuntimeError):
    """Résultat RPC absent/contradictoire : ne jamais régénérer operation_id."""

    def __init__(self, operation_id: str) -> None:
        super().__init__("Résultat CRM non confirmé ; réconciliation obligatoire")
        self.operation_id = operation_id


def _string(value: Any, name: str, length: int, *, optional: bool = False) -> str:
    if not isinstance(value, str) or len(value) > length:
        raise ValueError(f"{name} invalide")
    if not optional and not value.strip():
        raise ValueError(f"{name} invalide")
    return value


def _number(value: Any, name: str, minimum: int, maximum: int) -> int | float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{name} invalide")
    if isinstance(value, float) and not isfinite(value):
        raise ValueError(f"{name} invalide")
    try:
        number = Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError) as exc:
        raise ValueError(f"{name} invalide") from exc
    if not number.is_finite() or not minimum <= number <= maximum:
        raise ValueError(f"{name} invalide")
    return value


def build_rpc_request(
    kind: str,
    actor_id: str,
    payload: dict[str, Any],
    *,
    operation_id: str | None = None,
) -> dict[str, Any]:
    """Construire un argument RPC déterministe, sans le soumettre.

    L'identifiant UUID est généré UNE SEULE FOIS, puis sauvegardé de façon
    durable avant l'envoi lorsque les RPC seront réellement activées.
    """
    if kind not in _KINDS:
        raise ValueError("Nature CRM non autorisée")
    _string(actor_id, "Identité", 128)
    if not isinstance(payload, dict):
        raise ValueError("Contenu CRM invalide")
    expected = _OPPORTUNITY_FIELDS if kind == "opportunite" else _INTERACTION_FIELDS
    if set(payload) != expected:
        raise ValueError("Colonnes CRM manquantes ou inattendues")
    if kind == "opportunite":
        _string(payload["prospect_nom"], "Prospect", 200)
        _string(payload["contact"], "Contact", 400, optional=True)
        _string(payload["commercial_id"], "Commercial", 128, optional=True)
        if payload["statut"] not in _STATUSES:
            raise ValueError("Statut CRM invalide")
        _number(payload["valeur_estimee"], "Valeur", 0, 10**15 - 1)
        _number(payload["probabilite_pct"], "Probabilité", 0, 100)
    else:
        _string(payload["client_id"], "Client", 128)
        _string(payload["type_action"], "Action", 100)
        _string(payload["notes"], "Notes", 4000, optional=True)
        when = _string(payload["date_rappel"], "Date", 10, optional=True)
        if when:
            try:
                if date.fromisoformat(when).isoformat() != when:
                    raise ValueError("Date non canonique")
            except (ValueError, TypeError) as exc:
                raise ValueError("Date CRM invalide") from exc

    if operation_id is None:
        operation_id = str(uuid4())
    else:
        if not isinstance(operation_id, str):
            raise ValueError("UUID d'opération invalide")
        try:
            parsed = UUID(operation_id)
        except (ValueError, AttributeError) as exc:
            raise ValueError("UUID d'opération invalide") from exc
        if str(parsed) != operation_id:
            raise ValueError("UUID d'opération non canonique")
    # Ne pas muter les arguments du formulaire. Le SQL vérifie le payload aussi.
    return {
        "p_operation_id": operation_id,
        "p_actor_id": actor_id,
        "p_kind": kind,
        "p_payload": dict(payload),
    }


def require_rpc_confirmation(response: Any, request: dict[str, Any]) -> str:
    """Refuse toute réponse incertaine ; ne déclenche JAMAIS de retry.

    Le service appelant doit préserver request['p_operation_id'] si une
    réponse est absente, invalide ou si un timeout se produit.
    """
    operation_id = request["p_operation_id"]
    data = getattr(response, "data", None)
    prefix = "OPP-" if request["p_kind"] == "opportunite" else "INT-"
    if not isinstance(data, dict):
        raise CRMResponseUncertain(operation_id)
    doc_id = data.get("document_id")
    if (data.get("operation_id") != operation_id or
            data.get("kind") != request["p_kind"] or
            type(data.get("replayed")) is not bool or
            not isinstance(doc_id, str) or not doc_id.startswith(prefix) or
            len(doc_id) != len(prefix) + 32):
        raise CRMResponseUncertain(operation_id)
    return doc_id
