"""Audit structurel Achats/Ventes : lecture seule, aucune donnée individuelle publiée.

Les documents historiques peuvent être partiels : un lien manquant est un
signalement à examiner, pas une preuve de fraude ou d'erreur comptable.
"""
from __future__ import annotations

from collections import Counter
from decimal import Decimal, InvalidOperation


# Libellé, table des lignes, identifiant parent, table parent, clé parent,
# identifiant article, table catalogue, clé catalogue.
LINKS = (
    ("Commandes clients / lignes", "lignes_commande_ventes", "commande_vente_id",
     "commandes_ventes", "commande_vente_id", "sku_id", "sku_conditionnement", "sku_id"),
    ("Livraisons / lignes", "lignes_bons_livraison", "bl_id",
     "bons_livraison", "bl_id", "sku_id", "sku_conditionnement", "sku_id"),
    ("Factures clients / lignes", "lignes_facture", "facture_id",
     "factures", "facture_id", "sku_id", "sku_conditionnement", "sku_id"),
    ("Commandes fournisseurs / lignes", "lignes_achats", "commande_achat_id",
     "commandes_achats", "commande_achat_id", "mp_id", "matieres_premieres", "mp_id"),
    ("Réceptions / lignes", "lignes_bons_reception", "bon_reception_id",
     "bons_reception", "bon_reception_id", "mp_id", "matieres_premieres", "mp_id"),
)

HEADER_LINKS = (
    ("Livraisons / commandes", "bons_livraison", "commande_vente_id",
     "commandes_ventes", "commande_vente_id", True),
    ("Factures clients / commandes", "factures", "commande_vente_id",
     "commandes_ventes", "commande_vente_id", False),
    ("Réceptions / commandes", "bons_reception", "commande_achat_id",
     "commandes_achats", "commande_achat_id", True),
    ("Factures fournisseurs / commandes", "factures_fournisseurs", "commande_achat_id",
     "commandes_achats", "commande_achat_id", False),
    ("Factures fournisseurs / fournisseurs", "factures_fournisseurs", "fournisseur_id",
     "fournisseurs", "fournisseur_id", True),
)

TABLES = tuple(dict.fromkeys(
    [name for _, child, _, parent, _, catalog_key, catalogue, _ in LINKS
     for name in (child, parent, catalogue)]
    + [name for _, source, _, target, _, _ in HEADER_LINKS
       for name in (source, target)]
))


def _id(value) -> str:
    return str(value if value is not None else "").strip()


def _number(value) -> Decimal | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        n = Decimal(str(value).strip())
    except (InvalidOperation, ValueError, TypeError):
        return None
    return n if n.is_finite() else None


def audit_sales_purchases(rows: dict[str, list[dict]]) -> list[dict]:
    for table in TABLES:
        data = rows[table]
        if not isinstance(data, list) or any(not isinstance(x, dict) for x in data):
            raise ValueError(f"Lecture {table} absente ou invalide")
    report = []
    for label, child, foreign, parent, parent_id, article, catalogue, catalog_id in LINKS:
        parent_ids = {_id(x.get(parent_id)) for x in rows[parent] if _id(x.get(parent_id))}
        article_ids = {_id(x.get(catalog_id)) for x in rows[catalogue] if _id(x.get(catalog_id))}
        missing_parent = unknown_parent = missing_article = unknown_article = 0
        for line in rows[child]:
            ref = _id(line.get(foreign))
            sku = _id(line.get(article))
            missing_parent += not bool(ref)
            unknown_parent += bool(ref) and ref not in parent_ids
            missing_article += not bool(sku)
            unknown_article += bool(sku) and sku not in article_ids
        report.append({
            "Contrôle": label, "Lignes vérifiées": len(rows[child]),
            "Parents manquants": missing_parent, "Parents introuvables": unknown_parent,
            "Articles manquants": missing_article, "Articles introuvables": unknown_article,
            "Quantités invalides": 0, "Quantités non positives": 0,
        })
    for label, source, foreign, target, target_id, required in HEADER_LINKS:
        ids = {_id(row.get(target_id)) for row in rows[target] if _id(row.get(target_id))}
        records = rows[source]
        report.append({
            "Contrôle": label, "Lignes vérifiées": len(records),
            "Parents manquants": sum(required and not _id(x.get(foreign)) for x in records),
            "Parents introuvables": sum(
                bool(_id(x.get(foreign))) and _id(x.get(foreign)) not in ids
                for x in records
            ),
            "Articles manquants": 0, "Articles introuvables": 0,
            "Quantités invalides": 0, "Quantités non positives": 0,
        })
    quantity_field = {
        "lignes_commande_ventes": "quantite",
        "lignes_bons_livraison": "quantite_livree",
        "lignes_facture": "quantite",
        "lignes_achats": "qte_totale",
        "lignes_bons_reception": "quantite_recue",
    }
    for index, (_, child, *_rest) in enumerate(LINKS):
        for row in rows[child]:
            quantity = _number(row.get(quantity_field[child]))
            if quantity is None:
                report[index]["Quantités invalides"] += 1
            elif quantity <= 0:
                report[index]["Quantités non positives"] += 1
    return report


def audit_sales_purchases_autorise(*, reader=None) -> list[dict]:
    """Chaque lecture passe par le RBAC serveur, jamais de rapport partiel."""
    if reader is None:
        from core.db_service import fetch_data_paginated
        def reader(table):
            return fetch_data_paginated(table, page_size=200, max_rows=5000)
    data = {table: reader(table) for table in TABLES}
    return audit_sales_purchases(data)
