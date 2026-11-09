"""Adaptateur interne, lecture seule, pour la RPC fiscale TAX-V2 candidate.

N'utilise pas create_facture_brouillon et n'active pas la transaction legacy.
Aucune mutation, aucun taux légal codé en dur. Source de classification : SQL,
jamais un indicateur transmis par le navigateur.
"""
from __future__ import annotations

from datetime import date
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
import re
from typing import Any


class ApercuFiscalIndisponible(ValueError):
    """Simulation invalide, RPC absente ou réponse insuffisamment traçable."""


_CENT = Decimal("0.01")
_MAX = Decimal("1e15")
_AMOUNT = re.compile(r"[0-9]{1,15}(?:\.[0-9]{1,2})?\Z")
_CODES = frozenset({"TVA_TAUX_NORMAL", "TVA_TAUX_REDUIT"})


def _montant(value: Any, field: str) -> Decimal:
    if not isinstance(value, str) or not _AMOUNT.fullmatch(value):
        raise ApercuFiscalIndisponible(f"{field}: montant monétaire texte requis")
    try:
        number = Decimal(value)
    except (ValueError, InvalidOperation) as exc:
        raise ApercuFiscalIndisponible(f"{field}: montant invalide") from exc
    if not number.is_finite() or not Decimal("0") <= number < _MAX:
        raise ApercuFiscalIndisponible(f"{field}: montant hors limites")
    return number


def _taux(value: Any) -> Decimal:
    if not isinstance(value, str) or len(value) > 50:
        raise ApercuFiscalIndisponible("Taux numérique texte requis")
    try:
        number = Decimal(value)
    except (ValueError, InvalidOperation) as exc:
        raise ApercuFiscalIndisponible("Taux invalide") from exc
    if not number.is_finite() or not Decimal("0") <= number <= Decimal("1"):
        raise ApercuFiscalIndisponible("Taux hors bornes")
    return number


def _date_iso(value: Any) -> str:
    if not isinstance(value, str):
        raise ApercuFiscalIndisponible("Date fiscale ISO requise")
    try:
        parsed = date.fromisoformat(value)
    except ValueError as exc:
        raise ApercuFiscalIndisponible("Date fiscale invalide") from exc
    if parsed.isoformat() != value:
        raise ApercuFiscalIndisponible("Date fiscale non canonique")
    return value


def simuler_tva_sql(
    *, db_client: Any, lignes: list[dict[str, Any]],
    date_facture: str, paiement_especes: bool = False,
) -> dict[str, Any]:
    """Demande un calcul vérifié au serveur sur montants HT déjà qualifiés.

    Le client serveur doit être explicitement injecté. Le nom de la RPC
    candidate n'est pas celui d'une transaction de facturation ; si elle
    n'est pas déployée, l'appel échoue sans effet secondaire.
    """
    operation_date = _date_iso(date_facture)
    if paiement_especes is not False:
        raise ApercuFiscalIndisponible("Timbre espèces non qualifié")
    if not isinstance(lignes, list) or not 1 <= len(lignes) <= 500:
        raise ApercuFiscalIndisponible("Lignes fiscales manquantes")
    if db_client is None or not callable(getattr(db_client, "rpc", None)):
        raise ApercuFiscalIndisponible("Client serveur interne requis")

    safe: list[dict[str, str]] = []
    seen: set[str] = set()
    for index, item in enumerate(lignes):
        if not isinstance(item, dict) or set(item) != {"sku_id", "montant_ht"}:
            raise ApercuFiscalIndisponible("Classification cliente interdite")
        sku = item["sku_id"]
        if not isinstance(sku, str) or not sku.strip() or len(sku.strip()) > 200:
            raise ApercuFiscalIndisponible("SKU invalide")
        sku = sku.strip()
        if sku in seen:
            raise ApercuFiscalIndisponible("SKU dupliqué")
        seen.add(sku)
        amount = _montant(item["montant_ht"], f"Ligne {index} HT")
        safe.append({"sku_id": sku, "montant_ht": f"{amount:.2f}"})

    try:
        response = db_client.rpc("erp_tax_preview_classified", {
            "p_lines": safe, "p_date": operation_date, "p_cash": False,
        }).execute()
        data = response.data
    except Exception as exc:
        raise ApercuFiscalIndisponible(
            "Prévisualisation SQL indisponible : aucune facture créée"
        ) from exc

    if not isinstance(data, dict) or data.get("statut") != "CALCUL_ISOLE_NON_COMPTABILISE":
        raise ApercuFiscalIndisponible("Réponse SQL non vérifiable")
    if data.get("date_facture") != operation_date or not isinstance(data.get("lignes"), list):
        raise ApercuFiscalIndisponible("Date ou lignes SQL incohérentes")
    output_lines = data["lignes"]
    if len(output_lines) != len(safe):
        raise ApercuFiscalIndisponible("Nombre de lignes SQL incohérent")

    total_ht = Decimal("0")
    total_tva = Decimal("0")
    for expected, result in zip(safe, output_lines):
        if not isinstance(result, dict) or result.get("sku_id") != expected["sku_id"]:
            raise ApercuFiscalIndisponible("SKU retourné différent")
        code = result.get("code_tva")
        if code not in _CODES:
            raise ApercuFiscalIndisponible("Qualification TVA absente")
        if any(not isinstance(result.get(k), str) or not result[k].strip()
               for k in ("source_classification", "source_taux",
                         "date_verification_classification", "date_verification_taux")):
            raise ApercuFiscalIndisponible("Traçabilité TVA incomplète")
        _date_iso(result["date_verification_classification"])
        _date_iso(result["date_verification_taux"])
        amount = _montant(result.get("montant_ht"), "HT SQL")
        tax = _montant(result.get("montant_tva"), "TVA SQL")
        if amount != _montant(expected["montant_ht"], "HT transmis"):
            raise ApercuFiscalIndisponible("Assiette modifiée par la RPC")
        rate = _taux(result.get("taux_tva"))
        if tax != (amount * rate).quantize(_CENT, rounding=ROUND_HALF_UP):
            raise ApercuFiscalIndisponible("TVA par ligne non concordante")
        total_ht += amount
        total_tva += tax

    if (_montant(data.get("montant_ht"), "Total HT") != total_ht
            or _montant(data.get("montant_tva"), "Total TVA") != total_tva
            or _montant(data.get("montant_timbre"), "Timbre") != 0
            or _montant(data.get("montant_ttc"), "TTC") != total_ht + total_tva):
        raise ApercuFiscalIndisponible("Sommes SQL non concordantes")
    return data
