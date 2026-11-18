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
    elif kind in ("Bon de livraison", "Commande client"):
        order = (header if kind == "Commande client" else
                 _single(reader, "commandes_ventes", "commande_vente_id",
                         str(header.get("commande_vente_id") or "")))
        client_id = order.get("client_id")
        if not isinstance(client_id, str) or not client_id:
            raise OperationPrintError("Client non rattaché")
        client = _single(reader, "clients", "client_id", client_id)
        partner = str(client.get("nom") or client_id)
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
    else:
        order = (header if kind == "Commande fournisseur" else
                 _single(reader, "commandes_achats", "commande_achat_id",
                         str(header.get("commande_achat_id") or "")))
        supplier_id = order.get("fournisseur_id")
        if not isinstance(supplier_id, str) or not supplier_id:
            raise OperationPrintError("Fournisseur non rattaché")
        supplier = _single(reader, "fournisseurs", "fournisseur_id", supplier_id)
        partner = str(supplier.get("nom") or supplier_id)
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
        lines.append({
            "reference": article, "designation": designation, "unite": unit,
            "quantite": _amount(qty, allow_null=False),
            "prix_unitaire": _amount(row.get("prix_unitaire")),
            "total_ht": _amount(
                row.get("total_ligne_ht") if kind == "Facture (aperçu interne)"
                else row.get("total_devise") if kind == "Commande fournisseur" else None),
            "lot": str(row.get("lot_id") or row.get("lot_attribue_id") or ""),
        })
    if not lines or len(lines) > 200:
        raise OperationPrintError("Lignes d'opération invalides")
    return {
        "kind": kind, "id": identifier, "date": _day(doc_date),
        "partner": partner, "meta": meta, "totals": totals, "lines": lines,
        "source": table, "warning": (
            "APERÇU INTERNE - NON VALABLE FISCALEMENT / NON ÉMIS"
            if kind == "Facture (aperçu interne)"
            else "COPIE DE CONSULTATION - NON SIGNÉE / NON ÉMISE"
        ),
    }


def render_operation_pdf(snapshot: dict) -> bytes:
    """PDF de consultation lisible et imprimable, sans prétention de certification."""
    from fpdf import FPDF
    from fpdf.enums import XPos, YPos

    def latin(value: object, limit: int = 240) -> str:
        return str(value if value is not None else "").encode(
            "latin-1", "replace").decode("latin-1")[:limit]

    if not isinstance(snapshot, dict) or snapshot.get("kind") not in KINDS:
        raise OperationPrintError("Dossier d'impression invalide")
    if not isinstance(snapshot.get("lines"), list) or not 1 <= len(snapshot["lines"]) <= 200:
        raise OperationPrintError("Lignes d'impression invalides")
    pdf = FPDF(format="A4", unit="mm")
    pdf.set_auto_page_break(auto=True, margin=18)
    pdf.add_page()
    pdf.set_font("Helvetica", "B", 15)
    pdf.set_text_color(14, 43, 79)
    pdf.cell(190, 10, "NEXTGEN - " + latin(snapshot["kind"]).upper(),
             new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.set_font("Helvetica", "B", 9)
    pdf.set_text_color(175, 32, 40)
    pdf.multi_cell(190, 6, latin(snapshot["warning"]),
                   new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.set_text_color(0, 0, 0)
    pdf.set_font("Helvetica", "", 9)
    pdf.cell(190, 6, f"Référence ERP : {latin(snapshot['id'])}   |   Date : {latin(snapshot['date'])}",
             new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    for label, value in snapshot["meta"]:
        pdf.multi_cell(190, 5, latin(label + " : " + value, 180),
                       new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.ln(4)
    widths = [32, 74, 17, 19, 24, 24]
    headers = ["Référence", "Désignation", "Unité", "Qté", "P.U.", "Total HT"]
    pdf.set_fill_color(14, 43, 79)
    pdf.set_text_color(255, 255, 255)
    pdf.set_font("Helvetica", "B", 8)
    for width, title in zip(widths, headers):
        pdf.cell(width, 8, latin(title), border=1, fill=True)
    pdf.ln(8)
    pdf.set_text_color(0, 0, 0)
    pdf.set_font("Helvetica", "", 7.5)
    for row in snapshot["lines"]:
        values = [row.get("reference", ""), row.get("designation", ""),
                  row.get("unite", ""), row.get("quantite", ""),
                  row.get("prix_unitaire", ""), row.get("total_ht", "")]
        if pdf.get_y() > 250:
            pdf.add_page()
            pdf.set_font("Helvetica", "", 7.5)
        for width, value in zip(widths, values):
            pdf.cell(width, 9, latin(value, 40), border=1)
        pdf.ln(9)
        if row.get("lot"):
            pdf.set_font("Helvetica", "I", 7)
            pdf.cell(190, 5, "Lot : " + latin(row["lot"]),
                     new_x=XPos.LMARGIN, new_y=YPos.NEXT)
            pdf.set_font("Helvetica", "", 7.5)
    pdf.ln(4)
    pdf.set_font("Helvetica", "B", 9)
    for label, value in snapshot["totals"]:
        pdf.cell(190, 6, latin(f"{label} : {value if value else 'NON RENSEIGNÉ'} DZD"
                              if value else f"{label} : NON RENSEIGNÉ"),
                 new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.ln(5)
    pdf.set_font("Helvetica", "I", 8)
    pdf.multi_cell(190, 5, "Copie de lecture seule des données enregistrées dans l'ERP. "
                   "Aucune signature, émission, validation fiscale ou comptable n'est produite.")
    return bytes(pdf.output())
