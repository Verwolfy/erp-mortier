"""Revue des attestations TVA en lecture seule, réservée SECURITY_MANAGER.

Le gestionnaire est ré-authentifié par RPC serveur avant toute requête.
Aucune opération d'écriture ni lecture des pièces de stockage.
"""
from __future__ import annotations

from typing import Any
from core.db_service import get_supabase_client
from core.security_service import require_security_manager

_MAX_DOSSIERS = 500
_MAX_PORTEES = 2000


def lister_attestations_pour_manager() -> list[dict[str, Any]]:
    require_security_manager()  # fail-closed, identité utilisateur vérifiée par RPC
    client = get_supabase_client()
    headers = (
        client.table("erp_exonerations_tva_clients")
        .select("attestation_id,client_id,reference_attestation,"
                "reference_piece_interne,date_effet,date_fin,statut,"
                "date_verification,date_validation,valide_par")
        .order("attestation_id").range(0, _MAX_DOSSIERS).execute().data
    )
    if not isinstance(headers, list) or len(headers) > _MAX_DOSSIERS:
        raise RuntimeError("Liste d'attestations incomplète ou indisponible")
    if not headers:
        return []
    if any(not isinstance(row, dict) or not isinstance(row.get("attestation_id"), str)
           for row in headers):
        raise RuntimeError("Dossier d'attestation non structuré")
    ids = [row["attestation_id"] for row in headers]
    if len(set(ids)) != len(ids):
        raise RuntimeError("Référentiel d'attestations incohérent")
    portees = (
        client.table("erp_exonerations_tva_skus")
        .select("attestation_id,sku_id")
        .order("attestation_id").range(0, _MAX_PORTEES).execute().data
    )
    if not isinstance(portees, list) or len(portees) > _MAX_PORTEES:
        raise RuntimeError("Portées SKU incomplètes ou indisponibles")
    if any(not isinstance(row, dict) for row in portees):
        raise RuntimeError("Portée SKU non structurée")
    compte: dict[str, int] = {id: 0 for id in ids}
    for row in portees:
        attestation_id, sku_id = row.get("attestation_id"), row.get("sku_id")
        if attestation_id not in compte or not isinstance(sku_id, str) or not sku_id:
            raise RuntimeError("Portée orpheline ou invalide")
        compte[attestation_id] += 1
    return [
        {**row, "nombre_sku_couverts": compte[row["attestation_id"]]}
        for row in headers
    ]


def creer_brouillon_attestation(
    payload: dict[str, Any], *, operation_id: str,
) -> str:
    """Crée atomiquement un dossier A_VALIDER ; aucune exonération accordée.

    operation_id DOIT être conservé lors d'une reprise après échec réseau.
    Toute décision de validation reste réservée au second circuit fiscal SQL.
    """
    from datetime import date
    from uuid import UUID

    if not isinstance(payload, dict):
        raise ValueError("Dossier d'attestation invalide")
    obligatoires = {
        "client_id", "reference_attestation", "autorite_emettrice",
        "reference_piece_interne", "justification", "date_effet",
        "date_fin", "sku_ids",
    }
    if set(payload) != obligatoires:
        raise ValueError("Champs du dossier d'attestation incohérents")
    limites = {
        "client_id": 200, "reference_attestation": 200,
        "autorite_emettrice": 200, "reference_piece_interne": 250,
        "justification": 2000,
    }
    for champ, maximum in limites.items():
        val = payload[champ]
        if not isinstance(val, str) or not 1 <= len(val.strip()) <= maximum:
            raise ValueError(f"{champ} obligatoire ou trop long")
        if any(ord(ch) < 32 for ch in val):
            raise ValueError(f"{champ} : caractères de contrôle interdits")
    for champ in ("date_effet", "date_fin"):
        val = payload[champ]
        if not isinstance(val, str):
            raise ValueError(f"{champ} invalide")
        try:
            parsed = date.fromisoformat(val)
        except ValueError as exc:
            raise ValueError(f"{champ} invalide") from exc
        if parsed.isoformat() != val:
            raise ValueError(f"{champ} invalide")
    if payload["date_fin"] < payload["date_effet"]:
        raise ValueError("Période de l'attestation invalide")
    skus = payload["sku_ids"]
    if (not isinstance(skus, list) or not 1 <= len(skus) <= 200
        or any(not isinstance(x, str) or not x.strip() for x in skus)
        or len(set(skus)) != len(skus)):
        raise ValueError("Portée SKU invalide")
    if not isinstance(operation_id, str):
        raise ValueError("Identifiant d'opération requis")
    try:
        op = UUID(operation_id)
    except (ValueError, AttributeError) as exc:
        raise ValueError("Identifiant d'opération invalide") from exc
    if str(op) != operation_id:
        raise ValueError("Identifiant d'opération non canonique")

    acteur = require_security_manager()  # autorisation fraîche avant RPC
    response = get_supabase_client().rpc("erp_exoneration_tva_action", {
        "p_actor_id": acteur,
        "p_action": "CREER_BROUILLON",
        "p_operation_id": operation_id,
        "p_payload": payload,
    }).execute()
    resultat = response.data
    if not isinstance(resultat, dict):
        raise RuntimeError("Réponse de création d'attestation non confirmée")
    if (resultat.get("operation_id") != operation_id
        or resultat.get("action") != "CREER_BROUILLON"
        or resultat.get("statut") != "A_VALIDER"):
        raise RuntimeError("Transaction d'attestation non vérifiable")
    attestation_id = resultat.get("attestation_id")
    if not isinstance(attestation_id, str):
        raise RuntimeError("Référence d'attestation non confirmée")
    try:
        if str(UUID(attestation_id)) != attestation_id:
            raise ValueError
    except (ValueError, AttributeError) as exc:
        raise RuntimeError("Référence d'attestation invalide") from exc
    return attestation_id
