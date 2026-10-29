"""Pont fiscal pur entre qualification SKU et paramètres TVA datés.

Outil de prévalidation uniquement : ne calcule pas une facture transactionnelle,
ne détermine pas les exonérations et ne modifie aucune donnée.
"""
from datetime import date
from decimal import Decimal
from typing import Any, Mapping, Sequence

from core.classification_fiscale import ClassificationIndisponible
from core.fiscalite_facturation import FiscaliteNonDisponible, _parametre
from core.precontrole_panier_fiscal import verifier_panier_fiscal


def taux_par_ligne(
    lignes: Sequence[Mapping[str, Any]],
    date_operation: date,
    classifications: Sequence[Mapping[str, Any]],
    parametres: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    classes = verifier_panier_fiscal(lignes, date_operation, classifications)
    if not isinstance(parametres, (list, tuple)):
        raise FiscaliteNonDisponible("Référentiel de paramètres TVA invalide")
    resultat = []
    for ligne, classe in zip(lignes, classes):
        categorie = classe["categorie_tva"]
        code = classe["code_parametre"]
        if categorie in ("EXONERE", "HORS_CHAMP"):
            raise ClassificationIndisponible(
                "Exonération ou hors champ : traitement juridique spécifique requis"
            )
        if categorie not in ("NORMAL", "REDUIT"):
            raise ClassificationIndisponible("Catégorie TVA non prise en charge")
        taux, preuve = _parametre(list(parametres), code, date_operation, "fraction")
        if taux < Decimal("0") or taux > Decimal("1"):
            raise FiscaliteNonDisponible("Taux TVA hors plage")
        resultat.append({
            "sku_id": ligne["sku_id"],
            "categorie_tva": categorie,
            "taux_tva": taux,
            "justificatif_taux": preuve,
            "source_classification": classe["source_juridique"],
        })
    return resultat
