"""Préremplissage facultatif des brouillons depuis les référentiels ERP.

Lecture seule, RBAC serveur vérifié par core.db_service, fail-closed.
Aucune valeur de prix/taxe n'est décidée automatiquement.
"""
from __future__ import annotations

CLIENT_TYPES = frozenset({"Devis", "Bon de commande client", "Facture", "Avoir", "Bon de livraison"})
SUPPLIER_TYPES = frozenset({"Demande d'achat", "Bon de commande fournisseur", "Bon de réception", "Contrôle facture fournisseur"})
PRODUCT_TYPES = frozenset({"Devis", "Bon de commande client", "Facture", "Avoir", "Bon de livraison"})
MATERIAL_TYPES = frozenset({"Bon de consommation", "Bon de sortie", "Transfert de stock", "Inventaire", "Ordre de fabrication", "Rapport de fabrication", "Contrôle qualité"})


def _active(value: object) -> bool:
    return str(value).strip().upper() in {"OUI", "TRUE", "1", "ACTIF"}


def _read(table: str) -> list[dict]:
    """Réutilise la permission fraîche et la projection autorisée du service ERP."""
    from core.db_service import fetch_data_paginated
    return fetch_data_paginated(table, page_size=200, max_rows=2000)


def list_parties(kind: str, *, reader=None) -> list[dict]:
    if kind in CLIENT_TYPES:
        table, key = "clients", "client_id"
    elif kind in SUPPLIER_TYPES:
        table, key = "fournisseurs", "fournisseur_id"
    else:
        return []
    fetch = reader or _read
    return sorted([
        {"id": str(x[key]), "nom": str(x.get("nom") or ""),
         "adresse": str(x.get("adresse") or "")}
        for x in fetch(table)
        if isinstance(x, dict) and x.get(key) and _active(x.get("actif"))
    ], key=lambda x: (x["nom"], x["id"]))


def list_skus(kind: str, *, reader=None) -> list[dict]:
    if kind not in PRODUCT_TYPES:
        return []
    fetch = reader or _read
    skus = fetch("sku_conditionnement")
    products = {
        str(x.get("pf_id")): x
        for x in fetch("produits")
        if isinstance(x, dict) and x.get("pf_id") and _active(x.get("actif"))
    }
    results = []
    for sku in skus:
        if not isinstance(sku, dict) or not _active(sku.get("actif")):
            continue
        product = products.get(str(sku.get("pf_id")))
        if not product or not sku.get("sku_id"):
            continue
        results.append({
            "id": str(sku["sku_id"]), "designation": str(product.get("nom") or ""),
            "unite": str(sku.get("unite_vente") or ""),
            "format": str(sku.get("format") or ""),
            # Prix catalogue : affiché à titre informatif, jamais appliqué sans choix.
            "prix_vente_defaut": str(sku.get("prix_vente_defaut") or ""),
        })
    return sorted(results, key=lambda x: (x["designation"], x["id"]))


def apply_party(doc: dict, party: dict) -> dict:
    from copy import deepcopy
    out = deepcopy(doc)
    out["tiers_nom"] = party["nom"]
    out["tiers_adresse"] = party.get("adresse") or ""
    return out


def append_sku(doc: dict, sku: dict) -> dict:
    from copy import deepcopy
    out = deepcopy(doc)
    lines = out.setdefault("items", [])
    if len(lines) >= 200:
        raise ValueError("200 lignes maximum")
    lines.append({
        "reference": sku["id"],
        "designation": sku["designation"],
        "unite": sku["unite"],
        "quantite": "",
        "prix_unitaire": "",
        "total_ht": "",
    })
    return out


def list_materials(kind: str, *, reader=None) -> list[dict]:
    """Catalogue matières actives sans prix, stock ni état des lots."""
    if kind not in MATERIAL_TYPES:
        return []
    fetch = reader or _read
    return sorted([
        {"id": str(x["mp_id"]), "designation": str(x.get("nom") or ""),
         "unite": str(x.get("unite_stock") or "")}
        for x in fetch("matieres_premieres")
        if isinstance(x, dict) and x.get("mp_id") and _active(x.get("actif"))
    ], key=lambda x: (x["designation"], x["id"]))


def append_material(doc: dict, material: dict) -> dict:
    from copy import deepcopy
    from modules.documents.layout_nextgen import columns_for
    if doc.get("type") not in MATERIAL_TYPES:
        raise ValueError("Matière non applicable à ce type de document")
    out = deepcopy(doc)
    rows = out.setdefault("items", [])
    if len(rows) >= 200:
        raise ValueError("200 lignes maximum")
    new_line = {key: "" for key, _ in columns_for(out["type"])}
    new_line.update(reference=material["id"],
                    designation=material["designation"],
                    unite=material["unite"])
    rows.append(new_line)
    return out
