"""Contrats purs de classification fiscale SKU, valeurs fictives."""
from datetime import date
import pytest
from core.classification_fiscale import ClassificationIndisponible, selectionner_classification


def row(start="2026-01-01", end=None, **kw):
    return {"sku_id": "SKU-TEST", "date_effet": start, "date_fin": end,
            "statut_juridique": "en_vigueur", "niveau_confiance": "CONFIRMEE",
            "source": "SOURCE-FICTIVE-TEST", **kw}


def test_classification_datee_exacte():
    a = row(start="2025-01-01", end="2025-12-31")
    b = row(start="2026-01-01")
    assert selectionner_classification("SKU-TEST", date(2025, 12, 31), [a, b]) is a
    assert selectionner_classification("SKU-TEST", date(2026, 1, 1), [a, b]) is b


def test_ambiguite_interdite():
    with pytest.raises(ClassificationIndisponible, match="ambiguë"):
        selectionner_classification("SKU-TEST", date(2026, 2, 1), [row(), row()])


def test_absence_interdite():
    with pytest.raises(ClassificationIndisponible):
        selectionner_classification("SKU-INCONNU", date(2026, 2, 1), [row()])


@pytest.mark.parametrize("field,value", [
    ("statut_juridique", "a_confirmer"),
    ("niveau_confiance", "NON_VERIFIEE"),
])
def test_non_confirme_refuse(field, value):
    item = row()
    item[field] = value
    with pytest.raises(ClassificationIndisponible):
        selectionner_classification("SKU-TEST", date(2026, 2, 1), [item])


def test_source_absente_interdite():
    item = row()
    item["source"] = ""
    with pytest.raises(ClassificationIndisponible, match="Source"):
        selectionner_classification("SKU-TEST", date(2026, 2, 1), [item])
