"""Empreinte reproductible d'un brouillon NEXTGEN, sans effet réseau.

Une empreinte SHA-256 seule n'est pas une signature ni une preuve d'émission :
la comparaison devra se faire avec une valeur enregistrée côté serveur.
"""
from __future__ import annotations

from datetime import date
from hashlib import sha256
import json
import re

TRACE_ID = re.compile(r"NG-[A-F0-9]{32}\Z")
_FIELDS = (
    "type", "numero", "date", "tiers_nom", "tiers_adresse", "objet",
    "items", "total_ht", "total_taxes", "total_ttc", "observations",
    "trace_id", "statut",
)
LINE_LIMIT = 200


def canonical_draft(doc: dict) -> bytes:
    """Canonicalise les mêmes champs quelle que soit l'ordre des clés JSON.

    Ne persiste aucune information. Les lignes conservent leur ordre métier.
    Les champs hors contrat ne participent pas à l'empreinte.
    """
    from modules.documents.views import validate_draft
    from modules.documents.layout_nextgen import columns_for
    from modules.documents.calculations import normalize_financial_export

    validate_draft(doc)
    if not TRACE_ID.fullmatch(doc["trace_id"]):
        raise ValueError("Identifiant QR invalide")
    if doc.get("statut") != "BROUILLON":
        raise ValueError("Une empreinte de brouillon exige le statut BROUILLON")
    try:
        document_date = date.fromisoformat(doc["date"]).isoformat()
    except (TypeError, ValueError) as exc:
        raise ValueError("Date de document invalide") from exc
    if len(doc["items"]) > LINE_LIMIT:
        raise ValueError("Trop de lignes")

    prepared = normalize_financial_export(doc)
    allowed_columns = {key for key, _ in columns_for(prepared["type"])}
    payload = {}
    for field in _FIELDS:
        if field == "items":
            payload[field] = []
            for index, row in enumerate(prepared["items"], 1):
                if not isinstance(row, dict):
                    raise ValueError("Ligne invalide")
                clean = {}
                for key in sorted(allowed_columns):
                    value = row.get(key, "")
                    if value is None:
                        value = ""
                    if not isinstance(value, (str, int, float)):
                        raise ValueError(f"Ligne {index} : champ invalide")
                    text = str(value)
                    if len(text) > 1000:
                        raise ValueError("Champ de ligne trop long")
                    clean[key] = text
                payload[field].append(clean)
        elif field == "date":
            payload[field] = document_date
        else:
            value = prepared.get(field, "")
            if not isinstance(value, (str, int, float)) and value is not None:
                raise ValueError(f"Champ {field} invalide")
            text = str(value if value is not None else "")
            if len(text) > 2000:
                raise ValueError(f"Champ {field} trop long")
            payload[field] = text
    return json.dumps(payload, ensure_ascii=False, sort_keys=True,
                      separators=(",", ":"), allow_nan=False).encode("utf-8")


def draft_sha256(doc: dict) -> str:
    """Empreinte locale à comparer ultérieurement à un registre protégé."""
    return sha256(canonical_draft(doc)).hexdigest()
