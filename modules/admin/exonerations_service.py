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
