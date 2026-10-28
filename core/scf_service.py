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


def _exiger_droit_scf(db_client: Any) -> None:
    """Revalide l'acteur depuis la session et les autorisations PostgreSQL.

    Aucun booléen ni identifiant fourni par le code appelant ne peut tenir
    lieu d'autorisation. Ce contrôle doit précéder toute lecture comptable.
    """
    try:
        import streamlit as st
        from config.roles import has_permission

        if st.session_state.get("authenticated") is not True:
            raise PermissionError("Session SCF non authentifiée")
        actor = st.session_state.get("user")
        actor_id = actor.get("user_id") if isinstance(actor, dict) else None
        if not isinstance(actor_id, str) or not actor_id.strip():
            raise PermissionError("Identité SCF manquante")
        result = (
            db_client.table("users")
            .select("user_id,role,actif")
            .eq("user_id", actor_id)
            .limit(2)
            .execute()
        )
        rows = result.data
        if not isinstance(rows, list) or len(rows) != 1 or not isinstance(rows[0], dict):
            raise PermissionError("Compte SCF non vérifiable")
        account = rows[0]
        active = account.get("actif")
        if (
            account.get("user_id") != actor_id
            or (active is not True and str(active).strip().upper() not in
                {"OUI", "TRUE", "1", "ACTIF", "ACTIVE", "YES"})
            or not isinstance(account.get("role"), str)
            or has_permission(account["role"], "SCF", "lecture") is not True
        ):
            raise PermissionError("Droit SCF absent ou révoqué")
    except PermissionError:
        raise
    except Exception as exc:
        raise PermissionError("Vérification des droits SCF indisponible") from exc


def lire_balance_scf(*, db_client: Any = None) -> dict[str, Any]:
    """Calcule la balance des pièces validées sous habilitation serveur fraîche.

    Une anomalie de paginage, une pièce sans lignes ou une somme déséquilibrée
    bloque tout l'affichage ; aucun total partiel n'est retourné.
    """
    if db_client is None:
        from core.db_service import get_supabase_client
        db_client = get_supabase_client()
    _exiger_droit_scf(db_client)
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
