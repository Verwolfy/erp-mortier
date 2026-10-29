"""Précontrôle fiscal pur d'un panier, sans calcul de taxe ni écriture SQL.

Ne remplace pas erp_sale_transaction. Interdit de considérer un panier comme
qualifié tant que chaque SKU n'a pas une classification validée et datée.
"""
from __future__ import annotations

from datetime import date
from typing import Any, Mapping, Sequence

from core.classification_fiscale import (
    ClassificationIndisponible,
    selectionner_classification_bdd,
)


def verifier_panier_fiscal(
    lignes: Sequence[Mapping[str, Any]],
    date_operation: date,
    classifications: Sequence[Mapping[str, Any]],
) -> list[Mapping[str, Any]]:
    if not isinstance(lignes, (list, tuple)) or not lignes:
        raise ClassificationIndisponible("Panier fiscal vide ou invalide")
    if len(lignes) > 500:
        raise ClassificationIndisponible("Panier fiscal supérieur à 500 lignes")
    if not isinstance(date_operation, date) or hasattr(date_operation, "hour"):
        raise ClassificationIndisponible("Date d'opération invalide")
    if not isinstance(classifications, (list, tuple)):
        raise ClassificationIndisponible("Référentiel fiscal invalide")
    for classement in classifications:
        if not isinstance(classement, Mapping):
            raise ClassificationIndisponible("Ligne de référentiel fiscal non structurée")
    resultats = []
    for ligne in lignes:
        if not isinstance(ligne, Mapping):
            raise ClassificationIndisponible("Ligne fiscale non structurée")
        sku = ligne.get("sku_id")
        if not isinstance(sku, str) or not sku.strip():
            raise ClassificationIndisponible("SKU obligatoire sur chaque ligne")
        resultats.append(
            selectionner_classification_bdd(sku, date_operation, classifications)
        )
    return resultats
