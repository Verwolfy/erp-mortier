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


def test_export_pdf_n_utilise_plus_ln_ni_dest_deprecies():
    import warnings

    facture = new_draft("Facture")
    facture["items"] = [{
        "reference": "REF", "designation": "Échantillon",
        "unite": "SAC", "quantite": "2", "prix_unitaire": "150",
    }]
    livraison = new_draft("Bon de livraison")
    livraison["items"] = [{"reference": "REF", "designation": "Échantillon",
                           "unite": "SAC", "quantite": "2"}]
    with warnings.catch_warnings(record=True) as captured:
        warnings.simplefilter("always", DeprecationWarning)
        assert export_pdf(facture).startswith(b"%PDF")
        assert export_pdf(livraison).startswith(b"%PDF")
    forbidden = [
        str(item.message)
        for item in captured
        if issubclass(item.category, DeprecationWarning)
        and ('parameter "ln"' in str(item.message)
             or '"dest" parameter' in str(item.message))
    ]
    assert forbidden == []


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


def test_exports_financiers_recalculent_ht_et_refusent_incoherence():
    from copy import deepcopy
    doc = new_draft("Facture")
    doc["items"] = [{
        "reference": "P1", "designation": "Produit démo", "unite": "SAC",
        "quantite": "10", "prix_unitaire": "300",
    }]
    original = deepcopy(doc)
    # Totaux manquants : le moteur les déduit sur la copie d'impression.
    pdf = export_pdf(doc)
    word = export_docx(doc)
    assert pdf.startswith(b"%PDF")
    assert word.startswith(b"PK")
    assert doc == original
    from zipfile import ZipFile
    with ZipFile(BytesIO(word)) as zf:
        xml = zf.read("word/document.xml").decode("utf-8")
        assert "3000.00" in xml

    doc["items"][0]["total_ht"] = "2999"
    with pytest.raises(ValueError, match="incohérent"):
        export_pdf(doc)
    with pytest.raises(ValueError, match="incohérent"):
        export_docx(doc)


def test_exports_refusent_ttc_incoherent_et_taxes_sans_ligne():
    doc = new_draft("Devis")
    doc["items"] = [{"designation": "Produit", "quantite": "2",
                     "prix_unitaire": "100"}]
    doc["total_taxes"] = "10"
    doc["total_ttc"] = "999"
    with pytest.raises(ValueError, match="total_ttc incohérent"):
        export_pdf(doc)
    doc["total_ttc"] = "210.00"
    assert export_pdf(doc).startswith(b"%PDF")
    doc["items"] = [{"designation": "Maquette non chiffrée"}]
    with pytest.raises(ValueError):
        export_docx(doc)


def test_montants_excessifs_refuses_avec_erreur_metier():
    from modules.documents.calculations import calculate_financial_draft
    result = calculate_financial_draft([{
        "designation": "Excès", "quantite": "999999999999",
        "prix_unitaire": "999999999999",
    }])
    assert result["errors"] and "excessif" in result["errors"][0]


def test_import_json_brouillon_rond_trip():
    import json
    from modules.documents.draft_io import read_draft_json
    draft = new_draft("Bon de livraison")
    draft["numero"] = "BL-DEMO-01"
    draft["tiers_nom"] = "Client essai"
    draft["items"] = [{"reference": "P1", "designation": "Produit",
                       "unite": "SAC", "quantite": "10",
                       "quantite_livree": "8", "observation": "2 en attente"}]
    result = read_draft_json(json.dumps(draft).encode("utf-8"), "Bon de livraison")
    assert result["trace_id"] == draft["trace_id"]
    assert result["numero"] == draft["numero"]
    assert result["items"][0]["quantite_livree"] == "8"
    assert export_pdf(result).startswith(b"%PDF")
    assert export_docx(result).startswith(b"PK")


def test_import_refuse_type_statut_trace_et_limites():
    import json
    from modules.documents.draft_io import read_draft_json
    draft = new_draft("Facture")
    def decode(value, kind="Facture"):
        return read_draft_json(json.dumps(value).encode("utf-8"), kind)
    with pytest.raises(ValueError, match="même type"):
        decode(draft, "Devis")
    draft["statut"] = "EMIS"
    with pytest.raises(ValueError, match="BROUILLON"):
        decode(draft)
    draft["statut"] = "BROUILLON"
    draft["trace_id"] = "NG-INVALID"
    with pytest.raises(ValueError, match="QR"):
        decode(draft)
    draft["trace_id"] = new_draft("Facture")["trace_id"]
    draft["items"] = [{}] * 201
    with pytest.raises(ValueError, match="200"):
        decode(draft)
    with pytest.raises(ValueError, match="volumineux"):
        read_draft_json(b"x" * 300001, "Facture")
    with pytest.raises(ValueError, match="invalide"):
        read_draft_json(b"{", "Facture")


def test_ui_import_json_existe_sans_stockage_supabase():
    from pathlib import Path
    source = Path("modules/documents/views.py").read_text(encoding="utf-8")
    assert "ng_draft_import_button" in source
    assert "read_draft_json(" in source


def test_prefill_clients_fournisseurs_et_sku_autorises():
    from modules.documents.prefill import (
        list_parties, list_skus, apply_party, append_sku,
    )
    tables = {
        "clients": [
            {"client_id": "C1", "nom": "Client A", "adresse": "Bouira", "actif": "OUI"},
            {"client_id": "C2", "nom": "Inactif", "adresse": "Alger", "actif": "NON"},
        ],
        "fournisseurs": [
            {"fournisseur_id": "F1", "nom": "Fournisseur A", "adresse": "Oran", "actif": "OUI"}
        ],
        "produits": [
            {"pf_id": "PF1", "nom": "FENEK BOND", "actif": "OUI"},
            {"pf_id": "PF2", "nom": "Produit inactif", "actif": "NON"},
        ],
        "sku_conditionnement": [
            {"sku_id": "SKU1", "pf_id": "PF1", "unite_vente": "SAC",
             "format": "25 KG", "prix_vente_defaut": "300", "actif": "OUI"},
            {"sku_id": "SKU2", "pf_id": "PF2", "actif": "OUI"},
        ],
    }
    def reader(table):
        return tables[table]
    clients = list_parties("Devis", reader=reader)
    assert [x["id"] for x in clients] == ["C1"]
    suppliers = list_parties("Bon de commande fournisseur", reader=reader)
    assert [x["id"] for x in suppliers] == ["F1"]
    assert list_parties("Feuille de temps", reader=reader) == []
    products = list_skus("Devis", reader=reader)
    assert [x["id"] for x in products] == ["SKU1"]
    assert list_skus("Bon de consommation", reader=reader) == []

    draft = new_draft("Devis")
    changed = apply_party(draft, clients[0])
    changed = append_sku(changed, products[0])
    assert draft["tiers_nom"] == ""
    assert changed["tiers_nom"] == "Client A"
    assert changed["items"][0]["designation"] == "FENEK BOND"
    assert changed["items"][0]["prix_unitaire"] == ""
    assert changed["items"][0]["quantite"] == ""


def test_prefill_refuse_lecture_sans_droits_et_borne_lignes():
    from modules.documents.prefill import list_parties, append_sku
    def denied(table):
        raise PermissionError("Accès interdit")
    with pytest.raises(PermissionError):
        list_parties("Facture", reader=denied)
    doc = new_draft("Devis")
    doc["items"] = [{} for _ in range(200)]
    with pytest.raises(ValueError, match="200"):
        append_sku(doc, {"id": "X", "designation": "Produit", "unite": "KG"})


def test_ui_prefill_lecture_seule_et_sans_prix_force():
    from pathlib import Path
    code = Path("modules/documents/views.py").read_text(encoding="utf-8")
    assert "Charger les référentiels autorisés" in code
    assert "list_parties(kind)" in code
    assert "list_skus(kind)" in code
    assert "Ajouter ce SKU au brouillon" in code
    service = Path("modules/documents/prefill.py").read_text(encoding="utf-8")
    assert "fetch_data_paginated" in service
    assert "insert_hybrid" not in service and "update_hybrid" not in service


def test_prefill_matieres_stock_production_lecture_seule():
    from modules.documents.prefill import list_materials, append_material
    catalogue = [
        {"mp_id": "MP-1", "nom": "Résine", "unite_stock": "KG", "actif": "OUI"},
        {"mp_id": "MP-2", "nom": "Inactive", "unite_stock": "KG", "actif": "NON"},
    ]
    result = list_materials("Bon de consommation", reader=lambda table: catalogue)
    assert [x["id"] for x in result] == ["MP-1"]
    assert list_materials("Facture", reader=lambda table: catalogue) == []
    source = new_draft("Bon de consommation")
    filled = append_material(source, result[0])
    assert source["items"] == []
    assert filled["items"][0]["reference"] == "MP-1"
    assert filled["items"][0]["unite"] == "KG"
    assert "prix_unitaire" not in filled["items"][0]
    assert export_pdf(filled).startswith(b"%PDF")
    assert export_docx(filled).startswith(b"PK")
    with pytest.raises(ValueError):
        append_material(new_draft("Facture"), result[0])


def test_ui_matiere_premiere_sans_mouvement_stock():
    from pathlib import Path
    code = Path("modules/documents/views.py").read_text(encoding="utf-8")
    assert "list_materials(kind)" in code
    assert "Ajouter cette matière au brouillon" in code
    source = Path("modules/documents/prefill.py").read_text(encoding="utf-8")
    assert "insert_hybrid" not in source and "update_hybrid" not in source
