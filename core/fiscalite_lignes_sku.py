"""Simulation TVA par SKU classifié, sans IO ni valeur fiscale codée en dur.

Ce calcul isolé n'est PAS branché à la RPC de vente ni à un dépôt légal.
Seules les classes NORMAL et REDUIT justifiées et VALIDEE sont supportées.
Exonérations, hors-champ, avoirs et timbre de quittance exigent une autre
qualification juridique et ne reçoivent jamais un taux implicite.
"""
from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal, InvalidOperation, ROUND_DOWN, ROUND_HALF_UP
from typing import Any, Iterable, Mapping

from core.reglementation import RegleIndisponible, chercher_parametre


class ClassificationFiscaleIndisponible(ValueError):
    """La simulation ne peut pas établir les règles pour chaque SKU."""


_CENT = Decimal("0.01")
_LIMIT = Decimal("1e15")
_CODES = {"NORMAL": "TVA_TAUX_NORMAL", "REDUIT": "TVA_TAUX_REDUIT"}


def _date(value: Any) -> date:
    if isinstance(value, date) and not isinstance(value, datetime):
        return value
    if isinstance(value, str):
        try:
            parsed = date.fromisoformat(value)
        except ValueError as exc:
            raise ClassificationFiscaleIndisponible("Date fiscale invalide") from exc
        if parsed.isoformat() == value:
            return parsed
    raise ClassificationFiscaleIndisponible("Date fiscale ISO requise")


def _money(value: Any, champ: str) -> Decimal:
    if isinstance(value, bool) or not isinstance(value, (str, int, Decimal)):
        raise ClassificationFiscaleIndisponible(f"{champ}: décimal exact requis")
    try:
        d = Decimal(str(value))
    except (InvalidOperation, ValueError) as exc:
        raise ClassificationFiscaleIndisponible(f"{champ}: décimal invalide") from exc
    if not d.is_finite() or not 0 <= d < _LIMIT or d != d.quantize(_CENT):
        raise ClassificationFiscaleIndisponible(f"{champ}: montant hors limites ou non centimé")
    return d.quantize(_CENT)


def _texte(value: Any, champ: str) -> str:
    if not isinstance(value, str) or not value.strip() or len(value.strip()) > 200:
        raise ClassificationFiscaleIndisponible(f"{champ}: justificatif ou code absent")
    return value.strip()


def _classification(
    lignes: list[Mapping[str, Any]], sku_id: str, instant: date
) -> tuple[str, str, str]:
    applicables = []
    for row in lignes:
        if not isinstance(row, Mapping):
            raise ClassificationFiscaleIndisponible("Classification mal structurée")
        if row.get("sku_id") != sku_id:
            continue
        debut = _date(row.get("date_effet"))
        fin = _date(row["date_fin"]) if row.get("date_fin") is not None else None
        if fin is not None and fin < debut:
            raise ClassificationFiscaleIndisponible(f"{sku_id}: dates de classement incohérentes")
        if not (debut <= instant and (fin is None or instant <= fin)):
            continue
        if row.get("statut") != "VALIDEE":
            raise ClassificationFiscaleIndisponible(f"{sku_id}: classification applicable non validée")
        categorie = row.get("categorie_tva")
        if categorie not in _CODES or row.get("code_parametre") != _CODES[categorie]:
            raise ClassificationFiscaleIndisponible(
                f"{sku_id}: exonération, hors-champ ou correspondance TVA non qualifiée"
            )
        source = _texte(row.get("source_juridique"), "Source juridique SKU")
        _texte(row.get("justification"), "Justification SKU")
        _texte(row.get("valide_par"), "Validateur SKU")
        _date(row.get("date_verification"))
        _date(row.get("date_validation"))
        applicables.append((categorie, _CODES[categorie], source))
    if len(applicables) != 1:
        raise ClassificationFiscaleIndisponible(
            f"{sku_id}: {len(applicables)} classification(s) applicable(s), calcul interdit"
        )
    return applicables[0]


def _remises_reparties(montants: list[Decimal], remise: Decimal) -> list[Decimal]:
    """Répartition déterministe en centimes, par plus forts restes, sans flottants."""
    total = sum(montants, Decimal(0))
    if remise > total:
        raise ClassificationFiscaleIndisponible("Remise globale supérieure au HT")
    if not total:
        if remise:
            raise ClassificationFiscaleIndisponible("Remise avec assiette nulle")
        return [Decimal(0) for _ in montants]
    quotas = [remise * value / total for value in montants]
    parts = [q.quantize(_CENT, rounding=ROUND_DOWN) for q in quotas]
    restant = int((remise - sum(parts, Decimal(0))) / _CENT)
    ordre = sorted(range(len(montants)), key=lambda i: (quotas[i] - parts[i], -i), reverse=True)
    for i in ordre[:restant]:
        parts[i] += _CENT
    if any(part > montant for part, montant in zip(parts, montants)):
        raise ClassificationFiscaleIndisponible("Répartition de remise impossible")
    return parts


def simuler_tva_par_sku(
    lignes_facture: Iterable[Mapping[str, Any]],
    classifications_sku: Iterable[Mapping[str, Any]],
    parametres_reglementaires: Iterable[Mapping[str, Any]],
    date_facture: date | str,
    *,
    remise_globale: str | int | Decimal = "0",
    paiement_especes: bool = False,
) -> dict[str, Any]:
    """Simulation autonome de lignes pré-calculées en HT, PAS une facturation légale.

    Chaque ligne fournit sku_id et total_ligne_ht (centimes exacts). Les lignes
    préservent leur TVA propre ; la remise globale est répartie en centimes.
    Les montants n'autorisent aucun float ni hypothèse sur le régime du client.
    """
    if not isinstance(paiement_especes, bool) or paiement_especes:
        raise ClassificationFiscaleIndisponible(
            "Timbre de quittance/non-espèces : calcul sur facture non autorisé"
        )
    instant = _date(date_facture)
    items = list(lignes_facture)
    classes = list(classifications_sku)
    rates = list(parametres_reglementaires)
    if not 1 <= len(items) <= 500 or len(classes) > 5000 or len(rates) > 5000:
        raise ClassificationFiscaleIndisponible("Taille du lot fiscal invalide")
    normalized = []
    for item in items:
        if not isinstance(item, Mapping):
            raise ClassificationFiscaleIndisponible("Ligne de facture invalide")
        sku_id = _texte(item.get("sku_id"), "SKU")
        montant = _money(item.get("total_ligne_ht"), "HT ligne")
        normalized.append((sku_id, montant))
    ht = [n for _, n in normalized]
    discount = _money(remise_globale, "Remise globale")
    parts = _remises_reparties(ht, discount)
    results = []
    total_tva = Decimal("0.00")
    for (sku_id, montant), part in zip(normalized, parts):
        categorie, code, source = _classification(classes, sku_id, instant)
        try:
            regle = chercher_parametre(rates, code, instant, unite_attendue="fraction")
        except RegleIndisponible as exc:
            raise ClassificationFiscaleIndisponible(f"{sku_id}: taux fiscal indisponible") from exc
        if not Decimal(0) <= regle.valeur <= Decimal(1):
            raise ClassificationFiscaleIndisponible(f"{sku_id}: taux TVA hors bornes")
        net = montant - part
        tva = (net * regle.valeur).quantize(_CENT, rounding=ROUND_HALF_UP)
        total_tva += tva
        results.append({
            "sku_id": sku_id, "categorie_tva": categorie, "code_parametre": code,
            "montant_ht": net, "montant_tva": tva, "montant_ttc": net + tva,
            "source_classement": source,
            "source_taux": regle.source,
            "date_effet_taux": regle.date_effet.isoformat(),
        })
    total_ht = sum((row["montant_ht"] for row in results), Decimal("0.00"))
    total_ttc = total_ht + total_tva
    if total_ttc >= _LIMIT:
        raise ClassificationFiscaleIndisponible("Total facture trop élevé")
    return {
        "date_facture": instant.isoformat(), "lignes": results,
        "remise_globale": discount, "montant_ht": total_ht,
        "montant_tva": total_tva, "montant_timbre": Decimal("0.00"),
        "montant_ttc": total_ttc, "statut": "SIMULATION_SANS_ECRITURE",
    }
