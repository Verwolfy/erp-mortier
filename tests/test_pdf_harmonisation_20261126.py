"""Régression de mise en page NEXTGEN, sans accès à Supabase."""
from __future__ import annotations

import json

import pytest

from modules.documents.party_identity import normalize_party, configured_company, pdf_safe
from modules.documents.pdf_presentation import (
    amount_in_words, format_money, format_quantity, has_value,
    qr_payload, vat_label,
)
from modules.documents.views import new_draft, tracking_payload, export_pdf, export_docx
from modules.documents.erp_print import render_operation_pdf
from modules.documents.internal_print import render_internal_pdf


def test_official_company_identity_remains_verbatim():
    company = dict(configured_company())
    assert company["Raison Sociale"] == "SARL NEXT GENRATION BUILDING SOLUTIONS"
    assert "AI" not in company and "NIS" not in company


def test_blank_fields_and_placeholders_are_not_rendered_as_values():
    fields = dict(normalize_party({
        "nom": "Client test", "adresse": "   ", "rc": None,
        "nif": "Non renseigné", "ai": "", "nis": "Non renseignée",
        "pays": "DZ",
    }))
    assert fields == {"Raison Sociale": "Client test", "Pays": "DZ"}
    assert not has_value("NON RENSEIGNÉ")
    assert has_value("0")
    assert pdf_safe("Mortier — Sac 25 kg") == "Mortier  -  Sac 25 kg"


def test_french_money_and_cents_are_exact():
    assert format_money("360000.0") == "360 000,00"
    assert format_quantity("10000.00") == "10 000"
    assert amount_in_words("1487.50") == (
        "Mille quatre cent quatre-vingt-sept dinars et cinquante centimes.")
    assert amount_in_words("1.01") == "Un dinar et un centime."
    with pytest.raises(ValueError):
        amount_in_words("NaN")


@pytest.mark.parametrize("rate,label", [
    ("0.19", "TVA (19 %)"), ("19", "TVA (19 %)"),
    ("9", "TVA (9 %)"), ("10", "TVA (10 %)"),
    ("20", "TVA (20 %)"), ("0", "TVA (0 %)"),
])
def test_vat_label_never_mangles_rates(rate, label):
    assert vat_label(rate=rate) == label


def test_tax_rate_is_not_assumed_from_missing_supplier_invoice():
    assert vat_label(ht="80000", vat=None) == "TVA"
    assert vat_label(ht="1250", vat="237.5") == "TVA (19 %)"
    assert vat_label(ht="1250", vat="112.5") == "TVA"


def test_qr_contains_document_lookup_not_client_identity():
    snapshot = {
        "kind": "Facture (aperçu interne)", "id": "FAC-2026-000001",
        "date": "2026-10-24", "source": "factures",
        "party_fields": [("Raison Sociale", "Client privé"),
                         ("NIF", "112448859")],
        "lines": [{"reference": "SKU-001", "total_ht": "1250"}],
        "totals": [("Total TTC", "1487.5")],
    }
    code = json.loads(qr_payload(snapshot))
    assert code["ref"] == "FAC-2026-000001"
    assert code["date"] == "2026-10-24"
    assert code["statut"] == "COPIE_NON_EMISE"
    assert "Client privé" not in json.dumps(code)
    assert "112448859" not in json.dumps(code)
    changed = dict(snapshot, totals=[("Total TTC", "1490")])
    assert json.loads(qr_payload(changed))["empreinte"] != code["empreinte"]


def test_draft_qr_keeps_trace_without_public_secret():
    doc = new_draft("Facture")
    doc["tiers_nom"] = "Client privé"
    doc["tiers_nif"] = "NIF-SENSIBLE"
    payload = tracking_payload(doc)
    data = json.loads(payload)
    assert doc["trace_id"] == data["id"]
    assert "NIF-SENSIBLE" not in payload
    assert "Client privé" not in payload
    assert "https://" not in payload
    assert export_pdf(doc).startswith(b"%PDF")
    assert export_docx(doc).startswith(b"PK")


def test_operation_long_ref_blank_fields_and_qr_remain_printable():
    snap = {
        "kind": "Commande fournisseur", "id": "CMA-0006",
        "date": "2026-11-23", "meta": [("Zone", ""), ("Statut", "EN_ATTENTE")],
        "lines": [{"reference": "NG-EMB-SAC-25KG",
                   "designation": "Emballage sac - format nominal 25 KG",
                   "unite": "U", "quantite": "10000",
                   "prix_unitaire": "36.0", "total_ht": "360000"}],
        "totals": [("Total", "360000")], "partner": "Fournisseur",
        "party_fields": [("Raison Sociale", "Fournisseur"),
                         ("Adresse de Facturation", "")],
        "party_role": "FOURNISSEUR", "warning": "COPIE NON ÉMISE",
    }
    assert render_operation_pdf(snap).startswith(b"%PDF")


def test_internal_document_without_optional_values_still_prints():
    snapshot = {
        "kind": "Fiche de mouvement MP", "id": "MVT-1",
        "date": "2026-11-23", "section": "Stocks",
        "partner": "MP-1", "source": "mouvements",
        "warning": "COPIE NON SIGNÉE",
        "fields": [("Lot", ""), ("Référence source", "Non renseigné"),
                   ("Quantité", "12")],
    }
    assert render_internal_pdf(snapshot).startswith(b"%PDF")
