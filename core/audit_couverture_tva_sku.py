"""Diagnostic en lecture seule de la couverture TVA du catalogue de SKU.

Pure fonction, sans connexion à Supabase et sans calcul de facture.
Un catalogue préqualifié ne signifie jamais que la facturation est activable :
le régime de l'entreprise, les quittances, la RPC et les droits sont distincts.
"""
from __future__ import annotations

from datetime import date
from typing import Any, Mapping, Sequence

from core.classification_fiscale import ClassificationIndisponible
from core.fiscalite_facturation import FiscaliteNonDisponible
from core.liaison_tva_sku import taux_par_ligne


def auditer_couverture_tva(
    sku_actifs: Sequence[str],
    date_operation: date,
    classifications: Sequence[Mapping[str, Any]],
    parametres: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    """Renvoie les SKU préqualifiés et les blocages documentés par SKU."""
    if not isinstance(date_operation, date) or hasattr(date_operation, "hour"):
        raise ValueError("Date d'audit fiscale invalide")
    if not isinstance(sku_actifs, (list, tuple)):
        raise ValueError("Liste de SKU actifs invalide")
    if len(sku_actifs) != len(set(sku_actifs)) or any(
        not isinstance(s, str) or not s.strip() for s in sku_actifs
    ):
        raise ValueError("Liste SKU invalide ou doublonnée")
    resultats = []
    for sku in sku_actifs:
        try:
            tva = taux_par_ligne(
                [{"sku_id": sku}], date_operation, classifications, parametres
            )[0]
            resultats.append({
                "sku_id": sku, "prequalifie": True,
                "categorie_tva": tva["categorie_tva"],
                "code_source": tva["justificatif_taux"]["code"],
                "blocage": None,
            })
        except (ClassificationIndisponible, FiscaliteNonDisponible) as exc:
            resultats.append({
                "sku_id": sku, "prequalifie": False,
                "categorie_tva": None, "code_source": None,
                "blocage": str(exc),
            })
    qualifie = sum(1 for ligne in resultats if ligne["prequalifie"])
    return {
        "date_audit": date_operation.isoformat(),
        "sku_actifs": len(sku_actifs),
        "sku_prequalifies": qualifie,
        "prequalification_catalogue_complete": bool(sku_actifs) and qualifie == len(sku_actifs),
        "autorise_activation_facturation": False,
        "resultats": resultats,
    }
