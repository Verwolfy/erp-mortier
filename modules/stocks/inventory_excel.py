"""ERP-057 : modèle et validation stricte des comptages Excel (.xlsx).

Le classeur n'est jamais exécuté : cellules-formules interdites, taille et
nombre de lignes bornés, références vérifiées contre la photographie en base.
L'import n'écrit rien ; seul l'appel RPC atomique le fera après prévisualisation.
"""
from __future__ import annotations

from decimal import Decimal, InvalidOperation
from io import BytesIO
from typing import Mapping, Sequence
import re

MAX_IMPORT_BYTES = 2_000_000
MAX_IMPORT_ROWS = 500
FIELDS = ("type_article", "article_id", "quantite_comptee", "motif_ecart")
_ALLOWED_NUMBER = re.compile(r"(0|[1-9][0-9]*)(\.[0-9]+)?\Z")


class InventoryImportError(ValueError):
    pass


def _number(raw: object) -> str:
    if isinstance(raw, bool) or raw is None or not isinstance(raw, (str, int, float, Decimal)):
        raise InventoryImportError("Quantité invalide")
    txt = str(raw).strip()
    if not 1 <= len(txt) <= 45 or not _ALLOWED_NUMBER.fullmatch(txt):
        raise InventoryImportError("Quantité invalide : utiliser un nombre décimal positif avec point")
    try:
        n = Decimal(txt)
    except InvalidOperation as exc:
        raise InventoryImportError("Quantité invalide") from exc
    if not n.is_finite() or n < 0 or n >= Decimal("1e15"):
        raise InventoryImportError("Quantité hors limites")
    return format(n, "f")


def export_count_template(snapshot: Sequence[Mapping], *, campaign_id: str | None = None) -> bytes:
    """Modèle neutre : aucune quantité physique n'est préremplie."""
    if not isinstance(snapshot, (list, tuple)) or len(snapshot) > 5000:
        raise InventoryImportError("Photographie incomplète")
    from openpyxl import Workbook
    from openpyxl.styles import Font, PatternFill, Alignment
    from openpyxl.utils import get_column_letter
    wb = Workbook()
    ws = wb.active
    ws.title = "Comptages"
    ws.merge_cells("A1:D1")
    ws["A1"] = "NEXTGEN — COMPTAGES INVENTAIRE"
    ws["A1"].fill = PatternFill("solid", fgColor="0C2B50")
    ws["A1"].font = Font(color="FFFFFF", bold=True, size=15)
    ws.row_dimensions[1].height = 30
    ws.merge_cells("A2:D2")
    ws["A2"] = "Ne renseigner que les quantités réellement comptées. Colonnes et identifiants inchangés."
    ws.merge_cells("A3:D3")
    ws["A3"] = "Aucune entrée/sortie ni validation comptable produite par ce fichier."
    ws["A4"] = "CAMPAGNE:" + (campaign_id or "MODELE")
    for index, key in enumerate(FIELDS, 1):
        cell = ws.cell(5, index, key)
        cell.fill = PatternFill("solid", fgColor="048B5B")
        cell.font = Font(color="FFFFFF", bold=True)
        cell.alignment = Alignment(wrap_text=True)
        ws.column_dimensions[get_column_letter(index)].width = [17, 42, 25, 55][index - 1]
    for i, line in enumerate(snapshot, 6):
        kind, article = line.get("type_article"), line.get("article_id")
        if kind not in ("MP", "PF") or not isinstance(article, str) or not article:
            raise InventoryImportError("Photographie invalide")
        ws.cell(i, 1, kind)
        ws.cell(i, 2, article)
        ws.cell(i, 2).number_format = "@"
        # Quantité physiquement observée, jamais le stock théorique :
        ws.cell(i, 3, None)
        ws.cell(i, 4, None)
    ws.freeze_panes = "C6"
    ws.auto_filter.ref = f"A5:D{max(5, 5+len(snapshot))}"
    wb.properties.creator = "NEXTGEN ERP"
    wb.properties.title = "Inventaire — modèle de comptage vierge"
    out = BytesIO()
    wb.save(out)
    return out.getvalue()


def parse_count_workbook(data: bytes, snapshot: Sequence[Mapping], *, campaign_id: str | None = None) -> list[dict]:
    if not isinstance(data, bytes) or not 0 < len(data) <= MAX_IMPORT_BYTES:
        raise InventoryImportError("Fichier Excel absent ou trop volumineux (2 Mo max)")
    if not isinstance(snapshot, (list, tuple)) or len(snapshot) > 5000:
        raise InventoryImportError("Photographie d'inventaire non vérifiable")
    from openpyxl import load_workbook
    try:
        workbook = load_workbook(BytesIO(data), read_only=True,
                                 data_only=False, keep_links=False)
    except Exception as exc:
        raise InventoryImportError("Classeur XLSX invalide") from exc
    try:
        if len(workbook.sheetnames) != 1:
            raise InventoryImportError("Un seul onglet de comptage est autorisé")
        sheet = workbook.active
        if sheet.max_column != 4:
            raise InventoryImportError("Colonnes supplémentaires interdites")
        if campaign_id is not None and sheet["A4"].value != "CAMPAGNE:" + campaign_id:
            raise InventoryImportError("Ce fichier appartient à une autre campagne")
        header = None
        for n, row in enumerate(sheet.iter_rows(min_row=1, max_row=5, max_col=4), 1):
            cells = tuple(v.value for v in row)
            if cells == FIELDS:
                header = n
                break
        if header is None:
            raise InventoryImportError("Colonnes requises : " + ", ".join(FIELDS))
        # Le fichier peut inclure les références non comptées : ces lignes
        # restent vides et sont ignorées ; une référence hors snapshot échoue.
        keys = {(r.get("type_article"), r.get("article_id")): r
                for r in snapshot if isinstance(r, Mapping)}
        if len(keys) != len(snapshot):
            raise InventoryImportError("Références de la photographie dupliquées")
        seen: set[tuple[str, str]] = set()
        result: list[dict] = []
        for n, cells in enumerate(sheet.iter_rows(min_row=header+1, max_col=4), header+1):
            if n > header + 5002:
                raise InventoryImportError("Fichier trop long")
            if any(getattr(c, "data_type", None) == "f" for c in cells):
                raise InventoryImportError("Formules Excel interdites dans le fichier")
            kind, article, raw, motive = (cell.value for cell in cells)
            if all(value is None or value == "" for value in (kind, article, raw, motive)):
                continue
            if not isinstance(kind, str) or kind not in ("MP", "PF"):
                raise InventoryImportError(f"Type d'article invalide, ligne {n}")
            if not isinstance(article, str) or not article.strip() or article != article.strip():
                raise InventoryImportError(f"Référence non textuelle/invalide, ligne {n}")
            key = (kind, article)
            if key not in keys:
                raise InventoryImportError(f"Article absent de cette campagne, ligne {n}")
            if key in seen:
                raise InventoryImportError(f"Article en double, ligne {n}")
            seen.add(key)
            # Ligne de modèle laissée volontairement non comptée.
            if raw is None or raw == "":
                if motive not in (None, ""):
                    raise InventoryImportError(f"Motif fourni sans quantité, ligne {n}")
                continue
            qty = _number(raw)
            if motive is None:
                motive = ""
            if not isinstance(motive, str) or len(motive) > 600:
                raise InventoryImportError(f"Motif invalide, ligne {n}")
            expected = Decimal(str(keys[key].get("quantite_theorique")))
            if not expected.is_finite() or expected < 0:
                raise InventoryImportError("Stock théorique non vérifiable")
            if Decimal(qty) != expected and len(motive.strip()) < 5:
                raise InventoryImportError(f"Écart sans justification, ligne {n}")
            result.append({"type_article": kind, "article_id": article,
                           "quantite_comptee": qty, "motif_ecart": motive.strip()})
            if len(result) > MAX_IMPORT_ROWS:
                raise InventoryImportError("Limite de 500 comptages par import")
        if not result:
            raise InventoryImportError("Aucune quantité physique renseignée")
        return result
    finally:
        workbook.close()
