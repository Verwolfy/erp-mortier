"""Prévention conservatrice des doublons tiers, sans mutation de données.

Vérifie NIF, RC et désignation normalisés dans un même référentiel.
Pas de confusion inter-référentiels : une entreprise peut être à la fois
cliente et fournisseur. La garantie anti-concurrence exige ultérieurement
une contrainte SQL validée sur les identifiants légaux.
"""
from __future__ import annotations

import re
import unicodedata
from collections.abc import Mapping, Sequence


class DuplicateTierError(ValueError):
    """Création bloquée : un tiers existant doit être vérifié."""


def _norm_name(value: object) -> str:
    if not isinstance(value, str):
        return ""
    value = unicodedata.normalize("NFKD", value)
    value = "".join(ch for ch in value if not unicodedata.combining(ch))
    return re.sub(r"[^\w]+", " ", value.casefold(), flags=re.UNICODE).strip()


def _norm_legal_id(value: object) -> str:
    if not isinstance(value, str):
        return ""
    value = unicodedata.normalize("NFKC", value).casefold().upper()
    # Les séparateurs de saisie ne modifient pas l'identité du numéro.
    return re.sub(r"[^A-Z0-9]", "", value)


def ensure_new_tier(*, kind: str, data: Mapping, existing: Sequence[Mapping]) -> None:
    """Refuse les identités exactes normalisées, sans recherche approximative.

    Fail closed si le référentiel complet ne peut pas être lu correctement.
    Ne retourne aucune donnée nominative dans le message d'erreur.
    """
    if kind not in {"client", "fournisseur"}:
        raise ValueError("Type de tiers invalide")
    primary = "client_id" if kind == "client" else "fournisseur_id"
    if not isinstance(data, Mapping):
        raise ValueError("Fiche tierce invalide")
    name = _norm_name(data.get("nom"))
    if not name:
        raise ValueError("Nom du tiers obligatoire")
    nif, rc = (_norm_legal_id(data.get("nif")),
               _norm_legal_id(data.get("rc")))
    if not isinstance(existing, Sequence) or isinstance(existing, (str, bytes)):
        raise RuntimeError("Liste complète des tiers indisponible")
    for record in existing:
        if not isinstance(record, Mapping) or not isinstance(record.get(primary), str) or not record[primary].strip():
            raise RuntimeError("Référentiel tiers incomplet : création refusée")
        identifier = record[primary].strip()
        if nif and nif == _norm_legal_id(record.get("nif")):
            raise DuplicateTierError(
                f"{kind.capitalize()} déjà répertorié : NIF identique à la fiche "
                f"{identifier}. Vérifier la fiche existante plutôt que la recréer.")
        if rc and rc == _norm_legal_id(record.get("rc")):
            raise DuplicateTierError(
                f"{kind.capitalize()} potentiellement déjà répertorié : RC identique "
                f"à la fiche {identifier}. Vérifier l'identité légale avant toute création.")
        if name == _norm_name(record.get("nom")):
            raise DuplicateTierError(
                f"{kind.capitalize()} potentiellement déjà répertorié : désignation "
                f"identique à la fiche {identifier}. Vérifier la fiche existante.")



def ensure_updated_tier(*, kind: str, target_id: str,
                        updates: Mapping, existing: Sequence[Mapping]) -> None:
    """Bloque une modification qui duplique l'identité d'un AUTRE tiers.

    La fiche courante provient de la lecture exhaustive la plus récente, pas
    des valeurs possiblement périmées du tableau d'édition. Refuse les ID
    absents, dupliqués ou mal formés avant toute écriture.
    """
    if kind not in {"client", "fournisseur"}:
        raise ValueError("Type de tiers invalide")
    primary = "client_id" if kind == "client" else "fournisseur_id"
    if not isinstance(target_id, str) or not target_id.strip():
        raise ValueError("Identifiant de tiers manquant")
    if not isinstance(updates, Mapping):
        raise ValueError("Modifications de tiers invalides")
    if not isinstance(existing, Sequence) or isinstance(existing, (str, bytes)):
        raise RuntimeError("Liste complète des tiers indisponible")

    current = []
    others = []
    for row in existing:
        if not isinstance(row, Mapping):
            raise RuntimeError("Référentiel tiers incomplet : modification refusée")
        identifier = row.get(primary)
        if not isinstance(identifier, str) or not identifier.strip():
            raise RuntimeError("Identifiant de tiers absent : modification refusée")
        if identifier.strip() == target_id.strip():
            current.append(row)
        else:
            others.append(row)
    if len(current) != 1:
        raise RuntimeError("Fiche de tiers introuvable ou dupliquée : modification refusée")

    # Ne pas appliquer de valeurs du formulaire sur une autre fiche.
    candidate = {**current[0], **updates}
    ensure_new_tier(kind=kind, data=candidate, existing=others)
