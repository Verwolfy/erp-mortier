"""Reconstruction pure d'une attestation TVA client depuis les 2 tables 025.

Entrées transmises par un service serveur déjà autorisé. Aucun appel réseau,
aucune écriture ou activation de facturation. Échoue sans arbitrage implicite
en cas de dossiers concurrents, de portée vide ou de statut non validé.
"""
from __future__ import annotations

from datetime import date
from typing import Any, Mapping, Sequence
from uuid import UUID

from core.exoneration_tva_client import qualifier_exoneration_client, _date_stricte
from core.fiscalite_facturation import FiscaliteNonDisponible


def _uuid_strict(value: Any) -> str:
    if not isinstance(value, str):
        raise FiscaliteNonDisponible("Identifiant d'attestation invalide")
    try:
        parsed = UUID(value)
    except (ValueError, AttributeError) as exc:
        raise FiscaliteNonDisponible("Identifiant d'attestation invalide") from exc
    if str(parsed) != value:
        raise FiscaliteNonDisponible("Identifiant d'attestation non canonique")
    return value


def selectionner_attestation_client(
    client_id: str,
    date_operation: date,
    entetes: Sequence[Mapping[str, Any]],
    portees: Sequence[Mapping[str, Any]],
) -> dict[str, Any] | None:
    """Sélectionne un dossier daté unique et sa portée SKU.

    None veut dire **aucune attestation applicable enregistrée** : cela ne
    certifie PAS que le client n'est pas exonéré. En cas de dossier applicable
    en attente/révoqué, refuser au lieu d'appliquer silencieusement 0/19 %.
    """
    if not isinstance(client_id, str) or not client_id.strip():
        raise FiscaliteNonDisponible("Identité client obligatoire")
    if not isinstance(date_operation, date) or hasattr(date_operation, "hour"):
        raise FiscaliteNonDisponible("Date d'opération invalide")
    if not isinstance(entetes, (list, tuple)) or not isinstance(portees, (list, tuple)):
        raise FiscaliteNonDisponible("Registre d'attestations incomplet")
    if len(entetes) > 1000 or len(portees) > 10000:
        raise FiscaliteNonDisponible("Registre d'attestations trop volumineux")
    if any(not isinstance(row, Mapping) for row in (*entetes, *portees)):
        raise FiscaliteNonDisponible("Ligne d'attestation non structurée")

    ids: set[str] = set()
    valides: list[Mapping[str, Any]] = []
    for entete in entetes:
        attestation_id = _uuid_strict(entete.get("attestation_id"))
        if attestation_id in ids:
            raise FiscaliteNonDisponible("Attestation dupliquée")
        ids.add(attestation_id)
        if entete.get("client_id") != client_id:
            continue
        debut = _date_stricte(entete.get("date_effet"), "date_effet")
        fin = _date_stricte(entete.get("date_fin"), "date_fin")
        if fin < debut:
            raise FiscaliteNonDisponible("Période d'attestation invalide")
        if debut <= date_operation <= fin:
            valides.append(entete)
    if len(valides) > 1:
        raise FiscaliteNonDisponible("Attestations client concurrentes à arbitrer")
    if not valides:
        return None

    entete = valides[0]
    if entete.get("statut") != "VALIDEE":
        raise FiscaliteNonDisponible("Attestation client non validée ou révoquée")
    identifiant = entete["attestation_id"]
    sku_ids: list[str] = []
    vus: set[str] = set()
    for portee in portees:
        portee_id = _uuid_strict(portee.get("attestation_id"))
        if portee_id != identifiant:
            continue
        sku_id = portee.get("sku_id")
        if not isinstance(sku_id, str) or not sku_id.strip() or sku_id in vus:
            raise FiscaliteNonDisponible("Portée SKU de l'attestation invalide")
        vus.add(sku_id)
        sku_ids.append(sku_id)
    if not isinstance(entete.get("reference_piece_interne"), str) or not entete["reference_piece_interne"].strip():
        raise FiscaliteNonDisponible("Référence de pièce justificative absente")
    preuve = qualifier_exoneration_client(
        client_id, date_operation,
        {
            **entete,
            "sku_ids_couverts": sku_ids,
        }
    )
    if preuve is None:
        raise FiscaliteNonDisponible("Attestation non sélectionnable")
    return {
        **preuve, "attestation_id": identifiant,
        "reference_piece_interne": entete["reference_piece_interne"].strip(),
    }
