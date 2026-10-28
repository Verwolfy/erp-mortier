"""Lecture serveur fail-closed de la balance SCF.

Aucune écriture SQL, aucun contrôle de droits basé sur un rôle fourni par le
navigateur : le point d'entrée exige une habilitation déjà revérifiée côté
serveur et les permissions SQL de Supabase restent applicables.
"""
from __future__ import annotations

from collections import defaultdict
from typing import Any, Mapping
from uuid import UUID

from core.scf_journal import EcritureSCFInvalide, calculer_balance_scf

_MAX_PIECES = 999
_MAX_LIGNES = 9999
_CHAMPS_PIECES = "piece_id,statut,date_ecriture,code_journal,reference,libelle"
_CHAMPS_LIGNES = "ligne_id,piece_id,numero,compte,debit,credit"


class LectureSCFIndisponible(ValueError):
    """Résultat SQL incomplet, écriture invalide ou habilitation refusée."""


def _complet(result: Any, limite: int) -> list[dict]:
    data = getattr(result, "data", None)
    count = getattr(result, "count", None)
    if (not isinstance(data, list)
            or isinstance(count, bool)
            or not isinstance(count, int)
            or count != len(data)
            or count > limite
            or not all(isinstance(row, dict) for row in data)):
        raise LectureSCFIndisponible("Lecture SCF incomplète ou incohérente")
    return data


def _uuid(value: Any) -> str:
    if not isinstance(value, str):
        raise LectureSCFIndisponible("Identifiant SCF invalide")
    try:
        ident = str(UUID(value))
    except (ValueError, AttributeError) as exc:
        raise LectureSCFIndisponible("Identifiant SCF invalide") from exc
    if ident != value.lower():
        raise LectureSCFIndisponible("Format d'identifiant SCF invalide")
    return ident


def lire_balance_scf(*, autorisation_serveur: bool, db_client: Any = None) -> dict[str, Any]:
    """Calcule la balance à partir des seules pièces VALIDEE vérifiées.

    Une anomalie de paginage, une pièce privée sans lignes ou une somme
    déséquilibrée bloque l'intégralité de l'affichage : aucun total partiel.
    """
    if autorisation_serveur is not True:
        raise PermissionError("Lecture de la comptabilité SCF interdite")
    if db_client is None:
        from core.db_service import get_supabase_client
        db_client = get_supabase_client()
    try:
        response = (
            db_client.table("scf_pieces")
            .select(_CHAMPS_PIECES, count="exact")
            .eq("statut", "VALIDEE")
            .order("date_ecriture")
            .range(0, _MAX_PIECES - 1)
            .execute()
        )
        pieces = _complet(response, _MAX_PIECES)
        by_id = {}
        for piece in pieces:
            ident = _uuid(piece.get("piece_id"))
            if ident in by_id or piece.get("statut") != "VALIDEE":
                raise LectureSCFIndisponible("Pièce SCF dupliquée ou non validée")
            by_id[ident] = {
                "statut": "VALIDEE", "date_ecriture": piece.get("date_ecriture"),
                "journal": piece.get("code_journal"),
                "reference": piece.get("reference"), "libelle": piece.get("libelle"),
                "lignes": [],
            }
        if not by_id:
            return {"pieces": 0, "lignes": 0, "balance": {}}
        # Des lots de 80 évitent les URL trop longues de l'API PostgREST.
        nombre = 0
        lignes_vues: set[int] = set()
        ids = list(by_id)
        for debut in range(0, len(ids), 80):
            subset = ids[debut:debut + 80]
            result = (
                db_client.table("scf_lignes")
                .select(_CHAMPS_LIGNES, count="exact")
                .in_("piece_id", subset)
                .order("piece_id")
                .order("numero")
                .range(0, _MAX_LIGNES - 1)
                .execute()
            )
            lignes = _complet(result, _MAX_LIGNES)
            nombre += len(lignes)
            if nombre > _MAX_LIGNES:
                raise LectureSCFIndisponible("Journal trop volumineux pour cette consultation")
            for ligne in lignes:
                pid = _uuid(ligne.get("piece_id"))
                lid = ligne.get("ligne_id")
                if pid not in by_id or isinstance(lid, bool) or not isinstance(lid, int) or lid in lignes_vues:
                    raise LectureSCFIndisponible("Ligne SCF inconnue ou dupliquée")
                lignes_vues.add(lid)
                by_id[pid]["lignes"].append({
                    "compte": ligne.get("compte"),
                    "debit": str(ligne.get("debit")),
                    "credit": str(ligne.get("credit")),
                })
        try:
            balance = calculer_balance_scf(list(by_id.values()))
        except EcritureSCFInvalide as exc:
            raise LectureSCFIndisponible("Journal SCF non équilibré ou incomplet") from exc
        return {"pieces": len(by_id), "lignes": nombre, "balance": balance}
    except (LectureSCFIndisponible, PermissionError):
        raise
    except Exception as exc:
        raise LectureSCFIndisponible("Lecture SCF indisponible") from exc
