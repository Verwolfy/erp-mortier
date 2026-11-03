"""Brouillons documentaires NEXTGEN, sans écriture métier ni validation fiscale."""
from __future__ import annotations
from datetime import date
from io import BytesIO
import json
from uuid import uuid4

import streamlit as st

COMPANY = "SARL NEXT GENRATION BUILDING SOLUTIONS"
ADDRESS = "ERRICH Bt N°3, BLOC N°3, Et N°2, SECTION N° 7, ILOT N°48, BOUIRA"
RC = "10/00-0285651 B26"
NIF = "002610028565199"
EMAIL = "contact@nextgen-buildingsolutions.com"

DOCUMENTS = {
    "Ventes": ["Devis", "Bon de commande client", "Facture", "Avoir", "Bon de livraison"],
    "Achats": ["Demande d'achat", "Bon de commande fournisseur", "Bon de réception", "Contrôle facture fournisseur"],
    "Stocks": ["Bon de consommation", "Bon de sortie", "Transfert de stock", "Inventaire"],
    "Production": ["Ordre de fabrication", "Rapport de fabrication", "Contrôle qualité"],
    "Finance": ["Accusé interne d'encaissement", "Ordre de paiement"],
    "RH": ["Demande de congé", "Feuille de temps"],
}
FISCAL = {"Facture", "Avoir"}
COLUMNS = ["Référence", "Désignation", "Unité", "Quantité", "Prix unitaire", "Montant HT"]


def new_draft(kind: str) -> dict:
    if kind not in {name for values in DOCUMENTS.values() for name in values}:
        raise ValueError("Type documentaire inconnu")
    return {
        "type": kind, "numero": "BROUILLON", "date": date.today().isoformat(),
        "tiers_nom": "", "tiers_adresse": "", "objet": "",
        "items": [], "total_ht": "", "total_taxes": "", "total_ttc": "",
        "observations": "", "trace_id": "NG-" + uuid4().hex.upper(),
        "statut": "BROUILLON",
    }


def validate_draft(doc: dict) -> None:
    if not isinstance(doc, dict) or doc.get("type") not in {x for xs in DOCUMENTS.values() for x in xs}:
        raise ValueError("Document invalide")
    if not isinstance(doc.get("trace_id"), str) or not doc["trace_id"].startswith("NG-"):
        raise ValueError("Identifiant de traçabilité invalide")
    if not isinstance(doc.get("items"), list) or len(doc["items"]) > 200:
        raise ValueError("Nombre de lignes incorrect")
    for item in doc["items"]:
        if not isinstance(item, dict):
            raise ValueError("Ligne de document invalide")


def tracking_payload(doc: dict) -> str:
    """QR hors ligne : une identité, pas une URL de suivi fictive."""
    validate_draft(doc)
    return json.dumps({"issuer": NIF, "id": doc["trace_id"],
                       "type": doc["type"], "number": str(doc.get("numero", ""))[:100],
                       "date": str(doc.get("date", ""))[:20]}, ensure_ascii=False,
                      sort_keys=True, separators=(",", ":"))


def _safe(value: object) -> str:
    return str(value if value is not None else "").encode("latin-1", "replace").decode("latin-1")[:250]


def export_pdf(doc: dict, logo_path: str | None = None) -> bytes:
    """Export A4 multipage, brouillon visible. Aucun calcul fiscal."""
    validate_draft(doc)
    import qrcode
    from fpdf import FPDF
    pdf = FPDF()
    pdf.set_auto_page_break(auto=True, margin=34)
    pdf.add_page()
    if logo_path:
        from pathlib import Path
        if Path(logo_path).is_file():
            pdf.image(logo_path, x=12, y=10, w=33)
    pdf.set_xy(47, 12)
    pdf.set_font("Helvetica", "B", 12)
    pdf.set_text_color(15, 43, 80)
    pdf.multi_cell(148, 7, _safe(COMPANY))
    pdf.set_text_color(0, 0, 0)
    pdf.set_xy(10, 34)
    pdf.set_font("Helvetica", "B", 17)
    pdf.cell(0, 12, _safe(doc["type"]).upper(), align="C", ln=True)
    pdf.set_font("Helvetica", "B", 11)
    pdf.set_text_color(190, 37, 38)
    pdf.cell(0, 7, "BROUILLON - NON VALABLE / NON EMIS", align="C", ln=True)
    pdf.set_text_color(0, 0, 0)
    pdf.set_font("Helvetica", "", 10)
    for label, value in [
        ("N°", doc.get("numero", "")), ("Date", doc.get("date", "")),
        ("Tiers", doc.get("tiers_nom", "")), ("Adresse", doc.get("tiers_adresse", "")),
        ("Objet", doc.get("objet", "")),
    ]:
        pdf.set_x(10)
        pdf.multi_cell(190, 6, _safe(label + " : " + str(value)))
    pdf.ln(5)
    pdf.set_x(10)
    pdf.set_fill_color(15, 43, 80)
    pdf.set_text_color(255, 255, 255)
    pdf.set_font("Helvetica", "B", 9)
    widths = [27, 55, 19, 22, 32, 35]
    for head, width in zip(COLUMNS, widths):
        pdf.cell(width, 8, _safe(head), border=1, fill=True)
    pdf.ln()
    pdf.set_text_color(0, 0, 0)
    pdf.set_font("Helvetica", "", 8)
    for item in doc["items"]:
        if pdf.get_y() > 247:
            pdf.add_page()
        values = [item.get(x, "") for x in ("reference", "designation", "unite", "quantite", "prix_unitaire", "total_ht")]
        for value, width in zip(values, widths):
            pdf.cell(width, 7, _safe(value)[:35], border=1)
        pdf.ln()
    pdf.ln(5)
    pdf.set_font("Helvetica", "B", 10)
    for label, key in (("Total HT", "total_ht"), ("Taxes - valeur fournie", "total_taxes"),
                       ("Total TTC", "total_ttc")):
        if doc.get(key) not in ("", None):
            pdf.cell(0, 7, _safe(f"{label} : {doc[key]} DZD"), ln=True, align="R")
    if doc.get("observations"):
        pdf.set_font("Helvetica", "", 9)
        pdf.multi_cell(0, 5, _safe("Observations : " + str(doc["observations"])))
    qr = qrcode.make(tracking_payload(doc))
    bio = BytesIO()
    qr.save(bio, format="PNG")
    bio.seek(0)
    if pdf.get_y() > 228:
        pdf.add_page()
    y = pdf.get_y() + 2
    pdf.image(bio, x=158, y=y, w=30, h=30)
    pdf.set_xy(12, y + 6)
    pdf.set_font("Helvetica", "", 8)
    pdf.multi_cell(140, 5, _safe("Traçabilité locale : " + doc["trace_id"]))
    pdf.set_y(-30)
    pdf.set_draw_color(17, 120, 91)
    pdf.line(10, 266, 200, 266)
    pdf.set_font("Helvetica", "", 7.5)
    pdf.set_xy(10, 268)
    pdf.multi_cell(190, 4, _safe(ADDRESS) + "\n" +
                   _safe("RC: " + RC + " | NIF: " + NIF + " | " + EMAIL), align="C")
    result = pdf.output(dest="S")
    return bytes(result) if not isinstance(result, str) else result.encode("latin-1")


def export_docx(doc: dict, logo_path: str | None = None) -> bytes:
    validate_draft(doc)
    from docx import Document
    from docx.shared import Cm, Pt, RGBColor
    from pathlib import Path
    document = Document()
    sec = document.sections[0]
    sec.header_distance = Cm(1)
    sec.footer_distance = Cm(1)
    header = sec.header.paragraphs[0]
    if logo_path and Path(logo_path).is_file():
        header.add_run().add_picture(logo_path, width=Cm(3))
    header.add_run("  " + COMPANY).bold = True
    document.add_heading(doc["type"].upper(), 0)
    p = document.add_paragraph("BROUILLON - NON VALABLE / NON EMIS")
    p.runs[0].font.color.rgb = RGBColor(190, 37, 38)
    for label, key in (("N°", "numero"), ("Date", "date"), ("Tiers", "tiers_nom"),
                       ("Adresse", "tiers_adresse"), ("Objet", "objet")):
        paragraph = document.add_paragraph()
        paragraph.add_run(label + " : ").bold = True
        paragraph.add_run(str(doc.get(key, "")))
    table = document.add_table(rows=1, cols=6)
    table.style = "Table Grid"
    for cell, value in zip(table.rows[0].cells, COLUMNS):
        cell.text = value
    for item in doc["items"]:
        for cell, key in zip(table.add_row().cells, ("reference", "designation", "unite",
                                                   "quantite", "prix_unitaire", "total_ht")):
            cell.text = str(item.get(key, ""))
    for label, key in (("Total HT", "total_ht"), ("Taxes (montant fourni)", "total_taxes"),
                       ("Total TTC", "total_ttc")):
        if doc.get(key) not in ("", None):
            document.add_paragraph(f"{label} : {doc[key]} DZD")
    document.add_paragraph("Observations : " + str(doc.get("observations", "")))
    import qrcode
    qr = qrcode.make(tracking_payload(doc))
    image = BytesIO()
    qr.save(image, format="PNG")
    image.seek(0)
    document.add_picture(image, width=Cm(3))
    document.add_paragraph("Identifiant QR : " + doc["trace_id"])
    foot = sec.footer.paragraphs[0]
    foot.text = ADDRESS + "\nRC: " + RC + " | NIF: " + NIF + " | " + EMAIL
    foot.style = document.styles["Normal"]
    out = BytesIO()
    document.save(out)
    return out.getvalue()


def show_documents_page():
    st.title("Documents administratifs NEXTGEN")
    st.caption("20 modèles - édition de brouillons et exports PDF/DOCX sans écriture Supabase")
    st.warning("Aucune pièce officielle n'est émise ici. Le QR fournit un identifiant unique, pas encore un suivi en ligne.")
    group = st.selectbox("Module", list(DOCUMENTS), key="doc_group")
    kind = st.selectbox("Type de document", DOCUMENTS[group], key="doc_kind")
    doc_key = "nextgen_doc_draft"
    if st.session_state.get("nextgen_doc_type") != kind:
        for widget_key in ("doc_number", "doc_date", "doc_tiers", "doc_address",
                           "doc_subject", "doc_lines"):
            st.session_state.pop(widget_key, None)
        st.session_state[doc_key] = new_draft(kind)
        st.session_state["nextgen_doc_type"] = kind
    doc = st.session_state[doc_key]
    doc["numero"] = st.text_input("Numéro / référence", value=doc["numero"], key="doc_number")
    doc["date"] = str(st.date_input("Date", value=date.fromisoformat(doc["date"]), key="doc_date"))
    doc["tiers_nom"] = st.text_input("Client / fournisseur / service", value=doc["tiers_nom"], key="doc_tiers")
    doc["tiers_adresse"] = st.text_input("Adresse", value=doc["tiers_adresse"], key="doc_address")
    doc["objet"] = st.text_input("Objet", value=doc["objet"], key="doc_subject")
    import pandas as pd
    if not doc["items"]:
        doc["items"] = [{"reference": "", "designation": "", "unite": "",
                          "quantite": "", "prix_unitaire": "", "total_ht": ""}]
    df = pd.DataFrame(doc["items"])
    st.subheader("Lignes")
    edited = st.data_editor(df, num_rows="dynamic", hide_index=True, key="doc_lines")
    doc["items"] = edited.fillna("").to_dict("records")
    if kind in FISCAL:
        st.error("Document fiscal : aucun taux calculé, émission finale bloquée.")
    c1, c2, c3 = st.columns(3)
    doc["total_ht"] = c1.text_input("Total HT (fourni)", value=doc["total_ht"])
    doc["total_taxes"] = c2.text_input("Taxes (fournies)", value=doc["total_taxes"])
    doc["total_ttc"] = c3.text_input("Total TTC (fourni)", value=doc["total_ttc"])
    doc["observations"] = st.text_area("Observations", value=doc["observations"])
    st.code(doc["trace_id"], language=None)
    try:
        logo = "assets/nextgen_logo.jpg"
        pdf = export_pdf(doc, logo)
        word = export_docx(doc, logo)
    except (ValueError, RuntimeError, ImportError) as exc:
        st.error(f"Export indisponible : {type(exc).__name__}")
        return
    left, right = st.columns(2)
    left.download_button("Exporter PDF (brouillon)", pdf,
                         file_name=doc["trace_id"] + ".pdf", mime="application/pdf")
    right.download_button("Exporter Word modifiable", word,
                          file_name=doc["trace_id"] + ".docx",
                          mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document")
    st.download_button("Exporter JSON (brouillon)", json.dumps(doc, ensure_ascii=False, indent=2),
                       file_name=doc["trace_id"] + ".json", mime="application/json")
