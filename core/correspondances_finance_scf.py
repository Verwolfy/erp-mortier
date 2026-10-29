"""Diagnostic des correspondances entre comptes de trésorerie Finance et SCF.

Ne crée ni compte, ni lettrage, ni écriture comptable. Les numéros Finance
sont comparés au numéro SCF *exact* sans supposer d'équivalence juridique.
"""
from __future__ import annotations

from typing import Any, Mapping, Sequence


class CorrespondanceSCFIndisponible(ValueError):
    """Source manquante, registre contradictoire ou lecture tronquée."""


def _rows(source: Any, name: str) -> list[Mapping[str, Any]]:
    if not isinstance(source, (list, tuple)) or len(source) > 10000:
        raise CorrespondanceSCFIndisponible(f"{name} manquant ou hors limites")
    if not all(isinstance(x, Mapping) for x in source):
        raise CorrespondanceSCFIndisponible(f"{name} contient une ligne invalide")
    return list(source)


def _text(value: Any, name: str, *, optional: bool = False) -> str:
    if value is None and optional:
        return ""
    if not isinstance(value, str) or len(value.strip()) > 200:
        raise CorrespondanceSCFIndisponible(f"{name} invalide")
    value = value.strip()
    if not value and not optional:
        raise CorrespondanceSCFIndisponible(f"{name} absent")
    return value


def analyser_correspondances_finance_scf(
    comptes_finance: Sequence[Mapping[str, Any]],
    plan_scf: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    """Contrôle exact en lecture seule, sans inférence d'une affectation.

    Un compte exact et mouvementable n'est qu'un candidat : sa validité pour
    le type Banque/Caisse/Tiers de l'entreprise doit encore être homologuée.
    """
    finance = _rows(comptes_finance, "Comptes Finance")
    scf = _rows(plan_scf, "Plan SCF")
    by_code: dict[str, Mapping[str, Any]] = {}
    for row in scf:
        code = _text(row.get("numero_compte"), "Numéro SCF")
        if not code.isdigit() or not (2 <= len(code) <= 8):
            raise CorrespondanceSCFIndisponible("Numéro SCF mal formé")
        if code in by_code:
            raise CorrespondanceSCFIndisponible("Numéro SCF répété")
        if not isinstance(row.get("actif"), bool) or not isinstance(row.get("mouvementable"), bool):
            raise CorrespondanceSCFIndisponible("Statut SCF illisible")
        _text(row.get("libelle"), "Libellé SCF")
        by_code[code] = row

    seen: set[str] = set()
    result = []
    totals = {"SANS_NUMERO": 0, "NON_REFERENCE": 0,
              "REFERENCE_INACTIVE": 0, "CANDIDAT_A_VALIDER": 0,
              "COMPTE_FINANCE_INACTIF": 0}
    for row in finance:
        identifier = _text(row.get("compte_id"), "Identifiant Finance")
        if identifier in seen:
            raise CorrespondanceSCFIndisponible("Compte Finance dupliqué")
        seen.add(identifier)
        account_name = _text(row.get("nom_compte"), "Nom du compte")
        account_type = _text(row.get("type_compte"), "Type de compte")
        active_status = _text(row.get("statut"), "Statut Finance")
        if active_status.upper() not in ("OUI", "NON"):
            raise CorrespondanceSCFIndisponible("Statut de compte Finance inconnu")
        raw_number = row.get("numero_compte")
        number = _text(raw_number, "Numéro Finance", optional=True)
        match = by_code.get(number)
        if active_status.upper() == "NON":
            status = "COMPTE_FINANCE_INACTIF"
        elif not number:
            status = "SANS_NUMERO"
        elif match is None:
            status = "NON_REFERENCE"
        elif not match["actif"] or not match["mouvementable"]:
            status = "REFERENCE_INACTIVE"
        else:
            status = "CANDIDAT_A_VALIDER"
        totals[status] += 1
        result.append({
            "compte_finance_id": identifier,
            "compte_finance_nom": account_name,
            "type_finance": account_type,
            "numero_compte_saisi": number or None,
            "numero_scf_identique": number if match is not None else None,
            "libelle_scf_reference": match["libelle"] if match is not None else None,
            "statut": status,
        })

    return {
        "nombre_comptes_finance": len(finance),
        "nombre_comptes_scf": len(scf),
        "repartition": totals,
        "lignes": sorted(result, key=lambda x: x["compte_finance_id"]),
        "ecritures_automatiques_autorisees": False,
        "statut": "CORRESPONDANCES_NON_HOMOLOGUEES",
    }


def lire_correspondances_finance_scf(
    comptes_finance: Sequence[Mapping[str, Any]], *, db_client: Any,
) -> dict[str, Any]:
    """La vérification fraîche de l'habilitation Finance revient à l'appelant."""
    if db_client is None:
        raise CorrespondanceSCFIndisponible("Client serveur requis")
    try:
        response = (
            db_client.table("scf_plan_comptes")
            .select("numero_compte,libelle,actif,mouvementable", count="exact")
            .range(0, 999).execute()
        )
    except Exception as exc:
        raise CorrespondanceSCFIndisponible("Plan SCF inaccessible") from exc
    rows, count = getattr(response, "data", None), getattr(response, "count", None)
    if (not isinstance(rows, list) or isinstance(count, bool)
            or not isinstance(count, int) or count != len(rows)
            or count > 1000):
        raise CorrespondanceSCFIndisponible("Lecture du plan SCF incomplète")
    return analyser_correspondances_finance_scf(comptes_finance, rows)
