"""Export CSV contrôlé du journal SCF, sans adresse ni données RH.

L'appelant doit contrôler les permissions de téléchargement au niveau serveur.
Ce format est interne, et ne se prétend pas être un FEC officiel algérien.
"""
from __future__ import annotations

import csv
import io
from typing import Any, Iterable, Mapping

from core.scf_journal import EcritureSCFInvalide, calculer_balance_scf


class ExportRefuse(ValueError):
    """Une exportation peut divulguer une pièce non validée ou illisible."""


def _safe(value: Any) -> str:
    if not isinstance(value, str):
        raise ExportRefuse("Champ texte obligatoire")
    if len(value) > 500:
        raise ExportRefuse("Champ trop long")
    # Google Sheets et Excel interprètent aussi certaines chaînes comme formules.
    if value.lstrip().startswith(("=", "+", "-", "@", "\t", "\r", "\n")):
        return "'" + value
    return value


def exporter_journal_scf_csv(ecritures: Iterable[Mapping[str, Any]], *, droit_export: bool) -> str:
    """CSV UTF-8 délimité par point-virgule, uniquement pièces VALIDEE."""
    if droit_export is not True:
        raise PermissionError("Export SCF interdit")
    if not isinstance(ecritures, (list, tuple)):
        raise ExportRefuse("Jeu de pièces non validable")
    if len(ecritures) > 100000:
        raise ExportRefuse("Export trop volumineux")
    out = io.StringIO(newline="")
    writer = csv.writer(out, delimiter=";", quoting=csv.QUOTE_MINIMAL, lineterminator="\n")
    writer.writerow(["date_ecriture","journal","reference","compte","debit_dzd","credit_dzd","libelle"])
    for piece in ecritures:
        if not isinstance(piece, Mapping) or piece.get("statut") != "VALIDEE":
            raise ExportRefuse("Pièce non validée ou non structurée")
        # Réutilise la validation de l'équilibre et de la précision.
        try:
            calculer_balance_scf([piece])
        except EcritureSCFInvalide as exc:
            raise ExportRefuse("Pièce invalide ou déséquilibrée") from exc
        for ligne in piece["lignes"]:
            writer.writerow([
                _safe(piece["date_ecriture"]), _safe(piece["journal"]),
                _safe(piece["reference"]), _safe(ligne["compte"]),
                ligne["debit"], ligne["credit"], _safe(piece["libelle"]),
            ])
    return out.getvalue()
