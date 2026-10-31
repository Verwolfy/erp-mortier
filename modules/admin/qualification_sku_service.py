"""Inventaire fiscal SKU réel, réservé au SECURITY_MANAGER, lecture seule.

Ne crée pas de classification TVA et ne conclut jamais qu'un taux s'applique.
Toutes les lignes proviennent de Supabase PRODUCTION configuré côté serveur.
"""
from __future__ import annotations

from typing import Any

from core.db_service import get_supabase_client
from core.security_service import require_security_manager

_MAX_SKUS = 500
_MAX_DOSSIERS_FISCAUX = 2000


def lister_sku_a_qualifier() -> dict[str, Any]:
    """Retourne une revue de couverture, sans autoriser la facturation."""
    require_security_manager()
    db = get_supabase_client()
    sku_rows = (
        db.table("sku_conditionnement")
        .select("sku_id,pf_id,format,unite_vente,actif")
        .eq("actif", "OUI").order("sku_id")
        .range(0, _MAX_SKUS).execute().data
    )
    if not isinstance(sku_rows, list) or len(sku_rows) > _MAX_SKUS:
        raise RuntimeError("Catalogue actif non vérifiable ou tronqué")
    seen: set[str] = set()
    for row in sku_rows:
        if not isinstance(row, dict):
            raise RuntimeError("SKU non structuré")
        sku = row.get("sku_id")
        if (not isinstance(sku, str) or not sku.strip() or sku in seen
                or row.get("actif") != "OUI"
                or any(not isinstance(row.get(k), str) or not row[k].strip()
                       for k in ("pf_id", "format", "unite_vente"))):
            raise RuntimeError("Catalogue SKU incohérent")
        seen.add(sku)

    fiscal_rows = (
        db.table("erp_sku_fiscalite")
        .select("sku_id,statut")
        .order("sku_id").range(0, _MAX_DOSSIERS_FISCAUX).execute().data
    )
    if not isinstance(fiscal_rows, list) or len(fiscal_rows) > _MAX_DOSSIERS_FISCAUX:
        raise RuntimeError("Registre fiscal incomplet ou indisponible")
    n: dict[str, int] = {sku: 0 for sku in seen}
    for row in fiscal_rows:
        if (not isinstance(row, dict)
            or not isinstance(row.get("sku_id"), str)
            or not isinstance(row.get("statut"), str)
            or not row["statut"].strip()):
            raise RuntimeError("Classification fiscale illisible")
        if row["sku_id"] in n:
            n[row["sku_id"]] += 1
    rows = [{
        "sku_id": row["sku_id"], "pf_id": row["pf_id"],
        "format": row["format"], "unite_vente": row["unite_vente"],
        "dossiers_fiscaux": n[row["sku_id"]],
        "etat_revue": ("À qualifier" if n[row["sku_id"]] == 0
                       else "Dossier enregistré — vérification indépendante requise"),
    } for row in sku_rows]
    sans_dossier = sum(row["dossiers_fiscaux"] == 0 for row in rows)
    return {
        "sku_actifs": len(rows),
        "sku_sans_dossier": sans_dossier,
        "sku_avec_dossier": len(rows) - sans_dossier,
        "autorise_activation_facturation": False,
        "rows": rows,
    }
