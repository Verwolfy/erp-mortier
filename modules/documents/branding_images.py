"""Images corporate fixes pour en-tête/pied NEXTGEN (PDF et DOCX).

Rendu PNG déterministe à partir du logo du dépôt : aucune ressource externe,
aucun secret, aucune écriture de fichiers temporaire.
"""
from __future__ import annotations

from functools import lru_cache
from io import BytesIO
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont, UnidentifiedImageError

NAVY = (12, 43, 80)
GREEN = (4, 139, 91)
WHITE = (255, 255, 255)
GREY = (224, 229, 233)

# Coordonnées officielles fournies par l'entreprise.
COMPANY = "SARL NEXT GENRATION BUILDING SOLUTIONS"
ADDRESS = "ERRICH Bt N°3, BLOC N°3, Et N°2, SECTION N° 7, ILOT N°48, BOUIRA"
RC = "10/00-0285651 B26"
NIF = "002610028565199"
EMAIL = "contact@nextgen-buildingsolutions.com"


def _font(size: int, bold: bool = False):
    candidates = (
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold
        else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/liberation2/LiberationSans-Bold.ttf" if bold
        else "/usr/share/fonts/truetype/liberation2/LiberationSans-Regular.ttf",
    )
    for path in candidates:
        try:
            return ImageFont.truetype(path, size)
        except OSError:
            continue
    return ImageFont.load_default()


def _png(image: Image.Image) -> bytes:
    out = BytesIO()
    image.save(out, format="PNG", optimize=True)
    return out.getvalue()


@lru_cache(maxsize=8)
def branded_images(logo_path: str | None = None) -> tuple[bytes, bytes]:
    """Images A4 bord à bord ; l'en-tête reproduit la structure approuvée."""
    header = Image.new("RGB", (1500, 330), WHITE)
    d = ImageDraw.Draw(header)
    if logo_path and Path(logo_path).is_file():
        try:
            with Image.open(logo_path) as logo:
                logo = logo.convert("RGB")
                logo.thumbnail((360, 256), Image.Resampling.LANCZOS)
                header.paste(logo, (105 + (360 - logo.width)//2, 20 + (264 - logo.height)//2))
        except (OSError, ValueError, UnidentifiedImageError):
            pass
    d.line((514, 67, 514, 277), fill=NAVY, width=3)
    d.text((565, 100), "SARL NEXT GENRATION", font=_font(49, True), fill=NAVY)
    d.text((565, 165), "BUILDING SOLUTIONS", font=_font(49, True), fill=NAVY)
    d.polygon([(1430, 0), (1500, 0), (1500, 234), (1333, 234)], fill=NAVY)
    d.polygon([(1492, 62), (1500, 62), (1500, 257), (1391, 257)], fill=GREEN)
    d.rectangle((45, 307, 665, 312), fill=NAVY)
    d.polygon([(672,307),(886,307),(877,312),(665,312)], fill=GREEN)
    d.rectangle((897, 307, 1450, 312), fill=NAVY)

    footer = Image.new("RGB", (1500, 174), WHITE)
    fd = ImageDraw.Draw(footer)
    fd.rectangle((45, 3, 658, 7), fill=NAVY)
    fd.polygon([(665,3),(881,3),(873,7),(658,7)], fill=GREEN)
    fd.rectangle((890, 3, 1455, 7), fill=NAVY)
    fd.line((501, 32, 501, 153), fill=(168,180,192), width=2)
    fd.line((892, 32, 892, 153), fill=(168,180,192), width=2)
    fd.ellipse((62, 40, 95, 73), fill=NAVY)
    fd.polygon([(69,62),(89,62),(79,87)], fill=NAVY)
    fd.ellipse((74, 49, 84, 59), fill=WHITE)
    fd.rectangle((535, 44, 565, 78), outline=NAVY, width=3)
    fd.line((541, 54, 559, 54), fill=NAVY, width=2)
    fd.line((541, 63, 559, 63), fill=NAVY, width=2)
    fd.rectangle((930, 49, 973, 77), outline=NAVY, width=3)
    fd.line((930, 49, 951, 65), fill=NAVY, width=2)
    fd.line((951, 65, 973, 49), fill=NAVY, width=2)
    title = _font(24, True)
    body = _font(20)
    fd.text((112, 36), "Adresse de facturation :", fill=NAVY, font=title)
    fd.text((112, 75), "ERRICH Bt N°3, BLOC N°3, Et N°2,", fill=NAVY, font=body)
    fd.text((112, 105), "SECTION N° 7, ILOT N°48, BOUIRA", fill=NAVY, font=body)
    fd.text((583, 46), "RC: " + RC, fill=NAVY, font=_font(21))
    fd.text((583, 88), "NIF: " + NIF, fill=NAVY, font=_font(21))
    fd.text((998, 44), "Email :", fill=NAVY, font=title)
    fd.text((998, 83), EMAIL, fill=NAVY, font=_font(18))
    return _png(header), _png(footer)
