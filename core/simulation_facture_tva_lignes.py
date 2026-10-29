"""Simulation TVA par ligne : lecture pure, aucune facturation transactionnelle.

Hypothèses explicites : vente positive de SKU conditionnés à quantités entières,
remises en montants HT par ligne, aucun avoir, aucun timbre, aucune remise
globale non ventilée. TVA arrondie au centime par ligne (méthode proposée,
PAS encore validée juridiquement/comptablement pour la RPC existante).
Aucune de ces données ne doit être envoyée à erp_sale_transaction.
"""
from __future__ import annotations

from datetime import date
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from typing import Any, Mapping, Sequence

from core.fiscalite_facturation import FiscaliteNonDisponible, _decimal
from core.liaison_tva_sku import taux_par_ligne


_CENT = Decimal("0.01")
_LIMITE = Decimal("1e15")


def _montant(value: Any, champ: str, *, positif: bool = False) -> Decimal:
    nombre = _decimal(value, champ)
    if nombre < 0 or nombre >= _LIMITE or (positif and nombre == 0):
        raise FiscaliteNonDisponible(f"{champ}: valeur hors plage")
    return nombre


def simuler_tva_facture_lignes(
    lignes: Sequence[Mapping[str, Any]],
    date_facture: date,
    classifications: Sequence[Mapping[str, Any]],
    parametres: Sequence[Mapping[str, Any]],
    *,
    remise_globale: str | int | Decimal = "0",
    paiement_especes: bool = False,
) -> dict[str, Any]:
    """Évalue une vente standard par ligne après contrôle strict des SKU."""
    if not isinstance(paiement_especes, bool) or paiement_especes:
        raise FiscaliteNonDisponible("Timbre espèces à traiter sur la quittance")
    if _montant(remise_globale, "Remise globale") != 0:
        raise FiscaliteNonDisponible("Ventilation de remise globale non homologuée")
    if not isinstance(lignes, (list, tuple)) or not 1 <= len(lignes) <= 500:
        raise FiscaliteNonDisponible("Panier de 1 à 500 lignes requis")

    montants = []
    for ligne in lignes:
        if not isinstance(ligne, Mapping):
            raise FiscaliteNonDisponible("Ligne de facture non structurée")
        quantite = _montant(ligne.get("quantite"), "Quantité", positif=True)
        if quantite != quantite.to_integral_value():
            raise FiscaliteNonDisponible("Quantité de SKU conditionné non entière")
        prix = _montant(ligne.get("prix_unitaire"), "Prix unitaire")
        remise = _montant(ligne.get("remise", "0"), "Remise de ligne")
        brut = quantite * prix
        if brut >= _LIMITE or remise > brut:
            raise FiscaliteNonDisponible("Remise supérieure au brut ou plafond dépassé")
        ht = (brut - remise).quantize(_CENT, rounding=ROUND_HALF_UP)
        montants.append(ht)

    taux_lignes = taux_par_ligne(lignes, date_facture, classifications, parametres)
    details: list[dict[str, Any]] = []
    total_ht = Decimal("0.00")
    total_tva = Decimal("0.00")
    for ligne, ht, qualification in zip(lignes, montants, taux_lignes):
        taux = qualification["taux_tva"]
        taxe = (ht * taux).quantize(_CENT, rounding=ROUND_HALF_UP)
        total_ht += ht
        total_tva += taxe
        if total_ht + total_tva >= _LIMITE:
            raise FiscaliteNonDisponible("Total de facture hors plage")
        details.append({
            "sku_id": ligne["sku_id"],
            "montant_ht": ht,
            "taux_tva": taux,
            "montant_tva": taxe,
            "montant_ttc": ht + taxe,
            "categorie_tva": qualification["categorie_tva"],
            "justificatif_taux": qualification["justificatif_taux"],
            "source_classification": qualification["source_classification"],
            "justificatif_classification": qualification["justificatif_classification"],
        })
    return {
        "lignes": details,
        "montant_ht": total_ht,
        "montant_tva": total_tva,
        "montant_ttc": total_ht + total_tva,
        "montant_timbre": Decimal("0.00"),
        "simulation_sans_ecriture": True,
        "autorise_activation_facturation": False,
    }
