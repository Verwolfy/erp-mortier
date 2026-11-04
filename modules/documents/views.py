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


def _verified_logo(logo_path: str | bytes | None) -> str | bytes | None:
    """Un logo absent ou endommagé ne doit jamais empêcher un export."""
    if not logo_path:
        return None
    from pathlib import Path
    from PIL import Image, UnidentifiedImageError
    try:
        if isinstance(logo_path, bytes):
            if len(logo_path) > 4 * 1024 * 1024:
                return None
            with Image.open(BytesIO(logo_path)) as picture:
                if picture.width < 400 or picture.height < 200:
                    return None
                picture.verify()
            return logo_path
        path = Path(logo_path)
        if not path.is_file():
            return None
        with Image.open(path) as picture:
            picture.verify()
        return str(path)
    except (UnidentifiedImageError, OSError, ValueError, TypeError):
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


def export_pdf(doc: dict, logo_path: str | bytes | None = None) -> bytes:
    """PDF harmonisé NEXTGEN, brouillon non émis et QR hors ligne."""
    validate_draft(doc)
    from modules.documents.calculations import normalize_financial_export
    doc = normalize_financial_export(doc)
    from modules.documents.layout_nextgen import render_pdf
    return render_pdf(
        doc, _verified_logo(logo_path),
        company=COMPANY, address=ADDRESS, rc=RC, nif=NIF, email=EMAIL,
        tracking_payload=tracking_payload, draw_qr=_draw_qr_vector,
    )


def export_docx(doc: dict, logo_path: str | bytes | None = None) -> bytes:
    validate_draft(doc)
    from modules.documents.calculations import normalize_financial_export
    doc = normalize_financial_export(doc)
    from docx import Document
    from docx.shared import Cm, Pt, RGBColor
    from modules.documents.branding_images import branded_images
    document = Document()
    sec = document.sections[0]
    sec.top_margin = Cm(5.3)
    sec.bottom_margin = Cm(3.4)
    sec.left_margin = Cm(1.1)
    sec.right_margin = Cm(1.1)
    sec.header_distance = Cm(0)
    sec.footer_distance = Cm(0.25)
    header_png, footer_png = branded_images(_verified_logo(logo_path))
    header = sec.header.paragraphs[0]
    header.add_run().add_picture(BytesIO(header_png), width=Cm(18.8))
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
    foot.add_run().add_picture(BytesIO(footer_png), width=Cm(18.8))
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
        for widget_key in list(st.session_state):
            if widget_key.startswith("ng_line_") or widget_key in (
                "doc_number", "doc_date", "doc_tiers", "doc_address",
                "doc_subject", "doc_lines", "ng_doc_taxes",
                "ng_party_choice", "ng_sku_choice", "ng_material_choice",
            ):
                st.session_state.pop(widget_key, None)
        st.session_state[doc_key] = new_draft(kind)
        st.session_state["nextgen_doc_type"] = kind
    doc = st.session_state[doc_key]
    st.subheader("Reprendre un brouillon")
    import_file = st.file_uploader(
        "Importer un brouillon JSON exporté précédemment (300 Ko maximum)",
        type=["json"], key="ng_draft_import",
        help="Lecture locale : aucune création de pièce dans Supabase.",
    )
    if st.button("Charger le brouillon JSON", key="ng_draft_import_button",
                 disabled=import_file is None):
        from modules.documents.draft_io import read_draft_json
        try:
            imported = read_draft_json(import_file.getvalue(), kind)
        except ValueError as exc:
            st.error(str(exc))
        else:
            for state_key in list(st.session_state):
                if state_key.startswith("ng_line_") or state_key in (
                    "doc_number", "doc_date", "doc_tiers", "doc_address",
                    "doc_subject", "doc_lines", "ng_doc_taxes",
                ):
                    st.session_state.pop(state_key, None)
            st.session_state[doc_key] = imported
            st.success("Brouillon importé. Identifiant QR conservé.")
            st.rerun()
    # Les référentiels ne sont lus qu'à la demande, via les droits de lecture
    # serveur du service ERP (aucun accès direct avec service_role).
    from modules.documents.prefill import (
        CLIENT_TYPES, SUPPLIER_TYPES, PRODUCT_TYPES, MATERIAL_TYPES,
        list_parties, list_skus, list_materials,
        apply_party, append_sku, append_material,
    )
    with st.expander("Préremplir depuis les référentiels (lecture seule)", expanded=False):
        st.caption("Les données restent modifiables. Aucun document, tarif ou taxe n'est validé automatiquement.")
        if st.button("Charger les référentiels autorisés", key="ng_load_refs"):
            try:
                parties = list_parties(kind)
                skus = list_skus(kind)
                materials = list_materials(kind)
            except (PermissionError, ValueError, RuntimeError, OSError) as exc:
                st.session_state.pop("ng_ref_catalog", None)
                st.error("Lecture des référentiels indisponible ou non autorisée.")
            else:
                st.session_state["ng_ref_catalog"] = {
                    "type": kind, "parties": parties, "skus": skus,
                    "materials": materials
                }
        catalog = st.session_state.get("ng_ref_catalog")
        if isinstance(catalog, dict) and catalog.get("type") == kind:
            parties = catalog.get("parties", [])
            if kind in CLIENT_TYPES or kind in SUPPLIER_TYPES:
                if parties:
                    by_id = {party["id"]: party for party in parties}
                    choice = st.selectbox(
                        "Client / fournisseur",
                        options=[""] + list(by_id),
                        format_func=lambda k: "Sélectionner..." if not k else
                                    by_id[k]["nom"] + " (" + k + ")",
                        key="ng_party_choice",
                    )
                    if st.button("Reprendre les coordonnées du tiers",
                                 key="ng_apply_party", disabled=not choice):
                        st.session_state[doc_key] = apply_party(doc, by_id[choice])
                        for k in ("doc_tiers", "doc_address"):
                            st.session_state.pop(k, None)
                        st.rerun()
                else:
                    st.info("Aucun tiers actif accessible.")
            skus = catalog.get("skus", [])
            if kind in PRODUCT_TYPES:
                if skus:
                    by_sku = {sku["id"]: sku for sku in skus}
                    selected = st.selectbox(
                        "Produit / conditionnement",
                        options=[""] + list(by_sku),
                        format_func=lambda k: "Sélectionner..." if not k else
                                    by_sku[k]["designation"] + " — " + k,
                        key="ng_sku_choice",
                    )
                    if selected:
                        st.caption(
                            "Prix catalogue indicatif : " +
                            (by_sku[selected]["prix_vente_defaut"] or "non renseigné") +
                            " DZD. Prix à saisir et confirmer manuellement."
                        )
                    if st.button("Ajouter ce SKU au brouillon", key="ng_apply_sku",
                                 disabled=not selected):
                        try:
                            st.session_state[doc_key] = append_sku(doc, by_sku[selected])
                        except ValueError as exc:
                            st.error(str(exc))
                        else:
                            for key in list(st.session_state):
                                if key.startswith("ng_line_") and key != "ng_line_add" and key != "ng_line_remove":
                                    st.session_state.pop(key, None)
                            st.rerun()
                else:
                    st.info("Aucun SKU actif accessible.")
            materials = catalog.get("materials", [])
            if kind in MATERIAL_TYPES:
                if materials:
                    by_material = {m["id"]: m for m in materials}
                    selected_mp = st.selectbox(
                        "Matière première",
                        options=[""] + list(by_material),
                        format_func=lambda key: "Sélectionner..." if not key else
                                    by_material[key]["designation"] + " — " + key,
                        key="ng_material_choice",
                    )
                    if st.button("Ajouter cette matière au brouillon",
                                 key="ng_apply_material", disabled=not selected_mp):
                        try:
                            st.session_state[doc_key] = append_material(
                                doc, by_material[selected_mp])
                        except ValueError as exc:
                            st.error(str(exc))
                        else:
                            for key in list(st.session_state):
                                if key.startswith("ng_line_") and key not in (
                                    "ng_line_add", "ng_line_remove"):
                                    st.session_state.pop(key, None)
                            st.rerun()
                else:
                    st.info("Aucune matière première active accessible.")
    doc["numero"] = st.text_input("Numéro / référence", value=doc["numero"], key="doc_number")
    doc["date"] = str(st.date_input("Date", value=date.fromisoformat(doc["date"]), key="doc_date"))
    doc["tiers_nom"] = st.text_input("Client / fournisseur / service", value=doc["tiers_nom"], key="doc_tiers")
    doc["tiers_adresse"] = st.text_input("Adresse", value=doc["tiers_adresse"], key="doc_address")
    doc["objet"] = st.text_input("Objet", value=doc["objet"], key="doc_subject")
    from modules.documents.layout_nextgen import columns_for, FINANCIAL_KINDS
    columns = columns_for(kind)
    if not doc["items"]:
        doc["items"] = [{key: "" for key, _ in columns}]
    st.subheader("Lignes")
    st.caption("Saisie simplifiée, sans composant DataFrame.")
    actions = st.columns(2)
    if actions[0].button("➕ Ajouter une ligne", key="ng_line_add"):
        if len(doc["items"]) < 200:
            doc["items"].append({key: "" for key, _ in columns})
        st.rerun()
    if actions[1].button("➖ Supprimer la dernière ligne", key="ng_line_remove",
                         disabled=len(doc["items"]) <= 1):
        last = len(doc["items"]) - 1
        for field, _ in columns:
            st.session_state.pop(f"ng_line_{last}_{field}", None)
        doc["items"].pop()
        st.rerun()
    updated = []
    for index, item in enumerate(doc["items"]):
        with st.expander(f"Ligne {index + 1}", expanded=index == 0):
            groups = st.columns(2)
            values = {}
            for col_index, (field, label) in enumerate(columns):
                if kind in FINANCIAL_KINDS and field == "total_ht":
                    continue  # colonne dérivée ; jamais de saisie manuelle
                widget_key = f"ng_line_{index}_{field}"
                with groups[col_index % 2]:
                    values[field] = st.text_input(
                        label,
                        value=str(item.get(field, "") or ""),
                        key=widget_key,
                    )
            updated.append(values)
    doc["items"] = updated
    financial_errors = []
    if kind in FISCAL:
        st.warning("Brouillon fiscal uniquement : aucun taux de TVA n'est présumé.")
    if kind in FINANCIAL_KINDS:
        from modules.documents.calculations import calculate_financial_draft
        doc["total_taxes"] = st.text_input(
            "Montant des taxes validé, en DZD (laisser vide si inconnu)",
            value=str(doc.get("total_taxes") or ""), key="ng_doc_taxes",
        )
        result = calculate_financial_draft(doc["items"], doc["total_taxes"])
        doc["items"] = result["items"]
        doc["total_ht"] = result["total_ht"]
        doc["total_ttc"] = result["total_ttc"]
        financial_errors = result["errors"]
        for error in financial_errors:
            st.error(error)
        if doc["total_ht"]:
            st.metric("Total HT calculé", f'{doc["total_ht"]} DZD')
        else:
            st.caption("Total HT indisponible tant que les lignes ne sont pas complètes.")
        if doc["total_ttc"]:
            st.metric("Total TTC (taxes saisies)", f'{doc["total_ttc"]} DZD')
        else:
            st.caption("Total TTC non calculé sans montant de taxes validé.")
        st.caption("Aucun taux fiscal calculé automatiquement ; brouillon non émis.")
    doc["observations"] = st.text_area("Observations", value=doc["observations"])
    st.code(doc["trace_id"], language=None)
    st.subheader("Identité visuelle")
    st.caption("Logo officiel HD NEXTGEN installé par défaut (2048 × 868 pixels).")
    uploaded_logo = st.file_uploader(
        "Logo officiel haute définition (JPG ou PNG, 4 Mo maximum)",
        type=["jpg", "jpeg", "png"], key="ng_brand_logo_upload",
        help="Utilisé uniquement pour les exports de cette session ; aucune écriture Supabase.",
    )
    logo_override = None
    if uploaded_logo is not None:
        logo_override = _verified_logo(uploaded_logo.getvalue())
        if logo_override is None:
            st.error("Image invalide : utilisez un logo d'au moins 400 × 200 pixels, inférieur à 4 Mo.")
        else:
            st.caption("Logo haute définition chargé pour les PDF et Word de cette session.")
    if financial_errors:
        st.warning("Corrige les montants avant tout export.")
        return
    try:
        logo = logo_override or "assets/nextgen_logo_hd.jpg"
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
