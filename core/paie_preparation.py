"""Préparation contrôlée de paie : montant net et traçabilité, aucun bulletin légal.

Le montant IRG est fourni par un moteur fiscal validé séparément : le barème
brut ne suffit pas (exonérations et deux abattements peuvent s'appliquer).
Les assiettes sociales/fiscales doivent provenir d'éléments de paie classés.
"""
from __future__ import annotations

from datetime import date
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from typing import Any, Iterable, Mapping

from core.reglementation import RegleIndisponible, chercher_parametre


class PaieNonDisponible(ValueError):
    """Montant, assiette, barème ou référence de conformité non vérifiable."""


def _nombre(value: Any, nom: str) -> Decimal:
    if isinstance(value, bool) or not isinstance(value, (int, str, Decimal)):
        raise PaieNonDisponible(f"{nom}: montant exact requis")
    try:
        nombre = Decimal(str(value))
    except (ValueError, InvalidOperation) as exc:
        raise PaieNonDisponible(f"{nom}: montant invalide") from exc
    if not nombre.is_finite() or nombre < 0 or nombre >= Decimal("1e15"):
        raise PaieNonDisponible(f"{nom}: montant hors limites")
    if nombre != nombre.quantize(Decimal("0.01")):
        raise PaieNonDisponible(f"{nom}: deux décimales maximum")
    return nombre


def _texte(value: Any, champ: str, maximum: int = 200) -> str:
    if not isinstance(value, str) or not value.strip() or len(value.strip()) > maximum:
        raise PaieNonDisponible(f"{champ} absent ou trop long")
    return value.strip()


def _date(value: Any) -> date:
    if isinstance(value, date) and not hasattr(value, "hour"):
        return value
    if isinstance(value, str):
        try:
            d = date.fromisoformat(value)
        except ValueError as exc:
            raise PaieNonDisponible("Date de paie invalide") from exc
        if d.isoformat() == value:
            return d
    raise PaieNonDisponible("Date de paie doit être ISO")


def preparer_bulletin_paie(
    *,
    employe_id: str,
    date_paie: date | str,
    salaire_base: str | int | Decimal,
    primes: str | int | Decimal,
    assiette_cnas: str | int | Decimal,
    assiette_irg: str | int | Decimal,
    montant_irg: str | int | Decimal,
    preuve_irg: Mapping[str, Any],
    parametres: Iterable[Mapping[str, Any]],
    autres_retenues: str | int | Decimal = "0",
) -> dict[str, str | dict[str, str]]:
    """Prépare un brouillon seulement, sans l'émettre ni l'écrire en base.

    Les valeurs de cotisations proviennent du registre validé à date d'effet.
    Aucune retenue IRG n'est déduite d'un simple barème annuel : un moteur de
    liquidation IRG attesté devra fournir preuve_irg et montant_irg.
    """
    identite = _texte(employe_id, "employe_id")
    instant = _date(date_paie)
    base = _nombre(salaire_base, "salaire_base")
    bonus = _nombre(primes, "primes")
    brut = base + bonus
    if brut >= Decimal("1e15"):
        raise PaieNonDisponible("Salaire brut total hors limites")
    social = _nombre(assiette_cnas, "assiette_cnas")
    fiscale = _nombre(assiette_irg, "assiette_irg")
    irg = _nombre(montant_irg, "montant_irg")
    autres = _nombre(autres_retenues, "autres_retenues")
    if social > brut or fiscale > brut or irg > fiscale:
        raise PaieNonDisponible("Assiettes ou montant IRG incohérents")
    if (not isinstance(preuve_irg, Mapping)
        or preuve_irg.get("statut") != "CONFIRMEE"
        or not isinstance(preuve_irg.get("source"), str)
        or not preuve_irg.get("source", "").strip()
        or not isinstance(preuve_irg.get("code"), str)
        or not preuve_irg["code"].strip()
        or preuve_irg.get("date_paie") != instant.isoformat()):
        raise PaieNonDisponible("Preuve du calcul IRG obligatoire et datée")
    lignes = list(parametres)
    try:
        s = chercher_parametre(
            lignes, "CNAS_SALARIE_TAUX", instant, unite_attendue="fraction"
        )
        e = chercher_parametre(
            lignes, "CNAS_EMPLOYEUR_TAUX", instant, unite_attendue="fraction"
        )
    except RegleIndisponible as exc:
        raise PaieNonDisponible("Taux sociaux vérifiés manquants") from exc
    if not (Decimal(0) <= s.valeur <= Decimal(1)
            and Decimal(0) <= e.valeur <= Decimal(1)):
        raise PaieNonDisponible("Taux sociaux invalides")
    centime = Decimal("0.01")
    cot_salarie = (social * s.valeur).quantize(centime, rounding=ROUND_HALF_UP)
    cot_employeur = (social * e.valeur).quantize(centime, rounding=ROUND_HALF_UP)
    total_retenues = cot_salarie + irg + autres
    if total_retenues > brut:
        raise PaieNonDisponible("Retenues supérieures au brut : calcul bloqué")
    return {
        "employe_id": identite, "date_paie": instant.isoformat(),
        "statut": "SIMULATION_NON_VALIDEE",
        "salaire_base": format(base, "f"),
        "primes": format(bonus, "f"),
        "brut": format(brut, "f"),
        "assiette_cnas": format(social, "f"),
        "assiette_irg": format(fiscale, "f"),
        "cnas_salarie": format(cot_salarie, "f"),
        "cnas_employeur": format(cot_employeur, "f"),
        "irg": format(irg, "f"),
        "autres_retenues": format(autres, "f"),
        "net_a_payer": format(brut - total_retenues, "f"),
        "cout_employeur": format(brut + cot_employeur, "f"),
        "tracabilite": {
            "cnas_salarie": s.source, "cnas_employeur": e.source,
            "irg": _texte(preuve_irg["source"], "source IRG"),
            "code_irg": preuve_irg["code"],
            "version_cnas_salarie": s.date_effet.isoformat(),
            "version_cnas_employeur": e.date_effet.isoformat(),
        },
    }
