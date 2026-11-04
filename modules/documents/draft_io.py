"""Import contrôlé de brouillons JSON NEXTGEN, sans accès disque/SQL."""
from __future__ import annotations

from datetime import date
import json
import re

MAX_JSON_BYTES = 300_000
MAX_CELL_CHARS = 1_000
MAX_FIELD_CHARS = 2_000
TRACE_PATTERN = re.compile(r"NG-[A-F0-9]{32}\Z")


def read_draft_json(payload: bytes, kind: str) -> dict:
    """Charge un brouillon de même type, après validation des bornes.

    Préserve le trace_id d'origine pour assurer la continuité d'un brouillon,
    sans prétendre que cet identifiant est enregistré dans un registre central.
    """
    from modules.documents.views import DOCUMENTS
    from modules.documents.layout_nextgen import columns_for

    allowed = {x for group in DOCUMENTS.values() for x in group}
    if kind not in allowed:
        raise ValueError("Type de document non reconnu")
    if not isinstance(payload, bytes) or len(payload) > MAX_JSON_BYTES:
        raise ValueError("JSON absent ou trop volumineux (300 Ko maximum)")
    try:
        decoded = json.loads(payload.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError("Fichier JSON invalide") from exc
    if not isinstance(decoded, dict) or decoded.get("type") != kind:
        raise ValueError("Le document importé doit avoir le même type sélectionné")
    if decoded.get("statut") != "BROUILLON":
        raise ValueError("Seuls les documents BROUILLON peuvent être importés")
    trace = decoded.get("trace_id")
    if not isinstance(trace, str) or TRACE_PATTERN.fullmatch(trace) is None:
        raise ValueError("Identifiant QR du brouillon invalide")
    try:
        document_date = date.fromisoformat(decoded.get("date", ""))
    except (TypeError, ValueError) as exc:
        raise ValueError("Date du brouillon invalide") from exc
    lines = decoded.get("items", [])
    if not isinstance(lines, list) or len(lines) > 200:
        raise ValueError("Nombre de lignes invalide (200 maximum)")
    columns = {key for key, _ in columns_for(kind)}
    clean_lines = []
    for number, line in enumerate(lines, 1):
        if not isinstance(line, dict):
            raise ValueError(f"Ligne {number} invalide")
        values = {}
        for field in columns:
            raw = line.get(field, "")
            if not isinstance(raw, (str, int, float)) and raw is not None:
                raise ValueError(f"Ligne {number} : valeur non textuelle")
            value = str(raw if raw is not None else "")
            if len(value) > MAX_CELL_CHARS:
                raise ValueError(f"Ligne {number} : champ trop long")
            values[field] = value
        clean_lines.append(values)
    result = {
        "type": kind,
        "numero": "",
        "date": document_date.isoformat(),
        "tiers_nom": "",
        "tiers_adresse": "",
        "objet": "",
        "items": clean_lines,
        "total_ht": "",
        "total_taxes": "",
        "total_ttc": "",
        "observations": "",
        "trace_id": trace,
        "statut": "BROUILLON",
    }
    for field in ("numero", "tiers_nom", "tiers_adresse", "objet", "observations",
                  "total_ht", "total_taxes", "total_ttc"):
        value = decoded.get(field, "")
        if not isinstance(value, (str, int, float)) and value is not None:
            raise ValueError(f"Champ {field} invalide")
        value = str(value if value is not None else "")
        if len(value) > MAX_FIELD_CHARS:
            raise ValueError(f"Champ {field} trop long")
        result[field] = value
    return result
