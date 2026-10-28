"""Arrondi exact à un multiple décimal déclaré par une règle métier.

Decimal.quantize ne garantit qu'un *nombre de décimales*, pas un multiple de
0.05 ou 5.00. Cette fonction exige un quantum positif et fini. Aucun seuil
réglementaire n'est supposé ici.
"""
from __future__ import annotations

from decimal import Decimal, InvalidOperation, ROUND_HALF_UP


class ArrondiNonDisponible(ValueError):
    """Une unité d'arrondi ou un montant ne peut être représenté exactement."""


def arrondir_multiple(montant: Decimal, quantum: Decimal) -> Decimal:
    if not isinstance(montant, Decimal) or not isinstance(quantum, Decimal):
        raise ArrondiNonDisponible("Montant et quantum Decimal requis")
    if not montant.is_finite() or not quantum.is_finite() or quantum <= 0:
        raise ArrondiNonDisponible("Montant fini et quantum strictement positif requis")
    if montant.copy_abs() >= Decimal("1e15"):
        raise ArrondiNonDisponible("Montant au-delà de la limite de calcul")
    if quantum < Decimal("1e-9") or quantum > Decimal("1e9"):
        raise ArrondiNonDisponible("Quantum hors bornes de précision")
    try:
        unites = (montant / quantum).to_integral_value(rounding=ROUND_HALF_UP)
        resultat = (unites * quantum).quantize(quantum)
    except (InvalidOperation, OverflowError, ZeroDivisionError) as exc:
        raise ArrondiNonDisponible("Arrondi non réalisable") from exc
    if not resultat.is_finite():
        raise ArrondiNonDisponible("Résultat non fini")
    return resultat
