"""Simulation du mécanisme IRG traitements/salaires mensuels algériens.

La règle complète (tranches, seuils, coefficients d'abattements, période) est
fournie par un registre juridique versionné. Aucun taux ou seuil par défaut.
Ne délivre ni preuve IRG validée ni fiche de paie légale.
"""
from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from typing import Any, Mapping, Iterable

from core.baremes import (
    BaremeIndisponible, calculer_bareme_progressif,
    choisir_bareme_reglementaire,
)


class IRGNonDisponible(ValueError):
    """Le calcul est interdit quand la règle ou les éléments sont incomplets."""


def _dec(value: Any, champ: str) -> Decimal:
    if isinstance(value, bool) or not isinstance(value, (str, int, Decimal)):
        raise IRGNonDisponible(f"{champ}: nombre décimal exact obligatoire")
    try:
        result = Decimal(str(value))
    except (InvalidOperation, ValueError) as exc:
        raise IRGNonDisponible(f"{champ}: montant invalide") from exc
    if not result.is_finite() or result < 0 or result >= Decimal("1e15"):
        raise IRGNonDisponible(f"{champ}: montant hors limites")
    return result


def _date(value: date | str) -> date:
    if isinstance(value, date) and not isinstance(value, datetime):
        return value
    if isinstance(value, str):
        try:
            parsed = date.fromisoformat(value)
        except ValueError as exc:
            raise IRGNonDisponible("Date IRG invalide") from exc
        if parsed.isoformat() == value:
            return parsed
    raise IRGNonDisponible("Date IRG doit être ISO")


def _field(section: Mapping[str, Any], field: str) -> Decimal:
    if field not in section:
        raise IRGNonDisponible(f"Champ IRG manquant : {field}")
    return _dec(section[field], field)


def _ratio(section: Mapping[str, Any], numerateur: str, denominateur: str) -> Decimal:
    n = _field(section, numerateur)
    d = _field(section, denominateur)
    if d <= 0:
        raise IRGNonDisponible("Dénominateur nul ou négatif")
    return n / d


def simuler_irg_mensuel(
    revenu_imposable: str | int | Decimal,
    date_paie: str | date,
    categorie: str,
    regles: Iterable[Mapping[str, Any]],
    *,
    code: str = "IRG_SALAIRES_MENSUEL",
) -> dict[str, str]:
    """Calcule sur une assiette imposable *déjà déterminée* selon son régime.

    Le tableau annuel est mensualisé en le divisant par 12 ; on applique
    d'abord le dégrèvement commun, puis le second dégrèvement conditionnel.
    Les particularités d'avantages en nature, rappels, occasionnels, IRG non
    périodique, rétroactivité et certificats ne sont PAS traitées.
    """
    if categorie not in ("SALARIE", "HANDICAPE_RETRAITE"):
        raise IRGNonDisponible("Catégorie de salarié non prise en charge")
    date_evt = _date(date_paie)
    base = _dec(revenu_imposable, "revenu_imposable")
    try:
        regle = choisir_bareme_reglementaire(regles, code, date_evt)
    except BaremeIndisponible as exc:
        raise IRGNonDisponible("Règle IRG non disponible ou ambiguë") from exc
    config = regle.get("donnees")
    if not isinstance(config, Mapping):
        raise IRGNonDisponible("Configuration IRG absente")
    if (not isinstance(regle.get("source"), str)
            or not regle["source"].strip()):
        raise IRGNonDisponible("Source juridique IRG manquante")
    _date(regle.get("date_verification"))
    if not isinstance(config.get("tranches"), list) or not config["tranches"]:
        raise IRGNonDisponible("Tranches réglementaires manquantes")
    if _field(config, "periode_an") != 12:
        raise IRGNonDisponible("Calcul IRG réservé aux revenus mensuels")
    plafond_exonere = _field(config, "exoneration")
    pourcent = _field(config, "abattement_pct")
    abat_min = _field(config, "abattement_min")
    abat_max = _field(config, "abattement_max")
    if not (Decimal(0) <= pourcent <= Decimal(1)
            and abat_min <= abat_max and abat_max <= Decimal("1e12")):
        raise IRGNonDisponible("Paramètres d'abattement invalides")
    if base <= plafond_exonere:
        brut = net_apres_abat1 = final = Decimal(0)
        abat1 = Decimal(0)
        abat2 = Decimal(0)
    else:
        try:
            bareme = calculer_bareme_progressif(
                base * Decimal(12), regle, date_evt,
                code=code, unite_arrondi="0.01",
            )
        except BaremeIndisponible as exc:
            raise IRGNonDisponible("Barème progressif incomplet") from exc
        brut = sum((
            Decimal(v["montant_non_arrondi"]) for v in bareme["tranches"]
        ), Decimal(0)) / Decimal(12)
        abat1 = min(max(brut * pourcent, abat_min), abat_max)
        net_apres_abat1 = max(brut - abat1, Decimal(0))
        final = net_apres_abat1
        abat2 = Decimal(0)
        coefficients = config.get("abattements_supplementaires")
        if not isinstance(coefficients, Mapping) or categorie not in coefficients:
            raise IRGNonDisponible("Configuration d'abattement supplémentaire manquante")
        ab = coefficients[categorie]
        if not isinstance(ab, Mapping):
            raise IRGNonDisponible("Coefficient d'abattement invalide")
        seuil = _field(ab, "seuil")
        if base <= seuil:
            # Règle officielle fournie par le registre, jamais implicite.
            facteur = _ratio(ab, "multiplicateur_num", "multiplicateur_den")
            deduction = _ratio(ab, "deduction_num", "deduction_den")
            apres = max(net_apres_abat1 * facteur - deduction, Decimal(0))
            if apres > net_apres_abat1:
                raise IRGNonDisponible("Second abattement non réducteur : paramètres incohérents")
            abat2 = net_apres_abat1 - apres
            final = apres
    centime = Decimal("0.01")
    return {
        "code": code,
        "categorie": categorie,
        "revenu_imposable": format(base, "f"),
        "date_paie": date_evt.isoformat(),
        "impot_brut": format(brut.quantize(centime, rounding=ROUND_HALF_UP), "f"),
        "premier_abattement": format(abat1.quantize(centime, rounding=ROUND_HALF_UP), "f"),
        "apres_premier_abattement": format(net_apres_abat1.quantize(centime, rounding=ROUND_HALF_UP), "f"),
        "second_abattement": format(abat2.quantize(centime, rounding=ROUND_HALF_UP), "f"),
        "irg_simule": format(final.quantize(centime, rounding=ROUND_HALF_UP), "f"),
        "source": str(regle["source"]),
        "date_effet": str(regle["date_effet"]),
        "date_verification": str(regle["date_verification"]),
        "statut": "SIMULATION_NON_VALIDEE",
    }
