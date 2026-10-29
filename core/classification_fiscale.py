"""Tests de classification fiscale datée : aucune décision implicite par SKU."""
from datetime import date
from typing import Any, Mapping


class ClassificationIndisponible(ValueError):
    """Une classification fiscale valide et documentée manque."""


def selectionner_classification(
    sku_id: str, date_operation: date,
    classifications: list[Mapping[str, Any]],
) -> Mapping[str, Any]:
    if not isinstance(sku_id, str) or not sku_id.strip():
        raise ClassificationIndisponible("SKU obligatoire")
    if not isinstance(date_operation, date) or hasattr(date_operation, "hour"):
        raise ClassificationIndisponible("Date d'opération invalide")
    candidates = []
    for row in classifications:
        if row.get("sku_id") != sku_id:
            continue
        if row.get("statut_juridique") != "en_vigueur" or row.get("niveau_confiance") != "CONFIRMEE":
            continue
        if not isinstance(row.get("source"), str) or not row["source"].strip():
            raise ClassificationIndisponible("Source juridique absente")
        try:
            start = date.fromisoformat(row["date_effet"])
            end = date.fromisoformat(row["date_fin"]) if row.get("date_fin") else None
        except (TypeError, ValueError) as exc:
            raise ClassificationIndisponible("Date de classification invalide") from exc
        if end and end < start:
            raise ClassificationIndisponible("Intervalle invalide")
        if start <= date_operation and (end is None or date_operation <= end):
            candidates.append(row)
    if len(candidates) != 1:
        raise ClassificationIndisponible("Classification absente ou ambiguë")
    return candidates[0]


def selectionner_classification_bdd(
    sku_id: str, date_operation: date,
    lignes_bdd: list[Mapping[str, Any]],
) -> Mapping[str, Any]:
    """Sélectionne une ligne de public.erp_sku_fiscalite selon son schéma réel.

    Ne décide jamais du taux légal : retourne uniquement une classification
    validée par un responsable avec justification et preuve documentaire.
    """
    normalisees = []
    originaux = []
    for ligne in lignes_bdd:
        if not isinstance(ligne, Mapping):
            raise ClassificationIndisponible("Ligne SKU non structurée")
        if ligne.get("sku_id") != sku_id:
            continue
        if ligne.get("statut") != "VALIDEE":
            continue
        for champ in ("source_juridique", "justification", "valide_par"):
            val = ligne.get(champ)
            if not isinstance(val, str) or not val.strip():
                raise ClassificationIndisponible(f"Classification : {champ} absent")
        if not ligne.get("date_verification") or not ligne.get("date_validation"):
            raise ClassificationIndisponible("Dates de vérification et validation obligatoires")
        try:
            verification = ligne["date_verification"]
            validation = ligne["date_validation"]
            verification = verification if isinstance(verification, date) and not hasattr(verification, "hour") else date.fromisoformat(verification)
            validation = validation if isinstance(validation, date) and not hasattr(validation, "hour") else date.fromisoformat(validation)
        except (TypeError, ValueError) as exc:
            raise ClassificationIndisponible("Date de validation invalide") from exc
        if validation < verification:
            raise ClassificationIndisponible("Validation antérieure à la vérification")
        debut_fiscal = ligne.get("date_effet")
        fin_fiscal = ligne.get("date_fin")
        try:
            debut_fiscal = debut_fiscal if isinstance(debut_fiscal, date) and not hasattr(debut_fiscal, "hour") else date.fromisoformat(debut_fiscal)
            fin_fiscal = fin_fiscal if isinstance(fin_fiscal, date) and not hasattr(fin_fiscal, "hour") else date.fromisoformat(fin_fiscal) if fin_fiscal else None
        except (TypeError, ValueError) as exc:
            raise ClassificationIndisponible("Dates d'effet fiscal invalides") from exc
        if validation > date_operation:
            raise ClassificationIndisponible("Classification validée après la date d'opération")
        if fin_fiscal is not None and fin_fiscal < debut_fiscal:
            raise ClassificationIndisponible("Période fiscale invalide")
        categorie = ligne.get("categorie_tva")
        code = ligne.get("code_parametre")
        attendus = {"NORMAL": "TVA_TAUX_NORMAL", "REDUIT": "TVA_TAUX_REDUIT",
                    "EXONERE": None, "HORS_CHAMP": None}
        if categorie not in attendus or code != attendus[categorie]:
            raise ClassificationIndisponible("Catégorie TVA et paramètre incohérents")
        debut, fin = ligne.get("date_effet"), ligne.get("date_fin")
        if isinstance(debut, date) and not hasattr(debut, "hour"):
            debut = debut.isoformat()
        if isinstance(fin, date) and not hasattr(fin, "hour"):
            fin = fin.isoformat()
        normalisees.append({
            "sku_id": sku_id, "date_effet": debut, "date_fin": fin,
            "statut_juridique": "en_vigueur", "niveau_confiance": "CONFIRMEE",
            "source": ligne["source_juridique"],
        })
        originaux.append(ligne)
    choisie = selectionner_classification(sku_id, date_operation, normalisees)
    return originaux[next(i for i, ligne in enumerate(normalisees) if ligne is choisie)]
