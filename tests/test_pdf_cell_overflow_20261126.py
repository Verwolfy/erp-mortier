"""Régression PDF : aucune désignation ne doit sortir du bord de sa cellule.

Cas réel : « Mortier Colle Haute Performance C2TE - Sac 25kg ».
Un calcul antérieur prévoyait 2 lignes, mais fpdf2 en imprimait 3 parce
que les marges intérieures n'étaient pas déduites lors du pré-découpage.
"""
from __future__ import annotations

from fpdf import FPDF
import pytest

from modules.documents.party_identity import (
    draw_table_cell_text, wrap_table_cell_text,
)
from modules.documents.erp_print import render_operation_pdf

DESIGNATION = "Mortier Colle Haute Performance C2TE - Sac 25kg"


def test_fpdf_lignes_reelles_tiennent_dans_les_57_mm():
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Helvetica", "", 7.5)
    lines = wrap_table_cell_text(pdf, DESIGNATION, 57)
    assert lines == [
        "Mortier Colle Haute Performance C2TE -",
        "Sac 25kg",
    ]
    height = max(8, len(lines) * 4.1 + 2)
    assert height == pytest.approx(10.2)
    for line in lines:
        assert (pdf.get_string_width(line)
                <= 57 - 3 - 2 * pdf.c_margin - 0.1)
    draw_table_cell_text(pdf, lines, x=48, y=90, width=57,
                         height=height, line_height=4.1)
    assert pdf.page_no() == 1


def test_copie_facture_designation_reste_dans_bordure(monkeypatch):
    """Contrôle l'ordre de dessin et les coordonnées réelles sur la facture."""
    cells = []
    borders = []
    cell_original = FPDF.cell
    rect_original = FPDF.rect

    def spy_cell(self, *args, **kwargs):
        text = args[2] if len(args) > 2 else kwargs.get("text", "")
        if "C2TE" in str(text) or "Sac 25kg" in str(text):
            cells.append((self.get_x(), self.get_y(),
                          args[1] if len(args) > 1 else kwargs.get("h"),
                          str(text), self.get_string_width(str(text)),
                          self.c_margin,
                          args[0] if len(args) > 0 else kwargs.get("w")))
        return cell_original(self, *args, **kwargs)

    def spy_rect(self, x, y, w, h, *args, **kwargs):
        if abs(x - 48) < .01 and abs(w - 57) < .01:
            borders.append((y, h))
        return rect_original(self, x, y, w, h, *args, **kwargs)

    monkeypatch.setattr(FPDF, "cell", spy_cell)
    monkeypatch.setattr(FPDF, "rect", spy_rect)

    snapshot = {
        "kind": "Facture (aperçu interne)",
        "id": "FAC-2026-000001",
        "date": "2026-10-24",
        "source": "factures",
        "currency": "DZD",
        "party_role": "CLIENT",
        "partner": "Client de test",
        "party_fields": [
            ("Raison Sociale", "EURL Lounes"),
            ("Adresse de Facturation", "Bouira"),
        ],
        "meta": [("Statut ERP", "VALIDE"),
                 ("Type ERP", "FactureClient")],
        "lines": [{
            "reference": "SKU-001", "designation": DESIGNATION,
            "unite": "SAC", "quantite": "1",
            "prix_unitaire": "1250", "total_ht": "1250",
        }],
        "totals": [("Total HT", "1250"),
                   ("TVA (19 %)", "237.50"),
                   ("Timbre", "0"),
                   ("Total TTC", "1487.50")],
        "warning": "APERÇU INTERNE - NON VALABLE FISCALEMENT / NON ÉMIS",
    }

    data = render_operation_pdf(snapshot)
    assert data.startswith(b"%PDF")
    assert [row[3] for row in cells] == [
        "Mortier Colle Haute Performance C2TE -", "Sac 25kg",
    ]
    assert len(borders) == 1
    y, height = borders[0]
    for x_text, y_text, h_text, line, text_width, margin, cell_width in cells:
        assert x_text >= 48
        assert y_text >= y + .95
        assert y_text + h_text <= y + height + .02
        assert text_width <= cell_width - 2 * margin
