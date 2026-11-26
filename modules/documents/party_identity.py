"""Coordonnées légales des tiers pour les documents de consultation NEXTGEN.

La société émettrice reprend exclusivement ses coordonnées configurées ; les
fournisseurs/clients proviennent des référentiels déjà autorisés par RBAC.
AI n'existe pas dans le schéma ERP actuel : toujours l'afficher comme manquant,
jamais le déduire de RC, NIF ou NIS. Aucun numéro n'est inventé.
"""
from __future__ import annotations

from typing import Mapping

NAVY = (14, 43, 79)
GREEN = (10, 133, 93)
PALE = (240, 244, 248)
MISSING = "Non renseigné"

LEGAL_KEYS = ("nom", "adresse", "rc", "nif", "nis", "ai")
PARTY_LABELS = (
    ("Raison Sociale", "nom", True),
    ("Adresse de Facturation", "adresse", True),
    ("Wilaya", "wilaya", False),
    ("Pays", "pays", False),
    ("RC", "rc", True),
    ("NIF", "nif", True),
    ("NIS", "nis", True),
    ("AI", "ai", True),
    ("Contact", "nom_contact", False),
    ("Fonction du contact", "poste_contact", False),
    ("Téléphone fixe", "telephone_fixe", False),
    ("Téléphone mobile", "mobile_contact", False),
    ("E-mail entreprise", "email_entreprise", False),
    ("E-mail contact", "email_contact", False),
    ("Site web", "site_web", False),
)


def _clean(value: object) -> str:
    if value is None:
        return ""
    if not isinstance(value, (str, int, float)):
        return ""
    return str(value).strip()


def normalize_party(source: Mapping | None, *, issuer: bool = False) -> list[tuple[str, str]]:
    """Photographie de l'identité ; champs essentiels explicitement présents."""
    source = source if isinstance(source, Mapping) else {}
    entries = []
    for label, field, required in PARTY_LABELS:
        value = _clean(source.get(field))
        if value and value.casefold() not in {"non renseigné", "non renseigne", "non renseignée", "non renseignee"}:
            entries.append((label, value))
    return entries


def configured_company() -> list[tuple[str, str]]:
    from modules.documents.branding_images import COMPANY, ADDRESS, RC, NIF, EMAIL
    return normalize_party({
        "nom": COMPANY, "adresse": ADDRESS,
        "rc": RC, "nif": NIF, "email_entreprise": EMAIL,
    }, issuer=True)


def pdf_safe(value: object) -> str:
    """Compatible Helvetica latin-1 : jamais de troncature silencieuse."""
    text = str(value if value is not None else "")
    for original, replacement in (("—", " - "), ("–", "-"), ("’", "'"), ("“", '"' ), ("”", '"' ), ("•", "-")):
        text = text.replace(original, replacement)
    return text.encode("latin-1", "replace").decode("latin-1")


def wrap_pdf_text(pdf, value: object, width: float) -> list[str]:
    """Retourne toutes les lignes nécessaires, même pour les mots sans espace."""
    text = pdf_safe(value).replace("\r", "")
    result: list[str] = []
    for paragraph in text.split("\n"):
        line = ""
        for word in paragraph.split(" "):
            candidate = (line + " " + word).strip() if line else word
            if line and pdf.get_string_width(candidate) > width:
                result.append(line)
                line = word
            else:
                line = candidate
            # Découper les références très longues : éviter le débordement.
            if pdf.get_string_width(line) > width:
                segment = ""
                for char in line:
                    if segment and pdf.get_string_width(segment + char) > width:
                        result.append(segment)
                        segment = char
                    else:
                        segment += char
                line = segment
        result.append(line)
    return result or [""]



def wrap_table_cell_text(pdf, value: object, width: float,
                         *, inset: float = 1.5) -> list[str]:
    """Mesure la largeur *utile* dans une cellule FPDF, marges incluses.

    pdf.multi_cell retranchait ensuite 2*c_margin aux lignes déjà préparées,
    ce qui ajoutait une ligne hors du rectangle (ex.: « Sac 25kg »).
    """
    available = width - 2 * inset - 2 * pdf.c_margin - 0.4
    if available <= 0:
        raise ValueError("Colonne PDF trop étroite pour un texte lisible")
    return wrap_pdf_text(pdf, value, available)


def draw_table_cell_text(pdf, lines: list[str], *, x: float, y: float,
                         width: float, height: float,
                         line_height: float = 4.1, inset: float = 1.5,
                         align: str = "L") -> None:
    """Dessine ligne par ligne sans que multi_cell puisse replier le texte.

    Les positions du texte sont contrôlées dans les limites du rectangle.
    La fonction ne trace pas la bordure, qui reste à la charge de l'appelant.
    """
    if not lines or line_height <= 0 or 2 + len(lines) * line_height > height + 0.01:
        raise ValueError("Hauteur de cellule insuffisante pour le texte complet")
    inside = width - 2 * inset
    available = inside - 2 * pdf.c_margin - 0.1
    for index, line in enumerate(lines):
        text = pdf_safe(line)
        if pdf.get_string_width(text) > available:
            raise ValueError("Texte plus large que la cellule PDF")
        pdf.set_xy(x + inset, y + 1 + index * line_height)
        pdf.cell(inside, line_height, text, align=align)


def draw_party_panels(pdf, left_title: str, left_fields: list,
                      right_title: str, right_fields: list) -> None:
    """Deux blocs A4 de largeur identique, contenus sans couper les valeurs.

    Une annexe sur page supplémentaire est possible pour les fiches très
    détaillées ; on ne superpose jamais les deux colonnes au pied de page.
    """
    from fpdf.enums import XPos, YPos

    def prepared(fields):
        pdf.set_font("Helvetica", "", 7.4)
        rows = []
        for item in fields:
            if not (isinstance(item, (tuple, list)) and len(item) == 2):
                raise ValueError("Champ d'identité invalide")
            label, value = item
            lines = wrap_pdf_text(pdf, f"{label} : {value}", 86.5)
            rows.append(lines)
        return rows

    groups = [prepared(left_fields), prepared(right_fields)]
    # Hauteur variable mais aucune donnée tronquée.
    heights = [10 + sum(3.85 * len(lines) + 1.15 for lines in rows)
               for rows in groups]
    height = max(heights) + 2
    if height > 195:
        raise ValueError("Coordonnées trop longues pour un bloc A4 cohérent")
    if pdf.get_y() + height + 5 > 255:
        if getattr(pdf, "single_page", False):
            raise ValueError(
                "Bloc d'identité trop long pour une seule page A4"
            )
        pdf.add_page()
        pdf.set_y(50)

    y = pdf.get_y()
    for x, title, rows in zip((10, 107), (left_title, right_title), groups):
        pdf.set_draw_color(209, 219, 228)
        pdf.rect(x, y, 93, height)
        pdf.set_fill_color(*NAVY)
        pdf.rect(x, y, 93, 8, style="F")
        pdf.set_xy(x + 2, y + 1.5)
        pdf.set_text_color(255, 255, 255)
        pdf.set_font("Helvetica", "B", 8.6)
        pdf.cell(89, 5, pdf_safe(title))
        yy = y + 10
        pdf.set_font("Helvetica", "", 7.4)
        pdf.set_text_color(*NAVY)
        for lines in rows:
            for line in lines:
                pdf.set_xy(x + 3, yy)
                pdf.cell(87, 3.85, line)
                yy += 3.85
            yy += 1.15
    pdf.set_xy(10, y + height + 4)
