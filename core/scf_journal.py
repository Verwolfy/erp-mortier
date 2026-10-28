"""Préparation et contrôle d'écritures SCF, sans écriture dans la base.

Un contrôle local ne remplace pas le plan de comptes algérien officiel, les
règles de comptabilisation ou l'immutabilité imposée dans PostgreSQL.
"""
from __future__ import annotations

from datetime import date
from decimal import Decimal, InvalidOperation
from typing import Any, Iterable, Mapping


class EcritureSCFInvalide(ValueError):
    """Pièce incomplète, période non ouverte ou écriture déséquilibrée."""


def _argent(value: Any, champ: str) -> Decimal:
    if isinstance(value, bool) or not isinstance(value, (int, str, Decimal)):
        raise EcritureSCFInvalide(f"{champ} doit être un décimal exact")
    try:
        montant = Decimal(str(value))
    except (ValueError, InvalidOperation) as exc:
        raise EcritureSCFInvalide(f"{champ} invalide") from exc
    if not montant.is_finite() or montant < 0 or montant >= Decimal("1e15"):
        raise EcritureSCFInvalide(f"{champ} hors limites")
    if montant != montant.quantize(Decimal("0.01")):
        raise EcritureSCFInvalide(f"{champ} : plus de deux décimales")
    return montant


def _date(value: Any, champ: str) -> date:
    if isinstance(value, date) and not hasattr(value, "hour"):
        return value
    if isinstance(value, str):
        try:
            result = date.fromisoformat(value)
        except ValueError as exc:
            raise EcritureSCFInvalide(f"{champ} invalide") from exc
        if result.isoformat() == value:
            return result
    raise EcritureSCFInvalide(f"{champ} doit être ISO")


def _texte(value: Any, champ: str, limite: int = 200) -> str:
    if not isinstance(value, str) or not value.strip() or len(value.strip()) > limite:
        raise EcritureSCFInvalide(f"{champ} obligatoire ou trop long")
    return value.strip()


def preparer_ecriture_scf(
    *,
    date_ecriture: str | date,
    journal: str,
    reference: str,
    libelle: str,
    lignes: Iterable[Mapping[str, Any]],
    periode: Mapping[str, Any],
    comptes: Mapping[str, Mapping[str, Any]],
) -> dict[str, Any]:
    """Valide une écriture DZD avant un futur enregistrement transactionnel."""
    jour = _date(date_ecriture, "date_ecriture")
    if not isinstance(periode, Mapping) or periode.get("statut") != "OUVERTE":
        raise EcritureSCFInvalide("Période comptable non ouverte")
    if not _date(periode.get("date_debut"), "debut") <= jour <= _date(
        periode.get("date_fin"), "fin"
    ):
        raise EcritureSCFInvalide("Écriture hors période")
    if not isinstance(comptes, Mapping):
        raise EcritureSCFInvalide("Plan de comptes manquant")
    nom_journal = _texte(journal, "journal", 20)
    reference = _texte(reference, "reference")
    libelle = _texte(libelle, "libelle", 500)
    if not isinstance(lignes, (list, tuple)) or not 2 <= len(lignes) <= 200:
        raise EcritureSCFInvalide("Une écriture comporte de 2 à 200 lignes")
    total_debit = Decimal(0)
    total_credit = Decimal(0)
    resultats = []
    for numero, ligne in enumerate(lignes, 1):
        if not isinstance(ligne, Mapping):
            raise EcritureSCFInvalide("Ligne non structurée")
        compte = _texte(ligne.get("compte"), "compte", 12)
        if (not compte.isascii() or not compte.isdigit() or not 2 <= len(compte) <= 8
                or compte[0] not in "12345678"):
            raise EcritureSCFInvalide(f"Code de compte non reconnu en ligne {numero}")
        infos = comptes.get(compte)
        if not isinstance(infos, Mapping) or infos.get("actif") is not True or infos.get("mouvementable") is not True:
            raise EcritureSCFInvalide(f"Compte absent, inactif ou non mouvementable : {compte}")
        debit = _argent(ligne.get("debit", "0"), "debit")
        credit = _argent(ligne.get("credit", "0"), "credit")
        if (debit > 0) == (credit > 0):
            raise EcritureSCFInvalide(f"Débit/crédit exclusifs et non nuls en ligne {numero}")
        total_debit += debit
        total_credit += credit
        resultats.append({
            "ligne": numero, "compte": compte, "debit": format(debit, "f"),
            "credit": format(credit, "f"),
        })
    if total_debit != total_credit:
        raise EcritureSCFInvalide("Total débit différent du total crédit")
    return {
        "date_ecriture": jour.isoformat(), "journal": nom_journal,
        "reference": reference, "libelle": libelle, "devise": "DZD",
        "total_debit": format(total_debit, "f"),
        "total_credit": format(total_credit, "f"),
        "lignes": resultats, "statut": "PREPAREE",
    }


def calculer_balance_scf(ecritures_validees: Iterable[Mapping[str, Any]]) -> dict[str, dict[str, str]]:
    """Calcule une balance à partir d'écritures explicitement validées uniquement."""
    soldes: dict[str, list[Decimal]] = {}
    for document in ecritures_validees:
        if not isinstance(document, Mapping) or document.get("statut") != "VALIDEE":
            raise EcritureSCFInvalide("Balance réservée aux écritures validées")
        lignes = document.get("lignes")
        if not isinstance(lignes, (list, tuple)) or len(lignes) < 2:
            raise EcritureSCFInvalide("Écriture incomplète")
        debits = credits = Decimal(0)
        for ligne in lignes:
            if not isinstance(ligne, Mapping):
                raise EcritureSCFInvalide("Ligne invalide")
            compte = _texte(ligne.get("compte"), "compte")
            debit = _argent(ligne.get("debit"), "debit")
            credit = _argent(ligne.get("credit"), "credit")
            if (debit > 0) == (credit > 0):
                raise EcritureSCFInvalide("Débit/crédit invalides")
            somme = soldes.setdefault(compte, [Decimal(0), Decimal(0)])
            somme[0] += debit
            somme[1] += credit
            debits += debit
            credits += credit
        if debits != credits:
            raise EcritureSCFInvalide("Écriture source déséquilibrée")
    return {
        compte: {
            "debit": format(valeurs[0], "f"),
            "credit": format(valeurs[1], "f"),
            "solde": format(valeurs[0] - valeurs[1], "f"),
        } for compte, valeurs in sorted(soldes.items())
    }
