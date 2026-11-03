"""Brouillons FT/FDS NEXTGEN au graphisme de la facture de référence.

Aucune donnée produit, classification SGH ou propriété technique n'est inventée.
Les PDF/Word produits ici ne constituent pas des documents validés.
"""
from __future__ import annotations

from datetime import date
from io import BytesIO
import json
from pathlib import Path
from uuid import uuid4

COMPANY = "SARL NEXT GENRATION BUILDING SOLUTIONS"
ADDRESS = "ERRICH Bt N°3, BLOC N°3, Et N°2, SECTION N° 7, ILOT N°48, BOUIRA"
RC = "10/00-0285651 B26"
NIF = "002610028565199"
EMAIL = "contact@nextgen-buildingsolutions.com"
NAVY = (10, 49, 83)
GREEN = (9, 148, 78)
LIGHT = (237, 240, 243)

TECHNICAL = "Fiche technique"
SAFETY = "Fiche de données de sécurité"

TECHNICAL_SECTIONS = (
    ("identification", "1. Identification et description du produit"),
    ("applications", "2. Domaines d'application et usages"),
    ("caracteristiques", "3. Caractéristiques et performances vérifiées"),
    ("support", "4. Préparation des supports"),
    ("mise_en_oeuvre", "5. Mode d'emploi et mise en oeuvre"),
    ("consommation", "6. Consommation, rendement et temps de mise en oeuvre"),
    ("conditionnement", "7. Conditionnement et conservation"),
    ("precautions", "8. Précautions d'utilisation"),
    ("normes", "9. Normes, essais et documents de référence"),
    ("assistance", "10. Assistance technique et observations"),
)

# Les seize rubriques du format SGH/FDS : uniquement des intitulés,
# sans classification ni valeur produit préremplie.
SAFETY_SECTIONS = (
    ("s01", "1. Identification de la substance/du mélange et de la société"),
    ("s02", "2. Identification des dangers"),
    ("s03", "3. Composition et informations sur les composants"),
    ("s04", "4. Premiers secours"),
    ("s05", "5. Mesures de lutte contre l'incendie"),
    ("s06", "6. Mesures à prendre en cas de dispersion accidentelle"),
    ("s07", "7. Manipulation et stockage"),
    ("s08", "8. Contrôles de l'exposition et protection individuelle"),
    ("s09", "9. Propriétés physiques et chimiques"),
    ("s10", "10. Stabilité et réactivité"),
    ("s11", "11. Informations toxicologiques"),
    ("s12", "12. Informations écologiques"),
    ("s13", "13. Considérations relatives à l'élimination"),
    ("s14", "14. Informations relatives au transport"),
    ("s15", "15. Informations relatives à la réglementation"),
    ("s16", "16. Autres informations et références"),
)


def sections_for(kind: str) -> tuple[tuple[str, str], ...]:
    if kind == TECHNICAL:
        return TECHNICAL_SECTIONS
    if kind == SAFETY:
        return SAFETY_SECTIONS
    raise ValueError("Type de fiche inconnu")


def new_product_sheet(kind: str) -> dict:
    sections = sections_for(kind)
    return {
        "type": kind,
        "reference": "BROUILLON",
        "version": "0",
        "date": date.today().isoformat(),
        "produit": "",
        "code_produit": "",
        "conditionnement": "",
        "responsable": "",
        "sections": {key: "" for key, _ in sections},
        "trace_id": "NG-" + uuid4().hex.upper(),
        "statut": "BROUILLON_NON_VALIDE",
    }


def validate_product_sheet(sheet: dict) -> None:
    if not isinstance(sheet, dict):
        raise ValueError("Fiche invalide")
    sections = sections_for(sheet.get("type"))
    if sheet.get("statut") != "BROUILLON_NON_VALIDE":
        raise ValueError("Seuls les brouillons non validés sont exportables")
    if not isinstance(sheet.get("trace_id"), str) or not sheet["trace_id"].startswith("NG-"):
        raise ValueError("Identifiant de traçabilité incorrect")
    for key in ("reference", "version", "date", "produit", "code_produit",
                "conditionnement", "responsable"):
        if not isinstance(sheet.get(key), str) or len(sheet[key]) > 300:
            raise ValueError("Métadonnées invalides : " + key)
    values = sheet.get("sections")
    if not isinstance(values, dict) or set(values) != {key for key, _ in sections}:
        raise ValueError("Rubriques FT/FDS incomplètes")
    if any(not isinstance(value, str) or len(value) > 10000 for value in values.values()):
        raise ValueError("Contenu de rubrique invalide")


def sheet_tracking_payload(sheet: dict) -> str:
    """Identification interne, sans URL ni promesse de suivi public."""
    validate_product_sheet(sheet)
    return json.dumps(
        {"issuer": NIF, "id": sheet["trace_id"], "type": sheet["type"],
         "reference": sheet["reference"], "revision": sheet["version"]},
        ensure_ascii=False, sort_keys=True, separators=(",", ":"),
    )


def _latin(value: object, limit: int = 10000) -> str:
    return str(value or "").replace("\t", " ").encode(
        "latin-1", "replace"
    ).decode("latin-1")[:limit]


def _qr_image(sheet: dict) -> BytesIO:
    import qrcode
    stream = BytesIO()
    qrcode.make(sheet_tracking_payload(sheet)).save(stream, format="PNG")
    stream.seek(0)
    return stream


def export_product_sheet_pdf(sheet: dict, logo_path: str | None = None) -> bytes:
    """Export A4 multipage, bandeau bleu/vert, encarts gris et QR interne."""
    validate_product_sheet(sheet)
    from fpdf import FPDF

    class SheetPDF(FPDF):
        def header(self):
            self.set_text_color(*NAVY)
            self.set_draw_color(*NAVY)
            if logo_path and Path(logo_path).is_file():
                self.image(str(logo_path), x=12, y=9, w=29)
            self.set_xy(46, 11)
            self.set_font("Helvetica", "B", 12)
            self.multi_cell(152, 6, _latin(COMPANY))
            self.set_draw_color(*GREEN)
            self.set_line_width(1.1)
            self.line(10, 40 if self.page_no() == 1 else 29,
                      200, 40 if self.page_no() == 1 else 29)
            self.set_line_width(0.2)
            if self.page_no() == 1:
                self.set_fill_color(*NAVY)
                self.set_text_color(255, 255, 255)
                self.set_xy(42, 46)
                self.set_font("Helvetica", "B", 15)
                heading = "FICHE TECHNIQUE" if sheet["type"] == TECHNICAL else "FICHE DE DONNEES DE SECURITE"
                self.cell(126, 12, heading, fill=True, align="C")
                self.set_fill_color(*GREEN)
                self.rect(168, 46, 4, 12, "F")
                self.set_fill_color(*LIGHT)
                self.set_text_color(*NAVY)
                self.set_font("Helvetica", "B", 9)
                self.set_xy(10, 64)
                self.cell(95, 8, _latin("Réf. : " + sheet["reference"], 70), fill=True)
                self.cell(95, 8, _latin("Révision : " + sheet["version"], 70), fill=True)
                self.set_xy(10, 74)
                self.cell(95, 8, _latin("Date : " + sheet["date"], 70), fill=True)
                self.cell(95, 8, _latin("Code : " + sheet["code_produit"], 70), fill=True)
                self.set_xy(10, 86)
                self.set_font("Helvetica", "B", 11)
                self.set_text_color(*NAVY)
                self.multi_cell(190, 6, _latin("PRODUIT : " + (sheet["produit"] or "NON RENSEIGNÉ"), 200))
                self.set_font("Helvetica", "B", 9)
                self.set_text_color(171, 35, 37)
                self.set_x(10)
                self.cell(190, 8, "BROUILLON - DOCUMENT TECHNIQUE NON VALIDE", align="C")
                self.set_y(max(self.get_y() + 9, 109))
            else:
                self.set_xy(10, 32)
                self.set_font("Helvetica", "B", 9)
                self.cell(160, 6, _latin(sheet["type"].upper() + " - " + sheet["produit"], 100))
                self.set_text_color(171, 35, 37)
                self.cell(30, 6, "BROUILLON", align="R")
                self.set_y(42)

        def footer(self):
            self.set_y(-28)
            self.set_draw_color(*NAVY)
            self.line(10, self.get_y(), 200, self.get_y())
            self.set_y(-25)
            self.set_text_color(*NAVY)
            self.set_font("Helvetica", "", 7)
            self.multi_cell(190, 4, _latin(ADDRESS, 190), align="C")
            self.cell(190, 4, _latin("RC : " + RC + "  |  NIF : " + NIF + "  |  " + EMAIL), align="C")
            self.set_y(-11)
            self.set_text_color(90, 90, 90)
            self.cell(190, 5, "Page " + str(self.page_no()) + "/{nb} - BROUILLON", align="C")

    pdf = SheetPDF(orientation="P", unit="mm", format="A4")
    pdf.alias_nb_pages()
    pdf.set_auto_page_break(auto=True, margin=31)
    pdf.add_page()
    pdf.set_text_color(*NAVY)
    pdf.set_font("Helvetica", "", 9)
    pdf.multi_cell(190, 5, _latin(
        "Conditionnement : " + (sheet["conditionnement"] or "Non renseigné") +
        "    |    Responsable : " + (sheet["responsable"] or "Non renseigné"),
        250))
    pdf.ln(2)

    for key, heading in sections_for(sheet["type"]):
        if pdf.get_y() > 245:
            pdf.add_page()
        pdf.set_x(10)
        pdf.set_fill_color(*NAVY)
        pdf.set_text_color(255, 255, 255)
        pdf.set_font("Helvetica", "B", 9)
        pdf.multi_cell(190, 7, _latin(heading), fill=True)
        pdf.set_text_color(20, 28, 39)
        value = sheet["sections"][key].strip()
        pdf.set_font("Helvetica", "" if value else "I", 9)
        pdf.set_x(12)
        pdf.multi_cell(185, 5, _latin(value) if value else "Non renseigné - données à vérifier avant validation")
        pdf.ln(4)

    if pdf.get_y() > 222:
        pdf.add_page()
    pdf.ln(2)
    y = pdf.get_y()
    pdf.set_draw_color(*NAVY)
    pdf.rect(10, y, 141, 28)
    pdf.set_xy(13, y + 3)
    pdf.set_font("Helvetica", "B", 9)
    pdf.set_text_color(*NAVY)
    pdf.cell(133, 6, "Rédaction : __________________    Vérification : __________________")
    pdf.set_xy(13, y + 13)
    pdf.cell(133, 6, "Approbation : ________________    Date : _______________________")
    qr = _qr_image(sheet)
    pdf.image(qr, x=160, y=y, w=28, h=28)
    pdf.set_xy(10, y + 29)
    pdf.set_font("Helvetica", "", 8)
    pdf.set_text_color(70, 70, 70)
    pdf.cell(190, 5, _latin("QR interne : " + sheet["trace_id"], 120), align="R")

    result = pdf.output(dest="S")
    return bytes(result) if not isinstance(result, str) else result.encode("latin-1")


def export_product_sheet_docx(sheet: dict, logo_path: str | None = None) -> bytes:
    """Word modifiable reprenant les couleurs, les métadonnées et le suivi QR."""
    validate_product_sheet(sheet)
    from docx import Document
    from docx.shared import Cm, Pt, RGBColor
    from docx.enum.text import WD_ALIGN_PARAGRAPH

    document = Document()
    section = document.sections[0]
    section.top_margin = Cm(2)
    section.bottom_margin = Cm(2.3)
    section.header_distance = Cm(0.8)
    section.footer_distance = Cm(0.8)
    header = section.header.paragraphs[0]
    if logo_path and Path(logo_path).is_file():
        header.add_run().add_picture(str(logo_path), width=Cm(2.3))
    company_run = header.add_run("    " + COMPANY)
    company_run.bold = True
    company_run.font.color.rgb = RGBColor(*NAVY)
    title = document.add_heading(sheet["type"].upper(), 0)
    title.alignment = WD_ALIGN_PARAGRAPH.CENTER
    for run in title.runs:
        run.font.color.rgb = RGBColor(*NAVY)
    alert = document.add_paragraph("BROUILLON - DOCUMENT TECHNIQUE NON VALIDÉ")
    alert.alignment = WD_ALIGN_PARAGRAPH.CENTER
    alert.runs[0].bold = True
    alert.runs[0].font.color.rgb = RGBColor(171, 35, 37)
    table = document.add_table(rows=0, cols=2)
    table.style = "Table Grid"
    for left, right in (
        ("Référence : " + sheet["reference"], "Révision : " + sheet["version"]),
        ("Date : " + sheet["date"], "Code : " + sheet["code_produit"]),
        ("Produit : " + sheet["produit"], "Conditionnement : " + sheet["conditionnement"]),
    ):
        cells = table.add_row().cells
        cells[0].text, cells[1].text = left, right
    document.add_paragraph("Responsable : " + sheet["responsable"])

    for key, heading in sections_for(sheet["type"]):
        h = document.add_heading(heading, level=2)
        for run in h.runs:
            run.font.color.rgb = RGBColor(*NAVY)
        value = sheet["sections"][key].strip()
        paragraph = document.add_paragraph(value or "Non renseigné - données à vérifier avant validation")
        if not value:
            paragraph.runs[0].italic = True
    document.add_paragraph("Rédaction : __________________    Vérification : __________________")
    document.add_paragraph("Approbation : ________________    Date : _______________________")
    document.add_picture(_qr_image(sheet), width=Cm(2.6))
    document.add_paragraph("QR interne : " + sheet["trace_id"])
    footer = section.footer.paragraphs[0]
    footer.text = ADDRESS + "\nRC : " + RC + " | NIF : " + NIF + " | " + EMAIL
    footer.alignment = WD_ALIGN_PARAGRAPH.CENTER
    for run in footer.runs:
        run.font.size = Pt(7.5)
    out = BytesIO()
    document.save(out)
    return out.getvalue()


def show_product_sheets_page() -> None:
    """Éditeur autonome : aucun appel ni écriture Supabase."""
    import streamlit as st
    st.subheader("Fiches techniques et de données de sécurité")
    st.caption("Charte NEXTGEN : bleu marine, vert, bandeaux, blocs gris, QR interne et pied de page.")
    st.warning(
        "Export de brouillon uniquement. Les performances, classifications de danger, "
        "mesures de protection et références réglementaires doivent provenir de sources "
        "vérifiées et être approuvées avant diffusion."
    )
    kind = st.radio("Modèle", (TECHNICAL, SAFETY), horizontal=True, key="ng_sheet_kind")
    if st.session_state.get("ng_sheet_selected") != kind:
        st.session_state["ng_sheet_selected"] = kind
        st.session_state["ng_product_sheet"] = new_product_sheet(kind)
    sheet = st.session_state["ng_product_sheet"]
    a, b = st.columns(2)
    sheet["produit"] = a.text_input("Désignation du produit", value=sheet["produit"], key="ng_sheet_product")
    sheet["code_produit"] = b.text_input("Code produit/SKU", value=sheet["code_produit"], key="ng_sheet_code")
    a, b, c = st.columns(3)
    sheet["reference"] = a.text_input("Référence du document", value=sheet["reference"], key="ng_sheet_ref")
    sheet["version"] = b.text_input("Révision", value=sheet["version"], key="ng_sheet_revision")
    sheet["date"] = c.text_input("Date (AAAA-MM-JJ)", value=sheet["date"], key="ng_sheet_date")
    a, b = st.columns(2)
    sheet["conditionnement"] = a.text_input("Conditionnement", value=sheet["conditionnement"], key="ng_sheet_pack")
    sheet["responsable"] = b.text_input("Responsable de rédaction", value=sheet["responsable"], key="ng_sheet_author")
    st.divider()
    for key, heading in sections_for(kind):
        sheet["sections"][key] = st.text_area(
            heading, value=sheet["sections"][key], height=90,
            key="ng_sheet_section_" + kind[:5] + "_" + key,
            placeholder="À renseigner à partir des données techniques ou de sécurité vérifiées",
        )
    try:
        logo = "logo_entreprise.png"
        pdf = export_product_sheet_pdf(sheet, logo)
        docx = export_product_sheet_docx(sheet, logo)
    except (ValueError, RuntimeError, ImportError) as exc:
        st.error("Export non disponible : " + type(exc).__name__)
        return
    fname = ("FT" if kind == TECHNICAL else "FDS") + "_" + sheet["trace_id"]
    left, right = st.columns(2)
    left.download_button("Exporter PDF (brouillon)", pdf, file_name=fname + ".pdf",
                         mime="application/pdf")
    right.download_button("Exporter Word modifiable", docx, file_name=fname + ".docx",
                          mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document")
    st.download_button("Exporter JSON (brouillon)",
                       json.dumps(sheet, ensure_ascii=False, indent=2),
                       file_name=fname + ".json", mime="application/json")
    st.caption("Identifiant QR local : " + sheet["trace_id"] + " (aucun suivi en ligne).")
