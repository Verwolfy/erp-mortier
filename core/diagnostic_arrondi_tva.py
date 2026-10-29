"""Diagnostic d'écart d'arrondis TVA par ligne et par groupe fiscal.

Chaque groupe est identifié par catégorie, code de paramètre et taux.
Le calcul de comparaison reste une HYPOTHÈSE NON HOMOLOGUÉE ; il ne
reproduit pas la RPC historique ni une règle légale algérienne.
Aucune donnée n'est écrite, aucune facturation n'est autorisée.
"""
from __future__ import annotations

from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from typing import Any, Mapping

from core.fiscalite_facturation import FiscaliteNonDisponible, _decimal

_CENT = Decimal("0.01")
_LIMITE = Decimal("1e15")
_CODES = {"NORMAL": "TVA_TAUX_NORMAL", "REDUIT": "TVA_TAUX_REDUIT"}


def _monnaie_exacte(value: Any, champ: str) -> Decimal:
    nombre = _decimal(value, champ)
    if nombre < 0 or nombre >= _LIMITE:
        raise FiscaliteNonDisponible(f"{champ}: hors limites")
    try:
        if nombre != nombre.quantize(_CENT):
            raise FiscaliteNonDisponible(f"{champ}: centimes exacts requis")
    except InvalidOperation as exc:
        raise FiscaliteNonDisponible(f"{champ}: précision non autorisée") from exc
    return nombre


def comparer_arrondis_tva(simulation: Mapping[str, Any]) -> dict[str, Any]:
    """Compare l'arrondi par ligne à l'arrondi par catégorie/code/taux."""
    if (
        not isinstance(simulation, Mapping)
        or simulation.get("simulation_sans_ecriture") is not True
        or simulation.get("autorise_activation_facturation") is not False
    ):
        raise FiscaliteNonDisponible("Simulation de référence non sécurisée")
    lignes = simulation.get("lignes")
    if not isinstance(lignes, list) or not 1 <= len(lignes) <= 500:
        raise FiscaliteNonDisponible("Lignes simulées invalides")
    if _monnaie_exacte(simulation.get("montant_timbre"), "Timbre") != 0:
        raise FiscaliteNonDisponible("Timbre non pris en charge sur facture")

    groupes: dict[tuple[str, str, Decimal], dict[str, Any]] = {}
    total_ht = Decimal("0.00")
    tva_lignes = Decimal("0.00")
    for ligne in lignes:
        if not isinstance(ligne, Mapping):
            raise FiscaliteNonDisponible("Détail de simulation non structuré")
        sku = ligne.get("sku_id")
        if not isinstance(sku, str) or not sku.strip():
            raise FiscaliteNonDisponible("SKU fiscal manquant")
        ht = _monnaie_exacte(ligne.get("montant_ht"), "Montant HT ligne")
        tva = _monnaie_exacte(ligne.get("montant_tva"), "TVA ligne")
        ttc = _monnaie_exacte(ligne.get("montant_ttc"), "Montant TTC ligne")
        taux = _decimal(ligne.get("taux_tva"), "Taux TVA ligne")
        categorie = ligne.get("categorie_tva")
        justificatif = ligne.get("justificatif_taux")
        if (
            categorie not in _CODES
            or not isinstance(justificatif, Mapping)
            or justificatif.get("code") != _CODES[categorie]
            or not Decimal("0") <= taux <= Decimal("1")
        ):
            raise FiscaliteNonDisponible("Groupe fiscal de ligne incohérent")
        try:
            attendu = (ht * taux).quantize(_CENT, rounding=ROUND_HALF_UP)
        except InvalidOperation as exc:
            raise FiscaliteNonDisponible("Calcul TVA ligne hors précision") from exc
        if tva != attendu or ttc != ht + tva:
            raise FiscaliteNonDisponible("TVA ligne incohérente")
        cle = (categorie, justificatif["code"], taux)
        if cle not in groupes:
            groupes[cle] = {
                "categorie_tva": categorie,
                "code_parametre": justificatif["code"],
                "taux_tva": taux,
                "nombre_lignes": 0,
                "montant_ht": Decimal("0.00"),
                "tva_arrondie_par_ligne": Decimal("0.00"),
            }
        groupe = groupes[cle]
        groupe["nombre_lignes"] += 1
        groupe["montant_ht"] += ht
        groupe["tva_arrondie_par_ligne"] += tva
        total_ht += ht
        tva_lignes += tva
        if total_ht + tva_lignes >= _LIMITE:
            raise FiscaliteNonDisponible("Total de facture hors limites")

    if (
        total_ht != _monnaie_exacte(simulation.get("montant_ht"), "Montant HT total")
        or tva_lignes != _monnaie_exacte(simulation.get("montant_tva"), "TVA totale")
        or total_ht + tva_lignes != _monnaie_exacte(
            simulation.get("montant_ttc"), "Montant TTC total"
        )
    ):
        raise FiscaliteNonDisponible("Totaux de simulation incohérents")

    details: list[dict[str, Any]] = []
    tva_par_groupes = Decimal("0.00")
    for cle in sorted(groupes):
        groupe = groupes[cle]
        try:
            global_groupe = (
                groupe["montant_ht"] * groupe["taux_tva"]
            ).quantize(_CENT, rounding=ROUND_HALF_UP)
        except InvalidOperation as exc:
            raise FiscaliteNonDisponible("Calcul groupe hors précision") from exc
        groupe["tva_arrondie_par_groupe"] = global_groupe
        groupe["ecart"] = groupe["tva_arrondie_par_ligne"] - global_groupe
        tva_par_groupes += global_groupe
        details.append(groupe)

    ecart = tva_lignes - tva_par_groupes
    return {
        "montant_ht": total_ht,
        # Ancien champ conservé pour les simulations mono-groupe uniquement.
        "taux_comparatif": details[0]["taux_tva"] if len(details) == 1 else None,
        "nombre_groupes": len(details),
        "groupes_tva": details,
        "tva_arrondie_par_ligne": tva_lignes,
        # Pour plusieurs taux, cette somme vient des groupes fiscaux,
        # et non d'un taux moyen ou d'une assiette universelle.
        "tva_arrondie_globalement": tva_par_groupes,
        "ecart": ecart,
        "statut": "ECART" if ecart else "CONCORDANT",
        "conventions_non_homologuees": True,
        "autorise_activation_facturation": False,
    }
