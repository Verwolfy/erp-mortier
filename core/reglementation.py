"""Moteur réglementaire fail-closed pour l'ERP algérien (lot C, socle).

Ne contient aucun taux, plafond, barème ou date d'effet juridique.
Les règles doivent avoir été auditées, vérifiées et datées avant utilisation.
Ce module ne lit ni n'écrit Supabase et ne publie aucun document fiscal.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from typing import Any, Iterable, Mapping

from core.arrondis import ArrondiNonDisponible, arrondir_multiple


class RegleIndisponible(ValueError):
    """Aucune valeur juridique active vérifiée, ou plusieurs valeurs concurrentes."""


@dataclass(frozen=True)
class ParametreApplicable:
    code: str
    valeur: Decimal
    date_effet: date
    date_fin: date | None
    source: str
    date_verification: date


def _date(value: Any, name: str) -> date:
    if isinstance(value, date) and not isinstance(value, datetime):
        return value
    if isinstance(value, str):
        try:
            result = date.fromisoformat(value)
        except ValueError as exc:
            raise RegleIndisponible(f"{name} invalide") from exc
        if result.isoformat() == value:
            return result
    raise RegleIndisponible(f"{name} doit être une date ISO")


def _decimal(value: Any, name: str) -> Decimal:
    if isinstance(value, bool) or not isinstance(value, (str, int, Decimal)):
        raise RegleIndisponible(f"{name} doit être un nombre décimal exact")
    try:
        number = Decimal(str(value))
    except (ValueError, InvalidOperation) as exc:
        raise RegleIndisponible(f"{name} invalide") from exc
    if not number.is_finite():
        raise RegleIndisponible(f"{name} non fini")
    return number


def chercher_parametre(
    lignes: Iterable[Mapping[str, Any]], code: str, date_operation: date | str,
    *, unite_attendue: str | None = None,
) -> ParametreApplicable:
    """Recherche la valeur confirmée en vigueur à la date réelle de l'opération.

    Champs requis : code, valeur, date_effet, date_fin, statut_juridique,
    niveau_confiance, source, date_verification.
    Les règles projet, a_confirmer, abrogée ou sans source sont bloquées.
    L'existence de plusieurs règles actives déclenche un arrêt sans arbitrage tacite.
    Lorsqu'une unité est demandée, la règle active doit déclarer exactement
    cette unité ; pas de conversion implicite entre pourcentage et fraction.
    """
    if not isinstance(code, str) or not code.strip():
        raise RegleIndisponible("Code réglementaire absent")
    instant = _date(date_operation, "date_operation")
    candidates: list[ParametreApplicable] = []
    for row in lignes:
        if not isinstance(row, Mapping):
            raise RegleIndisponible("Enregistrement réglementaire invalide")
        if row.get("code") != code:
            continue
        if row.get("statut_juridique") != "en_vigueur" or row.get("niveau_confiance") != "CONFIRMEE":
            continue
        source = row.get("source")
        if not isinstance(source, str) or not source.strip():
            raise RegleIndisponible(f"{code}: source obligatoire")
        start = _date(row.get("date_effet"), "date_effet")
        end = _date(row["date_fin"], "date_fin") if row.get("date_fin") is not None else None
        verified = _date(row.get("date_verification"), "date_verification")
        if end is not None and end < start:
            raise RegleIndisponible(f"{code}: intervalle de validité invalide")
        if start <= instant and (end is None or instant <= end):
            if unite_attendue is not None and row.get("unite") != unite_attendue:
                raise RegleIndisponible(
                    f"{code}: unité invalide (attendu : {unite_attendue})"
                )
            candidates.append(ParametreApplicable(
                code, _decimal(row.get("valeur"), "valeur"), start, end,
                source.strip(), verified,
            ))
    if len(candidates) != 1:
        raise RegleIndisponible(
            f"{code}: {len(candidates)} règle(s) confirmée(s) applicable(s) ; calcul bloqué"
        )
    return candidates[0]


def calculer_pourcentage(
    assiette: str | int | Decimal,
    lignes: Iterable[Mapping[str, Any]],
    code_taux: str,
    date_operation: date | str,
    *,
    unite_arrondi: str | Decimal = "0.01",
) -> dict[str, str]:
    """Calcul générique traçable. Ni formule IRG ni assiette fiscale implicite.

    La valeur du taux est une fraction exacte (0.05 = cinq pour cent),
    fournie exclusivement par le registre vérifié. L'appelant décide de l'assiette.
    """
    base = _decimal(assiette, "assiette")
    quantum = _decimal(unite_arrondi, "unite_arrondi")
    if base < 0 or quantum <= 0:
        raise RegleIndisponible("Assiette et arrondi invalides")
    param = chercher_parametre(lignes, code_taux, date_operation)
    if not Decimal("0") <= param.valeur <= Decimal("1"):
        raise RegleIndisponible("Taux hors de l'intervalle [0,1]")
    try:
        montant = arrondir_multiple(base * param.valeur, quantum)
    except ArrondiNonDisponible as exc:
        raise RegleIndisponible("Unité d'arrondi non prise en charge") from exc
    return {
        "code": code_taux,
        "assiette": format(base, "f"),
        "taux": format(param.valeur, "f"),
        "montant": format(montant, "f"),
        "date_operation": _date(date_operation, "date_operation").isoformat(),
        "date_effet": param.date_effet.isoformat(),
        "source": param.source,
        "date_verification": param.date_verification.isoformat(),
    }
