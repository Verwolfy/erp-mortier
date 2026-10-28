"""Moteur générique de tranches marginales, sans barèmes légaux intégrés.

Le barème est une pièce de paramétrage vérifiée, applicable à la date du fait
juridique ; aucun taux d'IRG ou autre montant réglementaire n'est intégré.
Ne produit pas de bulletin ou de déclaration.
"""
from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from typing import Any, Mapping


class BaremeIndisponible(ValueError):
    """Barème absent, non vérifié, mal formé ou inapplicable."""


def _nombre(value: Any, nom: str) -> Decimal:
    if isinstance(value, bool) or not isinstance(value, (int, str, Decimal)):
        raise BaremeIndisponible(f"{nom}: décimal exact obligatoire")
    try:
        number = Decimal(str(value))
    except (InvalidOperation, ValueError) as exc:
        raise BaremeIndisponible(f"{nom}: valeur invalide") from exc
    if not number.is_finite():
        raise BaremeIndisponible(f"{nom}: valeur non finie")
    return number


def _date(value: Any, nom: str) -> date:
    if isinstance(value, date) and not isinstance(value, datetime):
        return value
    if isinstance(value, str):
        try:
            parsed = date.fromisoformat(value)
        except ValueError as exc:
            raise BaremeIndisponible(f"{nom}: date invalide") from exc
        if parsed.isoformat() == value:
            return parsed
    raise BaremeIndisponible(f"{nom}: date ISO requise")


def calculer_bareme_progressif(
    assiette: int | str | Decimal,
    regle: Mapping[str, Any],
    date_operation: date | str,
    *,
    code: str,
    unite_arrondi: str = "0.01",
) -> dict[str, Any]:
    """Calcul progressif marginal avec contrôle des bornes et provenance.

    Le champ tranches est une liste croissante d'objets avec jusqua (borne
    supérieure incluse, None pour +infini) et taux (fraction de 0 à 1).
    La première tranche part de zéro, chaque tranche suivante reprend exactement
    la borne précédente, et la dernière doit avoir jusqua = None.
    Le total est arrondi une seule fois, après sommation des montants non arrondis.
    Une règle non confirmée ou non datée n'est jamais appliquée.
    """
    if not isinstance(regle, Mapping) or not isinstance(code, str) or not code.strip():
        raise BaremeIndisponible("Barème et code obligatoires")
    if regle.get("code") != code:
        raise BaremeIndisponible("Code du barème différent")
    if (regle.get("statut_juridique") != "en_vigueur"
            or regle.get("niveau_confiance") != "CONFIRMEE"):
        raise BaremeIndisponible("Règle non confirmée et en vigueur")
    source = regle.get("source")
    if not isinstance(source, str) or not source.strip():
        raise BaremeIndisponible("Source juridique obligatoire")
    instant = _date(date_operation, "date_operation")
    debut = _date(regle.get("date_effet"), "date_effet")
    fin = (_date(regle["date_fin"], "date_fin")
           if regle.get("date_fin") is not None else None)
    verification = _date(regle.get("date_verification"), "date_verification")
    if (fin is not None and fin < debut) or instant < debut or (fin and instant > fin):
        raise BaremeIndisponible("Barème hors de sa période de validité")
    base = _nombre(assiette, "assiette")
    quantum = _nombre(unite_arrondi, "unite_arrondi")
    if base < 0 or base >= Decimal("1e15") or quantum <= 0:
        raise BaremeIndisponible("Assiette ou arrondi invalide")
    tranches = regle.get("tranches")
    if not isinstance(tranches, list) or not tranches:
        raise BaremeIndisponible("Liste de tranches absente")
    montant = Decimal(0)
    precedent = Decimal(0)
    details = []
    for index, item in enumerate(tranches):
        if not isinstance(item, Mapping):
            raise BaremeIndisponible("Tranche invalide")
        plafond = None if item.get("jusqua") is None else _nombre(item["jusqua"], "jusqua")
        taux = _nombre(item.get("taux"), "taux")
        if not Decimal(0) <= taux <= Decimal(1):
            raise BaremeIndisponible("Taux marginal invalide")
        if plafond is None and index != len(tranches) - 1:
            raise BaremeIndisponible("Tranche ouverte avant la fin")
        if plafond is not None and plafond <= precedent:
            raise BaremeIndisponible("Bornes non strictement croissantes")
        if index == len(tranches) - 1 and plafond is not None:
            raise BaremeIndisponible("Dernière tranche doit être ouverte")
        haut = base if plafond is None else min(base, plafond)
        taxable = max(Decimal(0), haut - precedent)
        produit = taxable * taux
        montant += produit
        details.append({
            "debut": format(precedent, "f"),
            "fin": format(plafond, "f") if plafond is not None else None,
            "assiette_tranche": format(taxable, "f"),
            "taux": format(taux, "f"),
            "montant_non_arrondi": format(produit, "f"),
        })
        if plafond is not None:
            precedent = plafond
    return {
        "code": code,
        "assiette": format(base, "f"),
        "montant": format(montant.quantize(quantum, rounding=ROUND_HALF_UP), "f"),
        "date_operation": instant.isoformat(),
        "date_effet": debut.isoformat(),
        "source": source.strip(),
        "date_verification": verification.isoformat(),
        "tranches": details,
    }

def test_bareme_depuis_registre_sql_jsonb():
    configuration = regle()
    tranches = configuration.pop("tranches")
    configuration["donnees"] = {"tranches": tranches}
    assert calculer_bareme_progressif(
        "300", configuration, "2026-06-30", code="TEST_PROGRESSIF"
    )["montant"] == "30.00"


def test_bareme_ambigu_refuse():
    configuration = regle(donnees={"tranches": [{"jusqua": None, "taux": "1"}]})
    with pytest.raises(BaremeIndisponible):
        calculer_bareme_progressif(
            "300", configuration, "2026-06-30", code="TEST_PROGRESSIF"
        )


def test_selection_dans_registre_versionne():
    ancien = regle(date_fin="2026-06-30")
    nouveau = regle(date_effet="2026-07-01")
    ancien["donnees"] = {"tranches": ancien.pop("tranches")}
    nouveau["donnees"] = {"tranches": nouveau.pop("tranches")}
    assert calculer_bareme_depuis_registre(
        "300", [ancien, nouveau], "2026-06-30", code="TEST_PROGRESSIF"
    )["montant"] == "30.00"
    assert calculer_bareme_depuis_registre(
        "300", [ancien, nouveau], "2026-07-01", code="TEST_PROGRESSIF"
    )["montant"] == "30.00"


def test_selection_refuse_chevauchement():
    with pytest.raises(BaremeIndisponible):
        calculer_bareme_depuis_registre(
            "100", [regle(), regle()], "2026-01-01", code="TEST_PROGRESSIF"
        )


def test_selection_refuse_absence():
    with pytest.raises(BaremeIndisponible):
        calculer_bareme_depuis_registre(
            "100", [], "2026-01-01", code="TEST_PROGRESSIF"
        )


def test_selection_ignore_projet_non_active():
    assert calculer_bareme_depuis_registre(
        "201", [regle(statut_juridique="projet"), regle()],
        "2026-01-01", code="TEST_PROGRESSIF"
    )["montant"] == "10.20"


def test_selection_refuse_type_incompatible():
    with pytest.raises(BaremeIndisponible):
        calculer_bareme_depuis_registre(
            "201", [regle(type_regle="echeance")],
            "2026-01-01", code="TEST_PROGRESSIF"
        )
