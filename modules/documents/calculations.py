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
                raw_amount = quantity * price
                if raw_amount > MAX_AMOUNT:
                    raise ValueError(f"Ligne {number} : montant excessif")
                line_amount = raw_amount.quantize(MONEY, rounding=ROUND_HALF_UP)
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


def normalize_financial_export(doc: dict) -> dict:
    """Copie défensive : tous les montants imprimés doivent être cohérents.

    Un modèle vide/non chiffré reste exportable en BROUILLON. À la première
    quantité/prix/taxe saisie, les valeurs monétaires doivent être complètes,
    et aucun total fourni ne peut contredire les calculs.
    """
    from modules.documents.layout_nextgen import FINANCIAL_KINDS

    if doc.get("type") not in FINANCIAL_KINDS:
        return dict(doc)

    clean = dict(doc)
    original_items = doc.get("items", [])
    if not isinstance(original_items, list):
        raise ValueError("Lignes invalides")
    # Des descriptions seules peuvent être exportées comme maquette.
    # En revanche une quantité ou un prix engage un contrôle chiffré.
    has_pricing = any(
        isinstance(line, dict) and any(
            str(line.get(key) or "").strip()
            for key in ("quantite", "prix_unitaire", "total_ht")
        )
        for line in original_items
    )
    declared = any(str(doc.get(key) or "").strip() for key in (
        "total_ht", "total_taxes", "total_ttc"
    ))
    if not has_pricing and not declared:
        return clean

    computed = calculate_financial_draft(original_items, str(doc.get("total_taxes") or ""))
    if computed["errors"]:
        raise ValueError("Montants incomplets ou invalides : " + "; ".join(computed["errors"]))
    if not computed["total_ht"]:
        raise ValueError("Aucune ligne chiffrée valide")

    # Ne pas faire confiance aux montants d'une ancienne session ou d'un JSON.
    from decimal import Decimal
    for field in ("total_ht", "total_ttc"):
        supplied = str(doc.get(field) or "").strip()
        actual = computed[field]
        if supplied and (not actual or decimal_value(supplied, field).quantize(MONEY) != Decimal(actual)):
            raise ValueError(f"{field} incohérent avec les lignes et taxes")
    for index, (given, calculated) in enumerate(zip(original_items, computed["items"]), 1):
        old = str(given.get("total_ht") or "").strip()
        if old and decimal_value(old, f"Ligne {index} : HT").quantize(MONEY) != Decimal(calculated["total_ht"]):
            raise ValueError(f"Ligne {index} : montant HT incohérent")
    clean["items"] = computed["items"]
    clean["total_ht"] = computed["total_ht"]
    clean["total_ttc"] = computed["total_ttc"]
    return clean
