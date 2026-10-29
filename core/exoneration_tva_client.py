"""Prévalidation pure des attestations d'exonération TVA client.

Règle métier ERP : la qualification du produit reste NORMAL ; une exonération
documentée du client peut donner une TVA facturée à zéro pour les SKU couverts.
Ce précontrôle n'affirme aucune règle juridique générale et ne réalise
aucune écriture Supabase ni facturation réelle.
"""
from __future__ import annotations

from datetime import date
from typing import Any, Mapping

from core.fiscalite_facturation import FiscaliteNonDisponible


def _date_stricte(value: Any, champ: str) -> date:
    if isinstance(value, date) and not hasattr(value, "hour"):
        return value
    if isinstance(value, str):
        try:
            parsed = date.fromisoformat(value)
            if parsed.isoformat() == value:
                return parsed
        except ValueError:
            pass
    raise FiscaliteNonDisponible(f"Exonération client : {champ} invalide")


def _texte(value: Any, champ: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise FiscaliteNonDisponible(f"Exonération client : {champ} obligatoire")
    return value.strip()


def qualifier_exoneration_client(
    client_id: str | None,
    date_facture: date,
    attestation: Mapping[str, Any] | None = None,
) -> dict[str, Any] | None:
    """Retourne une copie de preuve validée, sinon aucune exonération.

    Si une attestation est présentée mais invalide, refuse toute simulation.
    Le champ sku_ids_couverts doit être explicitement documenté : pas de
    présomption qu'une attestation couvre l'intégralité du catalogue.
    """
    if not isinstance(date_facture, date) or hasattr(date_facture, "hour"):
        raise FiscaliteNonDisponible("Date de facture invalide")
    if attestation is None:
        return None
    if not isinstance(attestation, Mapping):
        raise FiscaliteNonDisponible("Attestation client non structurée")
    identifiant = _texte(client_id, "client_id")
    if _texte(attestation.get("client_id"), "client_id") != identifiant:
        raise FiscaliteNonDisponible("Attestation appartenant à un autre client")
    if attestation.get("statut") != "VALIDEE":
        raise FiscaliteNonDisponible("Attestation client non validée")
    debut = _date_stricte(attestation.get("date_effet"), "date_effet")
    fin = _date_stricte(attestation.get("date_fin"), "date_fin")
    verification = _date_stricte(attestation.get("date_verification"), "date_verification")
    validation = _date_stricte(attestation.get("date_validation"), "date_validation")
    if fin < debut or validation < verification or validation > date_facture:
        raise FiscaliteNonDisponible("Chronologie de l'attestation incohérente")
    if not debut <= date_facture <= fin:
        raise FiscaliteNonDisponible("Attestation non applicable à cette date")
    reference = _texte(attestation.get("reference_attestation"), "reference_attestation")
    autorite = _texte(attestation.get("autorite_emettrice"), "autorite_emettrice")
    validateur = _texte(attestation.get("valide_par"), "valide_par")
    justification = _texte(attestation.get("justification"), "justification")
    portee = attestation.get("sku_ids_couverts")
    if (not isinstance(portee, (list, tuple)) or not portee
            or any(not isinstance(s, str) or not s.strip() for s in portee)
            or len(set(portee)) != len(portee)):
        raise FiscaliteNonDisponible("Portée SKU de l'attestation manquante ou invalide")
    return {
        "client_id": identifiant, "statut": "VALIDEE",
        "date_effet": debut.isoformat(), "date_fin": fin.isoformat(),
        "date_verification": verification.isoformat(),
        "date_validation": validation.isoformat(),
        "reference_attestation": reference, "autorite_emettrice": autorite,
        "valide_par": validateur, "justification": justification,
        "sku_ids_couverts": tuple(portee),
    }
