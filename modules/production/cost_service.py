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


def can_manage_costs() -> bool:
    """Droits d'écriture effectivement relus depuis la session serveur."""
    try:
        _allowed()
    except PermissionError:
        return False
    return True


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


# Pagination serveur : ne jamais masquer des lignes d'un rapport financier.
_REPORT_PAGE_SIZE = 500
_REPORT_MAX_ROWS = 100000


def _fetch_all(query, order_by: tuple[str, ...], *, page_size: int = _REPORT_PAGE_SIZE) -> list[dict]:
    """Récupère toutes les pages, dans un ordre stable, ou refuse le rapport."""
    if isinstance(page_size, bool) or not isinstance(page_size, int) or not 1 <= page_size <= 1000:
        raise ValueError("Taille de page invalide")
    if not order_by:
        raise ValueError("Ordre de pagination requis")
    for col in order_by:
        query = query.order(col)
    rows: list[dict] = []
    previous_key = None
    while True:
        response = query.range(len(rows), len(rows) + page_size - 1).execute()
        chunk = response.data
        if chunk is None:
            raise RuntimeError("Page analytique sans données : résultat incomplet")
        if len(chunk) > page_size or len(rows) + len(chunk) > _REPORT_MAX_ROWS:
            raise RuntimeError("Volume analytique supérieur à la limite de sécurité")
        # Une suppression/insertion entre deux requêtes paginées peut décaler
        # les offsets. Refuser les clés répétées ou hors ordre plutôt que
        # publier un rapport financièrement incohérent.
        for entry in chunk:
            key = tuple(entry.get(col) for col in order_by)
            if any(value is None for value in key):
                raise RuntimeError("Clé de pagination analytique manquante")
            if previous_key is not None and key <= previous_key:
                raise RuntimeError("Pagination analytique instable : doublon ou ordre rompu")
            previous_key = key
        rows.extend(chunk)
        if len(chunk) < page_size:
            return rows
        if len(rows) == _REPORT_MAX_ROWS:
            raise RuntimeError("Volume analytique maximal atteint : résultat potentiellement incomplet")


def list_periods() -> list[dict]:
    _read_allowed()
    q = _client().table("erp_cost_periods").select("period_id,libelle,date_debut,date_fin,statut")
    rows = _fetch_all(q, ("date_debut", "period_id"))
    return sorted(rows, key=lambda r: (r["date_debut"], r["period_id"]), reverse=True)


def list_natures() -> list[dict]:
    _read_allowed()
    q = _client().table("erp_cost_natures").select("nature_code,libelle,actif").eq("actif", True)
    return _fetch_all(q, ("nature_code",))


_REPORT_SECTIONS = (
    "pools", "drivers", "allocations", "summaries",
    "scf_reconciliation", "validation_drift",
)


def get_period_report(period_id: str, *, sections=None, include_audit: bool = True) -> dict:
    """Charge les sections demandées; audit optionnel, jamais mis en cache.

    Sans sélection : conserve le contrat historique et charge tout le rapport.
    Une section non demandée vaut [] mais figure explicitement hors de
    loaded_sections ; ne jamais la présenter comme une liste chargée vide.
    """
    _read_allowed()
    key = _ident(period_id)
    if not isinstance(include_audit, bool):
        raise ValueError("Paramètre audit invalide")
    if sections is None:
        requested = _REPORT_SECTIONS
    elif isinstance(sections, (tuple, list)) and sections and all(
        isinstance(name, str) and name in _REPORT_SECTIONS for name in sections
    ):
        requested = tuple(dict.fromkeys(sections))
    else:
        raise ValueError("Sélection de sections analytiques invalide")

    cfg = {
        "pools": (
            "erp_cost_pools",
            "pool_id,nature_code,base_imputation,montant_dzd,justificatif,statut",
            ("pool_id",),
        ),
        "drivers": (
            "erp_cost_drivers",
            "of_id,base_imputation,valeur,justificatif",
            ("of_id", "base_imputation"),
        ),
        "allocations": (
            "erp_cost_allocations",
            "pool_id,of_id,nature_code,base_imputation,montant_impute_dzd,"
            "cout_direct_of_dzd,quantite_produite",
            ("pool_id", "of_id"),
        ),
        "summaries": (
            "erp_cost_of_summary",
            "of_id,quantite_produite,cout_direct_of_dzd,charges_imputees_dzd,"
            "cout_analytique_total_dzd,cout_analytique_par_unite_dzd",
            ("of_id",),
        ),
        "scf_reconciliation": (
            "erp_cost_scf_reconciliation",
            "pool_id,nature_code,montant_impute_dzd,reference_scf,scf_ligne_id,"
            "compte,montant_debit_scf_dzd,solde_non_impute_dzd,rapprochement_ok",
            ("pool_id",),
        ),
        "validation_drift": (
            "erp_cost_of_validation_drift",
            "of_id,statut_of_valide,statut_of_actuel,quantite_validee,quantite_actuelle,"
            "cout_direct_valide_dzd,cout_direct_actuel_dzd,charges_validees_dzd,"
            "charges_actuelles_dzd,cout_total_valide_dzd,cout_total_actuel_dzd,"
            "derive_detectee,captured_at",
            ("of_id",),
        ),
    }
    client = _client()
    report = {name: [] for name in _REPORT_SECTIONS}
    for name in requested:
        table_name, columns, order_by = cfg[name]
        query = client.table(table_name).select(columns).eq("period_id", key)
        report[name] = _fetch_all(query, order_by)
    report["audit"] = (client.rpc("erp_cost_period_audit", {"p_period_id": key}).execute().data
                       if include_audit else None)
    report["audit_calculated"] = include_audit
    report["loaded_sections"] = list(requested)
    return report

def export_validated_period(period_id: str) -> dict:
    """Export analytique figé; un appel SQL, réservé à Production+Finance."""
    _read_allowed()
    key = _ident(period_id)
    result = _client().rpc(
        "erp_cost_export_validated", {"p_period_id": key}
    ).execute().data
    if (not isinstance(result, dict)
            or result.get("format") != "erp_cost_validated_export_v1"
            or result.get("snapshot_type") != "single_sql_statement"
            or (result.get("period") or {}).get("period_id") != key
            or (result.get("period") or {}).get("statut") != "VALIDE"
            or not isinstance(result.get("of_snapshots"), list)
            or not isinstance(result.get("pools"), list)
            or not isinstance(result.get("drivers"), list)):
        raise RuntimeError("Export analytique non confirmé")
    return result


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


def document_pool(period_id: str, pool_id: str, scf_piece_id: str, scf_line_id: int, explanation: str) -> None:
    """Lie une charge à une pièce SCF déjà validée, sans publier ni créer la pièce."""
    _editable(period_id)
    from uuid import UUID
    try:
        piece_id = str(UUID(scf_piece_id))
    except (ValueError, TypeError, AttributeError) as exc:
        raise ValueError("Identifiant UUID de pièce SCF requis") from exc
    if isinstance(scf_line_id, bool) or not isinstance(scf_line_id, int) or scf_line_id <= 0:
        raise ValueError("Identifiant de ligne SCF invalide")
    if not isinstance(explanation, str) or not 10 <= len(explanation.strip()) <= 1000:
        raise ValueError("Justification d'imputation de 10 à 1000 caractères obligatoire")
    key = _ident(pool_id)
    client = _client()
    pools = client.table("erp_cost_pools").select("pool_id,statut,montant_dzd").eq(
        "period_id", _ident(period_id)).eq("pool_id", key).limit(2).execute().data or []
    if len(pools) != 1 or pools[0]["statut"] not in ("SIMULATION", "DOCUMENTE"):
        raise ValueError("Charge absente ou non documentable")
    pieces = client.table("scf_pieces").select("piece_id,statut,date_validation").eq(
        "piece_id", piece_id).limit(2).execute().data or []
    if (len(pieces) != 1 or pieces[0]["statut"] != "VALIDEE"
            or not pieces[0].get("date_validation")):
        raise ValueError("Pièce SCF non validée ou absente")
    lines = client.table("scf_lignes").select("ligne_id,piece_id,debit,credit").eq(
        "ligne_id", scf_line_id).eq("piece_id", piece_id).limit(2).execute().data or []
    if len(lines) != 1:
        raise ValueError("Ligne SCF introuvable dans la pièce validée")
    debit = Decimal(str(lines[0]["debit"]))
    if not debit.is_finite() or debit <= 0 or Decimal(str(pools[0]["montant_dzd"])) > debit:
        raise ValueError("Montant de charge supérieur au débit SCF admissible")
    # Une seule RPC transactionnelle : jamais de preuve orpheline si le réseau
    # tombe entre la liaison et le passage en statut DOCUMENTE.
    response = client.rpc("erp_cost_document_pool_atomic", {
        "p_period_id": _ident(period_id),
        "p_pool_id": key,
        "p_piece_id": piece_id,
        "p_scf_ligne_id": scf_line_id,
        "p_explication": explanation.strip(),
    }).execute()
    result = response.data
    if not isinstance(result, dict) or result.get("documented") is not True:
        raise RuntimeError("Documentation SCF non confirmée")
