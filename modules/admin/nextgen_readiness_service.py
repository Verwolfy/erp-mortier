"""NextGen readiness: bounded, read-only, SECURITY_MANAGER only, no inferred approvals."""
from __future__ import annotations

from collections import Counter
from typing import Any
from core.db_service import get_supabase_client
from core.security_service import require_security_manager

PREFIXES = ("BOND-", "PROOF-", "FLOW-", "PAINT-")
LIMITS = {"produits": 200, "sku_conditionnement": 500, "matieres_premieres": 300, "erp_sku_fiscalite": 2500}
LIQUIDS = frozenset(("BIDON", "FUT", "IBC"))


def _read(db: Any, name: str, columns: str, *, active: bool = False) -> list[dict]:
    query = db.table(name).select(columns)
    if active:
        query = query.eq("actif", "OUI")
    data = query.range(0, LIMITS[name]).execute().data
    if not isinstance(data, list) or len(data) > LIMITS[name] or any(not isinstance(x, dict) for x in data):
        raise RuntimeError("Référentiel NextGen incomplet ou illisible")
    return data


def _id(row: dict, field: str) -> str:
    value = row.get(field)
    if not isinstance(value, str) or not value.strip():
        raise RuntimeError("Identifiant NextGen manquant")
    return value


def lister_blocages_nextgen() -> dict[str, Any]:
    """Never returns an authorization to bill, manufacture or publish."""
    require_security_manager()
    db = get_supabase_client()
    products = _read(db, "produits", "pf_id,nom,actif", active=True)
    skus = _read(db, "sku_conditionnement",
                 "sku_id,pf_id,format,unite_vente,poids_net,facteur_conversion,prix_vente_defaut,actif",
                 active=True)
    materials = _read(db, "matieres_premieres", "mp_id,actif,fournisseurs_ids")
    fiscal = _read(db, "erp_sku_fiscalite", "sku_id,statut")

    product_ids: set[str] = set()
    for row in products:
        pid = _id(row, "pf_id")
        if pid.startswith(PREFIXES):
            if pid in product_ids or row.get("actif") != "OUI":
                raise RuntimeError("Produit NextGen ambigu")
            _id(row, "nom")
            product_ids.add(pid)
    if not product_ids:
        raise RuntimeError("Catalogue NextGen actif introuvable")

    skus_seen: set[str] = set()
    nextgen_skus = []
    by_product = Counter()
    for row in skus:
        sid, pid = _id(row, "sku_id"), _id(row, "pf_id")
        if sid in skus_seen:
            raise RuntimeError("SKU dupliqué")
        skus_seen.add(sid)
        if sid.startswith("NG-SKU-"):
            if pid not in product_ids or row.get("actif") != "OUI":
                raise RuntimeError("SKU NextGen sans produit actif")
            _id(row, "format")
            _id(row, "unite_vente")
            nextgen_skus.append(row)
            by_product[pid] += 1

    material_seen: set[str] = set()
    candidate_count = missing_supplier = 0
    for row in materials:
        mid = _id(row, "mp_id")
        if mid in material_seen:
            raise RuntimeError("Matière dupliquée")
        material_seen.add(mid)
        if mid.startswith("NG-MP-"):
            if row.get("actif") != "OUI":
                raise RuntimeError("Matière candidate non active")
            candidate_count += 1
            supplier = row.get("fournisseurs_ids")
            if not isinstance(supplier, str) or not supplier.strip():
                missing_supplier += 1

    fiscal_ids: set[str] = set()
    for row in fiscal:
        sid = _id(row, "sku_id")
        _id(row, "statut")
        if sid.startswith("NG-SKU-"):
            fiscal_ids.add(sid)

    rows = []
    counter = Counter()
    for row in nextgen_skus:
        sid, unit = row["sku_id"], row["unite_vente"]
        blockers = []
        if row.get("prix_vente_defaut") is None:
            blockers.append("Tarif absent")
            counter["sans_tarif"] += 1
        if sid not in fiscal_ids:
            blockers.append("Dossier fiscal absent")
            counter["sans_dossier_fiscal"] += 1
        else:
            blockers.append("Dossier fiscal à vérifier indépendamment")
        if unit == "KIT" and row.get("poids_net") is None:
            blockers.append("Kit : quantité et composition à confirmer")
            counter["kits_incomplets"] += 1
        if unit in LIQUIDS and row.get("facteur_conversion") is None:
            blockers.append("Liquide : densité et conversion à confirmer")
            counter["liquides_sans_conversion"] += 1
        rows.append({"sku_id": sid, "pf_id": row["pf_id"],
                     "format": row["format"], "unite_vente": unit,
                     "blocages": " ; ".join(blockers) or "Revue documentaire requise"})
    return {
        "produits_actifs": len(product_ids),
        "sku_nextgen_actifs": len(nextgen_skus),
        "produits_sans_sku": sorted(product_ids - set(by_product)),
        "matieres_candidates": candidate_count,
        "matieres_sans_fournisseur": missing_supplier,
        "sans_tarif": counter["sans_tarif"],
        "sans_dossier_fiscal": counter["sans_dossier_fiscal"],
        "kits_incomplets": counter["kits_incomplets"],
        "liquides_sans_conversion": counter["liquides_sans_conversion"],
        "autorise_facturation": False,
        "autorise_fabrication": False,
        "rows": rows,
    }
