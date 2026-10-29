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
        # Copie de preuve indépendante des dictionnaires Supabase d'origine.
        # Les dates et le valideur sont nécessaires pour reconstituer
        # précisément la classification retenue au moment du précontrôle.
        def iso(value):
            return value.isoformat() if isinstance(value, date) else value

        justificatif_classification = {
            "sku_id": classe["sku_id"],
            "categorie_tva": categorie,
            "code_parametre": code,
            "date_effet": iso(classe["date_effet"]),
            "date_fin": iso(classe.get("date_fin")) if classe.get("date_fin") is not None else None,
            "source_juridique": classe["source_juridique"],
            "justification": classe["justification"],
            "date_verification": iso(classe["date_verification"]),
            "valide_par": classe["valide_par"],
            "date_validation": iso(classe["date_validation"]),
        }
        resultat.append({
            "sku_id": ligne["sku_id"],
            "categorie_tva": categorie,
            "taux_tva": taux,
            "justificatif_taux": preuve,
            "source_classification": classe["source_juridique"],
            "justificatif_classification": justificatif_classification,
        })
    return resultat
