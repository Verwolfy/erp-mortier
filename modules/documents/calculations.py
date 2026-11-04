"""Calculs de brouillons commerciaux : aucune règle TVA supposée.

Montants en DZD calculés avec Decimal. Les taxes restent saisies/validées
séparément ; les documents demeurent NON ÉMIS.
"""
from __future__ import annotations

from decimal import Decimal, InvalidOperation, ROUND_HALF_UP

MAX_AMOUNT = Decimal("999999999999.99")
MONEY = Decimal("0.01")


def decimal_value(value, label: str) -> Decimal:
    text = str(value if value is not None else "").strip().replace(" ", "").replace("\u00a0", "")
    if not text:
        raise ValueError(f"{label} manquant")
    if "," in text and "." in text:
        # Autoriser 1 234,56 mais pas les séparateurs ambigus.
        raise ValueError(f"{label} : format ambigu")
    text = text.replace(",", ".")
    try:
        result = Decimal(text)
    except InvalidOperation as exc:
        raise ValueError(f"{label} : nombre invalide") from exc
    if not result.is_finite() or result < 0 or result > MAX_AMOUNT:
        raise ValueError(f"{label} : valeur hors limites")
    return result


def amount_string(value: Decimal) -> str:
    return str(value.quantize(MONEY, rounding=ROUND_HALF_UP))


def calculate_financial_draft(items: list[dict], taxes: str = "") -> dict:
    """Retourne un résultat isolé, sans modifier les lignes de départ.

    Les lignes vides ne comptent pas. Dès qu'une ligne renseignée manque de
    quantité ou de prix, le total global reste indisponible.
    """
    if not isinstance(items, list):
        raise ValueError("Lignes invalides")
    updated = []
    errors = []
    total = Decimal(0)
    priced_rows = 0
    for number, item in enumerate(items, start=1):
        if not isinstance(item, dict):
            errors.append(f"Ligne {number} : données invalides")
            continue
        line = dict(item)
        fields = ("reference", "designation", "unite", "quantite", "prix_unitaire")
        meaningful = any(str(item.get(k, "") or "").strip() for k in fields)
        if not meaningful:
            line["total_ht"] = ""
        else:
            try:
                quantity = decimal_value(item.get("quantite"), f"Ligne {number} : quantité")
                price = decimal_value(item.get("prix_unitaire"), f"Ligne {number} : prix unitaire")
                line_amount = (quantity * price).quantize(MONEY, rounding=ROUND_HALF_UP)
                if line_amount > MAX_AMOUNT:
                    raise ValueError(f"Ligne {number} : montant excessif")
                line["total_ht"] = amount_string(line_amount)
                total += line_amount
                if total > MAX_AMOUNT:
                    raise ValueError("Total HT excessif")
                priced_rows += 1
            except ValueError as exc:
                line["total_ht"] = ""
                errors.append(str(exc))
        updated.append(line)
    ht = amount_string(total) if priced_rows and not errors else ""
    ttc = ""
    tax_amount = None
    if str(taxes or "").strip():
        try:
            tax_amount = decimal_value(taxes, "Montant des taxes")
        except ValueError as exc:
            errors.append(str(exc))
    if ht and tax_amount is not None and not errors:
        if total + tax_amount > MAX_AMOUNT:
            errors.append("Total TTC excessif")
        else:
            ttc = amount_string(total + tax_amount)
    return {"items": updated, "total_ht": ht, "total_ttc": ttc,
            "errors": errors, "priced_rows": priced_rows}
