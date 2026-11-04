"""Mise en page A4 NEXTGEN : brouillons uniquement, sans calcul fiscal."""
from __future__ import annotations

from io import BytesIO

NAVY = (14, 43, 79)
GREEN = (10, 133, 93)
PALE = (240, 244, 248)

# Les clés existantes sont conservées pour les imports JSON antérieurs.
BASE_COLUMNS = [
    ("reference", "Référence"), ("designation", "Désignation"),
    ("unite", "Unité"), ("quantite", "Qté"),
    ("prix_unitaire", "P.U. DZD"), ("total_ht", "Montant HT"),
]
MOVEMENT_COLUMNS = [
    ("reference", "Référence"), ("designation", "Désignation"),
    ("unite", "Unité"), ("quantite", "Qté sortie"),
    ("observation", "Observation"), ("visa", "Visa magasinier"),
]
DELIVERY_COLUMNS = [
    ("reference", "Référence"), ("designation", "Désignation"),
    ("unite", "Unité"), ("quantite", "Qté commandée"),
    ("quantite_livree", "Qté livrée"), ("observation", "Réserves"),
]
PRODUCTION_COLUMNS = [
    ("reference", "Référence"), ("designation", "Désignation"),
    ("unite", "Unité"), ("quantite", "Quantité"),
    ("lot", "Lot / OF"), ("observation", "Observations"),
]
RH_COLUMNS = [
    ("reference", "Référence"), ("designation", "Motif / activité"),
    ("unite", "Unité"), ("quantite", "Durée"),
    ("date_ligne", "Date / période"), ("observation", "Observations"),
]

FINANCIAL_KINDS = frozenset({
    "Devis", "Bon de commande client", "Facture", "Avoir",
    "Bon de commande fournisseur", "Contrôle facture fournisseur",
    "Accusé interne d'encaissement", "Ordre de paiement",
})
DELIVERY_KINDS = frozenset({"Bon de livraison", "Bon de réception"})
STOCK_KINDS = frozenset({"Bon de consommation", "Bon de sortie", "Transfert de stock", "Inventaire"})
PRODUCTION_KINDS = frozenset({"Ordre de fabrication", "Rapport de fabrication", "Contrôle qualité"})
RH_KINDS = frozenset({"Demande de congé", "Feuille de temps"})


def columns_for(kind: str):
    if kind in DELIVERY_KINDS:
        return DELIVERY_COLUMNS
    if kind in STOCK_KINDS:
        return MOVEMENT_COLUMNS
    if kind in PRODUCTION_KINDS:
        return PRODUCTION_COLUMNS
    if kind in RH_KINDS:
        return RH_COLUMNS
    return BASE_COLUMNS


def signature_labels(kind: str):
    if kind == "Devis":
        return ("Établi par NEXTGEN", "Bon pour accord - Client")
    if kind in DELIVERY_KINDS:
        return ("Livreur / magasinier", "Réceptionnaire - Réserves")
    if kind in STOCK_KINDS:
        return ("Responsable demandeur", "Magasinier / bénéficiaire")
    if kind in PRODUCTION_KINDS:
        return ("Responsable production", "Contrôle / validation")
    if kind in RH_KINDS:
        return ("Salarié / demandeur", "Responsable hiérarchique")
    return ("Établi par / cachet", "Reçu / validé par")


def latin(value, limit=220):
    return str("" if value is None else value).encode("latin-1", "replace").decode("latin-1")[:limit]


def _fit_text(pdf, text, max_width, font_size=8, max_lines=3):
    """Découpage sans perte pour les désignations longues (hors limite de page)."""
    words = latin(text, 800).split()
    result, line = [], ""
    for word in words:
        candidate = (line + " " + word).strip()
        if pdf.get_string_width(candidate) > max_width and line:
            result.append(line)
            line = word
        else:
            line = candidate
    if line:
        result.append(line)
    # Couper les chaînes sans espace pour éviter de déborder du cadre.
    fixed = []
    for line in result:
        if pdf.get_string_width(line) <= max_width:
            fixed.append(line)
            continue
        part = ""
        for char in line:
            if part and pdf.get_string_width(part + char) > max_width:
                fixed.append(part)
                part = char
            else:
                part += char
        if part:
            fixed.append(part)
    return fixed[:max_lines] or [""]


def render_pdf(doc, logo_path, *, company, address, rc, nif, email,
               tracking_payload, draw_qr):
    """Factures et autres pièces restent des brouillons non émis."""
    from fpdf import FPDF
    kind = doc["type"]
    cols = columns_for(kind)
    col_width = [27, 57, 17, 23, 31, 35]  # 190 mm

    class NextgenPDF(FPDF):
        def header(self):
            if logo_path:
                self.image(logo_path, x=12, y=9, w=31)
            self.set_xy(48, 13)
            self.set_font("Helvetica", "B", 12)
            self.set_text_color(*NAVY)
            self.multi_cell(148, 6.5, latin(company), align="L")
            self.set_draw_color(*NAVY)
            self.set_line_width(0.45)
            self.line(10, 34, 154, 34)
            self.set_draw_color(*GREEN)
            self.set_line_width(1.1)
            self.line(156, 34, 200, 34)

        def footer(self):
            self.set_auto_page_break(auto=False)
            self.set_draw_color(*NAVY)
            self.set_line_width(0.4)
            self.line(10, 266, 200, 266)
            self.set_draw_color(*GREEN)
            self.set_line_width(1.2)
            self.line(86, 266, 124, 266)
            self.set_text_color(*NAVY)
            self.set_xy(10, 268)
            self.set_font("Helvetica", "", 7)
            self.multi_cell(190, 4, latin(address) + "\n" +
                            latin("RC : " + rc + "   |   NIF : " + nif + "   |   " + email),
                            align="C")
            self.set_xy(10, 288)
            self.set_font("Helvetica", "", 7)
            self.cell(190, 4, f"Page {self.page_no()}/{{nb}}", align="R")

    pdf = NextgenPDF(format="A4", unit="mm")
    pdf.alias_nb_pages()
    pdf.set_auto_page_break(auto=True, margin=36)
    pdf.add_page()
    pdf.set_y(40)
    pdf.set_fill_color(*NAVY)
    pdf.set_text_color(255, 255, 255)
    pdf.set_font("Helvetica", "B", 17)
    pdf.cell(190, 12, latin(kind).upper(), align="C", fill=True, ln=True)
    pdf.set_text_color(175, 32, 40)
    pdf.set_font("Helvetica", "B", 9)
    pdf.cell(190, 8, "BROUILLON - NON VALABLE / NON EMIS", align="C", ln=True)
    pdf.set_text_color(*NAVY)
    pdf.set_font("Helvetica", "", 9)
    # Champs en deux colonnes, pas de faux identifiant juridique.
    for left, right in (
        (("N° document", doc.get("numero")), ("Date", doc.get("date"))),
        (("Objet", doc.get("objet")), ("Devise", "DZD")),
    ):
        y = pdf.get_y()
        for x, item in ((10, left), (109, right)):
            pdf.set_xy(x, y)
            pdf.set_fill_color(*PALE)
            pdf.cell(92, 7, latin(f"{item[0]} : {item[1] or '-'}", 90), fill=True)
        pdf.set_y(y + 9)
    pdf.set_y(pdf.get_y() + 3)
    partner_label = "Client / destinataire" if kind not in {
        "Bon de commande fournisseur", "Bon de réception", "Contrôle facture fournisseur",
    } else "Fournisseur"
    pdf.set_fill_color(*NAVY)
    pdf.set_text_color(255, 255, 255)
    pdf.set_font("Helvetica", "B", 10)
    pdf.cell(190, 7, latin("  " + partner_label), ln=True, fill=True)
    pdf.set_text_color(*NAVY)
    pdf.set_font("Helvetica", "", 9)
    for label, value in (("Raison sociale / service", doc.get("tiers_nom")),
                         ("Adresse", doc.get("tiers_adresse"))):
        pdf.set_x(11)
        pdf.multi_cell(185, 6, latin(f"{label} : {value or '-'}"))
    pdf.ln(5)

    def table_header():
        pdf.set_x(10)
        pdf.set_fill_color(*NAVY)
        pdf.set_text_color(255, 255, 255)
        pdf.set_font("Helvetica", "B", 8)
        for (key, label), width in zip(cols, col_width):
            pdf.cell(width, 8, latin(label), border=1, fill=True)
        pdf.ln()
        pdf.set_text_color(*NAVY)
        pdf.set_font("Helvetica", "", 8)

    table_header()
    for row_no, item in enumerate(doc.get("items", [])):
        if not any(str(v).strip() for v in item.values() if v is not None):
            continue
        pdf.set_font("Helvetica", "", 8)
        lines_by_cell = [_fit_text(pdf, item.get(key, ""), width - 3)
                         for (key, _), width in zip(cols, col_width)]
        height = min(24, max(7, max(len(lines) for lines in lines_by_cell) * 4.4 + 2))
        if pdf.get_y() + height > 244:
            pdf.add_page()
            pdf.set_y(43)
            table_header()
        y = pdf.get_y()
        fill = row_no % 2 == 1
        if fill:
            pdf.set_fill_color(*PALE)
        for width, lines in zip(col_width, lines_by_cell):
            x = pdf.get_x()
            pdf.rect(x, y, width, height, style="DF" if fill else "D")
            pdf.set_xy(x + 1.5, y + 1.0)
            pdf.multi_cell(width - 3, 4.4, "\n".join(lines))
            pdf.set_xy(x + width, y)
        pdf.set_xy(10, y + height)
    pdf.ln(5)

    if kind in FINANCIAL_KINDS:
        totals = (("Total HT", "total_ht"), ("Taxes (saisie contrôlée)", "total_taxes"),
                  ("Total TTC", "total_ttc"))
        for label, key in totals:
            value = doc.get(key)
            if value in ("", None):
                continue
            if pdf.get_y() > 222:
                pdf.add_page()
            pdf.set_x(104)
            pdf.set_fill_color(*(GREEN if key == "total_ttc" else PALE))
            pdf.set_text_color(*( (255,255,255) if key == "total_ttc" else NAVY ))
            pdf.set_font("Helvetica", "B", 9)
            pdf.cell(58, 8, latin(label), fill=True)
            pdf.cell(38, 8, latin(f"{value} DZD", 35), align="R", fill=True, ln=True)
        pdf.set_text_color(*NAVY)
    if doc.get("observations"):
        if pdf.get_y() > 220:
            pdf.add_page()
        pdf.set_x(10)
        pdf.set_font("Helvetica", "", 9)
        pdf.multi_cell(190, 5.5, latin("Observations / conditions : " + doc["observations"], 420))
    # Zone récapitulative finale gardée sur une seule page si possible.
    if pdf.get_y() > 191:
        pdf.add_page()
    base_y = max(170, pdf.get_y() + 6)
    draw_qr(pdf, doc, x=164, y=base_y, size=30)
    pdf.set_text_color(*NAVY)
    pdf.set_font("Helvetica", "", 7.5)
    pdf.set_xy(10, base_y + 9)
    pdf.multi_cell(147, 5, latin("ID de traçabilité QR : " + doc["trace_id"]))
    sig_y = base_y + 38
    if sig_y + 26 > 260:
        pdf.add_page()
        sig_y = 155
    for (label, x) in zip(signature_labels(kind), (10, 108)):
        pdf.set_xy(x, sig_y)
        pdf.set_font("Helvetica", "B", 9)
        pdf.cell(92, 6, latin(label))
        pdf.set_draw_color(*NAVY)
        pdf.rect(x, sig_y + 7, 91, 18)
    result = pdf.output(dest="S")
    return bytes(result) if not isinstance(result, str) else result.encode("latin-1")
