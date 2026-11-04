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


def _verified_logo(logo_path: str | None) -> str | None:
    """Un logo absent ou endommagé ne doit jamais empêcher un export."""
    if not logo_path:
        return None
    from pathlib import Path
    from PIL import Image, UnidentifiedImageError
    path = Path(logo_path)
    if not path.is_file():
        return None
    try:
        with Image.open(path) as picture:
            picture.verify()
        return str(path)
    except (UnidentifiedImageError, OSError, ValueError):
        return None


def _draw_qr_vector(pdf, doc: dict, x: float, y: float, size: float = 36) -> None:
    """Dessine un QR vectoriel à modules carrés, indépendant du codec image."""
    import qrcode
    code = qrcode.QRCode(error_correction=qrcode.constants.ERROR_CORRECT_M, border=4)
    code.add_data(tracking_payload(doc))
    code.make(fit=True)
    matrix = code.get_matrix()
    step = size / len(matrix)
    pdf.set_fill_color(255, 255, 255)
    pdf.rect(x, y, size, size, style="F")
    pdf.set_fill_color(0, 0, 0)
    for row_no, row in enumerate(matrix):
        for col_no, filled in enumerate(row):
            if filled:
                pdf.rect(x + col_no * step, y + row_no * step,
                         step + 0.01, step + 0.01, style="F")


def export_pdf(doc: dict, logo_path: str | None = None) -> bytes:
    """PDF harmonisé NEXTGEN, brouillon non émis et QR hors ligne."""
    validate_draft(doc)
    from modules.documents.layout_nextgen import render_pdf
    return render_pdf(
        doc, _verified_logo(logo_path),
        company=COMPANY, address=ADDRESS, rc=RC, nif=NIF, email=EMAIL,
        tracking_payload=tracking_payload, draw_qr=_draw_qr_vector,
    )


def export_docx(doc: dict, logo_path: str | None = None) -> bytes:
    validate_draft(doc)
    from docx import Document
    from docx.shared import Cm, Pt, RGBColor
    document = Document()
    sec = document.sections[0]
    sec.header_distance = Cm(1)
    sec.footer_distance = Cm(1)
    header = sec.header.paragraphs[0]
    valid_logo = _verified_logo(logo_path)
    if valid_logo:
        header.add_run().add_picture(valid_logo, width=Cm(3))
    header.add_run("  " + COMPANY).bold = True
    document.add_heading(doc["type"].upper(), 0)
    p = document.add_paragraph("BROUILLON - NON VALABLE / NON EMIS")
    p.runs[0].font.color.rgb = RGBColor(190, 37, 38)
    for label, key in (("N°", "numero"), ("Date", "date"), ("Tiers", "tiers_nom"),
                       ("Adresse", "tiers_adresse"), ("Objet", "objet")):
        paragraph = document.add_paragraph()
        paragraph.add_run(label + " : ").bold = True
        paragraph.add_run(str(doc.get(key, "")))
    from modules.documents.layout_nextgen import columns_for, signature_labels, FINANCIAL_KINDS
    columns = columns_for(doc["type"])
    table = document.add_table(rows=1, cols=len(columns))
    table.style = "Table Grid"
    for cell, (_, value) in zip(table.rows[0].cells, columns):
        cell.text = value
    for item in doc["items"]:
        for cell, (key, _) in zip(table.add_row().cells, columns):
            cell.text = str(item.get(key, ""))
    if doc["type"] in FINANCIAL_KINDS:
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
    for label in signature_labels(doc["type"]):
        document.add_paragraph(label + " : __________________________")
    foot = sec.footer.paragraphs[0]
    foot.text = ADDRESS + "\nRC: " + RC + " | NIF: " + NIF + " | " + EMAIL
    foot.style = document.styles["Normal"]
    out = BytesIO()
    document.save(out)
    return out.getvalue()


def show_documents_page():
    st.title("Documents administratifs NEXTGEN")
    st.caption("20 modèles administratifs + fiches techniques et FDS - exports PDF/DOCX sans écriture Supabase")
    st.warning("Aucune pièce officielle n'est émise ici. Le QR fournit un identifiant unique, pas encore un suivi en ligne.")
    group = st.selectbox("Module", list(DOCUMENTS) + ["Fiches produits"], key="doc_group")
    if group == "Fiches produits":
        from modules.documents.product_sheets import show_product_sheets_page
        show_product_sheets_page()
        return
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
    from modules.documents.layout_nextgen import columns_for, FINANCIAL_KINDS
    columns = columns_for(kind)
    if not doc["items"]:
        doc["items"] = [{key: "" for key, _ in columns}]
    df = pd.DataFrame(doc["items"])
    for key, _ in columns:
        if key not in df:
            df[key] = ""
    df = df[[key for key, _ in columns]]
    st.subheader("Lignes")
    edited = st.data_editor(df, num_rows="dynamic", hide_index=True, key="doc_lines",
                            column_config={key: st.column_config.TextColumn(label)
                                           for key, label in columns})
    doc["items"] = edited.fillna("").to_dict("records")
    if kind in FISCAL:
        st.error("Document fiscal : aucun taux calculé, émission finale bloquée.")
    if kind in FINANCIAL_KINDS:
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
