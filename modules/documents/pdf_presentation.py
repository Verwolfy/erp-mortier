"""Présentation sûre des montants et identifiants QR sur les copies ERP.

Aucun accès réseau, aucune écriture, aucune émission documentaire.
Un QR de consultation ne constitue pas une preuve de signature ni d'authenticité.
"""
from __future__ import annotations

from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from hashlib import sha256
import json

from num2words import num2words

_MONEY_UNIT = Decimal("0.01")
_MISSING = frozenset({"", "non renseigné", "non renseigne",
                      "non renseignée", "non renseignee", "non enregistrée",
                      "non enregistree"})


def has_value(value: object) -> bool:
    if value is None or isinstance(value, bool):
        return False
    return str(value).strip().casefold() not in _MISSING


def _number(value: object) -> Decimal:
    if isinstance(value, bool) or not has_value(value):
        raise ValueError("Montant ou quantité indisponible")
    try:
        value = Decimal(str(value).strip())
    except (InvalidOperation, ValueError, TypeError) as exc:
        raise ValueError("Montant ou quantité invalide") from exc
    if not value.is_finite() or value < 0 or value >= Decimal("1e15"):
        raise ValueError("Montant ou quantité hors limites")
    return value


def format_money(value: object) -> str:
    """DZD en notation française, sans conversion flottante."""
    amount = _number(value).quantize(_MONEY_UNIT, rounding=ROUND_HALF_UP)
    return f"{amount:,.2f}".replace(",", " ").replace(".", ",")


def format_quantity(value: object) -> str:
    amount = _number(value)
    rendered = format(amount, "f")
    if "." in rendered:
        rendered = rendered.rstrip("0").rstrip(".")
    whole, sep, fraction = rendered.partition(".")
    parts = []
    while whole:
        parts.append(whole[-3:])
        whole = whole[:-3]
    result = " ".join(reversed(parts))
    return result + ("," + fraction if sep else "")


def amount_in_words(value: object) -> str:
    """Épellation d'un montant en dinars algériens et centimes."""
    amount = _number(value).quantize(_MONEY_UNIT, rounding=ROUND_HALF_UP)
    dinars = int(amount)
    centimes = int((amount - Decimal(dinars)) * 100)
    words = num2words(dinars, lang="fr")
    result = words[0].upper() + words[1:] + (" dinar" if dinars == 1 else " dinars")
    if centimes:
        result += " et " + num2words(centimes, lang="fr") + (
            " centime" if centimes == 1 else " centimes")
    return result + "."


def vat_label(*, rate: object = None, ht: object = None,
              vat: object = None) -> str:
    """Affiche un taux uniquement s'il est enregistré ou démontré par les montants.

    19 % est le taux standard indicatif, jamais une substitution aux montants
    fiscaux historiques, aux exemptions ou aux taux réduits.
    """
    percent = None
    if has_value(rate):
        current = _number(rate)
        percent = current * 100 if current <= 1 else current
        if percent > 100:
            raise ValueError("Taux de TVA hors limites")
    elif has_value(ht) and has_value(vat):
        base = _number(ht)
        amount = _number(vat)
        if base > 0 and abs(amount - (base * Decimal("0.19")).quantize(
                _MONEY_UNIT, rounding=ROUND_HALF_UP)) <= Decimal("0.01"):
            percent = Decimal("19")
    if percent is None:
        return "TVA"
    return "TVA (" + format(percent, "f").rstrip("0").rstrip(".") + " %)"


def qr_payload(snapshot: dict) -> str:
    """Identité de consultation + empreinte; aucune donnée privée en clair.

    Le contrôle réel d'authenticité nécessitera un registre serveur protégé.
    """
    kind, ref = snapshot.get("kind"), snapshot.get("id")
    if not isinstance(kind, str) or not kind or not isinstance(ref, str) or not ref:
        raise ValueError("Référence QR absente")
    canonical = json.dumps(snapshot, ensure_ascii=False, sort_keys=True,
                           separators=(",", ":"), default=str, allow_nan=False)
    digest = sha256(canonical.encode("utf-8")).hexdigest()
    result = {"v": 1, "erp": "NEXTGEN", "type": kind[:80],
              "ref": ref[:128], "empreinte": digest[:32],
              "statut": "COPIE_NON_EMISE"}
    if has_value(snapshot.get("date")) and str(snapshot["date"])[:10].count("-") == 2:
        result["date"] = str(snapshot["date"])[:10]
    return json.dumps(result, ensure_ascii=True, sort_keys=True,
                      separators=(",", ":"))


def draw_qr(pdf, payload: str, *, x: float, y: float, size: float = 32) -> None:
    """QR vectoriel de lecture rapide, sans URL ni accès public."""
    import qrcode
    if not isinstance(payload, str) or not payload or len(payload) > 900:
        raise ValueError("Données QR invalides")
    qr = qrcode.QRCode(error_correction=qrcode.constants.ERROR_CORRECT_M, border=4)
    qr.add_data(payload)
    qr.make(fit=True)
    cells = qr.get_matrix()
    step = size / len(cells)
    pdf.set_fill_color(255, 255, 255)
    pdf.rect(x, y, size, size, style="F")
    pdf.set_fill_color(0, 0, 0)
    for row, values in enumerate(cells):
        for col, active in enumerate(values):
            if active:
                pdf.rect(x + col * step, y + row * step,
                         step + 0.01, step + 0.01, style="F")
