"""Services Ventes : factures et expéditions transactionnelles.

Supabase est la source de vérité. Les écritures passent par erp_sale_transaction.
Aucune annulation de facture ne déclenche un mouvement physique de stock.
Migration préalable : SQL 002, puis SQL 005, sur un Supabase de TEST.
"""
from __future__ import annotations

from datetime import date
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from typing import Any
from uuid import uuid4

import pandas as pd

from core.db_service import check_server_permission, fetch_data, fetch_data_filtered, get_supabase_client
from core.utils import get_local_now
from modules.stocks.service import _stock_rpc_client

try:
    from num2words import num2words
except ImportError:
    num2words = None

CENT = Decimal("0.01")
LIMIT = Decimal("1e15")
TAUX_TVA = Decimal("0.19")  # Convention actuelle, à faire valider par la comptabilité
TAUX_TIMBRE = Decimal("0.01")
MAX_TIMBRE = Decimal("2500.00")
MAX_LINES = 500


class SaleOperationError(RuntimeError):
    """Résultat de transaction incertain : conserver operation_id pour une reprise."""

    def __init__(self, message: str, *, operation_id: str):
        super().__init__(message)
        self.operation_id = operation_id


def _text(value: Any, field: str, *, max_len: int = 200, optional: bool = False) -> str:
    if not isinstance(value, str) or len(value.strip()) > max_len or (not optional and not value.strip()):
        raise ValueError(f"{field} invalide")
    return value.strip()


def _decimal(value: Any, field: str, *, strictly_positive: bool = False) -> Decimal:
    if isinstance(value, bool):
        raise ValueError(f"{field} invalide")
    raw = str(value)
    if len(raw) > 64:
        raise ValueError(f"{field} trop long")
    try:
        n = Decimal(raw)
    except (InvalidOperation, ValueError, TypeError) as exc:
        raise ValueError(f"{field} invalide") from exc
    if not n.is_finite() or n >= LIMIT or n < 0 or (strictly_positive and n == 0) or n.as_tuple().exponent < -12:
        raise ValueError(f"{field} doit être positif, fini et précis")
    return n


def _money(amount: Decimal) -> Decimal:
    return amount.quantize(CENT, rounding=ROUND_HALF_UP)


def _fmt(amount: Decimal) -> str:
    return format(amount, "f")


def _lines(panier: Any) -> list[dict]:
    if not isinstance(panier, list) or not 1 <= len(panier) <= MAX_LINES or any(not isinstance(x, dict) for x in panier):
        raise ValueError("Le panier doit contenir entre 1 et 500 lignes")
    return panier


def _date(value: str, field: str, *, optional: bool = False) -> str:
    text = _text(value, field, max_len=10, optional=optional)
    if text:
        try:
            parsed = date.fromisoformat(text)
        except ValueError as exc:
            raise ValueError(f"{field} : date attendue AAAA-MM-JJ") from exc
        if parsed.isoformat() != text:
            raise ValueError(f"{field} : format invalide")
    return text


def get_factures() -> pd.DataFrame:
    return pd.DataFrame(fetch_data("factures"))


def get_lignes_facture(facture_id: str) -> list:
    return fetch_data_filtered("lignes_facture", "facture_id", facture_id)


def get_bons_livraison() -> pd.DataFrame:
    return pd.DataFrame(fetch_data("bons_livraison"))


def get_lignes_bons_livraison(bl_id: str = None) -> pd.DataFrame:
    if bl_id:
        return pd.DataFrame(fetch_data_filtered("lignes_bons_livraison", "bl_id", bl_id))
    return pd.DataFrame(fetch_data("lignes_bons_livraison"))


def generer_numero_facture_legal(type_document: str) -> str:
    """API historique pour réservation manuelle ; NE PAS utiliser pour créer un brouillon.

    La création transactionnelle calcule son numéro à l'intérieur de la RPC.
    Cette fonction historique peut réserver un numéro sans créer de facture.
    """
    if type_document not in ("FactureClient", "FactureAvoir"):
        raise ValueError("Type de compteur inconnu")
    if check_server_permission("factures") is not True:
        raise PermissionError("Droit Ventes refusé")
    data = fetch_data_filtered("compteurs", "type_document", type_document)
    if len(data) != 1:
        raise RuntimeError("Compteur légal absent ou ambigu")
    row = data[0]
    prefixe = _text(row.get("prefixe"), "Préfixe", max_len=30)
    annee = _text(row.get("annee"), "Année", max_len=10)
    # Une seule modification en base par increment_compteur ; PAS de update_hybrid en plus.
    response = get_supabase_client().rpc("increment_compteur", {"p_type_document": type_document}).execute()
    raw = response.data
    if isinstance(raw, bool) or not isinstance(raw, int) or not 0 < raw < 1000000000:
        raise RuntimeError("Numéro légal non vérifiable")
    return f"{prefixe}-{annee}-{raw:06d}"


def _invoice_lines(panier: list) -> tuple[list[dict], Decimal]:
    converted: list[dict] = []
    total = Decimal("0")
    for item in _lines(panier):
        sku = _text(item.get("sku_id"), "SKU")
        qte = _decimal(item.get("quantite"), "Quantité", strictly_positive=True)
        if qte != qte.to_integral_value():
            raise ValueError("Une facture de SKU conditionnés exige des unités entières")
        prix = _decimal(item.get("prix_unitaire"), "Prix unitaire")
        remise = _decimal(item.get("remise", 0), "Remise de ligne")
        brut = qte * prix
        if brut >= LIMIT or remise > brut:
            raise ValueError("Remise supérieure au montant de ligne")
        net = _money(brut - remise)
        total += net
        if total >= LIMIT:
            raise ValueError("Montant facture trop élevé")
        converted.append({"sku_id": sku, "quantite": _fmt(qte), "prix_unitaire": _fmt(prix),
                          "remise_ligne": _fmt(remise), "total_ligne_ht": _fmt(net)})
    return converted, total


def _totals(panier: list, remise_globale: Any, paiement_especes: bool) -> tuple[dict, list[dict]]:
    if not isinstance(paiement_especes, bool):
        raise ValueError("Paiement espèces invalide")
    lines, total_net = _invoice_lines(panier)
    global_discount = _decimal(remise_globale, "Remise globale")
    if global_discount > total_net:
        raise ValueError("La remise globale dépasse le montant HT")
    ht = _money(total_net - global_discount)
    tva = _money(ht * TAUX_TVA)
    ttc_before_stamp = ht + tva
    stamp = min(_money(ttc_before_stamp * TAUX_TIMBRE), MAX_TIMBRE) if paiement_especes else Decimal("0")
    ttc = _money(ttc_before_stamp + stamp)
    gross = sum((Decimal(line["quantite"]) * Decimal(line["prix_unitaire"]) for line in lines), Decimal("0"))
    discount_lines = sum((Decimal(line["remise_ligne"]) for line in lines), Decimal("0"))
    amounts = {"total_ht": _money(gross), "total_remise": _money(discount_lines + global_discount),
               "net_a_payer": ht, "total_tva": tva, "timbre_fiscal": stamp, "total_ttc": ttc}
    return amounts, lines


def calculer_montants_facture(panier: list, remise_globale: float = 0.0, paiement_especes: bool = False) -> dict:
    """Remise de ligne exprimée en montant, et non en pourcentage."""
    sums, _ = _totals(panier, remise_globale, paiement_especes)
    ttc = sums["total_ttc"]
    integer = int(ttc)
    cents = int((ttc - Decimal(integer)) * 100)
    if num2words:
        wording = f"{num2words(integer, lang='fr')} Dinars Algériens"
        if cents:
            wording += f" et {num2words(cents, lang='fr')} Centimes"
    else:
        wording = f"{ttc:,.2f} Dinars Algériens"
    return {**{k: float(v) for k, v in sums.items()}, "montant_lettres": wording.capitalize()}


def _rpc(action: str, payload: dict, *, operation_id: str | None = None) -> dict:
    op_id = _text(operation_id, "Identifiant opération", max_len=128) if operation_id is not None else f"SALE-{uuid4()}"
    if check_server_permission("factures" if action != "SHIP" else "bons_livraison") is not True:
        raise PermissionError("Droit d'écriture Ventes refusé")
    if action == "SHIP" and check_server_permission("mouvements_pf") is not True:
        raise PermissionError("Droit d'écriture Stocks refusé")
    try:
        response = _stock_rpc_client().rpc("erp_sale_transaction", {
            "p_action": action, "p_operation_id": op_id, "p_payload": payload,
        }).execute()
    except Exception as exc:
        raise SaleOperationError(
            "Opération non confirmée : vérifier Supabase et reprendre avec le MÊME operation_id",
            operation_id=op_id,
        ) from exc
    result = response.data
    if not isinstance(result, dict) or result.get("operation_id") != op_id or result.get("action") != action:
        raise SaleOperationError("Réponse SQL non vérifiable", operation_id=op_id)
    return result


def create_facture_brouillon(client_id: str, date_echeance: str, panier: list,
                             remise_globale: float = 0.0, paiement_especes: bool = False,
                             is_avoir: bool = False, facture_origine_id: str = "",
                             *, operation_id: str | None = None) -> str:
    """Brouillon complet + lignes + compteur dans UNE transaction (aucun mouvement stock)."""
    client = _text(client_id, "Client")
    echeance = _date(date_echeance, "Échéance", optional=True)
    if not isinstance(is_avoir, bool):
        raise ValueError("Type d'avoir invalide")
    origine = _text(facture_origine_id, "Facture origine", optional=True)
    if is_avoir and not origine:
        raise ValueError("Un avoir doit référencer une facture d'origine")
    if not is_avoir and origine:
        raise ValueError("Seul un avoir peut avoir une facture d'origine")
    if is_avoir and paiement_especes:
        raise ValueError("Le timbre espèces d'un avoir nécessite un traitement fiscal dédié")
    amounts, lines = _totals(panier, remise_globale, paiement_especes)
    payload = {
        "client_id": client, "date_echeance": echeance,
        "remise_globale": _fmt(_decimal(remise_globale, "Remise globale")),
        "paiement_especes": paiement_especes,
        "type_facture": "FactureAvoir" if is_avoir else "FactureClient",
        "facture_origine_id": origine,
        "montant_ht": _fmt(-amounts["net_a_payer"] if is_avoir else amounts["net_a_payer"]),
        "montant_tva": _fmt(-amounts["total_tva"] if is_avoir else amounts["total_tva"]),
        "montant_timbre": _fmt(amounts["timbre_fiscal"]),
        "montant_ttc": _fmt(-amounts["total_ttc"] if is_avoir else amounts["total_ttc"]),
        "lignes": lines,
    }
    result = _rpc("DRAFT", payload, operation_id=operation_id)
    return _text(result.get("facture_id"), "Numéro facture")


def valider_facture(facture_id: str, *, operation_id: str | None = None):
    """Valide la facture en base, sans sortie de stock (débit physique au BL)."""
    doc_id = _text(facture_id, "Facture")
    return _rpc("VALIDATE", {"facture_id": doc_id}, operation_id=operation_id)


def annuler_facture(facture_id: str, *, operation_id: str | None = None):
    """Annule exclusivement un brouillon. Aucun mouvement stock créé."""
    doc_id = _text(facture_id, "Facture")
    return _rpc("CANCEL", {"facture_id": doc_id}, operation_id=operation_id)


def creer_bon_livraison(commande_vente_id: str, transporteur: str, zone: str,
                        items_livraison: list, *, operation_id: str | None = None) -> str:
    """BL et sorties FIFO dans UNE transaction ; lots du résultat FIFO réel."""
    order_id = _text(commande_vente_id, "Commande client")
    carrier = _text(transporteur, "Transporteur", max_len=200, optional=True)
    zone = _text(zone, "Zone", max_len=200, optional=True)
    lines: list[dict] = []
    for item in _lines(items_livraison):
        sku = _text(item.get("sku_id"), "SKU")
        qty = _decimal(item.get("quantite_livree"), "Quantité livrée", strictly_positive=True)
        if qty != qty.to_integral_value():
            raise ValueError("Une livraison de SKU conditionnés exige des unités entières")
        preferred = item.get("lot_id")
        if preferred not in (None, "", "DEFAUT"):
            raise ValueError("Choix manuel d'un lot non pris en charge par le FIFO automatique")
        lines.append({"sku_id": sku, "quantite_livree": _fmt(qty)})
    result = _rpc("SHIP", {"commande_vente_id": order_id, "transporteur": carrier,
                           "zone": zone, "lignes": lines}, operation_id=operation_id)
    return _text(result.get("bl_id"), "Numéro de livraison")
