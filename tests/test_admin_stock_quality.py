"""Contrôles de cohérence Stocks sans écriture de données."""
import pytest

from modules.admin.stock_quality import audit_stocks, audit_stocks_autorise


def _data():
    return {
        "matieres_premieres": [{"mp_id": "MP1"}],
        "sku_conditionnement": [{"sku_id": "SKU1"}],
        "stock_actuel": [
            {"mp_id": "MP1", "quantite_disponible": "10.5"},
            {"mp_id": "MP2", "quantite_disponible": "-2"},
            {"mp_id": "MP1", "quantite_disponible": "NaN"},
        ],
        "stock_actuel_pf": [
            {"sku_id": "SKU1", "quantite_disponible": "0"},
        ],
        "lots": [
            {"lot_id": "L1", "type_item": "MP", "item_id": "MP1",
             "quantite_initiale": "10", "quantite_restante": "12"},
            {"lot_id": "L2", "type_item": "PF", "item_id": "INCONNU",
             "quantite_initiale": "2", "quantite_restante": "-1"},
            {"lot_id": "L3", "type_item": "ZZ", "item_id": "MP1",
             "quantite_initiale": "texte", "quantite_restante": "4"},
        ],
    }


def test_stocks_quantites_lots_references():
    data = _data()
    report = audit_stocks(data)
    assert len(report) == 3
    assert report[0]["ID en doublon"] == 1
    assert report[0]["Références introuvables"] == 1
    assert report[0]["Quantités invalides"] == 1
    assert report[0]["Quantités négatives"] == 1
    assert report[1]["Quantités négatives"] == 0
    assert report[2]["Références introuvables"] == 2
    assert report[2]["Quantités invalides"] == 1
    assert report[2]["Quantités négatives"] == 1
    assert report[2]["Lots au-delà de l'initial"] == 1
    assert all("mp_id" not in row and "sku_id" not in row for row in report)


def test_stocks_refus_rbac_et_lectures_invalides():
    data = _data()
    assert audit_stocks_autorise(reader=lambda table: data[table]) == audit_stocks(data)

    def denied(table):
        if table == "lots":
            raise PermissionError("Lecture interdite")
        return data[table]

    with pytest.raises(PermissionError):
        audit_stocks_autorise(reader=denied)
    with pytest.raises(ValueError):
        audit_stocks({**data, "lots": ["malformed"]})


def test_ui_stock_audit_lecture_seule():
    from pathlib import Path
    view = Path("modules/admin/views.py").read_text(encoding="utf-8")
    service = Path("modules/admin/stock_quality.py").read_text(encoding="utf-8")
    assert "Analyser les stocks autorisés" in view
    assert "audit_stocks_autorise()" in view
    assert "fetch_data_paginated" in service
    assert "insert_hybrid" not in service
    assert "update_hybrid" not in service


def test_mouvements_quantites_articles_lots_et_types():
    from modules.admin.stock_quality import audit_stock_movements
    rows = _data()
    rows["mouvements"] = [
        {"mp_id": "MP1", "quantite": "4", "type_mouvement": "ENTREE", "lot_id": "L1"},
        {"mp_id": "MP1", "quantite": "0", "type_mouvement": "SORTIE", "lot_id": "L2"},
        {"mp_id": "MP404", "quantite": "NaN", "type_mouvement": "AUTRE", "lot_id": "X"},
    ]
    rows["mouvements_pf"] = [
        {"sku_id": "SKU1", "quantite": "2", "type_mouvement": "SORTIE", "lot_id": ""},
    ]
    result = audit_stock_movements(rows)
    assert result[0]["Articles introuvables"] == 1
    assert result[0]["Lots absents ou incompatibles"] == 2
    assert result[0]["Quantités invalides"] == 1
    assert result[0]["Quantités non positives"] == 1
    assert result[0]["Types inconnus"] == 1
    assert result[1]["Articles introuvables"] == 0
    assert result[1]["Lots absents ou incompatibles"] == 0


def test_mouvements_audit_refus_lecture_partielle():
    from modules.admin.stock_quality import audit_stock_movements_autorise
    rows = _data()
    rows["mouvements"] = []
    rows["mouvements_pf"] = []
    assert len(audit_stock_movements_autorise(
        reader=lambda name: rows[name])) == 2
    with pytest.raises(PermissionError):
        audit_stock_movements_autorise(
            reader=lambda name: (_ for _ in ()).throw(PermissionError("Refus"))
        )


def test_ui_mouvements_sans_prise_ecriture():
    from pathlib import Path
    code = Path("modules/admin/views.py").read_text(encoding="utf-8")
    assert "Analyser les mouvements de stock autorisés" in code
    service = Path("modules/admin/stock_quality.py").read_text(encoding="utf-8")
    assert "insert_hybrid" not in service and "update_hybrid" not in service
