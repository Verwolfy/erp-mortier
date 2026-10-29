"""Diagnostic pur d'écart entre arrondi TVA par ligne et arrondi global.

Le calcul global est une HYPOTHÈSE COMPARATIVE, pas une méthode homologuée.
Ne prétend pas reproduire la RPC erp_sale_transaction ni le droit algérien.
L'outil refuse les taux multiples et les simulations incohérentes.
"""
from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP
from typing import Any, Mapping

from core.fiscalite_facturation import FiscaliteNonDisponible, _decimal

_CENT = Decimal("0.01")


def comparer_arrondis_tva(simulation: Mapping[str, Any]) -> dict[str, Any]:
    """Compare deux conventions d'arrondi sans autoriser la facturation."""
    if (
        not isinstance(simulation, Mapping)
        or simulation.get("simulation_sans_ecriture") is not True
        or simulation.get("autorise_activation_facturation") is not False
    ):
        raise FiscaliteNonDisponible("Simulation de référence non sécurisée")
    lignes = simulation.get("lignes")
    if not isinstance(lignes, list) or not 1 <= len(lignes) <= 500:
        raise FiscaliteNonDisponible("Lignes simulées invalides")

    taux_uniques: set[Decimal] = set()
    total_ht = Decimal("0.00")
    tva_lignes = Decimal("0.00")
    for ligne in lignes:
        if not isinstance(ligne, Mapping):
            raise FiscaliteNonDisponible("Détail de simulation non structuré")
        ht = _decimal(ligne.get("montant_ht"), "Montant HT ligne")
        tva = _decimal(ligne.get("montant_tva"), "TVA ligne")
        taux = _decimal(ligne.get("taux_tva"), "Taux TVA ligne")
        if (ht < 0 or tva < 0 or not Decimal(0) <= taux <= Decimal(1)
                or ht != ht.quantize(_CENT) or tva != tva.quantize(_CENT)):
            raise FiscaliteNonDisponible("Ligne fiscale financièrement invalide")
        if tva != (ht * taux).quantize(_CENT, rounding=ROUND_HALF_UP):
            raise FiscaliteNonDisponible("TVA ligne incohérente")
        total_ht += ht
        tva_lignes += tva
        taux_uniques.add(taux)

    if (
        len(taux_uniques) != 1
        or total_ht != _decimal(simulation.get("montant_ht"), "Montant HT total")
        or tva_lignes != _decimal(simulation.get("montant_tva"), "TVA totale")
        or total_ht + tva_lignes != _decimal(
            simulation.get("montant_ttc"), "Montant TTC total"
        )
    ):
        raise FiscaliteNonDisponible("Taux multiples ou totaux de simulation incohérents")

    taux = next(iter(taux_uniques))
    tva_globale = (total_ht * taux).quantize(_CENT, rounding=ROUND_HALF_UP)
    ecart = tva_lignes - tva_globale
    return {
        "montant_ht": total_ht,
        "taux_comparatif": taux,
        "tva_arrondie_par_ligne": tva_lignes,
        "tva_arrondie_globalement": tva_globale,
        "ecart": ecart,
        "statut": "ECART" if ecart else "CONCORDANT",
        "conventions_non_homologuees": True,
        "autorise_activation_facturation": False,
    }
