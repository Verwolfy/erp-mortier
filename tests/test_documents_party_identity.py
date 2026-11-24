"""Identités légales sur tous les documents, sans données inventées ni DB réelle."""
from __future__ import annotations

from io import BytesIO
from pathlib import Path
from unittest.mock import MagicMock
from zipfile import ZipFile

import pytest

from modules.documents.erp_print import (
    load_operation_snapshot, render_operation_pdf,
)
from modules.documents.party_identity import (
    MISSING, configured_company, normalize_party,
)
from modules.documents.views import new_draft, export_pdf, export_docx
from modules.documents.prefill import list_parties, apply_party
from modules.documents.draft_io import read_draft_json
from modules.documents.views import tracking_payload
import json

PARTNER = {
    "nom": "SARL Fournisseur Nord",
    "adresse": "Rue principale, Zone industrielle 4, bâtiment B, BP 202, Bouira",
    "wilaya": "Bouira",
    "pays": "Algérie",
    "rc": "RC-123-XYZ",
    "nif": "NIF-888-222",
    "nis": "NIS-987",
    "ai": "AI-456",
    "nom_contact": "Responsable achats",
    "poste_contact": "Direction commerciale",
    "telephone_fixe": "021 00 00 00",
    "mobile_contact": "0555 00 00 00",
    "email_entreprise": "direction@exemple.dz",
    "email_contact": "achats@exemple.dz",
    "site_web": "www.exemple.dz",
}


def _dataset(kind):
    data = {
        ("fournisseurs", "fournisseur_id", "FR-1"): [
            {"fournisseur_id": "FR-1", **PARTNER}
        ],
        ("clients", "client_id", "CL-1"): [
            {"client_id": "CL-1", **PARTNER}
        ],
        ("matieres_premieres", "mp_id", "MP-1"): [
            {"mp_id": "MP-1", "nom": "Matière de construction", "unite_stock": "KG"}
        ],
        ("sku_conditionnement", "sku_id", "SKU-1"): [
            {"sku_id": "SKU-1", "pf_id": "PF-1", "format": "Sac 25 kg", "unite_vente": "SAC"}
        ],
        ("produits", "pf_id", "PF-1"): [{"pf_id": "PF-1", "nom": "Produit"}],
        ("commandes_achats", "commande_achat_id", "CA-1"): [
            {"commande_achat_id": "CA-1", "fournisseur_id": "FR-1",
             "date_commande": "2026-11-23", "devise": "DZD",
             "montant_total_local": "1500", "statut": "EN_ATTENTE"}
        ],
        ("lignes_achats", "commande_achat_id", "CA-1"): [
            {"commande_achat_id": "CA-1", "mp_id": "MP-1", "unite_cond": "KG",
             "qte_totale": "10", "prix_unitaire": "150", "total_devise": "1500"}
        ],
        ("factures_fournisseurs", "facture_fournisseur_id", "FF-1"): [
            {"facture_fournisseur_id": "FF-1", "fournisseur_id": "FR-1",
             "commande_achat_id": "CA-1", "date": "2026-11-23",
             "montant_ht": "1000", "montant_tva": "190", "montant_ttc": "1190"}
        ],
        ("lignes_factures_fournisseurs", "facture_fournisseur_id", "FF-1"): [
            {"facture_fournisseur_id": "FF-1", "mp_id_ou_service": "Service technique",
             "quantite": "1", "prix_unitaire": "1000", "total_ht": "1000"}
        ],
        ("factures", "facture_id", "FAC-1"): [
            {"facture_id": "FAC-1", "client_id": "CL-1", "date": "2026-11-23",
             "montant_ht": "100", "montant_tva": "19", "montant_timbre": "0",
             "montant_ttc": "119"}
        ],
        ("lignes_facture", "facture_id", "FAC-1"): [
            {"facture_id": "FAC-1", "sku_id": "SKU-1",
             "quantite": "1", "prix_unitaire": "100", "total_ligne_ht": "100"}
        ],
    }
    if kind == "commande":
        return "Commande fournisseur", "CA-1", data
    if kind == "facture":
        return "Facture (aperçu interne)", "FAC-1", data
    return "Facture fournisseur (aperçu interne)", "FF-1", data


def _reader(data):
    def read(table, *, equal_column, equal_value, max_rows):
        return data.get((table, equal_column, equal_value), [])
    return read


@pytest.mark.parametrize("kind", ["commande", "facture", "facture_fournisseur"])
def test_all_partner_identifiers_copied_from_actual_referential(kind):
    doc, ref, data = _dataset(kind)
    snapshot = load_operation_snapshot(doc, ref, reader=_reader(data))
    fields = dict(snapshot["party_fields"])
    for label, value in (
        ("Nom / raison sociale", PARTNER["nom"]),
        ("Adresse", PARTNER["adresse"]),
        ("RC", PARTNER["rc"]),
        ("NIF", PARTNER["nif"]),
        ("NIS", PARTNER["nis"]),
        ("AI (article d'imposition)", PARTNER["ai"]),
        ("Téléphone fixe", PARTNER["telephone_fixe"]),
        ("Téléphone mobile", PARTNER["mobile_contact"]),
        ("E-mail entreprise", PARTNER["email_entreprise"]),
        ("E-mail contact", PARTNER["email_contact"]),
        ("Site web", PARTNER["site_web"]),
    ):
        assert fields[label] == value
    assert render_operation_pdf(snapshot).startswith(b"%PDF")


@pytest.mark.parametrize("kind,expected_left,expected_right", [
    ("commande", "NEXTGEN - ÉMETTEUR", "FOURNISSEUR"),
    ("facture", "NEXTGEN - ÉMETTEUR", "CLIENT"),
    ("facture_fournisseur", "FOURNISSEUR - ÉMETTEUR", "NEXTGEN - DESTINATAIRE"),
])
def test_issuer_is_never_confused_with_supplier_of_original_invoice(
    kind, expected_left, expected_right, monkeypatch,
):
    import modules.documents.party_identity as helper
    titles = []
    original = helper.draw_party_panels

    def capture(pdf, left_title, left_fields, right_title, right_fields):
        titles.append((left_title, right_title))
        return original(pdf, left_title, left_fields, right_title, right_fields)

    monkeypatch.setattr(helper, "draw_party_panels", capture)
    doc, ref, data = _dataset(kind)
    render_operation_pdf(load_operation_snapshot(doc, ref, reader=_reader(data)))
    assert titles == [(expected_left, expected_right)]


def test_unknown_ai_nis_explicitly_missing_never_derived_from_nif():
    fields = dict(normalize_party({
        "nom": "Client", "adresse": "Adresse", "rc": "RC-1", "nif": "NIF-1",
    }))
    assert fields["AI (article d'imposition)"] == MISSING
    assert fields["NIS"] == MISSING
    issuer = dict(configured_company())
    assert issuer["RC"] and issuer["NIF"]
    assert issuer["AI (article d'imposition)"] == MISSING
    assert issuer["NIS"] == MISSING


def test_very_long_address_and_designation_generate_pages_without_truncation():
    doc, ref, data = _dataset("commande")
    data[("fournisseurs", "fournisseur_id", "FR-1")][0]["adresse"] = (
        "Zone industrielle nord, lot 42, bâtiment 8, " * 4
    )
    lines = data[("lignes_achats", "commande_achat_id", "CA-1")]
    lines[:] = [
        dict(lines[0], mp_id="MP-1", ligne_achat_id=f"L{i}",
             qte_totale="1", prix_unitaire="15", total_devise="15")
        for i in range(75)
    ]
    data[("matieres_premieres", "mp_id", "MP-1")][0]["nom"] = (
        "Produit technique en poudre pour formulation industrielle " * 3
    )
    pdf = render_operation_pdf(
        load_operation_snapshot(doc, ref, reader=_reader(data))
    )
    assert pdf.startswith(b"%PDF")
    assert pdf.count(b"/Type /Page") > 2


def test_draft_prefill_preserves_all_party_legal_fields_in_pdf_docx_and_json():
    party = {"id": "CL-1", **PARTNER}
    listed = list_parties("Devis", reader=lambda table: [
        {"client_id": "CL-1", "actif": "OUI", **PARTNER}
    ])
    assert len(listed) == 1
    assert listed[0]["ai"] == "AI-456"
    draft = apply_party(new_draft("Devis"), listed[0])
    assert draft["tiers_rc"] == "RC-123-XYZ"
    assert draft["tiers_nif"] == "NIF-888-222"
    assert draft["tiers_ai"] == "AI-456"
    draft["items"] = []
    assert export_pdf(draft).startswith(b"%PDF")
    word = export_docx(draft)
    with ZipFile(BytesIO(word)) as z:
        xml = z.read("word/document.xml").decode("utf-8")
    assert "RC-123-XYZ" in xml
    assert "NIS-987" in xml
    assert "AI-456" in xml
    assert "www.exemple.dz" in xml
    imported = read_draft_json(json.dumps(draft).encode("utf-8"), "Devis")
    assert imported["tiers_ai"] == "AI-456"
    assert imported["tiers_email_contact"] == "achats@exemple.dz"
