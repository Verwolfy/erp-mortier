"""Contrats hors ligne du générateur de brouillons NEXTGEN."""
from io import BytesIO
from zipfile import ZipFile
import pytest
from modules.documents.views import (
    DOCUMENTS, COMPANY, EMAIL, new_draft, validate_draft,
    tracking_payload, export_pdf, export_docx,
)


def test_catalogue_20_modeles():
    assert sum(len(items) for items in DOCUMENTS.values()) == 20
    assert COMPANY == "SARL NEXT GENRATION BUILDING SOLUTIONS"
    assert EMAIL == "contact@nextgen-buildingsolutions.com"


def test_qr_uniques_sans_lien_non_deploye():
    first, second = new_draft("Bon de livraison"), new_draft("Bon de livraison")
    assert first["trace_id"] != second["trace_id"]
    assert "https://" not in tracking_payload(first)
    assert first["trace_id"] in tracking_payload(first)


def test_refus_documents_malformes():
    with pytest.raises(ValueError):
        new_draft("Document inconnu")
    doc = new_draft("Facture")
    doc["items"] = ["texte"]
    with pytest.raises(ValueError):
        validate_draft(doc)


def test_generation_brouillon_pdf_et_word():
    doc = new_draft("Bon de consommation")
    doc.update(numero="BCONS-EXEMPLE", tiers_nom="Atelier", objet="Essai hors ligne")
    doc["items"] = [{"reference": "MP-EXEMPLE", "designation": "Essai",
                     "unite": "KG", "quantite": "2",
                     "prix_unitaire": "", "total_ht": ""}]
    pdf = export_pdf(doc, None)
    assert pdf[:4] == b"%PDF"
    docx = export_docx(doc, None)
    assert docx[:2] == b"PK"
    with ZipFile(BytesIO(docx)) as archive:
        text = archive.read("word/document.xml").decode("utf-8")
    assert "BROUILLON" in text
    assert doc["trace_id"] in text


def test_logo_corrompu_ne_bloque_pas_les_exports(tmp_path):
    """Régression Streamlit PIL.UnidentifiedImageError."""
    broken = tmp_path / "nextgen_logo.jpg"
    broken.write_bytes(b"not-a-real-image")
    doc = new_draft("Bon de livraison")
    assert export_pdf(doc, str(broken)).startswith(b"%PDF")
    assert export_docx(doc, str(broken)).startswith(b"PK")


def test_pdf_brouillon_une_page_et_qr_vectoriel():
    """Une pièce presque vide ne doit plus créer un pied de page isolé."""
    import re
    doc = new_draft("Devis")
    doc["items"] = [{"reference": "", "designation": "", "unite": "",
                     "quantite": "", "prix_unitaire": "", "total_ht": ""}]
    output = export_pdf(doc, None)
    assert len(re.findall(rb"/Type\s*/Page\b", output)) == 1
    import zlib
    streams = re.findall(rb"stream\r?\n(.*?)\r?\nendstream", output, re.DOTALL)
    decoded = []
    for stream in streams:
        try:
            decoded.append(zlib.decompress(stream))
        except zlib.error:
            decoded.append(stream)
    assert doc["trace_id"].encode("ascii") in b" ".join(decoded)


def test_logo_officiel_est_lisible_et_exportable():
    """Le fichier du dépôt doit être un vrai JPEG et non un blob corrompu."""
    from pathlib import Path
    from PIL import Image
    logo = Path("assets/nextgen_logo.jpg")
    assert logo.is_file()
    with Image.open(logo) as picture:
        picture.verify()
    doc = new_draft("Facture")
    assert export_pdf(doc, str(logo)).startswith(b"%PDF")
    assert export_docx(doc, str(logo)).startswith(b"PK")


def test_colonnes_et_signatures_par_metier():
    from modules.documents.layout_nextgen import columns_for, signature_labels, FINANCIAL_KINDS
    assert "quantite_livree" in dict(columns_for("Bon de livraison"))
    assert "visa" in dict(columns_for("Bon de consommation"))
    assert "prix_unitaire" not in dict(columns_for("Bon de consommation"))
    assert "Bon pour accord" in signature_labels("Devis")[1]
    assert "Facture" in FINANCIAL_KINDS


def test_exports_brouillons_tous_documents():
    from modules.documents.layout_nextgen import columns_for
    for kinds in DOCUMENTS.values():
        for kind in kinds:
            draft = new_draft(kind)
            draft["items"] = [{key: "Test" if key == "designation" else ""
                               for key, _ in columns_for(kind)}]
            assert export_pdf(draft, None).startswith(b"%PDF")
            assert export_docx(draft, None).startswith(b"PK")


def test_pdf_multilignes_longues_sans_exception():
    from modules.documents.layout_nextgen import columns_for
    doc = new_draft("Bon de livraison")
    doc["items"] = [
        dict([(key, ("Désignation très longue de matériau industriel " * 5)
               if key == "designation" else "1") for key, _ in columns_for(doc["type"])])
        for _ in range(55)
    ]
    assert export_pdf(doc, None).startswith(b"%PDF")


def test_images_entete_pied_nextgen():
    from PIL import Image
    from modules.documents.branding_images import branded_images
    header, footer = branded_images("assets/nextgen_logo.jpg")
    for data, expected in ((header, (1500, 330)), (footer, (1500, 174))):
        with Image.open(BytesIO(data)) as image:
            assert image.format == "PNG"
            assert image.size == expected


def test_pdf_images_reelles_et_une_page():
    from modules.documents.branding_images import branded_images
    doc = new_draft("Devis")
    pdf = export_pdf(doc, "assets/nextgen_logo.jpg")
    assert pdf.startswith(b"%PDF")
    assert b"/Subtype /Image" in pdf
    assert len(__import__("re").findall(rb"/Type\s*/Page\b", pdf)) == 1


def test_editeur_documents_sans_dataframe_js():
    from pathlib import Path
    source = Path("modules/documents/views.py").read_text(encoding="utf-8")
    section = source.split("def show_documents_page():", 1)[1]
    assert "st.data_editor(" not in section
    assert "st.text_input(" in section
    assert "ng_line_add" in section
