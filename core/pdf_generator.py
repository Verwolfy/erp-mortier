"""
Générateur de documents PDF unifié (Factures, Commandes, Paie...).
Gère automatiquement les en-têtes, pieds de page et multipages.
"""
from fpdf import FPDF
import base64
import tempfile
import os

from modules.documents.pdf_presentation import (
    amount_in_words, draw_qr, format_money, qr_payload, has_value,
)
from modules.documents.party_identity import (
    pdf_safe, wrap_pdf_text, wrap_table_cell_text, draw_table_cell_text,
)

def hex_to_rgb(hex_color):
    """Convertit une couleur Hex en tuple RGB."""
    hex_color = hex_color.lstrip('#') if hex_color else "0047AB"
    if len(hex_color) != 6: return (0, 71, 171)
    return tuple(int(hex_color[i:i + 2], 16) for i in (0, 2, 4))

class ERPDocument(FPDF):
    """Classe personnalisée pour unifier l'en-tête et le pied de page de tous les documents."""

    def __init__(self, doc_type, doc_id, date_doc, partner_info, params, is_supplier=False):
        super().__init__(orientation="P", unit="mm", format="A4")
        self.doc_type = doc_type
        self.doc_id = doc_id
        self.date_doc = date_doc
        self.partner_info = partner_info
        self.params = params
        self.is_supplier = is_supplier
        self.couleur_theme = hex_to_rgb(params.get("doc_couleur", "#0047AB"))
        self.devise = params.get("devise", "DZD")

        # Gestion sécurisée du logo en fichier temporaire
        self.logo_path = None
        if params.get("logo_base64"):
            try:
                img_data = base64.b64decode(params["logo_base64"])
                temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".png")
                temp_file.write(img_data)
                temp_file.close()
                self.logo_path = temp_file.name
            except Exception:
                pass

    def header(self):
        """En-tête généré automatiquement sur chaque page."""
        # Logo
        if self.logo_path and os.path.exists(self.logo_path):
            self.image(self.logo_path, x=10, y=10, w=40)

        # Infos Entreprise (Haut Gauche)
        self.set_xy(10, 35)
        self.set_font("helvetica", "B", 14)
        self.set_text_color(*self.couleur_theme)
        self.cell(100, 6, self.params.get("entreprise_nom", "SARL NEXT GENRATION BUILDING SOLUTIONS"), ln=True)

        self.set_font("helvetica", "", 10)
        self.set_text_color(0, 0, 0)
        if self.params.get("entreprise_slogan"): self.cell(100, 5, self.params.get("entreprise_slogan"), ln=True)
        if self.params.get("entreprise_adresse"): self.cell(100, 5, self.params.get("entreprise_adresse"), ln=True)
        if self.params.get("entreprise_tel"): self.cell(100, 5, f"Tél : {self.params.get('entreprise_tel')}", ln=True)

        # Titre Document (Haut Droite)
        self.set_xy(120, 10)
        self.set_font("helvetica", "B", 22)
        self.set_text_color(*self.couleur_theme)
        self.cell(80, 10, self.doc_type.upper(), align="R", ln=True)

        self.set_font("helvetica", "B", 12)
        self.set_text_color(0, 0, 0)
        self.set_x(120)
        self.multi_cell(80, 7, pdf_safe(f"Référence : {self.doc_id}"), align="R")
        self.set_font("helvetica", "", 10)
        self.cell(190, 6, f"Date : {self.date_doc[:10]}", align="R", ln=True)

        # Encart Partenaire (Client ou Fournisseur)
        self.set_xy(110, 45)
        self.set_font("helvetica", "B", 11)
        self.set_fill_color(240, 240, 240)
        titre_partenaire = " FOURNISSEUR :" if self.is_supplier else " FACTURÉ À :"
        self.cell(90, 8, titre_partenaire, border=0, fill=True, ln=True)

        self.set_x(110)
        self.set_font("helvetica", "B", 12)
        if has_value(self.partner_info.get("nom")):
            self.multi_cell(90, 6, pdf_safe(
                "Raison Sociale : " + str(self.partner_info["nom"])))

        self.set_x(110)
        self.set_font("helvetica", "", 10)
        if has_value(self.partner_info.get("adresse")):
            self.multi_cell(90, 5, pdf_safe(
                "Adresse de Facturation : " + str(self.partner_info["adresse"])))
        if self.partner_info.get("telephone"): self.cell(90, 5, f" Tél : {self.partner_info.get('telephone')}", ln=True)
        if self.partner_info.get("nif"): self.cell(90, 5, f" NIF : {self.partner_info.get('nif')}", ln=True)
        if self.partner_info.get("rc"): self.cell(90, 5, f" RC : {self.partner_info.get('rc')}", ln=True)

        self.ln(15)

    def footer(self):
        """Pied de page généré automatiquement sur chaque page."""
        self.set_y(-25)
        self.set_font("helvetica", "I", 8)
        self.set_text_color(128, 128, 128)

        # Ligne de séparation
        self.line(10, self.get_y(), 200, self.get_y())
        self.ln(2)

        # Mentions légales & bancaires
        footer_text = self.params.get("doc_footer", "")
        self.multi_cell(0, 4, footer_text, align="C")

        # Numéro de page (automatique grâce à FPDF {nb})
        self.cell(0, 4, f"Page {self.page_no()}/{{nb}}", align="C")

    def cleanup(self):
        """Supprime le fichier temporaire du logo pour libérer la mémoire."""
        if self.logo_path and os.path.exists(self.logo_path):
            os.unlink(self.logo_path)


def generer_document_standard(doc_type: str, doc_id: str, date_doc: str, partner_info: dict, lignes: list, totaux: dict, params: dict, is_supplier=False):
    """
    Génère un document unifié (Facture, Devis, Commande, etc.).
    """
    pdf = ERPDocument(doc_type, doc_id, date_doc, partner_info, params, is_supplier)
    pdf.set_auto_page_break(auto=False)
    pdf.alias_nb_pages() # Permet le décompte total des pages
    pdf.add_page()

    devise = pdf.devise

    # --- TABLEAU DES ARTICLES ---
    pdf.set_fill_color(*pdf.couleur_theme)
    pdf.set_text_color(255, 255, 255)
    pdf.set_font("helvetica", "B", 9)

    # Largeurs de colonnes (Total = 190mm)
    pdf.cell(75, 8, " Nom Produit", border=1, fill=True)
    pdf.cell(20, 8, " Quantité", border=1, align="C", fill=True)
    pdf.cell(30, 8, f" P.U. ({devise})", border=1, align="R", fill=True)
    pdf.cell(30, 8, f" Remise ({devise})", border=1, align="R", fill=True)
    pdf.cell(35, 8, f" Total HT ({devise})", border=1, align="R", fill=True)
    pdf.ln()

    pdf.set_text_color(0, 0, 0)
    pdf.set_font("helvetica", "", 9)

    for ligne in lignes:
        from decimal import Decimal
        qte = Decimal(str(ligne.get("quantite", 0)))
        prix = Decimal(str(ligne.get("prix_unitaire", 0)))
        remise = Decimal(str(ligne.get("remise", 0)))
        total_ht = Decimal(str(ligne.get("total_ht", (qte * prix) - remise)))
        values = [
            str(ligne.get("nom") or ""), f"{qte:f}",
            format_money(prix), format_money(remise), format_money(total_ht),
        ]
        sizes = [75, 20, 30, 30, 35]
        pdf.set_font("Helvetica", "", 9)
        cells = [wrap_table_cell_text(pdf, val, size)
                 for val, size in zip(values, sizes)]
        height = max(8, 4.4 * max(len(row) for row in cells) + 2)
        if height > 195:
            raise ValueError("Ligne trop longue pour impression A4")
        if pdf.get_y() + height > 249:
            pdf.cleanup()
            raise ValueError(
                "Document trop volumineux pour une seule page A4"
            )
        x, y = 10, pdf.get_y()
        for idx, (size, wrapped) in enumerate(zip(sizes, cells)):
            pdf.rect(x, y, size, height)
            draw_table_cell_text(
                pdf, wrapped, x=x, y=y, width=size, height=height,
                line_height=4.4, align="R" if idx > 0 else "L",
            )
            x += size
        pdf.set_xy(10, y + height)

    # --- BLOC DES TOTAUX COMPTABLES ---
    pdf.ln(5)
    # QR et totaux côte à côte, jamais sur une page supplémentaire.
    summary_y = pdf.get_y()
    total_fields = (
        "total_ht", "total_remise", "net_a_payer", "total_tva",
        "timbre_fiscal", "total_ttc",
    )
    count_totals = sum(has_value(totaux.get(k)) for k in total_fields)
    if max(summary_y + 35, summary_y + count_totals * 7) > 240:
        pdf.cleanup()
        raise ValueError("Espace insuffisant pour une seule page A4")
    draw_qr(pdf, qr_payload({
        "kind": doc_type, "id": doc_id, "date": date_doc,
        "lines": lignes, "totals": totaux,
        "statut": "COPIE NON ÉMISE",
    }), x=12, y=summary_y, size=28)
    pdf.set_xy(10, summary_y + 29)
    pdf.set_font("Helvetica", "", 7)
    pdf.multi_cell(90, 4, "QR de repérage ERP - copie non émise")
    pdf.set_y(summary_y)

    x_totals = 125
    w_label = 35
    w_value = 30

    def print_total_line(label, value, bold=False, text_color=(0,0,0)):
        pdf.set_x(x_totals)
        pdf.set_font("helvetica", "B" if bold else "", 10)
        pdf.set_text_color(*text_color)
        pdf.cell(w_label, 7, label, border=0)
        pdf.cell(w_value, 7, f"{format_money(value)} {devise}", border=0, align="R", ln=True)

    for key, label, bold in (
            ("total_ht", "Total HT :", False),
            ("total_remise", "Remise :", False),
            ("net_a_payer", "Net à payer HT :", True),
            ("total_tva", "TVA :", False),
            ("timbre_fiscal", "Timbre fiscal :", False),
            ("total_ttc", "TOTAL TTC :", True)):
        if has_value(totaux.get(key)):
            if pdf.get_y() + 7 > 248:
                pdf.cleanup()
                raise ValueError("Totaux trop longs pour une seule page A4")
            print_total_line(label, float(totaux[key]), bold=bold,
                             text_color=pdf.couleur_theme if key == "total_ttc" else (0, 0, 0))

    # --- MONTANT EN LETTRES ---
    pdf.set_y(max(pdf.get_y(), summary_y + 37))
    pdf.ln(3)
    pdf.set_font("helvetica", "B", 10)
    pdf.set_text_color(0, 0, 0)
    montant_lettres = totaux.get("montant_lettres")
    if not has_value(montant_lettres) and has_value(totaux.get("total_ttc")):
        montant_lettres = amount_in_words(totaux["total_ttc"])
    if has_value(montant_lettres):
        pdf.multi_cell(0, 6, pdf_safe(
            f"Arrêté le présent document à la somme de : {montant_lettres}"))

    if pdf.get_y() > 261 or pdf.page_no() != 1:
        pdf.cleanup()
        raise ValueError("Document trop volumineux pour une seule page A4")
    pdf.cleanup()
    # Retourne les bytes directement compatibles avec Streamlit
    return bytes(pdf.output())