"""Audit qualité transverse des référentiels, strictement en lecture seule.

Aucun enregistrement individuel n'est retourné dans le bilan : seulement des
comptages et des catégories de problèmes. Le service de lecture ERP contrôle
l'autorisation de chaque table avant toute consultation.
"""
from __future__ import annotations

from collections import Counter

TABLES = {
    "Clients": ("clients", "client_id"),
    "Fournisseurs": ("fournisseurs", "fournisseur_id"),
    "Produits": ("produits", "pf_id"),
    "SKU": ("sku_conditionnement", "sku_id"),
    "Matières premières": ("matieres_premieres", "mp_id"),
}


def _active(value) -> bool:
    return str(value).strip().upper() in {"OUI", "ACTIF", "TRUE", "1"}


def _blank(value) -> bool:
    return not str(value if value is not None else "").strip()


def audit_referentiels(rows_by_table: dict) -> list[dict]:
    """Audit de structure sans inventer de normalisation juridique."""
    output = []
    for section, (table, key) in TABLES.items():
        rows = rows_by_table[table]
        if not isinstance(rows, list):
            raise ValueError(f"Lecture {table} invalide")
        if any(not isinstance(item, dict) for item in rows):
            raise ValueError(f"Ligne {table} invalide")
        ids = [str(x.get(key)).strip() for x in rows if not _blank(x.get(key))]
        duplicates = sum(n - 1 for n in Counter(ids).values() if n > 1)
        missing_id = sum(_blank(row.get(key)) for row in rows)
        missing_name = sum(_blank(row.get("nom")) for row in rows) if table != "sku_conditionnement" else 0
        inactive = sum(not _active(row.get("actif")) for row in rows)
        output.append({
            "Section": section, "Enregistrements": len(rows),
            "Inactifs / à vérifier": inactive,
            "ID manquants": missing_id,
            "ID en doublon": duplicates,
            "Désignations manquantes": missing_name,
            "Liens invalides": 0,
        })
    products = {
        str(row["pf_id"]).strip() for row in rows_by_table["produits"]
        if not _blank(row.get("pf_id"))
    }
    sku_rows = rows_by_table["sku_conditionnement"]
    invalid_links = sum(
        _blank(item.get("pf_id")) or str(item["pf_id"]).strip() not in products
        for item in sku_rows
    )
    output[3]["Liens invalides"] = invalid_links
    return output


def audit_autorise(*, reader=None) -> list[dict]:
    """Fail-closed : aucune synthèse partielle en cas de refus de droits."""
    if reader is None:
        from core.db_service import fetch_data_paginated
        reader = lambda table: fetch_data_paginated(
            table, page_size=200, max_rows=5000)
    readings = {}
    for table, _ in TABLES.values():
        readings[table] = reader(table)
    return audit_referentiels(readings)
