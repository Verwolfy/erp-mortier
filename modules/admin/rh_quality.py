"""Contrôles RH agrégés et non modifiants, sans divulgation d'employés."""
from datetime import date
from decimal import Decimal, InvalidOperation

TABLES = ("employes", "demandes_conges", "projets", "taches", "feuilles_de_temps")


def _id(value):
    return str(value if value is not None else "").strip()


def _date(value):
    if not isinstance(value, str):
        return None
    try:
        return date.fromisoformat(value)
    except ValueError:
        return None


def _hours(value):
    if value is None or isinstance(value, bool):
        return None
    try:
        hours = Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError):
        return None
    return hours if hours.is_finite() else None


def audit_rh(data):
    for table in TABLES:
        rows = data[table]
        if not isinstance(rows, list) or any(not isinstance(r, dict) for r in rows):
            raise ValueError("Lecture RH incomplète")
    employees = {_id(x.get("employe_id")) for x in data["employes"]}
    projects = {_id(x.get("projet_id")) for x in data["projets"]}
    tasks = {_id(x.get("tache_id")) for x in data["taches"]}
    result = []
    for title, table, ref, ids, mandatory in (
        ("Congés / employés", "demandes_conges", "employe_id", employees, True),
        ("Tâches / projets", "taches", "projet_id", projects, True),
        ("Tâches / affectations", "taches", "assigne_a", employees, False),
        ("Temps / employés", "feuilles_de_temps", "employe_id", employees, True),
        ("Temps / tâches", "feuilles_de_temps", "tache_id", tasks, True),
    ):
        records = data[table]
        result.append({
            "Section": title, "Enregistrements": len(records),
            "Liens manquants": sum(mandatory and not _id(row.get(ref)) for row in records),
            "Liens introuvables": sum(
                bool(_id(row.get(ref))) and _id(row.get(ref)) not in ids
                for row in records),
            "Dates invalides": 0, "Périodes inversées": 0,
            "Durées invalides": 0,
        })
    for row in data["demandes_conges"]:
        begin, end = _date(row.get("date_debut")), _date(row.get("date_fin"))
        if begin is None or end is None:
            result[0]["Dates invalides"] += 1
        elif end < begin:
            result[0]["Périodes inversées"] += 1
    for row in data["feuilles_de_temps"]:
        hours = _hours(row.get("heures"))
        if hours is None or hours <= 0 or hours > 24:
            result[3]["Durées invalides"] += 1
        if _date(row.get("date")) is None:
            result[3]["Dates invalides"] += 1
    return result


def audit_rh_autorise(*, reader=None):
    if reader is None:
        from core.db_service import fetch_data_paginated
        reader = lambda table: fetch_data_paginated(table, page_size=200, max_rows=5000)
    data = {table: reader(table) for table in TABLES}
    return audit_rh(data)
