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
        # Une entrée contradictoire non homologuée qui s'applique à la
        # date recherchée ne doit jamais être ignorée silencieusement.
        # Les versions historiques expirées et les versions futures sont
        # ignorées, même si leur validation reste incomplète.
        debut = _date(ligne.get("date_effet"))
        fin = _date(ligne["date_fin"]) if ligne.get("date_fin") is not None else None
        if fin is not None and fin < debut:
            raise FiscaliteNonDisponible(f"{code}: intervalle invalide")
        if not (debut <= instant and (fin is None or instant <= fin)):
            continue
        if (ligne.get("statut_juridique") != "en_vigueur"
                or ligne.get("niveau_confiance") != "CONFIRMEE"):
            raise FiscaliteNonDisponible(
                f"{code}: paramètre applicable non confirmé"
            )
        if ligne.get("unite") != unite:
            raise FiscaliteNonDisponible(f"{code}: unité incompatible")
        source = ligne.get("source")
        if not isinstance(source, str) or not source.strip():
            raise FiscaliteNonDisponible(f"{code}: source manquante")
        verifie = _date(ligne.get("date_verification"))
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


def calculer_tva_lignes_classees(
    lignes: Iterable[Mapping[str, Any]],
    date_facture: date | str,
    parametres: Iterable[Mapping[str, Any]],
    *,
    paiement_especes: bool = False,
) -> dict[str, Any]:
    """Préparation isolée, hors RPC, d'une facture à TVA classée par ligne.

    Chaque ligne doit être explicitement classée et justifiée par le métier.
    Le registre porte seulement les taux de référence datés :
    TVA_TAUX_NORMAL et TVA_TAUX_REDUIT. La présence d'une référence ne
    prouve pas que tel SKU relève de ce taux. Aucune exonération n'est
    déduite et aucune écriture n'est réalisée.
    """
    if not isinstance(paiement_especes, bool) or paiement_especes:
        raise FiscaliteNonDisponible(
            "Timbre espèces : quittance et règle spécifique requises"
        )
    instant = _date(date_facture)
    if isinstance(lignes, (str, bytes, Mapping)):
        raise FiscaliteNonDisponible("Lignes fiscales structurées requises")
    try:
        items = list(lignes)
        registre = list(parametres)
    except (TypeError, ValueError) as exc:
        raise FiscaliteNonDisponible("Lignes ou registre indisponibles") from exc
    if not 1 <= len(items) <= 500:
        raise FiscaliteNonDisponible("Nombre de lignes non autorisé")

    taux: dict[str, tuple[Decimal, dict[str, str]]] = {}
    calculs: list[dict[str, Any]] = []
    total_ht = Decimal("0.00")
    total_tva = Decimal("0.00")
    skus: set[str] = set()
    quantum = Decimal("0.01")
    for item in items:
        if not isinstance(item, Mapping):
            raise FiscaliteNonDisponible("Ligne fiscale invalide")
        sku = item.get("sku_id")
        if not isinstance(sku, str) or not sku.strip() or len(sku) > 200:
            raise FiscaliteNonDisponible("SKU fiscal invalide")
        sku = sku.strip()
        if sku in skus:
            raise FiscaliteNonDisponible("SKU fiscal dupliqué")
        skus.add(sku)
        code = item.get("code_tva")
        if code not in ("TVA_TAUX_NORMAL", "TVA_TAUX_REDUIT"):
            raise FiscaliteNonDisponible(
                "Classification TVA par SKU absente ou non prise en charge"
            )
        if item.get("classification_verifiee") is not True:
            raise FiscaliteNonDisponible("Classification TVA non vérifiée")
        preuve = item.get("source_classification")
        if not isinstance(preuve, str) or not preuve.strip():
            raise FiscaliteNonDisponible("Justificatif de classification manquant")
        montant = _decimal(item.get("montant_ht"), "Montant HT ligne")
        if montant < 0 or montant >= Decimal("1e15"):
            raise FiscaliteNonDisponible("Montant de ligne non autorisé")
        if montant != montant.quantize(quantum):
            raise FiscaliteNonDisponible("Montant HT ligne hors précision monétaire")
        if code not in taux:
            t, trace = _parametre(registre, code, instant, "fraction")
            if not Decimal("0") <= t <= Decimal("1"):
                raise FiscaliteNonDisponible("Taux TVA hors bornes")
            taux[code] = (t, trace)
        t, trace = taux[code]
        taxe = (montant * t).quantize(quantum, rounding=ROUND_HALF_UP)
        total_ht += montant
        total_tva += taxe
        if total_ht + total_tva >= Decimal("1e15"):
            raise FiscaliteNonDisponible("Facture hors plafond technique")
        calculs.append({
            "sku_id": sku,
            "montant_ht": montant,
            "code_tva": code,
            "taux_tva": t,
            "montant_tva": taxe,
            "source_classification": preuve.strip(),
            "justificatif_taux": trace,
        })
    return {
        "date_facture": instant.isoformat(),
        "montant_ht": total_ht,
        "montant_tva": total_tva,
        "montant_timbre": Decimal("0.00"),
        "montant_ttc": total_ht + total_tva,
        "lignes": calculs,
        "statut": "CALCUL_ISOLE_NON_COMPTABILISE",
    }
