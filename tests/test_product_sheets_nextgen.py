"""Tests hors ligne des fiches FT/FDS NEXTGEN (aucune écriture Supabase)."""
from io import BytesIO
from zipfile import ZipFile

import pytest

from modules.documents.product_sheets import (
    TECHNICAL, SAFETY, TECHNICAL_SECTIONS, SAFETY_SECTIONS,
    new_product_sheet, sections_for, validate_product_sheet,
    sheet_tracking_payload, export_product_sheet_pdf, export_product_sheet_docx,
)


@pytest.mark.parametrize("kind,count", [(TECHNICAL, 10), (SAFETY, 16)])
def test_sections_et_brouillon_par_defaut(kind, count):
    sheet = new_product_sheet(kind)
    assert len(sections_for(kind)) == count
    assert len(sheet["sections"]) == count
    assert all(value == "" for value in sheet["sections"].values())
    assert sheet["statut"] == "BROUILLON_NON_VALIDE"
    assert sheet["reference"] == "BROUILLON"


def test_qr_ne_simule_pas_le_suivi_en_ligne():
    first, second = new_product_sheet(SAFETY), new_product_sheet(SAFETY)
    assert first["trace_id"] != second["trace_id"]
    payload = sheet_tracking_payload(first)
    assert "https://" not in payload
    assert first["trace_id"] in payload


def test_refus_validation_et_contenu_incorrect():
    with pytest.raises(ValueError):
        new_product_sheet("inconnu")
    sheet = new_product_sheet(SAFETY)
    sheet["statut"] = "VALIDÉ"
    with pytest.raises(ValueError):
        validate_product_sheet(sheet)
    sheet["statut"] = "BROUILLON_NON_VALIDE"
    sheet["sections"].pop("s14")
    with pytest.raises(ValueError):
        validate_product_sheet(sheet)


@pytest.mark.parametrize("kind", [TECHNICAL, SAFETY])
def test_export_pdf_word_modifiables_sans_donnees_inventees(kind):
    sheet = new_product_sheet(kind)
    sheet["produit"] = "Produit essai"
    sheet["code_produit"] = "EX-01"
    sheet["sections"][next(iter(sheet["sections"]))] = "Texte validable par laboratoire"
    pdf = export_product_sheet_pdf(sheet)
    word = export_product_sheet_docx(sheet)
    assert pdf.startswith(b"%PDF")
    assert len(pdf) > 1000
    assert word.startswith(b"PK")
    with ZipFile(BytesIO(word)) as z:
        xml = z.read("word/document.xml").decode("utf-8")
    assert "BROUILLON" in xml
    assert sheet["trace_id"] in xml
    assert "Produit essai" in xml
    assert "Non renseigné" in xml
    if kind == SAFETY:
        assert len(SAFETY_SECTIONS) == 16
        assert "Informations toxicologiques" in xml
    else:
        assert len(TECHNICAL_SECTIONS) == 10
        assert "Caractéristiques et performances" in xml
