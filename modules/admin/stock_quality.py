"""Contrôles de cohérence Stocks (lecture seule, synthèses anonymisées).

Le total des lots ne représente PAS forcément le stock comptable : certains
mouvements historiques ne portent pas de lot. L'écart est donc indicatif.
"""
from __future__ import annotations

from collections import Counter
from decimal import Decimal, InvalidOperation

REQUIRED = (
    "matieres_premieres", "sku_conditionnement", "lots",
    "stock_actuel", "stock_actuel_pf",
)


def _decimal(value) -> Decimal | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        v = Decimal(str(value).strip())
    except (InvalidOperation, ValueError, TypeError):
        return None
    return v if v.is_finite() else None


def _ids(rows, field) -> set[str]:
    return {
        str(row[field]).strip() for row in rows
        if row.get(field) is not None and str(row[field]).strip()
    }


def audit_stocks(rows_by_table: dict) -> list[dict]:
    """Contrôles de format et de références, sans inférer de quantité réelle."""
    for table in REQUIRED:
        rows = rows_by_table[table]
        if not isinstance(rows, list) or any(not isinstance(x, dict) for x in rows):
            raise ValueError(f"Référentiel {table} invalide")
    mp = _ids(rows_by_table["matieres_premieres"], "mp_id")
    sku = _ids(rows_by_table["sku_conditionnement"], "sku_id")
    out = []
    for label, table, id_col, id_values in (
        ("Stock matières premières", "stock_actuel", "mp_id", mp),
        ("Stock produits finis", "stock_actuel_pf", "sku_id", sku),
    ):
        rows = rows_by_table[table]
        ids = [str(x.get(id_col) or "").strip() for x in rows]
        duplicate = sum(n - 1 for n in Counter(ids).values() if n > 1 and n)
        missing = sum(not value for value in ids)
        missing_references = sum(bool(value) and value not in id_values for value in ids)
        invalid = sum(_decimal(x.get("quantite_disponible")) is None for x in rows)
        negative = sum(
            (num := _decimal(x.get("quantite_disponible"))) is not None and num < 0
            for x in rows
        )
        out.append({
            "Section": label, "Enregistrements": len(rows),
            "ID manquants": missing, "ID en doublon": duplicate,
            "Références introuvables": missing_references,
            "Quantités invalides": invalid,
            "Quantités négatives": negative,
            "Lots au-delà de l'initial": 0,
        })
    lots = rows_by_table["lots"]
    bad_lot_ref = 0
    invalid_lot = 0
    negative_lot = 0
    excessive_lot = 0
    missing_lot_ids = 0
    for lot in lots:
        lot_id = str(lot.get("lot_id") or "").strip()
        if not lot_id:
            missing_lot_ids += 1
        item_type = str(lot.get("type_item") or "").strip().upper()
        item_id = str(lot.get("item_id") or "").strip()
        expected = mp if item_type == "MP" else sku if item_type == "PF" else None
        if expected is None or not item_id or item_id not in expected:
            bad_lot_ref += 1
        initial = _decimal(lot.get("quantite_initiale"))
        remaining = _decimal(lot.get("quantite_restante"))
        if initial is None or remaining is None:
            invalid_lot += 1
            continue
        if initial < 0 or remaining < 0:
            negative_lot += 1
        if remaining > initial:
            excessive_lot += 1
    out.append({
        "Section": "Lots", "Enregistrements": len(lots),
        "ID manquants": missing_lot_ids,
        "ID en doublon": sum(n - 1 for n in Counter(
            str(lot.get("lot_id") or "").strip() for lot in lots
            if str(lot.get("lot_id") or "").strip()
        ).values() if n > 1),
        "Références introuvables": bad_lot_ref,
        "Quantités invalides": invalid_lot,
        "Quantités négatives": negative_lot,
        "Lots au-delà de l'initial": excessive_lot,
    })
    return out


def audit_stocks_autorise(*, reader=None) -> list[dict]:
    """Lectures paginées RBAC réévaluées ; refus d'un bilan incomplet."""
    if reader is None:
        from core.db_service import fetch_data_paginated
        reader = lambda table: fetch_data_paginated(
            table, page_size=200, max_rows=5000)
    return audit_stocks({table: reader(table) for table in REQUIRED})


def audit_stock_movements(rows_by_table: dict) -> list[dict]:
    """Audit de références mouvements et lots, sans rapprochement de soldes."""
    for table in ("matieres_premieres", "sku_conditionnement", "lots",
                  "mouvements", "mouvements_pf"):
        value = rows_by_table[table]
        if not isinstance(value, list) or any(not isinstance(row, dict) for row in value):
            raise ValueError(f"Lecture {table} invalide")
    mp = _ids(rows_by_table["matieres_premieres"], "mp_id")
    sku = _ids(rows_by_table["sku_conditionnement"], "sku_id")
    lot_map = {
        str(row["lot_id"]).strip(): (
            str(row.get("type_item") or "").strip().upper(),
            str(row.get("item_id") or "").strip(),
        )
        for row in rows_by_table["lots"]
        if row.get("lot_id") is not None and str(row.get("lot_id")).strip()
    }
    result = []
    for section, table, reference_field, acceptable, type_item in (
        ("Mouvements MP", "mouvements", "mp_id", mp, "MP"),
        ("Mouvements PF", "mouvements_pf", "sku_id", sku, "PF"),
    ):
        records = rows_by_table[table]
        absent = wrong_lot = wrong_qty = negatives = unexpected_kind = 0
        for row in records:
            identifier = str(row.get(reference_field) or "").strip()
            if not identifier or identifier not in acceptable:
                absent += 1
            qty = _decimal(row.get("quantite"))
            if qty is None:
                wrong_qty += 1
            elif qty <= 0:
                negatives += 1
            if str(row.get("type_mouvement") or "").strip().upper() not in (
                "ENTREE", "SORTIE"
            ):
                unexpected_kind += 1
            lot_id = str(row.get("lot_id") or "").strip()
            if lot_id and lot_map.get(lot_id) != (type_item, identifier):
                wrong_lot += 1
        result.append({
            "Section": section, "Enregistrements": len(records),
            "Articles introuvables": absent,
            "Lots absents ou incompatibles": wrong_lot,
            "Quantités invalides": wrong_qty,
            "Quantités non positives": negatives,
            "Types inconnus": unexpected_kind,
        })
    return result


def audit_stock_movements_autorise(*, reader=None) -> list[dict]:
    """Aucun rapport si la lecture d'une table est refusée ou partielle."""
    if reader is None:
        from core.db_service import fetch_data_paginated
        reader = lambda table: fetch_data_paginated(
            table, page_size=200, max_rows=5000)
    selected = ("matieres_premieres", "sku_conditionnement", "lots",
                "mouvements", "mouvements_pf")
    return audit_stock_movements({name: reader(name) for name in selected})
