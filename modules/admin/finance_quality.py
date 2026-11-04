"""Contrôles Finance agrégés, sans écriture ni exposition de données individuelles."""
from decimal import Decimal, InvalidOperation

TABLES = ("comptes", "reglements", "lettrage", "ecritures_comptables")


def _value(value):
    return str(value if value is not None else "").strip()


def _number(value):
    if value is None or isinstance(value, bool) or not _value(value):
        return None
    try:
        amount = Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError):
        return None
    return amount if amount.is_finite() else None


def audit_finance(data):
    for table in TABLES:
        rows = data[table]
        if not isinstance(rows, list) or any(not isinstance(x, dict) for x in rows):
            raise ValueError("Lecture Finance incomplète")
    comptes = {_value(x.get("compte_id")) for x in data["comptes"]}
    regl = {_value(x.get("reglement_id")) for x in data["reglements"]}
    report = []
    for label, table, column, references in (
        ("Règlements / comptes", "reglements", "compte_id", comptes),
        ("Lettrage / règlements", "lettrage", "reglement_id", regl),
        ("Écritures / comptes", "ecritures_comptables", "compte_id", comptes),
    ):
        rows = data[table]
        report.append({
            "Section": label, "Enregistrements": len(rows),
            "Liens manquants": sum(not _value(x.get(column)) for x in rows),
            "Liens introuvables": sum(
                bool(_value(x.get(column))) and _value(x.get(column)) not in references
                for x in rows),
            "Montants invalides": 0, "Montants négatifs": 0,
            "Allocations supérieures au règlement": 0,
        })
    for x in data["reglements"]:
        amount, allocated = _number(x.get("montant_total")), _number(x.get("montant_alloue"))
        if amount is None or allocated is None:
            report[0]["Montants invalides"] += 1
        else:
            report[0]["Montants négatifs"] += int(amount < 0 or allocated < 0)
            report[0]["Allocations supérieures au règlement"] += int(allocated > amount)
    for x in data["lettrage"]:
        amount = _number(x.get("montant_applique"))
        if amount is None:
            report[1]["Montants invalides"] += 1
        elif amount < 0:
            report[1]["Montants négatifs"] += 1
    for x in data["ecritures_comptables"]:
        debit, credit = _number(x.get("debit")), _number(x.get("credit"))
        if debit is None or credit is None:
            report[2]["Montants invalides"] += 1
        elif debit < 0 or credit < 0:
            report[2]["Montants négatifs"] += 1
    return report


def audit_finance_autorise(*, reader=None):
    if reader is None:
        from core.db_service import fetch_data_paginated
        reader = lambda table: fetch_data_paginated(table, page_size=200, max_rows=5000)
    data = {table: reader(table) for table in TABLES}
    return audit_finance(data)
