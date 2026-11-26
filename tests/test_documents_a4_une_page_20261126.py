"""Contrainte métier : une pièce opérationnelle tient sur une page A4.

Ne jamais couper les lignes, mentions, QR ou montants pour forcer la page.
Aucun accès réseau ou Supabase pendant ces tests.
"""
from __future__ import annotations

import re

import pytest

from modules.documents.erp_print import (
    KINDS, OperationPrintError, render_operation_pdf,
)
from modules.documents.internal_print import (
    INTERNAL_KINDS, InternalPrintError, render_internal_pdf,
)
from modules.documents.views import DOCUMENTS, export_pdf, new_draft


def page_count(blob: bytes) -> int:
    assert blob.startswith(b"%PDF")
    return len(re.findall(rb"/Type\s*/Page\b", blob))


def basic_snapshot(kind: str) -> dict:
    fiscal = kind in (
        "Facture (aperçu interne)", "Facture fournisseur (aperçu interne)",
    )
    totals = (
        [("Total HT", "1250"), ("TVA (19 %)", "237.50"),
         ("Timbre", "0"), ("Total TTC", "1487.50")]
        if fiscal else [("Total HT", "1250")]
    )
    return {
        "kind": kind, "id": "FAC-2026-000001", "date": "2026-11-26",
        "source": "test", "party_role": "CLIENT",
        "partner": "EURL Exemple",
        "currency": "DZD", "meta": [
            ("Statut ERP", "VALIDE"), ("Type ERP", "FactureClient"),
            ("Commande", ""),
        ],
        "party_fields": [
            ("Raison Sociale", "EURL Exemple"),
            ("Adresse de Facturation", "Bouira"),
            ("Wilaya", "10"), ("Pays", "DZ"), ("RC", "RC-123"),
            ("NIF", "112448859"), ("NIS", "66384"),
            ("Contact", "Responsable commercial"),
            ("Fonction du contact", "Gérant"),
            ("Téléphone mobile", "0555 000 000"),
            ("E-mail contact", "contact@example.dz"),
        ],
        "lines": [{
            "reference": "SKU-001",
            "designation": "Mortier Colle Haute Performance C2TE - Sac 25kg",
            "unite": "SAC", "quantite": "1",
            "prix_unitaire": "1250", "total_ht": "1250",
        }],
        "totals": totals,
        "warning": "APERÇU INTERNE - NON VALABLE FISCALEMENT / NON ÉMIS",
    }


@pytest.mark.parametrize("kind", list(KINDS))
def test_copie_operationnelle_courte_une_seule_page(kind):
    assert page_count(render_operation_pdf(basic_snapshot(kind))) == 1


def test_facture_a_infos_completes_qr_et_lettres_sur_meme_page():
    invoice = basic_snapshot("Facture (aperçu interne)")
    invoice["id"] = "FAC-2026-000001"
    invoice["lines"][0]["designation"] *= 2
    assert page_count(render_operation_pdf(invoice)) == 1


def test_beaucoup_de_lignes_refusees_sans_troncature():
    invoice = basic_snapshot("Facture (aperçu interne)")
    invoice["lines"] = [dict(invoice["lines"][0], reference=f"SKU-{i:03}")
                        for i in range(75)]
    with pytest.raises(OperationPrintError, match="une seule page"):
        render_operation_pdf(invoice)


@pytest.mark.parametrize("kind", list(INTERNAL_KINDS))
def test_copie_interne_courte_une_page(kind):
    snapshot = {
        "kind": kind, "id": "DOC-001", "date": "2026-11-26",
        "source": "tests", "warning": "COPIE INTERNE - NON ÉMISE",
        "fields": [("Référence source", "CMD-001"), ("Quantité", "4")],
    }
    assert page_count(render_internal_pdf(snapshot)) == 1


def test_copie_interne_trop_longue_echoue_sans_page_de_suite():
    snapshot = {
        "kind": "Demande de congé", "id": "D-1",
        "date": "2026-11-26", "source": "tests",
        "warning": "COPIE INTERNE - NON ÉMISE",
        "fields": [(f"Champ {i}", "Information importante")
                   for i in range(70)],
    }
    with pytest.raises(InternalPrintError, match="une seule page"):
        render_internal_pdf(snapshot)


@pytest.mark.parametrize("kind", [
    item for kinds in DOCUMENTS.values() for item in kinds
])
def test_brouillons_courts_une_page(kind):
    doc = new_draft(kind)
    assert page_count(export_pdf(doc)) == 1


def test_brouillon_trop_long_refuse():
    draft = new_draft("Bon de livraison")
    draft["items"] = [{
        "reference": f"MAT-{i:04}",
        "designation": "Article de construction",
        "quantite": "1",
    } for i in range(70)]
    with pytest.raises(ValueError, match="une seule page"):
        export_pdf(draft)


def test_legacy_document_pdf_une_page_qr_et_montant_en_lettres():
    from core.pdf_generator import generer_document_standard
    pdf = generer_document_standard(
        "FACTURE", "FAC-TEST-01", "2026-11-26",
        {"nom": "Client ERP", "adresse": "Bouira, Algérie"},
        [{"nom": "Mortier colle 25 kg", "quantite": "1",
          "prix_unitaire": "1250", "remise": "0", "total_ht": "1250"}],
        {"total_ht": "1250", "total_tva": "237.5", "total_ttc": "1487.5"},
        {"entreprise_nom": "SARL NEXT GENRATION BUILDING SOLUTIONS"},
    )
    assert page_count(pdf) == 1


def test_legacy_document_trop_long_refuse():
    from core.pdf_generator import generer_document_standard
    with pytest.raises(ValueError, match="une seule page"):
        generer_document_standard(
            "COMMANDE", "CA-TEST-01", "2026-11-26",
            {"nom": "Fournisseur ERP"},
            [{"nom": "Article industriel", "quantite": "1",
              "prix_unitaire": "10", "total_ht": "10"}
             for _ in range(80)],
            {"total_ht": "800", "total_ttc": "800"},
            {},
        )
