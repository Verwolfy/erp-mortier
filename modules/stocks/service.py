"""Stock MP/PF : lectures compatibles et mutations atomiques via RPC PostgreSQL.

La base Supabase est la seule source de vérité. Toute mutation est exécutée
entièrement dans public.erp_apply_stock_movement. Ce module ne doit PAS écrire
lui-même dans stock_actuel, lots ou mouvements.

Prérequis : migration sql/002_atomic_stock_movement.sql sur une base de TEST et
st.secrets['supabase']['stock_service_key'] contenant une clé service_role
strictement serveur. Le compte Streamlit doit être autorisé par le RBAC existant.
"""

from __future__ import annotations

from decimal import Decimal, InvalidOperation
from typing import Any
from uuid import uuid4

import pandas as pd
import streamlit as st
from supabase import Client, create_client
from core.environment_guard import policy_from_streamlit, require_supabase_target

from core.db_service import check_server_permission, fetch_data, fetch_data_filtered


class StockOperationError(RuntimeError):
    """Échec d'une mutation, avec identifiant pour retenter sans double écriture."""

    def __init__(self, message: str, *, operation_id: str):
        super().__init__(message)
        self.operation_id = operation_id


def get_stock_actuel_mp() -> pd.DataFrame:
    return pd.DataFrame(fetch_data("stock_actuel"))


def get_stock_actuel_pf() -> pd.DataFrame:
    return pd.DataFrame(fetch_data("stock_actuel_pf"))


def get_mouvements() -> pd.DataFrame:
    """Lecture historique ; pour les grands volumes préférer les filtres/pagination."""
    return pd.DataFrame(fetch_data("mouvements"))


def get_mouvements_by_mp(mp_id: str) -> pd.DataFrame:
    return pd.DataFrame(fetch_data_filtered("mouvements", "mp_id", mp_id))


def get_mouvements_pf() -> pd.DataFrame:
    return pd.DataFrame(fetch_data("mouvements_pf"))


def get_mouvements_pf_by_sku(sku_id: str) -> pd.DataFrame:
    return pd.DataFrame(fetch_data_filtered("mouvements_pf", "sku_id", sku_id))


def get_lots() -> pd.DataFrame:
    return pd.DataFrame(fetch_data("lots"))


def _stock_rpc_client() -> Client:
    """Client *serveur dédié*, jamais authentifié avec un utilisateur final.

    Ne pas réutiliser ce client pour sign_in_with_password ni le transmettre aux
    écrans ou au navigateur. Refuse l'absence de clé plutôt que d'utiliser anon.
    """
    try:
        url = st.secrets["supabase"]["url"]
        key = st.secrets["supabase"]["stock_service_key"]
    except (KeyError, TypeError) as exc:
        raise RuntimeError("Clé serveur stock_service_key absente de st.secrets") from exc
    if not isinstance(url, str) or not url.startswith("https://"):
        raise RuntimeError("URL Supabase incorrecte")
    if not isinstance(key, str) or not key.strip():
        raise RuntimeError("Clé serveur stock_service_key vide")
    require_supabase_target(policy_from_streamlit(st.secrets), url)
    return create_client(url, key)


def _positive_number(value: Any, name: str, *, allow_zero: bool = False) -> str:
    if isinstance(value, bool):
        raise ValueError(f"{name} doit être numérique")
    try:
        number = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise ValueError(f"{name} doit être numérique") from exc
    if not number.is_finite() or number >= Decimal("1e15") or (number < 0 if allow_zero else number <= 0):
        raise ValueError(f"{name} doit être positif et fini")
    # La chaîne décimale évite la perte de précision dans la requête JSON.
    return format(number, "f")


def _required_text(value: Any, name: str, *, max_length: int = 200) -> str:
    if not isinstance(value, str) or not value.strip() or len(value.strip()) > max_length:
        raise ValueError(f"{name} est obligatoire (max {max_length} caractères)")
    return value.strip()


def _apply_stock(
    item_type: str,
    direction: str,
    item_id: str,
    quantite: Any,
    reference: str,
    *,
    unit_cost: Any = None,
    date_peremption: str | None = None,
    operation_id: str | None = None,
) -> dict[str, Any]:
    item_id = _required_text(item_id, "Identifiant article")
    reference = _required_text(reference, "Référence document", max_length=500)
    qte = _positive_number(quantite, "Quantité")
    if item_type not in ("MP", "PF") or direction not in ("ENTREE", "SORTIE"):
        raise ValueError("Type d'article ou de mouvement inconnu")
    if direction == "ENTREE":
        cout = _positive_number(unit_cost, "Coût unitaire", allow_zero=True)
    else:
        cout = None
    if date_peremption is not None and not isinstance(date_peremption, str):
        raise ValueError("Date de péremption incorrecte")
    if date_peremption is not None and len(date_peremption) > 40:
        raise ValueError("Date de péremption trop longue")
    op_id = (_required_text(operation_id, "Identifiant d'opération", max_length=128)
             if operation_id is not None else f"STK-{uuid4()}")

    # IMPORTANT : vérification par le backend de l'ERP ; elle doit fonctionner
    # même quand l'appel provient d'un module Production/Achats/Ventes.
    target_table = "mouvements" if item_type == "MP" else "mouvements_pf"
    if check_server_permission(target_table) is not True:
        raise PermissionError("Droit d'écriture Stocks refusé")

    params = {
        "p_operation_id": op_id,
        "p_item_type": item_type,
        "p_direction": direction,
        "p_item_id": item_id,
        "p_quantity": qte,
        "p_unit_cost": cout,
        "p_reference": reference,
        "p_expiry": date_peremption or None,
    }
    try:
        response = _stock_rpc_client().rpc("erp_apply_stock_movement", params).execute()
    except Exception as exc:
        # Un timeout peut se produire APRÈS le commit en base. Ne surtout pas
        # rappeler la fonction avec un nouvel operation_id dans ce cas.
        raise StockOperationError(
            "Mouvement non confirmé : vérifier Supabase, puis réessayer avec le MÊME operation_id",
            operation_id=op_id,
        ) from exc
    result = response.data
    if not isinstance(result, dict) or result.get("operation_id") != op_id:
        raise StockOperationError(
            "Réponse stock inattendue : vérifier l'opération avant toute reprise",
            operation_id=op_id,
        )
    if direction == "SORTIE":
        try:
            cost_total = Decimal(str(result["cost_total"]))
            remaining = Decimal(str(result["quantity_remaining"]))
            if not cost_total.is_finite() or cost_total < 0 or not remaining.is_finite() or remaining < 0:
                raise ValueError("réponse financière invalide")
        except (ValueError, InvalidOperation, KeyError, TypeError) as exc:
            raise StockOperationError(
                "Résultat financier non vérifiable : contrôler l'opération en base",
                operation_id=op_id,
            ) from exc
    return result


def enregistrer_entree_mp(
    mp_id: str, quantite: float, prix_entree: float, reference: str,
    date_peremption: str, *, operation_id: str | None = None,
) -> None:
    _apply_stock("MP", "ENTREE", mp_id, quantite, reference,
                 unit_cost=prix_entree, date_peremption=date_peremption,
                 operation_id=operation_id)


def enregistrer_sortie_mp(
    mp_id: str, quantite: float, reference: str, *, operation_id: str | None = None,
) -> float:
    result = _apply_stock("MP", "SORTIE", mp_id, quantite, reference,
                          operation_id=operation_id)
    return float(Decimal(str(result["cost_total"])))


def enregistrer_entree_pf(
    sku_id: str, quantite: float, cout_unitaire: float, reference: str,
    date_peremption: str, *, operation_id: str | None = None,
) -> None:
    _apply_stock("PF", "ENTREE", sku_id, quantite, reference,
                 unit_cost=cout_unitaire, date_peremption=date_peremption,
                 operation_id=operation_id)


def enregistrer_sortie_pf(
    sku_id: str, quantite: float, reference: str, *, operation_id: str | None = None,
) -> None:
    _apply_stock("PF", "SORTIE", sku_id, quantite, reference,
                 operation_id=operation_id)
