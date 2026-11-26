"""Exports tabulaires NEXTGEN : XLSX, CSV et PDF de consultation.

Aucune donnée n'est chargée ici : l'appelant fournit exclusivement des lignes
déjà autorisées par RBAC. Aucun export ne crée de pièce légale/fiscale/SCF.
"""
from __future__ import annotations

import csv
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from io import BytesIO, StringIO
from pathlib import Path
import re
from typing import Mapping, Sequence

NAVY = "0C2B50"
GREEN = "048B5B"
PALE = "F0F4F8"
WHITE = "FFFFFF"
MAX_ROWS = 10000
MAX_PDF_ROWS = 250
MAX_COLUMNS = 28
MAX_CELL = 10000
_NUMERIC = re.compile(
    r"(?:montant|quantit|qte|prix|co[uû]t|cmp|pmp|valeur|debit|cr[eé]dit|"
    r"solde|taux|poids|facteur|heures|remise|total|entrees|sorties|stock_"
    r"|nombre|probabilit)", re.IGNORECASE)
_NUMTEXT = re.compile(r"[+-]?(?:\d+\.?\d*|\.\d+)\Z")
_UNSAFE = re.compile(r"^[\s\x00-\x1f]*[=+@-]")
_FILENAME = re.compile(r"[^A-Za-z0-9_-]+")


class ExportError(ValueError):
    """Impossible d'exporter sans perte, validation ou droits en amont."""


def _text(value: object) -> str:
    if value is None:
        return ""
    if isinstance(value, (date, datetime)):
        value = value.isoformat()
    elif isinstance(value, (dict, list, tuple)):
        import json
        value = json.dumps(value, ensure_ascii=False, sort_keys=True, default=str)
    text = str(value).replace("\x00", "")
    if len(text) > MAX_CELL:
        raise ExportError("Valeur trop longue : export refusé pour éviter une coupure")
    return text


def _guard(rows: Sequence[Mapping], columns: Sequence[str], fmt: str) -> list[list[object]]:
    if fmt not in {"xlsx", "csv", "pdf"}:
        raise ExportError("Format d'export inconnu")
    if not isinstance(rows, (list, tuple)) or not isinstance(columns, (list, tuple)):
        raise ExportError("Données d'export invalides")
    if not 1 <= len(columns) <= MAX_COLUMNS or len(set(columns)) != len(columns):
        raise ExportError("Colonnes d'export invalides")
    if any(not isinstance(c, str) or not c or len(c) > 128 for c in columns):
        raise ExportError("Nom de colonne invalide")
    if len(rows) > (MAX_PDF_ROWS if fmt == "pdf" else MAX_ROWS):
        raise ExportError(
            "Export trop volumineux : réduire le périmètre ou choisir Excel/CSV"
            if fmt == "pdf" else "Volume au-delà de la limite d'export"
        )
    data = []
    for row in rows:
        if not isinstance(row, Mapping):
            raise ExportError("Ligne d'export invalide")
        data.append([row.get(key) for key in columns])
        for value in data[-1]:
            _text(value)
    return data


def _safe_spreadsheet(value: object) -> str:
    text = _text(value)
    # Les nombres négatifs sont des nombres, pas des formules.
    if _UNSAFE.match(text) and not _NUMTEXT.fullmatch(text):
        return "'" + text
    return text


def _safe_excel(value: object, column: str):
    if value is None:
        return None
    if isinstance(value, bool):
        return value
    numeric = isinstance(value, (int, float, Decimal)) or bool(_NUMERIC.search(column))
    if numeric:
        raw = _text(value).strip()
        if _NUMTEXT.fullmatch(raw):
            try:
                dec = Decimal(raw)
            except InvalidOperation:
                dec = None
            if dec is not None and dec.is_finite() and len(dec.normalize().as_tuple().digits) <= 15:
                return int(dec) if dec == dec.to_integral_value() else float(dec)
    return _safe_spreadsheet(value)


def export_csv(rows: Sequence[Mapping], columns: Sequence[str]) -> bytes:
    table = _guard(rows, columns, "csv")
    stream = StringIO(newline="")
    writer = csv.writer(stream, delimiter=";", lineterminator="\r\n",
                        quoting=csv.QUOTE_MINIMAL)
    writer.writerow(columns)
    for row in table:
        writer.writerow([_safe_spreadsheet(v) for v in row])
    return ("\ufeff" + stream.getvalue()).encode("utf-8")


def export_excel(
    rows: Sequence[Mapping], columns: Sequence[str], *,
    title: str, warning: str,
) -> bytes:
    table = _guard(rows, columns, "xlsx")
    from openpyxl import Workbook
    from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
    from openpyxl.utils import get_column_letter

    wb = Workbook()
    ws = wb.active
    ws.title = "Rapport NEXTGEN"
    last = get_column_letter(len(columns))
    ws.merge_cells(f"A1:{last}1") if len(columns) > 1 else None
    ws.merge_cells(f"A2:{last}2") if len(columns) > 1 else None
    ws.merge_cells(f"A3:{last}3") if len(columns) > 1 else None
    ws["A1"] = "NEXTGEN | " + _text(title)[:170]
    ws["A2"] = "SARL NEXT GENRATION BUILDING SOLUTIONS"
    ws["A3"] = "COPIE INTERNE — " + _text(warning)[:320]
    ws["A4"] = "Édité le " + date.today().isoformat()
    for row_num, color, foreground, size in (
        (1, NAVY, WHITE, 15), (2, NAVY, WHITE, 11),
        (3, PALE, NAVY, 10), (4, WHITE, GREEN, 9),
    ):
        for cell in ws[row_num][:len(columns)]:
            cell.fill = PatternFill("solid", fgColor=color)
            cell.font = Font(name="Calibri", size=size, bold=row_num <= 2,
                             color=foreground)
            cell.alignment = Alignment(vertical="center", wrap_text=True)
    for num, height in ((1, 31), (2, 23), (3, 31), (4, 21), (5, 26)):
        ws.row_dimensions[num].height = height
    for index, field in enumerate(columns, 1):
        header = ws.cell(5, index, field)
        header.fill = PatternFill("solid", fgColor=GREEN)
        header.font = Font(name="Calibri", size=10, bold=True, color=WHITE)
        header.alignment = Alignment(vertical="center", wrap_text=True)
        ws.column_dimensions[get_column_letter(index)].width = min(36, max(16, len(field) + 4))
    for num, row in enumerate(table, 6):
        for col, value in enumerate(row, 1):
            v = _safe_excel(value, columns[col - 1])
            cell = ws.cell(num, col, v)
            cell.fill = PatternFill("solid", fgColor=WHITE if num % 2 == 0 else PALE)
            cell.font = Font(name="Calibri", size=9, color=NAVY)
            cell.alignment = Alignment(vertical="top", wrap_text=True)
            if type(v) in (int, float):
                cell.number_format = "#,##0.############"
        ws.row_dimensions[num].height = 19
    ws.freeze_panes = "B6" if len(columns) > 1 else "A6"
    ws.auto_filter.ref = f"A5:{last}{max(5, len(table) + 5)}"
    ws.print_title_rows = "1:5"
    ws.sheet_properties.pageSetUpPr.fitToPage = True
    ws.page_setup.orientation = "landscape" if len(columns) > 6 else "portrait"
    ws.page_setup.fitToWidth = 1
    ws.page_setup.fitToHeight = 0
    ws.oddFooter.center.text = "NEXTGEN | Consultation interne - non émise"
    ws.oddFooter.right.text = "Page &P / &N"
    wb.properties.creator = "NEXTGEN ERP"
    wb.properties.title = _text(title)[:255]
    output = BytesIO()
    wb.save(output)
    return output.getvalue()


def _latin(value: object) -> str:
    from modules.documents.party_identity import pdf_safe
    return pdf_safe(_text(value))


def _wrap(pdf, text: str, width: float, *, max_lines: int = 3) -> list[str]:
    # Pas de découpe silencieuse : l'abréviation est annoncée dans l'en-tête.
    remaining = _latin(text)
    lines = []
    while remaining and len(lines) < max_lines:
        slice_end = min(len(remaining), 250)
        while slice_end > 1 and pdf.get_string_width(remaining[:slice_end]) > width - 3:
            slice_end -= 1
        lines.append(remaining[:slice_end])
        remaining = remaining[slice_end:]
    if not lines:
        lines = [""]
    if remaining:
        lines[-1] = (lines[-1][:-3] if len(lines[-1]) > 3 else "") + "..."
    return lines


def export_pdf(
    rows: Sequence[Mapping], columns: Sequence[str], *,
    title: str, warning: str,
) -> bytes:
    table = _guard(rows, columns, "pdf")
    from fpdf import FPDF
    from io import BytesIO
    from modules.documents.branding_images import branded_images
    path = Path("assets/nextgen_logo_hd.jpg")
    header, footer = branded_images(str(path) if path.is_file() else None)

    class BrandedPDF(FPDF):
        def header(self):
            self.image(BytesIO(header), x=0, y=0, w=210, h=46.2)
        def footer(self):
            self.image(BytesIO(footer), x=0, y=268, w=210, h=24.36)
            self.set_y(-8)
            self.set_font("Helvetica", "", 7)
            self.set_text_color(12, 43, 80)
            self.cell(190, 5, f"Page {self.page_no()}/{{nb}}", align="R")

    pdf = BrandedPDF(format="A4", unit="mm")
    pdf.alias_nb_pages()
    pdf.set_auto_page_break(auto=False)
    key = columns[0]
    # PDF portrait : la référence est répétée sur chaque volet d'un tableau large.
    others = columns[1:]
    panels = [[key] + others[i:i + 3] for i in range(0, len(others), 3)] if others else [[key]]
    for panel_num, panel in enumerate(panels, 1):
        pdf.add_page()
        pdf.set_y(49)
        pdf.set_font("Helvetica", "B", 14)
        pdf.set_text_color(12, 43, 80)
        pdf.multi_cell(190, 7, _latin(title)[:115])
        pdf.set_font("Helvetica", "B", 8)
        pdf.set_text_color(160, 30, 30)
        pdf.multi_cell(190, 4, _latin("COPIE INTERNE - " + warning)[:235])
        pdf.set_font("Helvetica", "", 8)
        pdf.set_text_color(80, 86, 95)
        pdf.multi_cell(190, 4, "Volet %d/%d - %d lignes. Valeurs longues abregees pour la lecture PDF ; "
                       "Excel/CSV conservent le texte complet." % (panel_num, len(panels), len(table)))
        pdf.ln(3)
        widths = [38] + [152 / (len(panel) - 1)] * (len(panel) - 1) if len(panel) > 1 else [190]
        def header_row():
            pdf.set_fill_color(12, 43, 80)
            pdf.set_text_color(255, 255, 255)
            pdf.set_font("Helvetica", "B", 8)
            for width, field in zip(widths, panel):
                pdf.cell(width, 8, _latin(field)[:22], border=1, fill=True)
            pdf.ln(8)
            pdf.set_font("Helvetica", "", 7.8)
            pdf.set_text_color(10, 25, 44)
        header_row()
        for row in table:
            parts = [_wrap(pdf, _text(row[columns.index(c)]), w)
                     for c, w in zip(panel, widths)]
            height = max(7, 4.2 * max(len(x) for x in parts) + 2)
            if pdf.get_y() + height > 263:
                pdf.add_page()
                pdf.set_y(49)
                header_row()
            y = pdf.get_y()
            x = 10
            for width, strings in zip(widths, parts):
                pdf.rect(x, y, width, height)
                pdf.set_xy(x + 1, y + 1)
                for line in strings:
                    pdf.cell(width - 2, 4.2, line)
                    pdf.set_xy(x + 1, pdf.get_y() + 4.2)
                x += width
            pdf.set_xy(10, y + height)

    # QR du rapport : recherche par titre/date/empreinte, aucune donnée en clair.
    from hashlib import sha256
    import json
    from modules.documents.pdf_presentation import draw_qr, qr_payload
    digest = sha256()
    for record in table:
        digest.update(json.dumps(
            [_text(v) for v in record], ensure_ascii=False,
            separators=(",", ":")).encode("utf-8"))
        digest.update(b"\\n")
    snapshot = {
        "kind": "Rapport ERP", "id": _text(title).strip()[:128] or "Rapport ERP",
        "date": date.today().isoformat(), "source": "export_formats",
        "columns": list(columns), "row_count": len(table),
        "digest_source": digest.hexdigest(), "statut": "CONSULTATION",
    }
    if pdf.get_y() > 212:
        pdf.add_page()
        pdf.set_y(51)
    qr_y = pdf.get_y() + 5
    draw_qr(pdf, qr_payload(snapshot), x=168, y=qr_y, size=30)
    pdf.set_xy(10, qr_y + 5)
    pdf.set_font("Helvetica", "", 8)
    pdf.multi_cell(150, 5, "QR de repérage de rapport - copie interne non émise")
    return bytes(pdf.output())


def build_export(
    rows: Sequence[Mapping], columns: Sequence[str], *,
    fmt: str, title: str, warning: str = "rapport de consultation non certifié",
) -> tuple[bytes, str, str]:
    _guard(rows, columns, fmt)
    if fmt == "csv":
        return export_csv(rows, columns), "text/csv", "csv"
    if fmt == "xlsx":
        return export_excel(rows, columns, title=title, warning=warning), (
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"), "xlsx"
    return export_pdf(rows, columns, title=title, warning=warning), "application/pdf", "pdf"


def export_filename(title: str, fmt: str) -> str:
    slug = _FILENAME.sub("_", _text(title).strip()).strip("_")[:70] or "rapport"
    return f"NEXTGEN_{slug}_{date.today().isoformat()}.{fmt}"
