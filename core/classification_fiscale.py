"""Tests de classification fiscale datée : aucune décision implicite par SKU."""
from datetime import date
from typing import Any, Mapping


class ClassificationIndisponible(ValueError):
    """Une classification fiscale valide et documentée manque."""


def selectionner_classification(
    sku_id: str, date_operation: date,
    classifications: list[Mapping[str, Any]],
) -> Mapping[str, Any]:
    if not isinstance(sku_id, str) or not sku_id.strip():
        raise ClassificationIndisponible("SKU obligatoire")
    if not isinstance(date_operation, date) or hasattr(date_operation, "hour"):
        raise ClassificationIndisponible("Date d'opération invalide")
    candidates = []
    for row in classifications:
        if row.get("sku_id") != sku_id:
            continue
        if row.get("statut_juridique") != "en_vigueur" or row.get("niveau_confiance") != "CONFIRMEE":
            continue
        if not isinstance(row.get("source"), str) or not row["source"].strip():
            raise ClassificationIndisponible("Source juridique absente")
        try:
            start = date.fromisoformat(row["date_effet"])
            end = date.fromisoformat(row["date_fin"]) if row.get("date_fin") else None
        except (TypeError, ValueError) as exc:
            raise ClassificationIndisponible("Date de classification invalide") from exc
        if end and end < start:
            raise ClassificationIndisponible("Intervalle invalide")
        if start <= date_operation and (end is None or date_operation <= end):
            candidates.append(row)
    if len(candidates) != 1:
        raise ClassificationIndisponible("Classification absente ou ambiguë")
    return candidates[0]
