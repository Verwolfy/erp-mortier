"""Consolidation d'assiettes de paie à partir d'éléments classés explicitement.

Aucune hypothèse sur les primes, indemnités, avantages ou exclusions légales.
L'outil reste un simulateur : une preuve déclarée dans un dossier n'est pas
une homologation externe de la classification juridique.
"""
from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from typing import Any, Mapping, Sequence


class AssiettesNonDisponibles(ValueError):
    """Éléments, montants ou qualifications insuffisants : calcul refusé."""


def _date(value: Any, label: str) -> date:
    if isinstance(value, date) and not isinstance(value, datetime):
        return value
    if isinstance(value, str):
        try:
            parsed = date.fromisoformat(value)
        except ValueError as exc:
            raise AssiettesNonDisponibles(f"{label} invalide") from exc
        if parsed.isoformat() == value:
            return parsed
    raise AssiettesNonDisponibles(f"{label} doit être ISO")


def _texte(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value.strip() or len(value.strip()) > 200:
        raise AssiettesNonDisponibles(f"{label} absent ou invalide")
    return value.strip()


def _montant(value: Any, label: str) -> Decimal:
    if isinstance(value, bool) or not isinstance(value, (str, int, Decimal)):
        raise AssiettesNonDisponibles(f"{label} décimal exact requis")
    try:
        n = Decimal(str(value))
        if (not n.is_finite() or n <= 0 or n >= Decimal("1e15")
                or n != n.quantize(Decimal("0.01"))):
            raise AssiettesNonDisponibles(f"{label} hors limites")
    except (InvalidOperation, ValueError) as exc:
        raise AssiettesNonDisponibles(f"{label} incorrect") from exc
    return n


def _preuve(value: Any, date_paie: date, label: str) -> str:
    if not isinstance(value, Mapping):
        raise AssiettesNonDisponibles(f"{label} obligatoire")
    if value.get("statut") != "CONFIRMEE":
        raise AssiettesNonDisponibles(f"{label} non confirmée")
    identifiant = _texte(value.get("code"), f"{label} code")
    _texte(value.get("source"), f"{label} source")
    debut = _date(value.get("date_effet"), f"{label} date_effet")
    fin = (_date(value.get("date_fin"), f"{label} date_fin")
           if value.get("date_fin") is not None else None)
    _date(value.get("date_verification"), f"{label} date_verification")
    if (fin is not None and fin < debut
            or date_paie < debut or fin is not None and date_paie > fin):
        raise AssiettesNonDisponibles(f"{label} non applicable à la date de paie")
    return identifiant


def consolider_assiettes_paie(
    elements: Sequence[Mapping[str, Any]],
    date_paie: str | date,
) -> dict[str, Any]:
    """Somme des gains selon deux classements explicites, jamais déduits.

    Tous les mouvements doivent être des gains positifs. Les résultats
    sont des SOMMES DE COMPOSANTES, avant plafonds, cotisations déductibles,
    ajustements fiscaux, exemptions spécifiques et autres déductions.
    Ils ne sont PAS des assiettes légales finales.
    """
    instant = _date(date_paie, "date_paie")
    if (not isinstance(elements, (list, tuple)) or not elements
            or len(elements) > 500 or not all(isinstance(x, Mapping) for x in elements)):
        raise AssiettesNonDisponibles("Liste d'éléments absente ou invalide")

    total = Decimal("0")
    cnas = Decimal("0")
    irg = Decimal("0")
    ids: set[str] = set()
    traces = []
    for item in elements:
        identifier = _texte(item.get("element_id"), "element_id")
        if identifier in ids:
            raise AssiettesNonDisponibles("Élément de rémunération dupliqué")
        ids.add(identifier)
        _texte(item.get("libelle"), "Libellé de rémunération")
        if item.get("type_mouvement") != "GAIN":
            raise AssiettesNonDisponibles("Seuls les gains positifs sont pris en charge")
        amount = _montant(item.get("montant"), "Montant rémunération")
        treatment_cnas = item.get("traitement_cnas")
        treatment_irg = item.get("traitement_irg")
        if treatment_cnas not in ("INCLUS", "EXCLU") or treatment_irg not in ("INCLUS", "EXCLU"):
            raise AssiettesNonDisponibles("Qualification IRG/CNAS obligatoire par élément")
        proof_cnas = _preuve(item.get("preuve_cnas"), instant, "Preuve CNAS")
        proof_irg = _preuve(item.get("preuve_irg"), instant, "Preuve IRG")
        total += amount
        if treatment_cnas == "INCLUS":
            cnas += amount
        if treatment_irg == "INCLUS":
            irg += amount
        if total >= Decimal("1e15"):
            raise AssiettesNonDisponibles("Total des gains trop élevé")
        traces.append({
            "element_id": identifier,
            "montant": format(amount, ".2f"),
            "cnas": treatment_cnas,
            "irg": treatment_irg,
            "preuve_cnas": proof_cnas,
            "preuve_irg": proof_irg,
        })
    if cnas > total or irg > total:
        raise AssiettesNonDisponibles("Assiettes supérieures aux gains")
    return {
        "date_paie": instant.isoformat(),
        "brut_reconstitue": format(total, ".2f"),
        "composantes_cnas_avant_regles": format(cnas, ".2f"),
        "composantes_irg_avant_deductions": format(irg, ".2f"),
        "elements_qualifies": traces,
        "statut": "BASES_SIMULATION_DOCUMENTEES_NON_HOMOLOGUEES",
        "bulletin_officiel_autorise": False,
    }
