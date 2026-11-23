"""Copie strictement consultative des demandes d'achat ERP-062.

La fonctionnalité n'est activable qu'après homologation SQL et utilisateur
approbateur indépendant. Cette impression ne soumet, n'approuve ni ne convertit
aucune demande. Les accès utilisent exclusivement le service de consultation
Achats existant et ses contrôles d'identité frais.
"""
from __future__ import annotations

from datetime import date
from decimal import Decimal, InvalidOperation
import os
import re

_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.:/-]{0,127}\Z")
_VALID_STATUSES = frozenset({"BROUILLON", "SOUMISE", "APPROUVEE", "REFUSEE", "COMMANDEE"})


class RequestPrintError(ValueError):
    """Demande ou lignes incompatibles avec une copie fiable."""


def _identity(value: object, label: str) -> str:
    if not isinstance(value, str) or not _ID.fullmatch(value):
        raise RequestPrintError(f"{label} absent ou invalide")
    return value


def _day(raw: object, label: str) -> str:
    if not isinstance(raw, str) or len(raw) < 10:
        raise RequestPrintError(f"{label} absent")
    try:
        return date.fromisoformat(raw[:10]).isoformat()
    except ValueError as exc:
        raise RequestPrintError(f"{label} invalide") from exc


def _quantity(value: object) -> str:
    if isinstance(value, bool) or value is None:
        raise RequestPrintError("Quantité non vérifiable")
    try:
        amount = Decimal(str(value))
    except (TypeError, ValueError, InvalidOperation) as exc:
        raise RequestPrintError("Quantité non vérifiable") from exc
    if not amount.is_finite() or not 0 < amount < Decimal("1e15"):
        raise RequestPrintError("Quantité non vérifiable")
    return format(amount, "f")


def build_request_snapshot(identifier: str, requests: list[dict],
                           lines: list[dict]) -> dict:
    """Données de lecture seulement ; aucune date, unité ni prix inventés."""
    _identity(identifier, "Référence")
    if (not isinstance(requests, list) or len(requests) > 200 or
            any(not isinstance(r, dict) for r in requests)):
        raise RequestPrintError("Registre non vérifiable")
    matches = [r for r in requests if r.get("demande_id") == identifier]
    if len(matches) != 1:
        raise RequestPrintError("Demande absente ou ambiguë")
    record = matches[0]
    demandeur = _identity(record.get("demandeur_id"), "Demandeur")
    state = record.get("statut")
    if state not in _VALID_STATUSES:
        raise RequestPrintError("Statut non qualifié")
    motivation = record.get("motivation")
    if not isinstance(motivation, str) or not 10 <= len(motivation.strip()) <= 1500:
        raise RequestPrintError("Motivation manquante ou invalide")
    wanted = _day(record.get("date_souhaitee"), "Date de besoin")
    created = _day(record.get("cree_le"), "Date de création")
    approver = record.get("approbateur_id")
    if approver not in (None, ""):
        approver = _identity(approver, "Approbateur")
        if approver == demandeur:
            raise RequestPrintError("Auto-approbation incohérente")
    command_id = record.get("commande_achat_id")
    if (state == "COMMANDEE") != (isinstance(command_id, str) and bool(command_id)):
        raise RequestPrintError("Lien de commande incohérent")
    if command_id:
        command_id = _identity(command_id, "BC lié")
    if not isinstance(lines, list) or not 1 <= len(lines) <= 100:
        raise RequestPrintError("Lignes d'achat absentes ou trop nombreuses")
    seen = set()
    fields: list[tuple[str, str]] = [
        ("Demandeur (référence)", demandeur),
        ("Statut enregistré", state),
        ("Date de création enregistrée", created),
        ("Date de besoin souhaitée", wanted),
        ("Motivation enregistrée (intégrale)", motivation.strip()),
        ("Approbateur (référence)", approver or "NON RENSEIGNÉ"),
        ("Motif de décision enregistré", str(record.get("decision_motif") or "NON RENSEIGNÉ")),
        ("Commande fournisseur liée", command_id or "AUCUNE"),
    ]
    for pos, line in enumerate(lines, 1):
        if not isinstance(line, dict):
            raise RequestPrintError("Ligne de demande invalide")
        mp = _identity(line.get("mp_id"), "Matière")
        if mp in seen:
            raise RequestPrintError("Matière en doublon")
        seen.add(mp)
        unit = line.get("unite_stock")
        if not isinstance(unit, str) or not 1 <= len(unit.strip()) <= 40:
            raise RequestPrintError("Unité enregistrée absente")
        quantity = _quantity(line.get("quantite"))
        fields.append((f"Ligne {pos} — matière / quantité / unité",
                       f"{mp} — {quantity} {unit.strip()}"))
    warning = (
        "DEMANDE D'ACHAT — COPIE INTERNE NON ÉMISE / NON SIGNÉE. "
        "Statut de lecture seulement, aucun visa ni commande créé par cette impression. "
        "Approbation indépendante obligatoire dans le processus ERP-062."
    )
    return {
        "kind": "Demande d'achat (copie interne)",
        "id": identifier, "date": created,
        "section": "Achats", "partner": demandeur,
        "source": "erp_purchase_requests / erp_purchase_request_lines",
        "fields": fields, "warning": warning, "date_label": "Date de création",
    }


def load_request_snapshot(identifier: str) -> dict:
    """La copie DA est impossible tant qu'ERP-062 n'est pas activé."""
    _identity(identifier, "Référence")
    if os.environ.get("ERP_PURCHASE_REQUESTS_ENABLED") != "1":
        raise RequestPrintError("Circuit de demandes d'achat désactivé")
    from modules.achats.requisitions import (
        list_purchase_requests, purchase_request_lines,
    )
    # Ces deux appels revérifient identité et droits Achats en base.
    requests = list_purchase_requests()
    # Écarter une référence étrangère avant lecture des lignes.
    if sum(r.get("demande_id") == identifier for r in requests) != 1:
        raise RequestPrintError("Référence absente ou ambiguë")
    lines = purchase_request_lines(identifier)
    return build_request_snapshot(identifier, requests, lines)
