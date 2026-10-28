"""Calculateur de timbre de quittance par classe de montant et tranches entières.

Ce moteur reçoit une règle vérifiée, datée et sourcée. Il ne comporte aucun
tarif légal par défaut et ne doit pas être appelé depuis le brouillon facture.
Son événement est une quittance pour un paiement effectivement constaté.
"""
from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal, InvalidOperation, ROUND_CEILING
from typing import Any, Iterable, Mapping


class TimbreNonDisponible(ValueError):
    """Classe de quittance, assiette ou règle fiscale non vérifiable."""


def _decimal(value: Any, champ: str) -> Decimal:
    if isinstance(value, bool) or not isinstance(value, (str, int, Decimal)):
        raise TimbreNonDisponible(f"{champ} : nombre décimal exact requis")
    try:
        num = Decimal(str(value))
    except (InvalidOperation, ValueError) as exc:
        raise TimbreNonDisponible(f"{champ} : nombre invalide") from exc
    if not num.is_finite() or num < 0 or num >= Decimal("1e15"):
        raise TimbreNonDisponible(f"{champ} : montant hors limites")
    return num


def _date(value: Any, champ: str) -> date:
    if isinstance(value, date) and not isinstance(value, datetime):
        return value
    if isinstance(value, str):
        try:
            parsed = date.fromisoformat(value)
        except ValueError as exc:
            raise TimbreNonDisponible(f"{champ} : date invalide") from exc
        if parsed.isoformat() == value:
            return parsed
    raise TimbreNonDisponible(f"{champ} : date ISO requise")


def _regle_applicable(regles: Iterable[Mapping[str, Any]], instant: date) -> Mapping[str, Any]:
    candidates = []
    for rule in regles:
        if not isinstance(rule, Mapping):
            raise TimbreNonDisponible("Enregistrement de barème mal formé")
        if rule.get("code") != "TIMBRE_QUITTANCE_ESPECES_BAREME":
            continue
        if rule.get("type_regle") != "calcul":
            raise TimbreNonDisponible("Type de règle de quittance incorrect")
        if (rule.get("statut_juridique") != "en_vigueur"
                or rule.get("niveau_confiance") != "CONFIRMEE"):
            continue
        if not isinstance(rule.get("source"), str) or not rule["source"].strip():
            raise TimbreNonDisponible("Source juridique absente")
        start = _date(rule.get("date_effet"), "date_effet")
        end = (_date(rule.get("date_fin"), "date_fin")
               if rule.get("date_fin") is not None else None)
        _date(rule.get("date_verification"), "date_verification")
        if end is not None and end < start:
            raise TimbreNonDisponible("Dates du barème incohérentes")
        if start <= instant and (end is None or instant <= end):
            candidates.append(rule)
    if len(candidates) != 1:
        raise TimbreNonDisponible(
            f"{len(candidates)} barème(s) applicable(s) ; calcul refusé"
        )
    return candidates[0]


def calculer_timbre_quittance(
    montant_regle: str | int | Decimal,
    date_paiement: date | str,
    moyen_paiement: str,
    regles: Iterable[Mapping[str, Any]],
) -> dict[str, Any]:
    """Calcule un timbre par classe de montant, sans progressivité marginale.

    Chaque classe fixe un tarif pour l'ensemble des tranches de l'assiette
    encaissée. Une tranche incomplète compte pour une tranche complète.
    L'assiette est le montant du règlement TTC réellement encaissé, pas une
    facture à crédit. Les exceptions propres aux quittances doivent être
    vérifiées en amont. Seuls ESPECES et ELECTRONIQUE sont traités.
    """
    if moyen_paiement not in ("ESPECES", "ELECTRONIQUE"):
        raise TimbreNonDisponible("Moyen de règlement non couvert")
    instant = _date(date_paiement, "date_paiement")
    montant = _decimal(montant_regle, "montant_regle")
    rule = _regle_applicable(regles, instant)
    cfg = rule.get("donnees")
    if not isinstance(cfg, Mapping):
        raise TimbreNonDisponible("Configuration de timbre absente")
    unite = _decimal(cfg.get("unite_tranche"), "unite_tranche")
    franchise = _decimal(cfg.get("montant_exonere_jusqua"), "franchise")
    minimum = _decimal(cfg.get("minimum_perception"), "minimum")
    if unite <= 0 or unite > Decimal("1e9"):
        raise TimbreNonDisponible("Unité de tranche invalide")
    if minimum != minimum.quantize(Decimal("0.01")):
        raise TimbreNonDisponible("Minimum : deux décimales maximum")
    bareme = cfg.get("tarifs")
    if not isinstance(bareme, list) or not bareme:
        raise TimbreNonDisponible("Classes de tarifs absentes")
    tarifs = []
    borne_precedente = franchise
    for index, part in enumerate(bareme):
        if not isinstance(part, Mapping):
            raise TimbreNonDisponible("Classe de tarif invalide")
        borne = (_decimal(part["jusqua"], "jusqua")
                 if part.get("jusqua") is not None else None)
        taux = _decimal(part.get("tarif_par_tranche"), "tarif_par_tranche")
        if taux != taux.quantize(Decimal("0.01")):
            raise TimbreNonDisponible("Tarif : deux décimales maximum")
        if (borne is None and index != len(bareme) - 1
                or borne is not None and borne <= borne_precedente
                or index == len(bareme) - 1 and borne is not None):
            raise TimbreNonDisponible("Limites des classes invalides")
        if taux <= 0:
            raise TimbreNonDisponible("Tarif par tranche non positif")
        tarifs.append((borne, taux))
        if borne is not None:
            borne_precedente = borne

    if moyen_paiement == "ELECTRONIQUE":
        if cfg.get("dispense_paiement_electronique") is not True:
            raise TimbreNonDisponible("Dispense électronique non confirmée")
        taxe = Decimal("0.00")
        tranches = 0
        tarif = Decimal(0)
    elif montant <= franchise:
        taxe = Decimal("0.00")
        tranches = 0
        tarif = Decimal(0)
    else:
        taux = next((val for bound, val in tarifs if bound is None or montant <= bound), None)
        if taux is None:
            raise TimbreNonDisponible("Classe de règlement manquante")
        try:
            tranches = int((montant / unite).to_integral_value(rounding=ROUND_CEILING))
            taxe = max(Decimal(tranches) * taux, minimum).quantize(Decimal("0.01"))
        except (InvalidOperation, OverflowError) as exc:
            raise TimbreNonDisponible("Calcul du timbre impossible") from exc
        tarif = taux
    if taxe >= Decimal("1e15"):
        raise TimbreNonDisponible("Droit de timbre au-delà de la limite")
    return {
        "code": rule["code"],
        "date_paiement": instant.isoformat(),
        "montant_regle": montant,
        "moyen_paiement": moyen_paiement,
        "nombre_tranches": tranches,
        "tarif_par_tranche": tarif,
        "montant_timbre": taxe,
        "source": rule["source"],
        "date_effet": _date(rule["date_effet"], "date_effet").isoformat(),
        "date_verification": _date(rule["date_verification"], "date_verification").isoformat(),
        "statut": "SIMULATION_NON_VALIDEE",
    }
