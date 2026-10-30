"""Lecture du précontrôle fiscal de vente (SQL 031), sans facturation.

La réponse n'est jamais une autorisation d'émettre une facture. L'appelant
doit confirmer indépendamment l'identité et les droits de l'opérateur Ventes.
Le contrôle de la TVA à 0 % restera à intégrer atomiquement à la future RPC
transactionnelle de vente, après homologation juridique.
"""
from __future__ import annotations

from datetime import date
from uuid import UUID

from core.db_service import get_supabase_client


class PrecontroleTVAIndisponible(ValueError):
    """Réponse fiscale absente ou potentiellement incorrecte."""


def verifier_exoneration_panier(
    client_id: str, sku_ids: list[str], date_facture: date
) -> dict:
    if not isinstance(client_id, str) or not 1 <= len(client_id.strip()) <= 200:
        raise PrecontroleTVAIndisponible("Client invalide")
    if (not isinstance(sku_ids, list) or not 1 <= len(sku_ids) <= 200
            or any(not isinstance(s, str) or not s.strip() for s in sku_ids)
            or len(sku_ids) != len(set(sku_ids))):
        raise PrecontroleTVAIndisponible("SKU invalides")
    if (not isinstance(date_facture, date) or hasattr(date_facture, "hour")
            or date_facture > date.today()):
        raise PrecontroleTVAIndisponible("Date facture invalide")
    response = get_supabase_client().rpc(
        "erp_exoneration_tva_precontrole_vente",
        {
            "p_client_id": client_id,
            "p_sku_ids": sku_ids,
            "p_date_facture": date_facture.isoformat(),
        },
    ).execute()
    result = response.data
    if not isinstance(result, dict) or result.get("autorise_facturation") is not False:
        raise PrecontroleTVAIndisponible("Réponse fiscale non sécurisée")

    statut = result.get("statut")
    motifs = {
        "AUCUN_DOSSIER": {"AUCUNE_PREUVE_ENREGISTREE"},
        "A_BLOQUER": {
            "CLIENT_INACTIF_OU_INCONNU", "SKU_INACTIF_OU_INCONNU",
            "ATTESTATIONS_CONCURRENTES", "ATTESTATION_NON_HOMOLOGUEE",
            "PORTEE_SKU_PARTIELLE",
        },
        "PRECONTROLE_OK": {"ATTESTATION_ET_PORTEE_VERIFIEES"},
    }
    if statut not in motifs or result.get("motif") not in motifs[statut]:
        raise PrecontroleTVAIndisponible("Statut fiscal inconnu")

    if statut == "PRECONTROLE_OK":
        value = result.get("attestation_id")
        try:
            if not isinstance(value, str) or str(UUID(value)) != value:
                raise ValueError
        except (ValueError, AttributeError) as exc:
            raise PrecontroleTVAIndisponible(
                "Référence d'attestation invalide"
            ) from exc
        if result.get("nombre_sku") != len(sku_ids):
            raise PrecontroleTVAIndisponible("Nombre de SKU incohérent")
        reference = result.get("reference_attestation")
        if not isinstance(reference, str) or not reference.strip():
            raise PrecontroleTVAIndisponible("Preuve d'attestation absente")
    elif result.get("attestation_id") is not None:
        raise PrecontroleTVAIndisponible(
            "Attestation fournie malgré le refus fiscal"
        )

    # Une copie explicite empêche qu'un autre champ injecté dans la réponse
    # (p. ex. taux 0 ou facture autorisée) soit exposé comme autorité.
    sortie = {
        "statut": statut, "motif": result["motif"],
        "autorise_facturation": False,
    }
    if statut == "PRECONTROLE_OK":
        sortie.update({
            "attestation_id": result["attestation_id"],
            "reference_attestation": result["reference_attestation"],
            "date_validation": result.get("date_validation"),
            "nombre_sku": len(sku_ids),
        })
    return sortie
