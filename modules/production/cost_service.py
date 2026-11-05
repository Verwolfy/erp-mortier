"""Référentiel analytique industriel : données Supabase privées, jamais de dual-write Sheets.

Le coût CUMP et les écritures SCF ne sont PAS modifiés.
"""
from __future__ import annotations

from datetime import date
from decimal import Decimal, InvalidOperation
from uuid import uuid4

from core.db_service import check_server_permission, check_server_read_permission
from modules.stocks.service import _stock_rpc_client

BASES = ("UNITS", "KG", "HOURS_LABOR", "HOURS_MACHINE", "KWH", "DIRECT_COST")


def _allowed() -> None:
    # Les écritures analytiques requièrent les deux habilitations métier.
    if check_server_permission("ordres_fabrication") is not True or check_server_permission("comptes") is not True:
        raise PermissionError("Écriture analytique interdite : droits Production et Finance requis")


def _ident(value: str) -> str:
    if not isinstance(value, str) or not (1 <= len(value.strip()) <= 128):
        raise ValueError("Identifiant invalide")
    return value.strip()


def _amount(value: object, name: str) -> str:
    if isinstance(value, bool) or len(str(value)) > 48:
        raise ValueError(f"{name} invalide")
    try:
        n = Decimal(str(value))
    except (TypeError, ValueError, InvalidOperation) as exc:
        raise ValueError(f"{name} invalide") from exc
    if not n.is_finite() or not (0 <= n < Decimal("1e15")) or n.as_tuple().exponent < -6:
        raise ValueError(f"{name} doit être positif et au maximum à 6 décimales")
    return format(n, "f")


def _client():
    return _stock_rpc_client()


def _read_allowed() -> None:
    if (check_server_read_permission("ordres_fabrication") is not True
            or check_server_read_permission("comptes") is not True):
        raise PermissionError("Lecture analytique réservée aux accès Production et Finance")


def list_periods() -> list[dict]:
    _read_allowed()
    response = _client().table("erp_cost_periods").select("period_id,libelle,date_debut,date_fin,statut").order("date_debut", desc=True).limit(100).execute()
    return response.data or []


def list_natures() -> list[dict]:
    _read_allowed()
    response = _client().table("erp_cost_natures").select("nature_code,libelle,actif").eq("actif", True).order("nature_code").execute()
    return response.data or []


def get_period_report(period_id: str) -> dict:
    _read_allowed()
    key = _ident(period_id)
    client = _client()
    pools = client.table("erp_cost_pools").select("pool_id,nature_code,base_imputation,montant_dzd,justificatif,statut").eq("period_id", key).limit(500).execute().data or []
    drivers = client.table("erp_cost_drivers").select("of_id,base_imputation,valeur,justificatif").eq("period_id", key).limit(2000).execute().data or []
    allocations = client.table("erp_cost_allocations").select("of_id,nature_code,base_imputation,montant_impute_dzd,cout_direct_of_dzd,quantite_produite").eq("period_id", key).limit(2000).execute().data or []
    summaries = client.table("erp_cost_of_summary").select("of_id,quantite_produite,cout_direct_of_dzd,charges_imputees_dzd,cout_analytique_total_dzd,cout_analytique_par_unite_dzd").eq("period_id", key).limit(1000).execute().data or []
    audit = client.rpc("erp_cost_period_audit", {"p_period_id": key}).execute().data
    return {"pools": pools, "drivers": drivers, "allocations": allocations,
            "summaries": summaries, "audit": audit}


def create_period(label: str, start: str, end: str) -> str:
    _allowed()
    if not isinstance(label, str) or not 1 <= len(label.strip()) <= 150:
        raise ValueError("Libellé de période invalide")
    a, b = date.fromisoformat(start), date.fromisoformat(end)
    if a > b:
        raise ValueError("Fin de période antérieure au début")
    period_id = f"COST-P-{uuid4()}"
    _client().table("erp_cost_periods").insert({
        "period_id": period_id, "libelle": label.strip(),
        "date_debut": a.isoformat(), "date_fin": b.isoformat(),
        "statut": "BROUILLON",
    }).execute()
    return period_id


def _editable(period_id: str) -> None:
    _allowed()
    rows = _client().table("erp_cost_periods").select("statut").eq("period_id", _ident(period_id)).limit(2).execute().data or []
    if len(rows) != 1 or rows[0]["statut"] != "BROUILLON":
        raise ValueError("Période absente ou non modifiable")


def add_pool(period_id: str, nature: str, base: str, amount: object, reference: str) -> str:
    _editable(period_id)
    if base not in BASES:
        raise ValueError("Base d'imputation inconnue")
    if not isinstance(reference, str) or not 1 <= len(reference.strip()) <= 500:
        raise ValueError("Justificatif obligatoire")
    pool_id = f"COST-POOL-{uuid4()}"
    _client().table("erp_cost_pools").insert({
        "pool_id": pool_id, "period_id": period_id, "nature_code": _ident(nature),
        "base_imputation": base, "montant_dzd": _amount(amount, "Montant"),
        "justificatif": reference.strip(), "statut": "SIMULATION",
    }).execute()
    return pool_id


def set_driver(period_id: str, of_id: str, base: str, value: object, reference: str) -> None:
    _editable(period_id)
    if base not in BASES:
        raise ValueError("Base d'imputation inconnue")
    if not isinstance(reference, str) or not 1 <= len(reference.strip()) <= 500:
        raise ValueError("Source de la mesure obligatoire")
    # Refuser les OF non terminés et hors période côté service.
    client = _client()
    periods = client.table("erp_cost_periods").select("date_debut,date_fin").eq("period_id", period_id).limit(1).execute().data or []
    orders = client.table("ordres_fabrication").select("of_id,statut,date_fin").eq("of_id", _ident(of_id)).limit(2).execute().data or []
    if len(periods) != 1 or len(orders) != 1 or orders[0].get("statut") != "TERMINE":
        raise ValueError("OF inexistant ou non terminé")
    finished = orders[0].get("date_fin")
    if not isinstance(finished, str) or not periods[0]["date_debut"] <= finished <= periods[0]["date_fin"]:
        raise ValueError("OF hors période de référence")
    client.table("erp_cost_drivers").upsert({
        "period_id": period_id, "of_id": of_id,
        "base_imputation": base, "valeur": _amount(value, "Assiette"),
        "justificatif": reference.strip(),
    }, on_conflict="period_id,of_id,base_imputation").execute()

def validate_period(period_id: str) -> dict:
    """Valide une période seulement lorsque toutes les charges sont imputables."""
    _editable(period_id)
    response = _client().rpc("erp_cost_validate_period",
                             {"p_period_id": _ident(period_id)}).execute()
    result = response.data
    if not isinstance(result, dict) or result.get("audit_ok") is not True:
        raise RuntimeError("Validation analytique non confirmée")
    return result

def create_nature(code: str, label: str, description: str = "") -> None:
    """Ajoute une catégorie analytique, sans montant implicite."""
    _allowed()
    import re
    if not isinstance(code, str) or re.fullmatch(r"[A-Z][A-Z0-9_]{1,39}", code) is None:
        raise ValueError("Code nature attendu en majuscules et chiffres")
    if not isinstance(label, str) or not 1 <= len(label.strip()) <= 150:
        raise ValueError("Libellé invalide")
    if not isinstance(description, str) or len(description) > 1000:
        raise ValueError("Description trop longue")
    _client().table("erp_cost_natures").insert({
        "nature_code": code, "libelle": label.strip(), "description": description,
        "actif": True,
    }).execute()


def document_pool(period_id: str, pool_id: str, document_reference: str) -> None:
    """Marque une charge justifiée; exige une référence documentaire explicite."""
    _editable(period_id)
    if not isinstance(document_reference, str) or not 3 <= len(document_reference.strip()) <= 500:
        raise ValueError("Référence de pièce justificative obligatoire")
    pool_id = _ident(pool_id)
    client = _client()
    rows = client.table("erp_cost_pools").select("pool_id,justificatif").eq(
        "period_id", period_id).eq("pool_id", pool_id).limit(2).execute().data or []
    if len(rows) != 1:
        raise ValueError("Charge inconnue")
    client.table("erp_cost_pools").update({
        "statut": "DOCUMENTE", "justificatif": document_reference.strip()
    }).eq("pool_id", pool_id).eq("period_id", period_id).execute()
