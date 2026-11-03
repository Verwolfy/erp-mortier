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
    assert doc["trace_id"].encode("ascii") in output
