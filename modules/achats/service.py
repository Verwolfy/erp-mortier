"""Achats : commandes et réceptions atomiques via les RPC PostgreSQL.

Les mutations utilisent Supabase comme source de vérité, et non plusieurs
insert_hybrid() successifs. Les noms publics des fonctions restent compatibles.

Prérequis : SQL 002 (Stocks), puis 004 (Achats), dans un projet de TEST ;
clé serveur stock_service_key réservée à Streamlit. Ne pas fusionner dans main
avant validation SQL réelle et adaptation des vues aux réceptions partielles.
"""

from __future__ import annotations

from decimal import Decimal, InvalidOperation
from typing import Any
from uuid import uuid4

import pandas as pd

from core.db_service import check_server_permission, fetch_data, fetch_data_filtered
from core.utils import generate_technical_id, generate_unique_id, get_local_now
from modules.stocks.service import _stock_rpc_client


MAX_LINES = 500
LIMIT = Decimal("1e15")


class PurchaseOperationError(RuntimeError):
    """Échec non confirmé. Réessayer avec le MÊME operation_id, jamais un nouveau."""

    def __init__(self, message: str, *, operation_id: str):
        super().__init__(message)
        self.operation_id = operation_id


def _text(value: Any, label: str, *, max_len: int = 200, allow_empty: bool = False) -> str:
    if not isinstance(value, str):
        raise ValueError(f"{label} doit être un texte")
    result = value.strip()
    if (not result and not allow_empty) or len(result) > max_len:
        raise ValueError(f"{label} invalide (maximum {max_len} caractères)")
    return result


def _number(value: Any, label: str, *, allow_zero: bool = False) -> Decimal:
    if isinstance(value, bool):
        raise ValueError(f"{label} doit être numérique")
    try:
        result = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise ValueError(f"{label} doit être numérique") from exc
    if not result.is_finite() or result >= LIMIT or (result < 0 if allow_zero else result <= 0):
        raise ValueError(f"{label} doit être positif et fini")
    return result


def _fmt(value: Decimal) -> str:
    return format(value, "f")


def _items(value: Any, label: str) -> list[dict[str, Any]]:
    if not isinstance(value, list) or not 1 <= len(value) <= MAX_LINES:
        raise ValueError(f"{label} doit contenir 1 à {MAX_LINES} lignes")
    if any(not isinstance(item, dict) for item in value):
        raise ValueError(f"{label} contient une ligne invalide")
    return value


def _rpc(name: str, params: dict[str, Any], *, receipt: bool) -> dict[str, Any]:
    op_id = params["p_operation_id"]
    if check_server_permission("bons_reception" if receipt else "commandes_achats") is not True:
        raise PermissionError("Droit d'écriture Achats refusé")
    if receipt and check_server_permission("mouvements") is not True:
        raise PermissionError("Droit d'écriture Stocks refusé")
    try:
        response = _stock_rpc_client().rpc(name, params).execute()
    except Exception as exc:
        raise PurchaseOperationError(
            "Transaction non confirmée : contrôler la base avant de réessayer avec le MÊME operation_id",
            operation_id=op_id,
        ) from exc
    result = response.data
    expected_doc = "bon_reception_id" if receipt else "commande_achat_id"
    if (not isinstance(result, dict) or result.get("operation_id") != op_id
            or not isinstance(result.get(expected_doc), str) or not result[expected_doc]):
        raise PurchaseOperationError(
            "Réponse RPC incomplète : vérifier l'opération avant reprise",
            operation_id=op_id,
        )
    return result


def get_commandes() -> pd.DataFrame:
    return pd.DataFrame(fetch_data("commandes_achats"))


def get_lignes_achats(commande_id: str | None = None) -> pd.DataFrame:
    data = (fetch_data_filtered("lignes_achats", "commande_achat_id", commande_id)
            if commande_id else fetch_data("lignes_achats"))
    return pd.DataFrame(data)


def get_bons_reception() -> pd.DataFrame:
    return pd.DataFrame(fetch_data("bons_reception"))


def get_lignes_bons_reception(br_id: str | None = None) -> pd.DataFrame:
    data = (fetch_data_filtered("lignes_bons_reception", "bon_reception_id", br_id)
            if br_id else fetch_data("lignes_bons_reception"))
    return pd.DataFrame(data)


def create_commande_achat(
    fournisseur_id: str, type_achat: str, devise: str, taux_change: float,
    mode_paiement: str, delai_paiement: str, date_voulue: str, panier: list,
    *, operation_id: str | None = None,
) -> str:
    """Enregistre en UNE transaction la commande et toutes ses lignes."""
    fournisseur = _text(fournisseur_id, "Fournisseur")
    nature = _text(type_achat, "Type d'achat")
    currency = _text(devise, "Devise", max_len=30)
    change = _number(taux_change, "Taux de change")
    # Un prix de stock est exprime en DZD ; un achat DZD ne se convertit pas.
    if currency.upper() == "DZD" and change != Decimal("1"):
        raise ValueError("Taux de change DZD obligatoire : 1")
    paiement = _text(mode_paiement, "Mode de paiement", allow_empty=True)
    delai = _text(delai_paiement, "Délai de paiement", allow_empty=True)
    date = _text(str(date_voulue), "Date voulue", max_len=40, allow_empty=True)
    lines: list[dict[str, Any]] = []
    for item in _items(panier, "Commande"):
        qty_cond = _number(item.get("qte_cond"), "Quantité conditionnement")
        qty_stock = _number(item.get("qte_totale"), "Quantité totale")
        unit_price = _number(item.get("prix_unitaire"), "Prix unitaire", allow_zero=True)
        line_total = _number(item.get("total_devise"), "Total ligne", allow_zero=True)
        # Aucune transformation de conditionnement n'est definie dans le schema actuel.
        if qty_cond != qty_stock:
            raise ValueError("Conversion de conditionnement non configuree : quantites differentes")
        if abs(line_total - qty_stock * unit_price) > Decimal("0.01"):
            raise ValueError("Total de ligne incoherent avec quantite x prix")
        lines.append({
            "ligne_achat_id": _text(generate_technical_id("LAC"), "ID ligne"),
            "mp_id": _text(item.get("mp_id"), "Matière première"),
            "unite_cond": _text(item.get("unite_cond"), "Unité conditionnement"),
            "qte_cond": _fmt(qty_cond),
            "qte_totale": _fmt(qty_stock),
            "prix_unitaire": _fmt(unit_price),
            "total_devise": _fmt(line_total),
        })
    # Même branche et même convention d'identifiants métier qu'avant.
    df = get_commandes()
    exist_ids = df["commande_achat_id"].dropna().tolist() if "commande_achat_id" in df.columns else []
    doc_id = _text(generate_unique_id("CMA", exist_ids), "ID commande")
    op_id = _text(operation_id, "ID opération", max_len=128) if operation_id is not None else f"ACH-{uuid4()}"
    result = _rpc("erp_create_purchase_order", {
        "p_operation_id": op_id,
        "p_order_id": doc_id,
        "p_fournisseur_id": fournisseur,
        "p_type_achat": nature,
        "p_devise": currency,
        "p_taux_change": _fmt(change),
        "p_mode_paiement": paiement,
        "p_delai_paiement": delai,
        "p_date_voulue": date,
        "p_lines": lines,
    }, receipt=False)
    return result["commande_achat_id"]


def creer_bon_reception(
    commande_achat_id: str, date_reception: str, controle_conformite: str,
    remarques: str, items_recus: list, date_peremption: str = "",
    *, operation_id: str | None = None,
) -> str:
    """Réception + lots réels + mouvements + statut BC en UNE transaction.

    N'admet que les livraisons conformes. Les réceptions partielles sont suivies
    avec le statut PARTIELLEMENT_RECEPTIONNE (vues à vérifier avant déploiement).
    """
    cmd_id = _text(commande_achat_id, "Commande achat")
    date = _text(date_reception, "Date de réception", max_len=40)
    controle = _text(controle_conformite, "Conformité", max_len=40).upper()
    if controle != "OUI":
        raise ValueError("Réception stock interdite sans conformité OUI")
    comment = _text(remarques, "Remarques", max_len=5000, allow_empty=True)
    expiry = _text(date_peremption, "Péremption", max_len=40, allow_empty=True)
    lines: list[dict[str, Any]] = []
    for item in _items(items_recus, "Réception"):
        lines.append({
            "ligne_br_id": _text(generate_technical_id("LBR"), "ID ligne réception"),
            "mp_id": _text(item.get("mp_id"), "Matière première"),
            "quantite_recue": _fmt(_number(item.get("quantite_recue"), "Quantité reçue")),
            # Champ historique conserve pour compatibilite RPC. Le SQL recalcule
            # exclusivement le cout DZD depuis la commande et son taux de change.
            "prix_unitaire": _fmt(_number(item.get("prix_unitaire", 0), "Prix commande", allow_zero=True)),
        })
    df = get_bons_reception()
    exist_ids = df["bon_reception_id"].dropna().tolist() if "bon_reception_id" in df.columns else []
    br_id = _text(generate_unique_id("BR", exist_ids), "ID réception")
    op_id = _text(operation_id, "ID opération", max_len=128) if operation_id is not None else f"ACH-{uuid4()}"
    result = _rpc("erp_receive_purchase_order", {
        "p_operation_id": op_id,
        "p_br_id": br_id,
        "p_commande_achat_id": cmd_id,
        "p_date_reception": date,
        "p_controle_conformite": controle,
        "p_remarques": comment,
        "p_date_peremption": expiry,
        "p_lines": lines,
    }, receipt=True)
    return result["bon_reception_id"]
