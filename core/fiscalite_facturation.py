"""Calcul de TVA et de timbre par paramètres réglementaires datés.

Pur et sans IO : aucun taux légal ni date réglementaire n'est codé en dur.
Le moteur ne détermine pas l'assujettissement/exonération d'un article.
"""
from __future__ import annotations

from datetime import date
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from typing import Any, Iterable, Mapping


class FiscaliteNonDisponible(ValueError):
    """La source réglementaire est insuffisante : calcul interdit."""


def _decimal(value: Any, name: str) -> Decimal:
    if isinstance(value, bool) or not isinstance(value, (str, int, Decimal)):
        raise FiscaliteNonDisponible(f"{name}: décimal exact requis")
    try:
        number = Decimal(str(value))
    except (InvalidOperation, ValueError) as exc:
        raise FiscaliteNonDisponible(f"{name}: invalide") from exc
    if not number.is_finite():
        raise FiscaliteNonDisponible(f"{name}: non fini")
    return number


def _date(value: Any) -> date:
    if isinstance(value, date) and not hasattr(value, "hour"):
        return value
    if isinstance(value, str):
        try:
            parsed = date.fromisoformat(value)
        except ValueError as exc:
            raise FiscaliteNonDisponible("Date fiscale invalide") from exc
        if parsed.isoformat() == value:
            return parsed
    raise FiscaliteNonDisponible("Date fiscale ISO requise")


def _parametre(lignes: list[Mapping[str, Any]], code: str, instant: date, unite: str) -> tuple[Decimal, dict[str, str]]:
    candidats = []
    for ligne in lignes:
        if not isinstance(ligne, Mapping):
            raise FiscaliteNonDisponible("Ligne réglementaire non structurée")
        if ligne.get("code") != code:
            continue
        if ligne.get("statut_juridique") != "en_vigueur" or ligne.get("niveau_confiance") != "CONFIRMEE":
            continue
        if ligne.get("unite") != unite:
            raise FiscaliteNonDisponible(f"{code}: unité incompatible")
        source = ligne.get("source")
        if not isinstance(source, str) or not source.strip():
            raise FiscaliteNonDisponible(f"{code}: source manquante")
        debut = _date(ligne.get("date_effet"))
        fin = _date(ligne["date_fin"]) if ligne.get("date_fin") is not None else None
        verifie = _date(ligne.get("date_verification"))
        if fin is not None and fin < debut:
            raise FiscaliteNonDisponible(f"{code}: intervalle invalide")
        if debut <= instant and (fin is None or instant <= fin):
            candidats.append((
                _decimal(ligne.get("valeur"), code),
                {"code": code, "date_effet": debut.isoformat(),
                 "date_verification": verifie.isoformat(), "source": source.strip()},
            ))
    if len(candidats) != 1:
        raise FiscaliteNonDisponible(f"{code}: {len(candidats)} valeur(s) confirmée(s) applicable(s)")
    return candidats[0]


def calculer_taxes_facture(
    montant_ht: str | int | Decimal,
    paiement_especes: bool,
    date_facture: date | str,
    parametres: Iterable[Mapping[str, Any]],
) -> dict[str, Any]:
    """Calcule TVA et timbre d'une facture standard assujettie.

    Les exemptions, taux réduits et ventilations par ligne nécessitent un moteur
    dédié : il est interdit de l'utiliser pour ces cas sans classification fiscale.
    Paramètre attendu : TVA_VENTE_TAUX uniquement, pour la simulation non
    fiscale d'une vente standard explicitement classée en amont.
    Pour une vente payée en espèces, l'ancien timbre de facture est
    incompatible avec le calcul légal sur quittance : appel refusé.
    """
    if not isinstance(paiement_especes, bool):
        raise FiscaliteNonDisponible("Indicateur espèces invalide")
    if paiement_especes:
        raise FiscaliteNonDisponible(
            "Ancien calcul de timbre sur facture interdit : "
            "le droit doit être déterminé sur une quittance de règlement "
            "avec son régime, son moyen de paiement et sa règle vérifiée"
        )
    instant = _date(date_facture)
    ht = _decimal(montant_ht, "Montant HT")
    if ht < 0 or ht >= Decimal("1e15"):
        raise FiscaliteNonDisponible("Montant HT non autorisé")
    lignes = list(parametres)
    tva_taux, trace_tva = _parametre(lignes, "TVA_VENTE_TAUX", instant, "fraction")
    if not Decimal(0) <= tva_taux <= Decimal(1):
        raise FiscaliteNonDisponible("Taux TVA invalide")
    arrondi = Decimal("0.01")
    tva = (ht * tva_taux).quantize(arrondi, rounding=ROUND_HALF_UP)
    net_avant_timbre = ht + tva
    # Le timbre ne peut être simulé sur une facture ; seul le règlement
    # constaté et juridiquement classifié pourra produire une quittance.
    timbre = Decimal("0.00")
    traces = [trace_tva]
    return {
        "montant_tva": tva,
        "montant_timbre": timbre,
        "montant_ttc": (net_avant_timbre + timbre).quantize(arrondi, rounding=ROUND_HALF_UP),
        "taux_tva": tva_taux,
        "date_facture": instant.isoformat(),
        "justificatifs": traces,
    }
