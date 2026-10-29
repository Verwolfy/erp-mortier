"""Couverture des classifications TVA par SKU — lecture, aucun calcul de facture.

Un statut « VALIDE » veut dire que le dossier de qualification du SKU a
des justificatifs et une date, non que l'ERP peut facturer. Le régime
de l'entreprise et le fait générateur restent à vérifier indépendamment.
"""
from __future__ import annotations
from datetime import date
from typing import Any, Mapping, Sequence


class QualificationTVAIndisponible(ValueError):
    """Référentiel incomplet, contradictoire ou illisible."""


_CODES = {
    "NORMAL": "TVA_TAUX_NORMAL",
    "REDUIT": "TVA_TAUX_REDUIT",
    "EXONERE": None,
    "HORS_CHAMP": None,
}


def _date(value: Any, field: str) -> date:
    if not isinstance(value, str):
        raise QualificationTVAIndisponible(f"{field} : ISO obligatoire")
    try:
        parsed = date.fromisoformat(value)
    except ValueError as exc:
        raise QualificationTVAIndisponible(f"{field} : date invalide") from exc
    if parsed.isoformat() != value:
        raise QualificationTVAIndisponible(f"{field} : date non canonique")
    return parsed


def _text(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value.strip() or len(value) > 1000:
        raise QualificationTVAIndisponible(f"{field} manquant")
    return value.strip()


def verifier_couverture_tva(
    skus: Sequence[Mapping[str, Any]],
    qualifications: Sequence[Mapping[str, Any]],
    date_operation: str,
    *,
    uniquement_actifs: bool = False,
) -> dict[str, Any]:
    """Vérifie tout le référentiel, avec affichage optionnel des SKU actifs."""
    if not isinstance(uniquement_actifs, bool):
        raise QualificationTVAIndisponible("Filtre SKU actifs invalide")
    target = _date(date_operation, "date_operation")
    if (not isinstance(skus, (list, tuple)) or not isinstance(qualifications, (list, tuple))
            or len(skus) > 10000 or len(qualifications) > 10000):
        raise QualificationTVAIndisponible("Sources manquantes ou incomplètes")
    if not all(isinstance(x, Mapping) for x in (*skus, *qualifications)):
        raise QualificationTVAIndisponible("Ligne illisible")
    products: dict[str, Mapping[str, Any]] = {}
    for sku in skus:
        sid = _text(sku.get("sku_id"), "SKU")
        if sid in products:
            raise QualificationTVAIndisponible("SKU en double")
        products[sid] = sku
    by_sku: dict[str, list[Mapping[str, Any]]] = {}
    seen_versions: set[tuple[str, date]] = set()
    for row in qualifications:
        sid = _text(row.get("sku_id"), "SKU fiscal")
        if sid not in products:
            raise QualificationTVAIndisponible("Classification d'un SKU absent")
        begin = _date(row.get("date_effet"), "date_effet")
        end = _date(row["date_fin"], "date_fin") if row.get("date_fin") is not None else None
        if end is not None and end < begin:
            raise QualificationTVAIndisponible("Période juridique inversée")
        key = (sid, begin)
        if key in seen_versions:
            raise QualificationTVAIndisponible("Version fiscale dupliquée")
        seen_versions.add(key)
        status = row.get("statut")
        category = row.get("categorie_tva")
        code = row.get("code_parametre")
        if status not in ("A_VALIDER", "VALIDEE"):
            raise QualificationTVAIndisponible("Statut fiscal inconnu")
        if category is not None and (
            category not in _CODES or _CODES[category] != code
        ) or category is None and code is not None:
            raise QualificationTVAIndisponible("Catégorie fiscale incohérente")
        if status == "VALIDEE":
            if category is None:
                raise QualificationTVAIndisponible("Catégorie validée absente")
            for field in ("source_juridique", "justification", "valide_par"):
                _text(row.get(field), field)
            _date(row.get("date_verification"), "date_verification")
            _date(row.get("date_validation"), "date_validation")
        by_sku.setdefault(sid, []).append(row)
    # Un intervalle à cheval sur un autre ne peut pas être arbitré.
    for sid, rows in by_sku.items():
        periods = sorted(
            [(_date(x["date_effet"], "date_effet"),
              _date(x["date_fin"], "date_fin") if x.get("date_fin") else date.max)
             for x in rows]
        )
        for index in range(1, len(periods)):
            if periods[index][0] <= periods[index - 1][1]:
                raise QualificationTVAIndisponible("Périodes fiscales superposées")
    result = []
    tally = {"NON_CLASSE": 0, "A_VALIDER": 0, "VALIDE": 0}
    for sid in sorted(products):
        # Vérifier la cohérence de TOUS les dossiers en amont, y compris
        # ceux des SKU inactifs. Filtrer seulement les lignes du résultat.
        if uniquement_actifs and products[sid].get("actif") != "OUI":
            continue
        applicable = [
            row for row in by_sku.get(sid, [])
            if _date(row["date_effet"], "date_effet") <= target
            and (row.get("date_fin") is None or target <= _date(row["date_fin"], "date_fin"))
        ]
        if len(applicable) > 1:
            raise QualificationTVAIndisponible("Périodes fiscales ambiguës")
        row = applicable[0] if applicable else None
        status = ("NON_CLASSE" if row is None
                  else "VALIDE" if row["statut"] == "VALIDEE"
                  else "A_VALIDER")
        tally[status] += 1
        result.append({
            "sku_id": sid,
            "produit": products[sid].get("pf_id") or "",
            "actif_sku": products[sid].get("actif") or "",
            "statut": status,
            "categorie_tva": row.get("categorie_tva") if row else None,
            "code_parametre": row.get("code_parametre") if row else None,
            "source_juridique": row.get("source_juridique") if row else None,
            "date_effet": row.get("date_effet") if row else None,
        })
    return {"date_operation": target.isoformat(), "nombre_skus": len(result),
            "par_statut": tally, "lignes": result,
            "facturation_automatique_autorisee": False}
