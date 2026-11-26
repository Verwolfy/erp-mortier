"""Mise en page A4 NEXTGEN : brouillons uniquement, sans calcul fiscal."""
from __future__ import annotations

from io import BytesIO

from modules.documents.pdf_presentation import (
    amount_in_words, format_money, has_value,
)

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
        
    from modules.documents.party_identity import pdf_safe
    return pdf_safe(value)


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
    return fixed or [""]


def render_pdf(doc, logo_path, *, company, address, rc, nif, email,
               tracking_payload, draw_qr):
    """Factures et autres pièces restent des brouillons non émis."""
    from fpdf import FPDF
    from fpdf.enums import XPos, YPos
    from modules.documents.branding_images import branded_images
    header_png, footer_png = branded_images(logo_path)
    kind = doc["type"]
    cols = columns_for(kind)
    col_width = [27, 57, 17, 23, 31, 35]  # 190 mm

    class NextgenPDF(FPDF):
        def header(self):
            self.image(BytesIO(header_png), x=0, y=0, w=210, h=46.2)

        def footer(self):
            # Image fixe issue du modèle validé, répétée sur chaque page.
            self.image(BytesIO(footer_png), x=0, y=268, w=210, h=24.36)
            self.set_xy(10, 292)
            self.set_font("Helvetica", "", 7)
            self.set_text_color(*NAVY)
            self.cell(190, 3, f"Page {self.page_no()}/{{nb}}", align="R")

    pdf = NextgenPDF(format="A4", unit="mm")
    pdf.single_page = True
    pdf.alias_nb_pages()
    pdf.set_auto_page_break(auto=False)
    pdf.add_page()
    pdf.set_y(51)
    pdf.set_fill_color(*NAVY)
    pdf.set_text_color(255, 255, 255)
    pdf.set_font("Helvetica", "B", 17)
    pdf.cell(190, 12, latin(kind).upper(), align="C", fill=True,
             new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.set_text_color(175, 32, 40)
    pdf.set_font("Helvetica", "B", 9)
    pdf.cell(190, 8, "BROUILLON - NON VALABLE / NON EMIS", align="C",
             new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.set_text_color(*NAVY)
    pdf.set_font("Helvetica", "", 9)
    # Champs en deux colonnes : les longues références se replient sans
    # dépasser ni déclencher une deuxième page.
    from modules.documents.party_identity import wrap_pdf_text
    for left, right in (
        (("N° document", doc.get("numero")), ("Date", doc.get("date"))),
        (("Objet", doc.get("objet")), ("Devise", "DZD")),
    ):
        y = pdf.get_y()
        pairs = [(x, item) for x, item in ((10, left), (109, right))
                 if has_value(item[1])]
        if not pairs:
            continue
        pdf.set_font("Helvetica", "", 9)
        lines_per_cell = [(x, wrap_pdf_text(
            pdf, f"{item[0]} : {item[1]}", 88))
            for x, item in pairs]
        height = max(7, 4.5 * max(len(lines) for _, lines in lines_per_cell) + 2)
        if y + height + 3 > 258:
            raise ValueError("Références trop longues pour une seule page A4")
        for x, lines in lines_per_cell:
            pdf.set_fill_color(*PALE)
            pdf.rect(x, y, 92, height, style="F")
            pdf.set_xy(x + 2, y + 1)
            pdf.multi_cell(88, 4.5, "\n".join(lines))
        pdf.set_y(y + height + 2)
    pdf.ln(2)
    from modules.documents.party_identity import (
        PARTY_LABELS, draw_party_panels, normalize_party,
        wrap_table_cell_text, draw_table_cell_text,
    )
    from modules.documents.prefill import CLIENT_TYPES, SUPPLIER_TYPES
    if kind in CLIENT_TYPES or kind in SUPPLIER_TYPES:
        issuer_fields = normalize_party({
            "nom": company, "adresse": address,
            "rc": rc, "nif": nif, "email_entreprise": email,
        }, issuer=True)
        party_data = {
            "nom": doc.get("tiers_nom", ""),
            "adresse": doc.get("tiers_adresse", ""),
        }
        party_data.update({
            field: doc.get("tiers_" + field, "")
            for _, field, _ in PARTY_LABELS if field not in ("nom", "adresse")
        })
        party_fields = normalize_party(party_data)
        title = "FOURNISSEUR" if kind in SUPPLIER_TYPES else "CLIENT"
        draw_party_panels(pdf, "NEXTGEN", issuer_fields,
                          title, party_fields)
    else:
        pdf.ln(3)

    def table_header():
        if pdf.get_y() + 8 > 250:
            raise ValueError(
                "Tableau trop long pour une seule page A4"
            )
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
        lines_by_cell = [wrap_table_cell_text(pdf, item.get(key, ""), width)
                         for (key, _), width in zip(cols, col_width)]
        height = max(7, max(len(lines) for lines in lines_by_cell) * 4.4 + 2)
        if height > 185:
            raise ValueError("Ligne documentaire trop longue pour une page A4")
        if pdf.get_y() + height > 251:
            raise ValueError(
                "Document trop volumineux pour une seule page A4 : "
                "réduire les lignes du tableau"
            )
        y = pdf.get_y()
        fill = row_no % 2 == 1
        if fill:
            pdf.set_fill_color(*PALE)
        for width, lines in zip(col_width, lines_by_cell):
            x = pdf.get_x()
            pdf.rect(x, y, width, height, style="DF" if fill else "D")
            draw_table_cell_text(
                pdf, lines, x=x, y=y, width=width, height=height,
                line_height=4.4,
            )
            pdf.set_xy(x + width, y)
        pdf.set_xy(10, y + height)
    pdf.ln(5)

    if kind in FINANCIAL_KINDS:
        tax_label = "TVA" if kind in ("Facture", "Avoir") else "Taxes"
        totals = (("Total HT", "total_ht"), (tax_label, "total_taxes"),
                  ("Total TTC", "total_ttc"))
        for label, key in totals:
            value = doc.get(key)
            if value in ("", None):
                continue
            if pdf.get_y() + 8 > 255:
                raise ValueError("Totaux trop longs pour une seule page A4")
            pdf.set_x(104)
            pdf.set_fill_color(*(GREEN if key == "total_ttc" else PALE))
            pdf.set_text_color(*( (255,255,255) if key == "total_ttc" else NAVY ))
            pdf.set_font("Helvetica", "B", 9)
            pdf.cell(58, 8, latin(label), fill=True)
            pdf.cell(38, 8, latin(f"{format_money(value)} DZD"), align="R", fill=True,
                     new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        pdf.set_text_color(*NAVY)
        if kind in ("Facture", "Avoir") and has_value(doc.get("total_ttc")):
            # L'énoncé en toutes lettres est obligatoire et doit rester lisible.
            if pdf.get_y() > 243:
                raise ValueError(
                    "Montant en lettres hors d'une seule page A4"
                )
            pdf.set_font("Helvetica", "B", 9)
            pdf.set_x(10)
            pdf.multi_cell(190, 5.5, latin(
                "Arrêté le présent document à : " + amount_in_words(doc["total_ttc"])),
                new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    if doc.get("observations"):
        if pdf.get_y() > 246:
            raise ValueError(
                "Observations trop longues pour une seule page A4"
            )
        pdf.set_x(10)
        pdf.set_font("Helvetica", "", 9)
        pdf.multi_cell(190, 5.5, latin("Observations / conditions : " + doc["observations"], 420))
    # Deux emplacements de signatures et le QR sur UNE même rangée.
    # Le modèle antérieur empilait QR et signatures et créait une page 2.
    base_y = max(170, pdf.get_y() + 5)
    if base_y + 36 > 258 or pdf.page_no() != 1:
        raise ValueError(
            "Document trop volumineux pour une seule page A4 : "
            "aucune information ne sera tronquée"
        )
    pdf.set_text_color(*NAVY)
    pdf.set_draw_color(*NAVY)
    for (label, x) in zip(signature_labels(kind), (10, 83)):
        pdf.set_font("Helvetica", "B", 8)
        pdf.set_xy(x, base_y)
        title_lines = wrap_pdf_text(pdf, label, 65)
        if len(title_lines) > 2:
            raise ValueError("Signature trop longue pour le format A4")
        pdf.multi_cell(65, 4, "\n".join(title_lines))
        pdf.rect(x, base_y + 9, 65, 18)
    draw_qr(pdf, doc, x=166, y=base_y, size=30)
    pdf.set_font("Helvetica", "", 7)
    pdf.set_xy(10, base_y + 29)
    pdf.multi_cell(148, 3.5, latin("ID de traçabilité QR : " + doc["trace_id"]))
    if pdf.page_no() != 1:
        raise ValueError("Document hors du format une page A4")
    result = pdf.output()
    return bytes(result) if not isinstance(result, str) else result.encode("latin-1")
