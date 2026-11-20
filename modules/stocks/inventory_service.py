"""ERP-056 — Inventaires physiques MP/PF, RPC idempotentes et lecture RBAC.

Aucune régularisation automatique : une validation constate l'écart mais ne
modifie jamais lots, PMP, stock, mouvements ni pièces SCF.
"""
from __future__ import annotations

from decimal import Decimal, InvalidOperation
import hashlib
import json
from uuid import uuid4
from typing import Any

import streamlit as st

from config.roles import has_permission
from core.db_service import get_supabase_client


class InventoryError(RuntimeError):
    pass


_ACTIVE = {"OUI", "TRUE", "1", "YES", "ACTIF", "ACTIVE"}
_ADMIN = {"ADMIN", "ADMINISTRATEUR", "SUPERADMIN"}


def _identity(*, writing: bool = False, approving: bool = False) -> tuple[str, str]:
    """Permission fraîche, identité réelle en base et rôle non pris de la session."""
    if st.session_state.get("authenticated") is not True:
        raise PermissionError("Session ERP absente")
    user = st.session_state.get("user")
    user_id = user.get("user_id") if isinstance(user, dict) else None
    if not isinstance(user_id, str) or not user_id.strip():
        raise PermissionError("Identité ERP absente")
    response = (get_supabase_client().table("users").select("user_id,role,actif")
                .eq("user_id", user_id).limit(2).execute())
    rows = response.data
    if not isinstance(rows, list) or len(rows) != 1 or rows[0].get("user_id") != user_id:
        raise PermissionError("Compte ERP non vérifiable")
    row = rows[0]
    if str(row.get("actif") or "").strip().upper() not in _ACTIVE:
        raise PermissionError("Compte ERP inactif")
    role = row.get("role")
    if not isinstance(role, str) or not has_permission(
        role, "Stocks", "ecriture" if writing else "lecture"
    ):
        raise PermissionError("Accès Stocks interdit")
    if approving and role.strip().upper() not in _ADMIN:
        raise PermissionError("Validation réservée à l'administrateur")
    return user_id, role


def _result(response: object, *, campaign: str) -> dict:
    data = getattr(response, "data", None)
    if not isinstance(data, dict) or data.get("inventaire_id") != campaign:
        raise InventoryError("Résultat inventaire non confirmé — ne pas répéter avec un autre identifiant")
    return data


def _rpc(name: str, params: dict, campaign: str) -> dict:
    try:
        response = get_supabase_client().rpc(name, params).execute()
    except Exception as exc:
        raise InventoryError(
            "Opération non confirmée : vérifier le journal Supabase avant tout nouvel essai."
        ) from exc
    return _result(response, campaign=campaign)


def _valid_quantity(quantity: Any) -> str:
    if isinstance(quantity, bool):
        raise ValueError("Quantité invalide")
    try:
        q = Decimal(str(quantity))
    except (TypeError, ValueError, InvalidOperation) as exc:
        raise ValueError("Quantité invalide") from exc
    if not q.is_finite() or q < 0 or q >= Decimal("1e15"):
        raise ValueError("Quantité invalide")
    return str(q)


def create_inventory(category: str, label: str, *, campaign_id: str) -> dict:
    user_id, _ = _identity(writing=True)
    if category not in {"MP", "PF", "TOUS"} or not isinstance(label, str) or not 3 <= len(label.strip()) <= 160:
        raise ValueError("Périmètre ou libellé invalide")
    if not isinstance(campaign_id, str) or not campaign_id.startswith("INV-"):
        raise ValueError("Identifiant de campagne invalide")
    return _rpc("erp_inventory_create", {
        "p_inventaire_id": campaign_id, "p_categorie": category,
        "p_libelle": label.strip(), "p_acteur_id": user_id,
    }, campaign_id)


def new_inventory_id() -> str:
    return "INV-" + uuid4().hex.upper()


def _page(table: str, *, campaign_id: str | None = None, max_rows: int = 5000) -> list[dict]:
    """Lecture serveur bornée, pagination complète ; aucune table générique ouverte."""
    if table not in {"erp_inventaires", "erp_inventaire_lignes", "erp_inventaire_lots"}:
        raise ValueError("Source inventaire inconnue")
    client = get_supabase_client()
    out: list[dict] = []
    index = 0
    count = None
    while True:
        query = client.table(table).select("*", count="exact")
        if campaign_id is not None:
            query = query.eq("inventaire_id", campaign_id)
        # Ordre total stable obligatoire : une pagination sans ORDER BY
        # peut perdre ou dupliquer des lignes lors d'une réorganisation SQL.
        query = query.order("inventaire_id")
        if table == "erp_inventaire_lignes":
            query = query.order("type_article").order("article_id")
        elif table == "erp_inventaire_lots":
            query = query.order("lot_id")
        query = query.range(index, index + 499)
        response = query.execute()
        batch = getattr(response, "data", None)
        reported = getattr(response, "count", None)
        if not isinstance(batch, list) or not isinstance(reported, int) or isinstance(reported, bool):
            raise InventoryError("Lecture inventaire non vérifiable")
        if count is None:
            count = reported
            if count > max_rows:
                raise InventoryError("Inventaire trop volumineux pour la consultation")
        if reported != count or len(batch) > 500 or len(out) + len(batch) > max_rows:
            raise InventoryError("Pagination inventaire incohérente")
        out.extend(batch)
        index += len(batch)
        if index == count:
            return out
        if not batch:
            raise InventoryError("Pagination inventaire incomplète")


def list_inventories() -> list[dict]:
    _identity()
    rows = _page("erp_inventaires", max_rows=5000)
    return sorted(rows, key=lambda r: str(r.get("date_snapshot") or ""), reverse=True)


def inventory_lines(campaign_id: str) -> tuple[dict, list[dict]]:
    _identity()
    if not isinstance(campaign_id, str) or not campaign_id.startswith("INV-"):
        raise ValueError("Campagne invalide")
    headers = _page("erp_inventaires", campaign_id=campaign_id)
    if len(headers) != 1:
        raise InventoryError("Campagne introuvable")
    lines = _page("erp_inventaire_lignes", campaign_id=campaign_id)
    if not lines:
        raise InventoryError("Campagne sans lignes")
    return headers[0], sorted(lines, key=lambda r: (
        r.get("type_article") or "", r.get("article_id") or ""
    ))


def count_article(campaign_id: str, kind: str, article_id: str,
                  quantity: Any, motive: str = "") -> dict:
    user_id, _ = _identity(writing=True)
    if kind not in {"MP", "PF"} or not isinstance(article_id, str) or not article_id:
        raise ValueError("Article inconnu")
    if not isinstance(motive, str) or len(motive) > 600:
        raise ValueError("Motif trop long")
    return _rpc("erp_inventory_count", {
        "p_inventaire_id": campaign_id,
        "p_type_article": kind, "p_article_id": article_id,
        "p_quantite": _valid_quantity(quantity),
        "p_motif": motive.strip(), "p_acteur_id": user_id,
    }, campaign_id)


def submit_inventory(campaign_id: str) -> dict:
    user_id, _ = _identity(writing=True)
    return _rpc("erp_inventory_submit", {
        "p_inventaire_id": campaign_id, "p_acteur_id": user_id,
    }, campaign_id)


def approve_inventory(campaign_id: str, comment: str) -> dict:
    user_id, _ = _identity(writing=True, approving=True)
    if not isinstance(comment, str) or not 10 <= len(comment.strip()) <= 600:
        raise ValueError("Justification de 10 à 600 caractères obligatoire")
    return _rpc("erp_inventory_approve", {
        "p_inventaire_id": campaign_id, "p_acteur_id": user_id,
        "p_commentaire": comment.strip(),
    }, campaign_id)


def summarize_inventory(lines: list[dict]) -> dict:
    """Quantités et valeurs d'écarts sans inventer de coût d'article."""
    total = len(lines)
    counted = sum(1 for r in lines if r.get("quantite_comptee") is not None)
    delta_count = 0
    value = Decimal(0)
    missing_cost = 0
    for row in lines:
        raw = row.get("quantite_comptee")
        if raw is None:
            continue
        delta = Decimal(str(raw)) - Decimal(str(row["quantite_theorique"]))
        if delta:
            delta_count += 1
            if row.get("pmp_snapshot") is None:
                missing_cost += 1
            else:
                pmp = Decimal(str(row["pmp_snapshot"]))
                if not pmp.is_finite() or pmp < 0:
                    raise InventoryError("PMP de snapshot incohérent")
                value += delta * pmp
    return {"lignes": total, "comptees": counted, "ecarts": delta_count,
            "ecarts_sans_pmp": missing_cost,
            "valeur_ecart_dzd": str(value) if not missing_cost else None}


def inventory_lots(campaign_id: str) -> list[dict]:
    """Lots effectivement photographiés à la création de la campagne."""
    _identity()
    if not isinstance(campaign_id, str) or not campaign_id.startswith("INV-"):
        raise ValueError("Campagne invalide")
    return _page("erp_inventaire_lots", campaign_id=campaign_id)


def count_inventory_lot(campaign_id: str, lot_id: str,
                        quantity: Any, motive: str = "") -> dict:
    user_id, _ = _identity(writing=True)
    if not isinstance(lot_id, str) or not lot_id or len(lot_id) > 200:
        raise ValueError("Lot invalide")
    if not isinstance(motive, str) or len(motive) > 600:
        raise ValueError("Motif de lot invalide")
    return _rpc("erp_inventory_count_lot", {
        "p_inventaire_id": campaign_id, "p_lot_id": lot_id,
        "p_quantite": _valid_quantity(quantity),
        "p_motif": motive.strip(), "p_acteur_id": user_id,
    }, campaign_id)


def import_inventory_counts(campaign_id: str, rows: list[dict]) -> dict:
    """Import tout-ou-rien avec clé stable de rejeu (même charge, même acteur)."""
    user_id, _ = _identity(writing=True)
    if not isinstance(campaign_id, str) or not campaign_id.startswith("INV-"):
        raise ValueError("Campagne invalide")
    if not isinstance(rows, list) or not 1 <= len(rows) <= 500:
        raise ValueError("Nombre de comptages invalide")
    canonical = json.dumps(rows, sort_keys=True, separators=(",", ":"),
                           ensure_ascii=False, allow_nan=False)
    # Ne pas utiliser un UUID à chaque essai : après un timeout réseau, il
    # faudrait re-soumettre exactement le même identifiant d'opération.
    digest = hashlib.sha256(
        (user_id + ":" + campaign_id + ":" + canonical).encode("utf-8")
    ).hexdigest().upper()[:40]
    operation_id = "INVIMP-" + digest
    return _rpc("erp_inventory_bulk_count", {
        "p_inventaire_id": campaign_id, "p_acteur_id": user_id,
        "p_rows": rows, "p_operation_id": operation_id,
    }, campaign_id)


def lot_reconciliation(article_lines: list[dict],
                       lots: list[dict]) -> dict:
    """Distinguer lacunes du registre de lots et écarts de comptage."""
    grouped: dict[tuple[str,str], dict] = {}
    for lot in lots:
        key = (lot["type_article"], lot["article_id"])
        entry = grouped.setdefault(key, {
            "stock_lots": Decimal("0"), "comptage_lots": Decimal("0"),
            "lot_non_compte": 0, "nombre_lots": 0,
        })
        qty = Decimal(str(lot["quantite_theorique"]))
        if not qty.is_finite() or qty < 0:
            raise InventoryError("Quantité de lot incohérente")
        entry["stock_lots"] += qty
        entry["nombre_lots"] += 1
        physical = lot.get("quantite_comptee")
        if physical is None:
            entry["lot_non_compte"] += 1
        else:
            value = Decimal(str(physical))
            if not value.is_finite() or value < 0:
                raise InventoryError("Quantité de lot comptée incohérente")
            entry["comptage_lots"] += value
    rows, anomalies = [], 0
    for article in article_lines:
        key = (article["type_article"], article["article_id"])
        total = Decimal(str(article["quantite_theorique"]))
        if not total.is_finite() or total < 0:
            raise InventoryError("Stock théorique incohérent")
        info = grouped.get(key, {
            "stock_lots": Decimal(0), "comptage_lots": Decimal(0),
            "lot_non_compte": 0, "nombre_lots": 0,
        })
        gap = total - info["stock_lots"]
        counted = article.get("quantite_comptee")
        physical_gap = (
            Decimal(str(counted)) - info["comptage_lots"]
            if counted is not None and info["nombre_lots"] and not info["lot_non_compte"]
            else None
        )
        is_anomaly = gap != 0 or (physical_gap is not None and physical_gap != 0)
        if is_anomaly:
            anomalies += 1
        rows.append({
            "type_article": key[0], "article_id": key[1],
            "stock_theorique": str(total),
            "stock_lots": str(info["stock_lots"]),
            "ecart_tracabilite": str(gap),
            "lots": info["nombre_lots"],
            "lots_non_comptes": info["lot_non_compte"],
            "ecart_comptage_lots": str(physical_gap) if physical_gap is not None else None,
            "anomalie": "A_RECONCILIER" if is_anomaly else "",
        })
    return {"lignes": rows, "articles_non_reconcilies": anomalies,
            "lots_non_comptes": sum(1 for lot in lots if lot.get("quantite_comptee") is None)}


def classify_inventory_difference(
    campaign_id: str, kind: str, article_id: str,
    nature: str, comment: str,
) -> dict:
    """Qualification de preuve seulement : aucun stock, lot ou avoir modifié."""
    user_id, _ = _identity(writing=True)
    allowed = {"PERTE", "CASSE", "PERIME", "RETOUR_CLIENT", "ERREUR_COMPTAGE", "AUTRE"}
    if nature not in allowed or kind not in {"MP", "PF"}:
        raise ValueError("Nature d'écart non autorisée")
    if not isinstance(comment, str) or not 10 <= len(comment.strip()) <= 600:
        raise ValueError("Justification obligatoire (10..600 caractères)")
    if not isinstance(article_id, str) or not article_id or len(article_id) > 200:
        raise ValueError("Référence article invalide")
    return _rpc("erp_inventory_classify_difference", {
        "p_inventaire_id": campaign_id, "p_type_article": kind,
        "p_article_id": article_id, "p_nature": nature,
        "p_commentaire": comment.strip(), "p_acteur_id": user_id,
    }, campaign_id)
