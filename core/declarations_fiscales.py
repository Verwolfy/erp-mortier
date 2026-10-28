"""Brouillon interne de TVA, pas un formulaire officiel ni une télédéclaration.

Les faits générateurs et les montants de TVA sont fournis par des pièces
classées et validées ; leur éligibilité fiscale est vérifiée en amont.
"""
from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from typing import Any, Iterable, Mapping


class DeclarationNonDisponible(ValueError):
    """Sources, dates, classement ou montants non vérifiables."""


def _date(value: Any) -> date:
    if isinstance(value, date) and not isinstance(value, datetime):
        return value
    if isinstance(value, str):
        try:
            dt = date.fromisoformat(value)
        except ValueError as exc:
            raise DeclarationNonDisponible("Date incorrecte") from exc
        if dt.isoformat() == value:
            return dt
    raise DeclarationNonDisponible("Date ISO requise")


def _montant(value: Any) -> Decimal:
    if isinstance(value, bool) or not isinstance(value, (str, int, Decimal)):
        raise DeclarationNonDisponible("Montant exact requis")
    try:
        number = Decimal(str(value))
    except (InvalidOperation, ValueError) as exc:
        raise DeclarationNonDisponible("Montant invalide") from exc
    if (not number.is_finite() or number < 0 or number >= Decimal("1e15")
            or number != number.quantize(Decimal("0.01"))):
        raise DeclarationNonDisponible("Montant hors limites ou précision interdite")
    return number


def preparer_tva_periodique(
    *,
    annee: int,
    mois: int,
    pieces: Iterable[Mapping[str, Any]],
    credit_anterieur: str | int | Decimal = "0",
) -> dict[str, Any]:
    """Synthèse de TVA collectée/déductible des pièces validées uniquement.

    Les périodes et droits à déduction ont été déterminés au niveau des pièces.
    Ne déduit jamais une TVA simplement parce qu'un montant figure sur une
    facture fournisseur : exige la preuve d'éligibilité correspondante.
    """
    if isinstance(annee, bool) or not isinstance(annee, int) or not 2000 <= annee <= 2100:
        raise DeclarationNonDisponible("Année invalide")
    if isinstance(mois, bool) or not isinstance(mois, int) or not 1 <= mois <= 12:
        raise DeclarationNonDisponible("Mois invalide")
    credit = _montant(credit_anterieur)
    totals = {"COLLECTEE": Decimal(0), "DEDUCTIBLE": Decimal(0)}
    vus = set()
    nombres = {"COLLECTEE": 0, "DEDUCTIBLE": 0}
    if not isinstance(pieces, (list, tuple)):
        raise DeclarationNonDisponible("Liste des pièces obligatoire")
    for piece in pieces:
        if not isinstance(piece, Mapping):
            raise DeclarationNonDisponible("Pièce non structurée")
        reference = piece.get("piece_id")
        if not isinstance(reference, str) or not reference.strip() or len(reference) > 200:
            raise DeclarationNonDisponible("Référence de pièce obligatoire")
        if reference in vus:
            raise DeclarationNonDisponible("Pièce dupliquée")
        vus.add(reference)
        if piece.get("statut") != "VALIDE":
            raise DeclarationNonDisponible("Pièce non validée")
        nature = piece.get("nature_tva")
        if not isinstance(nature, str) or nature not in totals:
            raise DeclarationNonDisponible("Nature fiscale non prise en charge")
        if (piece.get("classification_verifiee") is not True
                or not isinstance(piece.get("source_juridique"), str)
                or not piece["source_juridique"].strip()):
            raise DeclarationNonDisponible("Classification fiscale non vérifiée")
        date_tva = _date(piece.get("date_fait_generateur"))
        if (date_tva.year, date_tva.month) != (annee, mois):
            raise DeclarationNonDisponible("Pièce hors période du fait générateur")
        montant = _montant(piece.get("montant_tva"))
        totals[nature] += montant
        nombres[nature] += 1
    net = totals["COLLECTEE"] - totals["DEDUCTIBLE"] - credit
    return {
        "annee": annee, "mois": mois, "statut": "BROUILLON_INTERNE_NON_DEPOSABLE",
        "tva_collectee": format(totals["COLLECTEE"], "f"),
        "tva_deductible": format(totals["DEDUCTIBLE"], "f"),
        "credit_anterieur": format(credit, "f"),
        "tva_a_payer": format(max(net, Decimal(0)), "f"),
        "credit_a_reporter": format(max(-net, Decimal(0)), "f"),
        "nombre_pieces": nombres,
        "avertissement": "Aucun formulaire officiel ni dépôt automatique",
    }
