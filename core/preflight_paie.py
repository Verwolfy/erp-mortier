"""Diagnostic IRG/CNAS à date donnée : aucune simulation de paie ni taux légal par défaut.

La présence de références documentées ne vaut jamais homologation d'un
bulletin individuel, dont les assiettes et le profil restent à vérifier.
"""
from __future__ import annotations

from datetime import date
from typing import Any, Mapping, Sequence

from core.reglementation import RegleIndisponible, chercher_parametre
from core.baremes import BaremeIndisponible, choisir_bareme_reglementaire


class PreparationPaieIndisponible(ValueError):
    """Registre inaccessible, partiel, contradictoire ou illisible."""


_PARAM_CODES = ("CNAS_SALARIE_TAUX", "CNAS_EMPLOYEUR_TAUX")
_IRG_CODE = "IRG_SALAIRES_MENSUEL"
_CHAMPS_PARAM = (
    "code,valeur,unite,date_effet,date_fin,statut_juridique,"
    "niveau_confiance,source,date_verification"
)
_CHAMPS_REGLES = (
    "code,type_regle,donnees,date_effet,date_fin,statut_juridique,"
    "niveau_confiance,source,date_verification"
)


def verifier_referentiels_paie(
    parametres: Sequence[Mapping[str, Any]],
    regles: Sequence[Mapping[str, Any]],
    date_paie: str,
) -> dict[str, Any]:
    if not isinstance(date_paie, str):
        raise PreparationPaieIndisponible("Date de paie invalide")
    try:
        instant = date.fromisoformat(date_paie)
    except ValueError as exc:
        raise PreparationPaieIndisponible("Date de paie non ISO") from exc
    if instant.isoformat() != date_paie:
        raise PreparationPaieIndisponible("Date de paie non canonique")
    if (not isinstance(parametres, (list, tuple))
            or not isinstance(regles, (list, tuple))
            or len(parametres) > 1000 or len(regles) > 1000
            or not all(isinstance(x, Mapping) for x in (*parametres, *regles))):
        raise PreparationPaieIndisponible("Référentiel de paie incomplet")

    availability = {}
    for code in _PARAM_CODES:
        matching = [p for p in parametres if p.get("code") == code]
        if not matching:
            availability[code] = False
            continue
        try:
            entry = chercher_parametre(matching, code, instant)
        except RegleIndisponible as exc:
            # Un dossier présent mais non utilisable est un manque, sauf si
            # plusieurs règles confirmées concurrentes existent.
            if "règle(s) confirmée(s)" not in str(exc) or not str(exc).startswith(f"{code}: 0 "):
                raise PreparationPaieIndisponible("Paramètre CNAS contradictoire") from exc
            availability[code] = False
            continue
        if entry.valeur < 0 or entry.valeur > 1:
            raise PreparationPaieIndisponible("Taux CNAS hors limites")
        availability[code] = True

    matching_irg = [r for r in regles if r.get("code") == _IRG_CODE]
    irg_ready = False
    if matching_irg:
        try:
            rule = choisir_bareme_reglementaire(matching_irg, _IRG_CODE, instant)
        except BaremeIndisponible as exc:
            # Ne jamais transformer en règle fictive une absence ou une
            # ambiguïté : on signale le manque mais on reste non opérationnel.
            raise PreparationPaieIndisponible("Règle IRG ambiguë ou inapplicable") from exc
        if rule.get("type_regle") != "progressif":
            raise PreparationPaieIndisponible("Type de barème IRG incorrect")
        source = rule.get("source")
        if not isinstance(source, str) or not source.strip():
            raise PreparationPaieIndisponible("Source IRG absente")
        verification = rule.get("date_verification")
        if not isinstance(verification, str):
            raise PreparationPaieIndisponible("Date de vérification IRG absente")
        try:
            if date.fromisoformat(verification).isoformat() != verification:
                raise PreparationPaieIndisponible("Date de vérification IRG non canonique")
        except ValueError as exc:
            raise PreparationPaieIndisponible("Date de vérification IRG invalide") from exc
        settings = rule.get("donnees")
        if (not isinstance(settings, Mapping)
                or not isinstance(settings.get("tranches"), list)
                or not settings["tranches"]):
            raise PreparationPaieIndisponible("Tranches IRG incomplètes")
        irg_ready = True

    return {
        "date_paie": instant.isoformat(),
        "reference_cnas_salarie": availability["CNAS_SALARIE_TAUX"],
        "reference_cnas_employeur": availability["CNAS_EMPLOYEUR_TAUX"],
        "reference_irg_mensuel": irg_ready,
        "qualification_assiette_individuelle": "NON_VERIFIEE",
        "bulletin_officiel_autorise": False,
        "declaration_sociale_autorisee": False,
        "statut": "PREPARATION_A_COMPLETER",
    }


def lire_preparation_paie(*, db_client: Any, date_paie: str) -> dict[str, Any]:
    """La permission Paie/lecture doit être revérifiée avant cet appel."""
    if db_client is None:
        raise PreparationPaieIndisponible("Client serveur requis")
    results = []
    try:
        q = (db_client.table("parametres_reglementaires")
             .select(_CHAMPS_PARAM, count="exact")
             .in_("code", list(_PARAM_CODES)).order("date_effet")
             .range(0, 999).execute())
        results.append(q)
        q = (db_client.table("regles_reglementaires")
             .select(_CHAMPS_REGLES, count="exact")
             .eq("code", _IRG_CODE).order("date_effet")
             .range(0, 999).execute())
        results.append(q)
    except Exception as exc:
        raise PreparationPaieIndisponible("Lecture des règles de paie indisponible") from exc
    data = []
    for result in results:
        rows, count = getattr(result, "data", None), getattr(result, "count", None)
        if (not isinstance(rows, list) or isinstance(count, bool)
                or not isinstance(count, int) or count != len(rows)
                or len(rows) > 1000 or not all(isinstance(r, dict) for r in rows)):
            raise PreparationPaieIndisponible("Lecture réglementaire partielle")
        data.append(rows)
    return verifier_referentiels_paie(data[0], data[1], date_paie)
