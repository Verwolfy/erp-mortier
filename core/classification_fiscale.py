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
    """Sélectionne strictement une classification de public.erp_sku_fiscalite.

    Les versions historiques/futures sans effet à la date de l'opération ne
    bloquent pas une version applicable. Une version applicable mais non
    validée ne devient jamais implicitement valide. Ne calcule aucune taxe.
    """
    if not isinstance(sku_id, str) or not sku_id.strip():
        raise ClassificationIndisponible("SKU obligatoire")
    if not isinstance(date_operation, date) or hasattr(date_operation, "hour"):
        raise ClassificationIndisponible("Date d'opération invalide")
    if not isinstance(lignes_bdd, (list, tuple)):
        raise ClassificationIndisponible("Référentiel SKU invalide")

    def lire_date(valeur: Any, champ: str) -> date:
        if isinstance(valeur, date) and not hasattr(valeur, "hour"):
            return valeur
        if isinstance(valeur, str):
            try:
                resultat = date.fromisoformat(valeur)
                if resultat.isoformat() == valeur:
                    return resultat
            except ValueError:
                pass
        raise ClassificationIndisponible(f"{champ} invalide")

    candidates: list[Mapping[str, Any]] = []
    attendus = {"NORMAL": "TVA_TAUX_NORMAL", "REDUIT": "TVA_TAUX_REDUIT",
                "EXONERE": None, "HORS_CHAMP": None}
    for ligne in lignes_bdd:
        if not isinstance(ligne, Mapping):
            raise ClassificationIndisponible("Ligne SKU non structurée")
        if ligne.get("sku_id") != sku_id:
            continue
        if ligne.get("statut") not in ("VALIDEE", "A_VALIDER"):
            raise ClassificationIndisponible("Statut de classification inconnu")

        debut = lire_date(ligne.get("date_effet"), "Date d'effet fiscal")
        fin_valeur = ligne.get("date_fin")
        fin = lire_date(fin_valeur, "Date de fin fiscale") if fin_valeur is not None else None
        if fin is not None and fin < debut:
            raise ClassificationIndisponible("Période fiscale invalide")
        if not (debut <= date_operation and (fin is None or date_operation <= fin)):
            continue
        # Une classification A_VALIDER couvrant la même opération interdit
        # de réutiliser silencieusement une version VALIDEE concurrente.
        if ligne["statut"] == "A_VALIDER":
            raise ClassificationIndisponible("Classification applicable en attente de validation")

        for champ in ("source_juridique", "justification", "valide_par"):
            val = ligne.get(champ)
            if not isinstance(val, str) or not val.strip():
                raise ClassificationIndisponible(f"Classification : {champ} absent")

        verification = lire_date(ligne.get("date_verification"), "Date de vérification")
        validation = lire_date(ligne.get("date_validation"), "Date de validation")
        if validation < verification:
            raise ClassificationIndisponible("Validation antérieure à la vérification")
        if validation > date_operation:
            raise ClassificationIndisponible("Classification validée après la date d'opération")

        categorie, code = ligne.get("categorie_tva"), ligne.get("code_parametre")
        if categorie not in attendus or code != attendus[categorie]:
            raise ClassificationIndisponible("Catégorie TVA et paramètre incohérents")
        candidates.append(ligne)

    if len(candidates) != 1:
        raise ClassificationIndisponible("Classification absente ou ambiguë")
    return candidates[0]
