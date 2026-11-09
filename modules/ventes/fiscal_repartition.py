"""Préparation déterministe des assiettes TVA après remises (simulation seule).

Montants DZD fictifs dans les tests ; aucun taux fiscal codé en dur ici.
Le calcul ne classe aucun SKU et n'écrit aucune facture.
"""
from __future__ import annotations

from decimal import Decimal, ROUND_DOWN, localcontext
import re
from typing import Any

from modules.ventes.fiscal_preview import (
    ApercuFiscalIndisponible, _montant, _MAX, simuler_tva_sql,
)

_CENT = Decimal("0.01")
_INTEGER = re.compile(r"[1-9][0-9]{0,10}\Z")
_ALLOWED = frozenset({"sku_id", "quantite", "prix_unitaire", "remise_ligne"})


def preparer_assiettes_tva(
    panier: list[dict[str, Any]], remise_globale: str = "0.00",
) -> dict[str, Any]:
    """Ventile au centime la remise globale selon le poids HT des lignes.

    Méthode des plus grands restes, départagée par l'ordre d'origine.
    Une ligne ne reçoit jamais plus de remise que son montant HT.
    Les montants et les quantités sont des chaînes JSON, sans float.
    """
    if not isinstance(panier, list) or not 1 <= len(panier) <= 500:
        raise ApercuFiscalIndisponible("Panier fiscal : 1 à 500 lignes requises")
    global_discount = _montant(remise_globale, "Remise globale")
    skus: set[str] = set()
    amounts: list[Decimal] = []
    identifiers: list[str] = []
    for item in panier:
        if not isinstance(item, dict) or not {"sku_id","quantite","prix_unitaire"} <= set(item) or (set(item) - _ALLOWED):
            raise ApercuFiscalIndisponible("Panier fiscal : colonnes non prises en charge")
        sku = item["sku_id"]
        if not isinstance(sku, str) or not sku.strip() or len(sku.strip()) > 200:
            raise ApercuFiscalIndisponible("SKU invalide")
        sku = sku.strip()
        if sku in skus:
            raise ApercuFiscalIndisponible("SKU dupliqué")
        skus.add(sku)
        qty = item["quantite"]
        if not isinstance(qty, str) or not _INTEGER.fullmatch(qty):
            raise ApercuFiscalIndisponible("Quantité conditionnée entière requise")
        price = _montant(item["prix_unitaire"], "Prix unitaire HT")
        line_discount = _montant(item.get("remise_ligne", "0.00"), "Remise de ligne")
        gross = Decimal(qty) * price
        if not gross < _MAX or line_discount > gross:
            raise ApercuFiscalIndisponible("Remise ou prix ligne hors limites")
        amount = gross - line_discount
        if amount < 0 or amount >= _MAX:
            raise ApercuFiscalIndisponible("Montant HT ligne hors limites")
        identifiers.append(sku)
        amounts.append(amount)
    total = sum(amounts, Decimal("0"))
    if total >= _MAX or global_discount > total:
        raise ApercuFiscalIndisponible("Remise globale supérieure au total HT")
    # 60 chiffres de précision pour des montants techniques élevés.
    with localcontext() as ctx:
        ctx.prec = 60
        if total == 0:
            shares = [Decimal("0.00") for _ in amounts]
            fractional = [Decimal("0") for _ in amounts]
        else:
            exact = [global_discount * amount / total for amount in amounts]
            shares = [share.quantize(_CENT, rounding=ROUND_DOWN) for share in exact]
            fractional = [exact[i] - shares[i] for i in range(len(shares))]
        residual = int((global_discount - sum(shares, Decimal("0"))) * 100)
        if residual < 0 or residual > len(shares):
            raise ApercuFiscalIndisponible("Allocation de remise non équilibrée")
        order = sorted(range(len(shares)), key=lambda i: (-fractional[i], i))
        for index in order[:residual]:
            shares[index] += _CENT
    taxable: list[dict[str, str]] = []
    rebates: list[dict[str, str]] = []
    for sku, original, allocated in zip(identifiers, amounts, shares):
        if not Decimal("0") <= allocated <= original:
            raise ApercuFiscalIndisponible("Allocation de remise hors assiette")
        taxable.append({"sku_id": sku, "montant_ht": f"{original-allocated:.2f}"})
        rebates.append({"sku_id": sku, "remise_globale_affectee": f"{allocated:.2f}"})
    if sum((Decimal(x["montant_ht"]) for x in taxable), Decimal("0")) != total-global_discount:
        raise ApercuFiscalIndisponible("Somme des assiettes erronée")
    return {
        "lignes": taxable,
        "repartition_remise_globale": rebates,
        "total_ht_avant_remise_globale": f"{total:.2f}",
        "remise_globale": f"{global_discount:.2f}",
        "total_ht_apres_remise_globale": f"{total-global_discount:.2f}",
        "statut": "PREPARATION_ISOLEE_NON_COMPTABILISEE",
    }


def simuler_tva_panier(
    *, db_client: Any, panier: list[dict[str, Any]],
    date_facture: str, remise_globale: str = "0.00",
    paiement_especes: bool = False,
) -> dict[str, Any]:
    """Prépare les assiettes, puis appelle la simulation SQL serveur sans écriture."""
    preparation = preparer_assiettes_tva(panier, remise_globale)
    simulation = simuler_tva_sql(
        db_client=db_client, lignes=preparation["lignes"],
        date_facture=date_facture, paiement_especes=paiement_especes,
    )
    if Decimal(simulation["montant_ht"]) != Decimal(preparation["total_ht_apres_remise_globale"]):
        raise ApercuFiscalIndisponible("Assiettes de la simulation incohérentes")
    return {**preparation, "simulation": simulation}
