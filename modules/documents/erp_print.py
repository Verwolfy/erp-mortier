"""Impression de COPIES ERP à partir d'opérations enregistrées, lecture seule.

Ne génère jamais de facture fiscale homologuée, ne signe ni n'émet de document.
Les valeurs et taxes imprimées proviennent exclusivement des lignes persistées.
Chaque lecture réutilise le contrôle RBAC frais de core.strict_reads.
"""
from __future__ import annotations

from datetime import date
from decimal import Decimal, InvalidOperation
from io import BytesIO
import re

KINDS = {
    "Ordre de fabrication": ("ordres_fabrication", "of_id", None, None),
    "Bon de livraison": ("bons_livraison", "bl_id", "lignes_bons_livraison", "bl_id"),
    "Facture (aperçu interne)": ("factures", "facture_id", "lignes_facture", "facture_id"),
    "Bon de réception": ("bons_reception", "bon_reception_id", "lignes_bons_reception", "bon_reception_id"),
    "Commande client": ("commandes_ventes", "commande_vente_id", "lignes_commande_ventes", "commande_vente_id"),
    "Commande fournisseur": ("commandes_achats", "commande_achat_id", "lignes_achats", "commande_achat_id"),
    "Facture fournisseur (aperçu interne)": (
        "factures_fournisseurs", "facture_fournisseur_id",
        "lignes_factures_fournisseurs", "facture_fournisseur_id"),
    "Devis commercial": ("devis", "devis_id", "lignes_devis", "devis_id"),
}
_IDENT = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.:/-]{0,127}\Z")


class OperationPrintError(ValueError):
    """Dossier documentaire non vérifiable."""


def _amount(value: object, *, allow_null: bool = True) -> str:
    if value is None and allow_null:
        return ""
    if isinstance(value, bool):
        raise OperationPrintError("Montant invalide")
    try:
        n = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise OperationPrintError("Montant invalide") from exc
    if not n.is_finite() or n < 0 or n >= Decimal("1e15"):
        raise OperationPrintError("Montant invalide")
    return format(n, "f")


def _day(value: object) -> str:
    if not isinstance(value, str) or len(value) < 10:
        raise OperationPrintError("Date du document absente")
    try:
        return date.fromisoformat(value[:10]).isoformat()
    except ValueError as exc:
        raise OperationPrintError("Date du document invalide") from exc


def _single(reader, table: str, key: str, value: str) -> dict:
    records = reader(table, equal_column=key, equal_value=value, max_rows=2)
    if not isinstance(records, list) or len(records) != 1 or not isinstance(records[0], dict):
        raise OperationPrintError("Dossier absent ou ambigu")
    if records[0].get(key) != value:
        raise OperationPrintError("Référence de dossier incohérente")
    return records[0]


def _lines(reader, table: str, key: str, value: str) -> list[dict]:
    records = reader(table, equal_column=key, equal_value=value, max_rows=200)
    if not isinstance(records, list) or not records or len(records) > 200 or any(
        not isinstance(x, dict) or x.get(key) != value for x in records
    ):
        raise OperationPrintError("Lignes absentes ou incohérentes")
    return records


def load_operation_snapshot(kind: str, identifier: str, *, reader=None) -> dict:
    """Résout une opération existante ; aucun montant fiscal n'est recalculé."""
    if kind not in KINDS or not isinstance(identifier, str) or not _IDENT.fullmatch(identifier):
        raise OperationPrintError("Type ou référence non valide")
    if reader is None:
        from core.strict_reads import fetch_data_strict
        reader = fetch_data_strict
    table, pk, line_table, foreign_key = KINDS[kind]
    header = _single(reader, table, pk, identifier)
    source_lines = (_lines(reader, line_table, foreign_key, identifier)
                    if line_table else [])
    meta: list[tuple[str, str]] = []
    totals: list[tuple[str, str]] = []
    partner = ""
    party_record = None
    party_role = ""
    if kind == "Ordre de fabrication":
        source_lines = [{
            "sku_id": header.get("sku_id"),
            "quantite": header.get("quantite_prevue"),
        }]
        meta = [
            ("Produit", str(header.get("pf_id") or "")),
            ("Recette", str(header.get("recette_id") or "")),
            ("Statut", str(header.get("statut") or "")),
            ("Quantité produite", _amount(header.get("quantite_produite"))),
            ("Notes", str(header.get("notes") or "")),
        ]
        doc_date = header.get("date_planification")
    elif kind == "Devis commercial":
        client_id = header.get("client_id")
        if not isinstance(client_id, str) or not client_id:
            raise OperationPrintError("Client de devis non rattaché")
        client = _single(reader, "clients", "client_id", client_id)
        partner = str(client.get("nom") or client_id)
        party_record, party_role = client, "CLIENT"
        meta = [
            ("Client", partner),
            ("Statut du devis enregistré", str(header.get("statut") or "NON RENSEIGNÉ")),
            ("Commercial (référence)", str(header.get("commercial_id") or "NON RENSEIGNÉ")),
            ("Validité enregistrée", str(header.get("validite") or "NON RENSEIGNÉE")),
            ("Montants totaux", "Non enregistrés dans l'en-tête ; aucun calcul présumé"),
        ]
        doc_date = header.get("date")
    elif kind in ("Bon de livraison", "Commande client"):
        order = (header if kind == "Commande client" else
                 _single(reader, "commandes_ventes", "commande_vente_id",
                         str(header.get("commande_vente_id") or "")))
        client_id = order.get("client_id")
        if not isinstance(client_id, str) or not client_id:
            raise OperationPrintError("Client non rattaché")
        client = _single(reader, "clients", "client_id", client_id)
        partner = str(client.get("nom") or client_id)
        party_record, party_role = client, "CLIENT"
        meta = [("Client", partner), ("Commande", str(order.get("commande_vente_id") or "")),
                ("Statut", str(header.get("statut") or ""))]
        if kind == "Bon de livraison":
            meta.extend([("Transporteur", str(header.get("transporteur") or "")),
                         ("Zone", str(header.get("zone") or ""))])
        doc_date = header.get("date")
    elif kind == "Facture (aperçu interne)":
        client_id = header.get("client_id")
        if not isinstance(client_id, str) or not client_id:
            raise OperationPrintError("Client non rattaché")
        client = _single(reader, "clients", "client_id", client_id)
        partner = str(client.get("nom") or client_id)
        party_record, party_role = client, "CLIENT"
        meta = [("Client", partner), ("Statut ERP", str(header.get("statut") or "")),
                ("Type ERP", str(header.get("type_facture") or "")),
                ("Commande", str(header.get("commande_vente_id") or ""))]
        totals = [
            ("Total HT enregistré", _amount(header.get("montant_ht"))),
            ("TVA enregistrée (non homologuée)", _amount(header.get("montant_tva"))),
            ("Timbre enregistré", _amount(header.get("montant_timbre"))),
            ("Total TTC enregistré", _amount(header.get("montant_ttc"))),
        ]
        doc_date = header.get("date")
    elif kind == "Facture fournisseur (aperçu interne)":
        order_id = header.get("commande_achat_id")
        if not isinstance(order_id, str) or not order_id:
            raise OperationPrintError("Commande fournisseur absente")
        order = _single(reader, "commandes_achats", "commande_achat_id", order_id)
        supplier_id = header.get("fournisseur_id")
        if not isinstance(supplier_id, str) or not supplier_id or order.get("fournisseur_id") != supplier_id:
            raise OperationPrintError("Fournisseur facture/commande incohérent")
        supplier = _single(reader, "fournisseurs", "fournisseur_id", supplier_id)
        partner = str(supplier.get("nom") or supplier_id)
        party_record, party_role = supplier, "FOURNISSEUR"
        meta = [
            ("Fournisseur", partner),
            ("Commande fournisseur", order_id),
            ("Référence facture fournisseur", str(header.get("reference_facture_fournisseur") or "NON RENSEIGNÉE")),
            ("Statut paiement enregistré", str(header.get("statut_paiement") or "NON RENSEIGNÉ")),
            ("Taux TVA enregistré (non homologué)", _amount(header.get("taux_tva"))),
        ]
        totals = [
            ("Total HT enregistré", _amount(header.get("montant_ht"))),
            ("TVA enregistrée (non homologuée)", _amount(header.get("montant_tva"))),
            ("Total TTC enregistré", _amount(header.get("montant_ttc"))),
        ]
        doc_date = header.get("date")
    else:
        order = (header if kind == "Commande fournisseur" else
                 _single(reader, "commandes_achats", "commande_achat_id",
                         str(header.get("commande_achat_id") or "")))
        supplier_id = order.get("fournisseur_id")
        if not isinstance(supplier_id, str) or not supplier_id:
            raise OperationPrintError("Fournisseur non rattaché")
        supplier = _single(reader, "fournisseurs", "fournisseur_id", supplier_id)
        partner = str(supplier.get("nom") or supplier_id)
        party_record, party_role = supplier, "FOURNISSEUR"
        meta = [("Fournisseur", partner),
                ("Commande", str(order.get("commande_achat_id") or "")),
                ("Statut", str(header.get("statut") or ""))]
        if kind == "Bon de réception":
            meta.append(("Contrôle conformité", str(header.get("controle_conformite") or "")))
            doc_date = header.get("date_reception")
        else:
            totals = [("Total DZD enregistré", _amount(header.get("montant_total_local")))]
            doc_date = header.get("date_commande")
    lines = []
    for row in source_lines:
        sku_id = row.get("sku_id")
        mp_id = row.get("mp_id")
        if kind == "Facture fournisseur (aperçu interne)":
            # mp_id_ou_service peut désigner une prestation : ne jamais prétendre
            # que chaque ligne est une matière première ou inventer une unité.
            article = row.get("mp_id_ou_service")
            if not isinstance(article, str) or not article.strip():
                raise OperationPrintError("Article ou prestation de facture absent")
            designation, unit = article, ""
        else:
            article = sku_id or mp_id
            if not isinstance(article, str) or not article:
                raise OperationPrintError("Article de ligne absent")
            if sku_id:
                sku = _single(reader, "sku_conditionnement", "sku_id", sku_id)
                product = _single(reader, "produits", "pf_id", str(sku.get("pf_id") or ""))
                designation = f"{product.get('nom') or sku_id} — {sku.get('format') or ''}"
                unit = str(sku.get("unite_vente") or "")
            else:
                material = _single(reader, "matieres_premieres", "mp_id", mp_id)
                designation = str(material.get("nom") or mp_id)
                unit = str(material.get("unite_stock") or "")
                if kind == "Commande fournisseur":
                    # Une commande conserve son unité historique dans la ligne.
                    # Ne pas substituer l'unité actuelle si elle a changé depuis.
                    recorded_unit = row.get("unite_cond")
                    if isinstance(recorded_unit, str) and recorded_unit.strip():
                        unit = recorded_unit.strip()
        if kind == "Bon de livraison":
            qty = row.get("quantite_livree")
        elif kind == "Bon de réception":
            qty = row.get("quantite_recue")
        elif kind == "Commande fournisseur":
            qty = row.get("qte_totale")
        else:
            qty = row.get("quantite")
        discount = row.get("remise_ligne") if kind == "Facture (aperçu interne)" else None
        if discount is not None and Decimal(_amount(discount)) != 0:
            designation += f" (remise enregistrée : {_amount(discount)})"
        if kind == "Devis commercial":
            rate = row.get("remise_pct")
            if rate is not None:
                parsed_rate = Decimal(_amount(rate))
                if parsed_rate > Decimal("100"):
                    raise OperationPrintError("Remise de devis hors limites")
                designation += f" (remise enregistrée : {_amount(rate)} %)"
        lines.append({
            "reference": article, "designation": designation, "unite": unit,
            "quantite": _amount(qty, allow_null=False),
            "prix_unitaire": _amount(row.get("prix_unitaire")),
            "total_ht": _amount(
                row.get("total_ligne_ht") if kind == "Facture (aperçu interne)"
                else row.get("total_ht") if kind == "Facture fournisseur (aperçu interne)"
                else row.get("total_devise") if kind == "Commande fournisseur" else None),
            "lot": str(row.get("lot_id") or row.get("lot_attribue_id") or ""),
        })
    if not lines or len(lines) > 200:
        raise OperationPrintError("Lignes d'opération invalides")
    from modules.documents.party_identity import normalize_party
    return {
        "kind": kind, "id": identifier, "date": _day(doc_date),
        "partner": partner, "meta": meta, "totals": totals, "lines": lines,
        "party_fields": normalize_party(party_record) if party_record is not None else [],
        "party_role": party_role,
        "currency": (
            str(header.get("devise") or "DZD").strip().upper()
            if kind == "Commande fournisseur" else "DZD"
        ),
        "source": table, "warning": (
            "APERÇU INTERNE - NON VALABLE FISCALEMENT / NON ÉMIS"
            if kind in ("Facture (aperçu interne)", "Facture fournisseur (aperçu interne)")
            else "COPIE DE CONSULTATION - NON SIGNÉE / NON ÉMISE"
        ),
    }


def render_operation_pdf(snapshot: dict) -> bytes:
    """Copie A4 lisible : identité légale émetteur/destinataire + lignes non tronquées.

    Les champs RC/NIF/NIS/AI manquants apparaissent comme "Non renseigné".
    Pas d'émission, de calcul fiscal ni de validation commerciale.
    """
    from pathlib import Path
    from fpdf import FPDF
    from fpdf.enums import XPos, YPos
    from modules.documents.branding_images import branded_images
    from modules.documents.party_identity import (
        NAVY, GREEN, PALE, configured_company, draw_party_panels,
        pdf_safe, wrap_pdf_text,
    )

    if not isinstance(snapshot, dict) or snapshot.get("kind") not in KINDS:
        raise OperationPrintError("Dossier d'impression invalide")
    if not isinstance(snapshot.get("lines"), list) or not 1 <= len(snapshot["lines"]) <= 200:
        raise OperationPrintError("Lignes d'impression invalides")

    logo = Path("assets/nextgen_logo_hd.jpg")
    header_png, footer_png = branded_images(str(logo) if logo.is_file() else None)

    class OperationPDF(FPDF):
        def header(self):
            self.image(BytesIO(header_png), x=0, y=0, w=210, h=46.2)

        def footer(self):
            self.image(BytesIO(footer_png), x=0, y=268, w=210, h=24.36)
            self.set_y(-8)
            self.set_font("Helvetica", "", 7)
            self.set_text_color(*NAVY)
            self.cell(190, 5, f"Page {self.page_no()}/{{nb}}", align="R")

    pdf = OperationPDF(format="A4", unit="mm")
    pdf.alias_nb_pages()
    pdf.set_auto_page_break(auto=True, margin=36)
    pdf.add_page()
    pdf.set_y(49)

    def ensure_height(height: float, *, extra_margin: float = 0) -> None:
        if pdf.get_y() + height + extra_margin > 255:
            pdf.add_page()
            pdf.set_y(50)

    # Bandeau titre cohérent avec les autres documents NEXTGEN.
    pdf.set_fill_color(*NAVY)
    pdf.set_text_color(255, 255, 255)
    pdf.set_font("Helvetica", "B", 13)
    pdf.cell(190, 11, pdf_safe(snapshot["kind"]).upper(),
             align="C", fill=True, new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.set_text_color(175, 32, 40)
    pdf.set_font("Helvetica", "B", 8.5)
    pdf.multi_cell(190, 5, pdf_safe(snapshot["warning"]),
                   align="C", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.ln(2)
    pdf.set_fill_color(*PALE)
    pdf.set_text_color(*NAVY)
    pdf.set_font("Helvetica", "B", 9)
    pdf.cell(190, 8, pdf_safe(f"Référence : {snapshot['id']}     |     Date : {snapshot['date']}"),
             fill=True, new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.ln(3)

    counterpart = snapshot.get("party_fields")
    if isinstance(counterpart, list) and counterpart:
        issuer = configured_company()
        if snapshot["kind"] == "Facture fournisseur (aperçu interne)":
            # L'original vient du fournisseur : ne jamais présenter NEXTGEN
            # comme émetteur de cette facture tierce.
            draw_party_panels(pdf, "FOURNISSEUR - ÉMETTEUR", counterpart,
                              "NEXTGEN - DESTINATAIRE", issuer)
        else:
            title = "FOURNISSEUR" if snapshot.get("party_role") == "FOURNISSEUR" else "CLIENT"
            draw_party_panels(pdf, "NEXTGEN - ÉMETTEUR", issuer, title, counterpart)

    # Metadata opérationnelles, sans redoubler la raison sociale du tiers.
    metadata = [(label, value) for label, value in snapshot["meta"]
                if label not in ("Client", "Fournisseur")]
    if metadata:
        ensure_height(9)
        pdf.set_fill_color(*PALE)
        pdf.set_text_color(*NAVY)
        pdf.set_font("Helvetica", "B", 8.5)
        pdf.cell(190, 7, "Informations de l'opération",
                 fill=True, new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        pdf.set_font("Helvetica", "", 8)
        for label, value in metadata:
            lines = wrap_pdf_text(pdf, f"{label} : {value}", 186)
            for line in lines:
                ensure_height(5)
                pdf.cell(190, 4.5, line,
                         new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        pdf.ln(3)

    currency = pdf_safe(snapshot.get("currency") or "DZD")
    is_order = snapshot["kind"] == "Commande fournisseur"
    headings = [
        "Référence", "Désignation", "Unité", "Qté",
        f"P.U. {currency}" if is_order else "P.U.",
        f"Montant {currency}" if is_order else "Total HT",
    ]
    widths = [27, 65, 18, 17, 32, 31]  # somme = 190 mm

    def table_header() -> None:
        ensure_height(9)
        pdf.set_x(10)
        pdf.set_fill_color(*NAVY)
        pdf.set_text_color(255, 255, 255)
        pdf.set_font("Helvetica", "B", 7.6)
        for width, title in zip(widths, headings):
            pdf.cell(width, 8, pdf_safe(title), border=1, fill=True)
        pdf.ln(8)
        pdf.set_text_color(*NAVY)

    table_header()
    for index, item in enumerate(snapshot["lines"]):
        if not isinstance(item, dict):
            raise OperationPrintError("Ligne d'impression invalide")
        values = [
            item.get("reference", ""), item.get("designation", ""),
            item.get("unite", ""), item.get("quantite", ""),
            item.get("prix_unitaire", ""), item.get("total_ht", ""),
        ]
        pdf.set_font("Helvetica", "", 7.5)
        wrapped = [
            wrap_pdf_text(pdf, v, width - 3) for width, v in zip(widths, values)
        ]
        row_height = max(8, max(len(lines) for lines in wrapped) * 4.1 + 2)
        if row_height > 185:
            raise OperationPrintError("Ligne trop longue pour l'impression A4")
        if pdf.get_y() + row_height > 254:
            pdf.add_page()
            pdf.set_y(50)
            table_header()

        row_y = pdf.get_y()
        fill = index % 2 == 1
        if fill:
            pdf.set_fill_color(*PALE)
        x = 10
        for col, (width, lines) in enumerate(zip(widths, wrapped)):
            pdf.rect(x, row_y, width, row_height, style="DF" if fill else "D")
            pdf.set_xy(x + 1.5, row_y + 1.0)
            pdf.multi_cell(width - 3, 4.1, "\n".join(lines),
                           align="R" if col >= 3 else "L")
            x += width
        pdf.set_xy(10, row_y + row_height)
        if item.get("lot"):
            pdf.set_font("Helvetica", "I", 7.1)
            lot_lines = wrap_pdf_text(pdf, f"Lot : {item['lot']}", 186)
            for lot_line in lot_lines:
                ensure_height(5)
                pdf.cell(190, 4.5, lot_line,
                         new_x=XPos.LMARGIN, new_y=YPos.NEXT)

    pdf.ln(4)
    pdf.set_text_color(*NAVY)
    for label, value in snapshot["totals"]:
        ensure_height(9)
        text = f"{label} : {value} DZD" if value else f"{label} : NON RENSEIGNÉ"
        pdf.set_x(82)
        pdf.set_font("Helvetica", "B", 8.7)
        pdf.set_fill_color(*PALE)
        pdf.cell(118, 8, pdf_safe(text), fill=True, align="R",
                 new_x=XPos.LMARGIN, new_y=YPos.NEXT)

    ensure_height(24)
    pdf.ln(6)
    pdf.set_font("Helvetica", "I", 8)
    pdf.set_text_color(*NAVY)
    pdf.multi_cell(
        190, 5, "Copie de consultation des données enregistrées dans l'ERP. "
        "Aucune signature, émission, validation fiscale ou comptable produite.",
        new_x=XPos.LMARGIN, new_y=YPos.NEXT,
    )
    result = pdf.output()
    return bytes(result) if not isinstance(result, str) else result.encode("latin-1")
