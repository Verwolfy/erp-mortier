"""Copies documentaires internes pour Finance, Stocks et RH.

Chaque copie est une photographie *de consultation* des seules lignes persistées.
Ne crée, n'approuve, ne signe et ne transmet aucun document. N'atteste aucune
conformité fiscale, comptable, sociale ni un mouvement de stock supplémentaire.
"""
from __future__ import annotations

from datetime import date
from decimal import Decimal, InvalidOperation
from io import BytesIO
from pathlib import Path
import re

from modules.documents.pdf_presentation import (
    draw_qr, format_money, has_value, qr_payload,
)

_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.:/-]{0,127}\Z")

# (table, clé primaire, libellé)
INTERNAL_KINDS = {
    "Accusé interne d'encaissement": ("erp_recus_internes", "recu_id", "Finance"),
    "Demande de congé": ("demandes_conges", "demande_conge_id", "RH"),
    "Fiche de mouvement MP": ("mouvements", "mouvement_id", "Stocks"),
    "Fiche de mouvement PF": ("mouvements_pf", "mouvement_pf_id", "Stocks"),
    "Fiche de consommation OF": ("consommations_of", "consommation_id", "Production"),
    "Compte rendu de contrôle qualité": ("controle_qualite", "qc_id", "Production"),
    # Registre ERP-062 NON ACTIF : chargement réservé au service RBAC Achats spécialisé.
    "Demande d'achat (copie interne)": ("erp_purchase_requests", "demande_id", "Achats"),
}


class InternalPrintError(ValueError):
    """Dossier interne absent, incohérent ou non consultable."""


def _required(row: dict, field: str) -> str:
    value = row.get(field)
    if not isinstance(value, str) or not value.strip():
        raise InternalPrintError(f"Champ {field} absent")
    return value.strip()


def _optional(row: dict, field: str) -> str:
    value = row.get(field)
    return "" if value is None or value == "" else str(value)


def _day(value: object) -> str:
    if not isinstance(value, str) or len(value) < 10:
        raise InternalPrintError("Date absente")
    try:
        return date.fromisoformat(value[:10]).isoformat()
    except ValueError as exc:
        raise InternalPrintError("Date incorrecte") from exc


def _amount(value: object, *, allow_zero: bool = False) -> str:
    if isinstance(value, bool) or value is None:
        raise InternalPrintError("Montant ou quantité invalide")
    try:
        number = Decimal(str(value))
    except (ValueError, TypeError, InvalidOperation) as exc:
        raise InternalPrintError("Montant ou quantité invalide") from exc
    if not number.is_finite() or number < 0 or number >= Decimal("1e15") or (
            not allow_zero and number == 0):
        raise InternalPrintError("Montant ou quantité invalide")
    return format(number, "f")


def load_internal_snapshot(kind: str, identifier: str, *, reader=None) -> dict:
    """Une lecture stricte RBAC et bornée, jamais un cache par utilisateur."""
    if (kind not in INTERNAL_KINDS or type(identifier) is not str
            or not _ID.fullmatch(identifier)):
        raise InternalPrintError("Référence ou type documentaire invalide")
    if kind == "Demande d'achat (copie interne)":
        if reader is not None:
            raise InternalPrintError("Accès DA réservé au service Achats ERP-062")
        from modules.achats.request_print import load_request_snapshot
        return load_request_snapshot(identifier)
    if reader is None:
        from core.strict_reads import fetch_data_strict
        reader = fetch_data_strict
    table, pk, section = INTERNAL_KINDS[kind]
    rows = reader(table, equal_column=pk, equal_value=identifier, max_rows=2)
    if (not isinstance(rows, list) or len(rows) != 1 or
            not isinstance(rows[0], dict) or rows[0].get(pk) != identifier):
        raise InternalPrintError("Dossier absent ou ambigu")
    row = rows[0]
    date_label = "Date"

    if kind == "Accusé interne d'encaissement":
        if (_required(row, "statut") != "INTERNE_NON_FISCAL"
                or _required(row, "timbre_statut") != "NON_CALCULE"):
            raise InternalPrintError("Accusé interne non vérifiable")
        partner = _required(row, "client_id")
        date_doc = _day(row.get("date_reglement"))
        fields = [
            ("Client (référence)", partner),
            ("Règlement (référence)", _required(row, "reglement_id")),
            ("Montant encaissé enregistré (DZD)", _amount(row.get("montant_encaisse"))),
            ("Mode de paiement", _optional(row, "mode_paiement")),
            ("Référence de règlement", _optional(row, "reference_reglement")),
            ("Statut de l'accusé", _required(row, "statut")),
            ("Timbre fiscal", "NON CALCULÉ / NON ATTESTÉ"),
        ]
        warning = ("ACCUSÉ INTERNE DE GESTION — NON FISCAL / NON SIGNÉ. "
                   "Ce document n'est pas une quittance légale et ne constate "
                   "aucun timbre ni nouvel encaissement.")
    elif kind == "Demande de congé":
        partner = _required(row, "employe_id")
        date_doc = _day(row.get("date_debut"))
        date_fin = _day(row.get("date_fin"))
        if date_fin < date_doc:
            raise InternalPrintError("Période du congé incohérente")
        fields = [
            ("Employé (référence)", partner),
            ("Date de début", date_doc),
            ("Date de fin", date_fin),
            ("Motif enregistré", _optional(row, "motif")),
            ("Statut ERP", _required(row, "statut")),
        ]
        warning = ("COPIE D'UNE DEMANDE ENREGISTRÉE — NON SIGNÉE. "
                   "Ne vaut pas autorisation de congé ni approbation de la hiérarchie.")
    elif kind == "Fiche de consommation OF":
        partner = _required(row, "of_id")
        date_doc = "NON ENREGISTRÉE DANS LE REGISTRE"
        date_label = "Date du mouvement de consommation"
        fields = [
            ("Ordre de fabrication (référence)", partner),
            ("Matière première (référence)", _required(row, "mp_id")),
            ("Lot consommé (référence)", _optional(row, "lot_id")),
            ("Quantité consommée enregistrée", _amount(row.get("quantite_consommee"))),
        ]
        warning = ("FICHE INTERNE DE CONSOMMATION — NON SIGNÉE. "
                   "Le registre ne contient pas la date propre de la consommation. "
                   "Aucune sortie supplémentaire de matière n'est générée.")
    elif kind == "Compte rendu de contrôle qualité":
        partner = _required(row, "of_id")
        date_doc = _day(row.get("date"))
        fields = [
            ("Ordre de fabrication (référence)", partner),
            ("Conformité enregistrée", _required(row, "conforme")),
            ("Contrôleur enregistré", _required(row, "controleur")),
            ("Observations enregistrées", _optional(row, "remarques")),
        ]
        warning = ("COPIE INTERNE DU CONTRÔLE QUALITÉ — NON SIGNÉE. "
                   "Ne constitue ni certificat qualité externe ni nouveau visa.")
    else:
        is_mp = kind == "Fiche de mouvement MP"
        partner = _required(row, "mp_id" if is_mp else "sku_id")
        date_doc = _day(row.get("date"))
        fields = [
            ("Article (référence)", partner),
            ("Type de mouvement", _required(row, "type_mouvement")),
            ("Quantité de mouvement enregistrée", _amount(row.get("quantite"))),
            ("Référence source", _optional(row, "reference")),
            ("Lot enregistré", _optional(row, "lot_id")),
        ]
        cost_field = "prix_entree" if is_mp else "cout_unitaire"
        if row.get(cost_field) not in ("", None):
            fields.append(("Coût/prix unitaire historique (DZD)",
                           _amount(row[cost_field], allow_zero=True)))
        warning = ("FICHE DE TRAÇABILITÉ DE MOUVEMENT — COPIE NON SIGNÉE. "
                   "N'est pas un bon de réception, de transfert ou de sortie homologué ; "
                   "aucune nouvelle écriture de stock n'est réalisée.")

    return {
        "kind": kind, "id": identifier, "date": date_doc,
        "section": section, "partner": partner, "source": table,
        "fields": fields, "warning": warning, "date_label": date_label,
    }


def render_internal_pdf(snapshot: dict) -> bytes:
    """PDF A4 NEXTGEN : simple copie de traçabilité, sans signature simulée."""
    from fpdf import FPDF
    from fpdf.enums import XPos, YPos
    from modules.documents.branding_images import branded_images

    if not isinstance(snapshot, dict) or snapshot.get("kind") not in INTERNAL_KINDS:
        raise InternalPrintError("Type interne inconnu")
    if not isinstance(snapshot.get("fields"), list) or not snapshot["fields"]:
        raise InternalPrintError("Données internes absentes")
    for required in ("id", "date", "warning", "source"):
        if not isinstance(snapshot.get(required), str) or not snapshot[required]:
            raise InternalPrintError("Métadonnées incomplètes")

    def safe(value: object, limit: int = 2000) -> str:
        from modules.documents.party_identity import pdf_safe
        text = pdf_safe(value)
        if len(text) > limit:
            raise InternalPrintError("Texte trop long pour une impression non tronquée")
        return text

    logo = Path("assets/nextgen_logo_hd.jpg")
    header, footer = branded_images(str(logo) if logo.is_file() else None)

    class InternalPDF(FPDF):
        def header(self):
            self.image(BytesIO(header), x=0, y=0, w=210, h=46.2)

        def footer(self):
            self.image(BytesIO(footer), x=0, y=268, w=210, h=24.36)
            self.set_y(-8)
            self.set_font("Helvetica", "", 7)
            self.set_text_color(14, 43, 79)
            self.cell(190, 5, f"Page {self.page_no()}/{{nb}}", align="R")

    pdf = InternalPDF(format="A4", unit="mm")
    pdf.single_page = True
    pdf.alias_nb_pages()
    pdf.set_auto_page_break(auto=False)
    pdf.add_page()
    pdf.set_y(49)
    pdf.set_text_color(14, 43, 79)
    pdf.set_font("Helvetica", "B", 15)
    pdf.multi_cell(190, 9, safe(snapshot["kind"]).upper(),
                   new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.set_text_color(175, 32, 40)
    pdf.set_font("Helvetica", "B", 9)
    pdf.multi_cell(190, 6, safe(snapshot["warning"]),
                   new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.ln(3)
    pdf.set_font("Helvetica", "", 9)
    pdf.set_text_color(0, 0, 0)
    from modules.documents.party_identity import wrap_pdf_text
    for label, value in [
        ("Référence ERP", snapshot["id"]),
        (snapshot.get("date_label", "Date"), snapshot["date"]),
        ("Registre source", snapshot["source"]),
        *snapshot["fields"],
    ]:
        if not isinstance(label, str):
            raise InternalPrintError("Libellé interne invalide")
        if not has_value(value) or (
                label == snapshot.get("date_label")
                and str(value).startswith("NON ENREGISTRÉE")):
            continue
        label = label.replace(" enregistrées", "").replace(
            " enregistrée", "").replace(" enregistré", "")
        if " (DZD)" in label:
            value = format_money(value) + " DZD"
        # Ligne compacte et intégrale « libellé : valeur ».
        # L'ancienne présentation sur deux blocs consommait 13 mm par champ.
        text_limit = 1500 if "Motivation" in label else 2000
        prepared = safe(value, text_limit)
        pdf.set_font("Helvetica", "", 8.3)
        wrapped = wrap_pdf_text(pdf, safe(label) + " : " + prepared, 188)
        line_height = 4.3
        required = line_height * len(wrapped) + 1.0
        if pdf.get_y() + required > 219:
            raise InternalPrintError(
                "Copie interne trop volumineuse pour une seule page A4"
            )
        pdf.multi_cell(190, line_height, "\n".join(wrapped),
                       new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        pdf.ln(1.0)
    if pdf.get_y() > 219:
        raise InternalPrintError(
            "Espace QR insuffisant pour une seule page A4"
        )
    qr_y = pdf.get_y() + 2
    draw_qr(pdf, qr_payload(snapshot), x=168, y=qr_y, size=30)
    pdf.set_xy(10, qr_y + 5)
    pdf.set_font("Helvetica", "", 8)
    pdf.multi_cell(146, 5, "QR de repérage ERP - copie non émise",
                   new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.set_y(qr_y + 32)
    # Le bandeau rouge en tête porte déjà l'avertissement complet.
    if pdf.page_no() != 1 or pdf.get_y() > 258:
        raise InternalPrintError(
            "Copie interne trop volumineuse pour une seule page A4"
        )
    return bytes(pdf.output())
