"""ERP-056 — Inventaires physiques MP/PF, RPC idempotentes et lecture RBAC.

Aucune régularisation automatique : une validation constate l'écart mais ne
modifie jamais lots, PMP, stock, mouvements ni pièces SCF.
"""
from __future__ import annotations

from decimal import Decimal, InvalidOperation
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
    if table not in {"erp_inventaires", "erp_inventaire_lignes"}:
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
