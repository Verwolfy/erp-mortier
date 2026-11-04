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


def test_polices_corporate_tailles_reelles():
    from modules.documents.branding_images import _font
    company_font = _font(49, bold=True)
    footer_font = _font(20)
    assert company_font.getbbox("NEXTGEN")[3] - company_font.getbbox("NEXTGEN")[1] >= 23
    assert footer_font.getbbox("BOUIRA")[3] - footer_font.getbbox("BOUIRA")[1] >= 11


def test_calcul_ht_ttc_decimal_sans_taux_implicite():
    from modules.documents.calculations import calculate_financial_draft
    rows = [
        {"reference": "1", "designation": "FENEK BOND", "quantite": "10",
         "prix_unitaire": "300"},
        {"reference": "2", "designation": "FENEK FLOW", "quantite": "2",
         "prix_unitaire": "100000"},
    ]
    output = calculate_financial_draft(rows, "2000")
    assert output["errors"] == []
    assert [x["total_ht"] for x in output["items"]] == ["3000.00", "200000.00"]
    assert output["total_ht"] == "203000.00"
    assert output["total_ttc"] == "205000.00"
    assert "total_ht" not in rows[0]  # aucune mutation
    assert calculate_financial_draft(rows)["total_ttc"] == ""


def test_calcul_refuse_incomplet_et_montants_invalides():
    from modules.documents.calculations import calculate_financial_draft
    assert calculate_financial_draft([{"designation": "Produit", "quantite": "3"}])["errors"]
    assert calculate_financial_draft([{"designation": "Produit", "quantite": "-1", "prix_unitaire": "2"}])["errors"]
    assert calculate_financial_draft([{"designation": "Produit", "quantite": "NaN", "prix_unitaire": "2"}])["errors"]
    assert calculate_financial_draft([{"designation": "Produit", "quantite": "1,5", "prix_unitaire": "2"}])["total_ht"] == "3.00"
    assert calculate_financial_draft([{"designation": "Produit", "quantite": "1", "prix_unitaire": "2"}], "-1")["errors"]
    assert calculate_financial_draft([{"designation": "Produit", "quantite": "1", "prix_unitaire": "2"}], "19%")["errors"]


def test_ui_montants_non_editables_et_calcules():
    from pathlib import Path
    source = Path("modules/documents/views.py").read_text(encoding="utf-8")
    section = source.split("def show_documents_page():", 1)[1]
    assert 'field == "total_ht"' in section
    assert "calculate_financial_draft(" in section
    assert "Montant des taxes validé" in section


def test_logo_hd_bytes_compatible_pdf_docx():
    """Image HD importée dans Streamlit sans écriture Supabase."""
    from PIL import Image
    from modules.documents.views import _verified_logo
    from modules.documents.branding_images import branded_images
    image = Image.new("RGB", (2048, 868), "white")
    output = BytesIO()
    image.save(output, format="JPEG", quality=90)
    logo_bytes = output.getvalue()
    assert _verified_logo(logo_bytes) == logo_bytes
    header, footer = branded_images(logo_bytes)
    with Image.open(BytesIO(header)) as picture:
        assert picture.size == (1500, 330)
    assert footer.startswith(b"\x89PNG")
    draft = new_draft("Devis")
    assert export_pdf(draft, logo_bytes).startswith(b"%PDF")
    assert export_docx(draft, logo_bytes).startswith(b"PK")
    assert _verified_logo(b"invalid-picture") is None
    assert _verified_logo(b"x" * (4 * 1024 * 1024 + 1)) is None


def test_interface_logo_hd_disponible():
    from pathlib import Path
    source = Path("modules/documents/views.py").read_text(encoding="utf-8")
    assert "ng_brand_logo_upload" in source
    assert "logo_override or" in source


def test_logo_original_hd_installe_et_exportable():
    from pathlib import Path
    from PIL import Image
    logo = Path("assets/nextgen_logo_hd.jpg")
    assert logo.is_file()
    with Image.open(logo) as source:
        assert source.size == (2048, 868)
        source.verify()
    draft = new_draft("Facture")
    assert export_pdf(draft, str(logo)).startswith(b"%PDF")
    assert export_docx(draft, str(logo)).startswith(b"PK")
    from modules.documents.branding_images import branded_images
    header, footer = branded_images(str(logo))
    assert header.startswith(b"\x89PNG")
    assert footer.startswith(b"\x89PNG")


def test_symbole_hd_et_typographie_decomposee():
    """Le JPEG horizontal ne doit plus être réduit en un seul mot-symbole flou."""
    from pathlib import Path
    from PIL import Image
    from modules.documents.branding_images import branded_images
    logo = Path("assets/nextgen_logo_hd.jpg")
    with Image.open(logo) as source:
        assert source.width > 2 * source.height
    header, _ = branded_images(str(logo))
    with Image.open(BytesIO(header)) as image:
        # Le mot NEXTGEN reconstruit doit être une zone foncée,
        # distincte du symbole géométrique en haut.
        import numpy as np
        pixel_array = np.asarray(image.convert("RGB"))
        word = pixel_array[180:243, 100:465]
        symbol = pixel_array[23:163, 135:450]
        assert int(((word[:,:,0] < 120) & (word[:,:,2] < 160)).sum()) > 700
        assert int(((symbol[:,:,0] < 120) & (symbol[:,:,1] < 185)).sum()) > 400
