"""Diagnostic de mise en service fiscale/SCF, lecture seule et fail-closed.

Les références officielles générales ne suffisent pas à classifier les SKU.
Aucune facture, écriture ou paramètre n'est créé par ce module.
"""
from __future__ import annotations

from datetime import date
from typing import Any, Mapping

from core.reglementation import RegleIndisponible, chercher_parametre

class PreflightIndisponible(ValueError):
    pass

TABLES = {
    "parametres_reglementaires": "code,valeur,unite,statut_juridique,niveau_confiance,date_effet,date_fin,source,date_verification",
    "regles_reglementaires": "code,donnees,statut_juridique,niveau_confiance",
    "scf_plan_comptes": "numero_compte,actif,mouvementable",
    "scf_exercices": "exercice_id,statut",
    "scf_journaux": "code_journal",
}
_MAX = 999

def examiner_referentiels(
    snapshots: Mapping[str, list[dict]], *, date_reference: date | str | None = None
) -> dict[str, Any]:
    """Contrôle de disponibilité documentaire, jamais homologation juridique.

    Les taux sont lus dans les versions confirmées et datées du registre,
    sans comparaison à des pourcentages figés dans le code.
    """
    if not isinstance(snapshots, Mapping) or set(snapshots) != set(TABLES):
        raise PreflightIndisponible("Inventaire incomplet")
    for key, rows in snapshots.items():
        if not isinstance(rows, list) or len(rows) > _MAX or not all(isinstance(r, dict) for r in rows):
            raise PreflightIndisponible(f"Inventaire {key} invalide")
    rates = snapshots["parametres_reglementaires"]
    instant = date_reference if date_reference is not None else date.today()
    observed = {}
    for code in ("TVA_TAUX_NORMAL", "TVA_TAUX_REDUIT"):
        lignes_code = [row for row in rates if row.get("code") == code]
        if not lignes_code:
            continue
        try:
            param = chercher_parametre(
                lignes_code, code, instant, unite_attendue="fraction"
            )
        except RegleIndisponible as exc:
            raise PreflightIndisponible(
                f"{code}: aucune version réglementaire unique, confirmée et datée"
            ) from exc
        if not 0 <= param.valeur <= 1:
            raise PreflightIndisponible(f"{code}: taux de référence hors bornes")
        observed[code] = True
    scf = snapshots["scf_plan_comptes"]
    ids = [r.get("numero_compte") for r in scf]
    if any(not isinstance(i, str) or not i for i in ids) or len(set(ids)) != len(ids):
        raise PreflightIndisponible("Plan SCF dupliqué ou incomplet")
    if any(not isinstance(r.get("actif"), bool) or
           not isinstance(r.get("mouvementable"), bool) for r in scf):
        raise PreflightIndisponible("Statuts des comptes SCF invalides")
    active = sum(bool(r["actif"] and r["mouvementable"]) for r in scf)
    g50 = [r for r in snapshots["regles_reglementaires"] if r.get("code") == "TVA_G50_MENSUEL_REGIME_REEL"]
    if len(g50) > 1:
        raise PreflightIndisponible("Règles déclaratives concurrentes")
    if any(not isinstance(row.get("donnees"), dict) for row in g50):
        raise PreflightIndisponible("Règle déclarative illisible")
    g50_unclassified = len(g50) == 1 and g50[0]["donnees"].get("application_entreprise") == "NON_CLASSEE"
    journals = snapshots["scf_journaux"]
    exercises = snapshots["scf_exercices"]
    # Aucun taux par SKU ni régime fiscal de l'entreprise n'est déduit d'un taux général.
    return {
        "reference_tva_officielle": len(observed) == 2,
        "taux_reference_disponibles": len(observed),
        "classification_tva_produits": "NON_VERIFIEE",
        "regime_fiscal_entreprise": "NON_VERIFIE",
        "g50_conditionnelle": g50_unclassified,
        "comptes_scf_reference": len(scf),
        "comptes_scf_mouvementables": active,
        "journaux_scf": len(journals),
        "exercices_scf_ouverts": sum(r.get("statut") == "OUVERT" for r in exercises),
        "facturation_reglementaire_prete": False,
        "comptabilisation_scf_prete": False,
        "statut": "CONFIGURATION_METIER_A_COMPLETER",
    }

def lire_preflight(
    *, db_client: Any, date_reference: date | str | None = None
) -> dict[str, Any]:
    """Accès interne uniquement : client serveur explicitement fourni."""
    if db_client is None:
        raise PreflightIndisponible("Client serveur requis")
    snapshots = {}
    try:
        for name, fields in TABLES.items():
            result = (db_client.table(name).select(fields, count="exact")
                      .range(0, _MAX - 1).execute())
            rows, count = getattr(result, "data", None), getattr(result, "count", None)
            if (not isinstance(rows, list) or isinstance(count, bool)
                    or not isinstance(count, int) or count != len(rows)
                    or count > _MAX or not all(isinstance(r, dict) for r in rows)):
                raise PreflightIndisponible("Lecture partielle du registre")
            snapshots[name] = rows
    except PreflightIndisponible:
        raise
    except Exception as exc:
        raise PreflightIndisponible("Registres réglementaires indisponibles") from exc
    return examiner_referentiels(snapshots, date_reference=date_reference)
