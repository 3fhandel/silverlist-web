"""Eigenstaendiges Berichtsmodul fuer zweiseitige Wochenangebote.

Designs sind reine Daten. Ein weiteres Erscheinungsbild benoetigt nur zwei
Hintergrundbilder und einen Eintrag in ``DESIGNS``; Import, Slot-Editor und
Renderer bleiben davon unberuehrt.
"""

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal, InvalidOperation
from io import BytesIO
from pathlib import Path
import csv
from functools import lru_cache
import math
import re

from django.conf import settings
from PIL import Image as PILImage, ImageOps
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.lib.utils import ImageReader
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfbase.pdfmetrics import stringWidth
from reportlab.pdfgen import canvas

from reports.catalog import ReportDefinition


REQUIRED_COLUMNS = (
    "Artikel-Nr.", "Preis", "S.-Einheit", "Bezeichnung 1",
    "Gültig ab", "Gültig bis",
)
SLOT_CHOICES = tuple(
    [(f"front-{number}", f"Vorderseite {number}") for number in range(1, 10)]
    + [(f"back-{number}", f"Rückseite {number}") for number in range(1, 21)]
)


@dataclass(frozen=True)
class OfferDesign:
    key: str
    name: str
    front_background: str
    back_background: str
    accent: str = "#C71920"
    card_fill: str = "#FFFFFF"
    card_alpha: float = .84
    text_color: str = "#111827"
    style: str = "photo"


DESIGN_ROOT = Path(__file__).with_name("weekly_offer_designs")
ASSET_ROOT = Path(__file__).with_name("weekly_offer_assets")
SLAUGHTERHOUSE_BACKGROUNDS = (
    "background-fruit.jpg",
    "background-meat.jpg",
    "background-dairy.jpg",
    "background-vegetables.jpg",
)
DESIGNS = {
    item.key: item for item in (
        OfferDesign("fruechte", "Früchte", "fruechte/front.jpg", "fruechte/back.jpg"),
        OfferDesign("gebaeude", "Firmengebäude", "gebaeude/front.jpg", "gebaeude/back.jpg", "#0069A8"),
        OfferDesign("herbst", "Herbst", "herbst/front.jpg", "herbst/back.jpg", "#A83D16"),
        OfferDesign("winter", "Winter", "winter/front.jpg", "winter/back.jpg", "#17689A"),
        OfferDesign(
            "modern-3f", "Modern 3F", "", "", "#0789D1", "#FFFFFF", .97,
            "#102A43", "modern",
        ),
        OfferDesign(
            "schlachthof", "Schlachthof", "", "", "#0789D1", "#FFFFFF", .98,
            "#2A2020", "slaughterhouse",
        ),
    )
}


def definitions() -> list[ReportDefinition]:
    return [ReportDefinition(
        key="wochenangebot",
        name="Wochenangebot",
        description="Zweiseitiges Angebotsblatt mit frei belegbaren Artikelpositionen.",
        export_source="Stammdaten → Preislisten-Definitionen",
        export_instructions=(
            "In SilverERP die Preislisten-Definition exportieren. Benötigt werden "
            "Artikel-Nr., Preis, S.-Einheit, Bezeichnung 1, Gültig ab und Gültig bis."
        ),
        required_columns=REQUIRED_COLUMNS,
        implementation="python",
        renderer="weekly-offer",
    )]


def _decode(path: str | Path) -> str:
    raw = Path(path).read_bytes()
    try:
        return raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        return raw.decode("cp1252")


def short_article_number(value: str) -> str:
    return value.rsplit("-", 1)[-1].strip()


def find_product_images(directory: Path | None) -> dict[str, str]:
    if not directory or not directory.is_dir():
        return {}
    found = {}
    for path in directory.rglob("*"):
        if not path.is_file() or path.suffix.lower() not in {".png", ".jpg", ".jpeg", ".webp"}:
            continue
        match = re.match(r"(\d+)", path.stem)
        if match:
            found.setdefault(match.group(1), str(path))
    return found


def load_products(path: str | Path) -> list[dict]:
    rows = csv.DictReader(_decode(path).splitlines(), delimiter=";", quotechar='"')
    images = find_product_images(getattr(settings, "WEEKLY_OFFER_IMAGE_DIR", None))
    products = []
    for index, row in enumerate(rows):
        article_number = (row.get("Artikel-Nr.") or "").strip()
        short_number = short_article_number(article_number)
        products.append({
            "id": index,
            "article_number": article_number,
            "short_number": short_number,
            "description": (row.get("Bezeichnung 1") or "").strip(),
            "price": (row.get("Preis") or "").strip(),
            "unit": (row.get("S.-Einheit") or "").strip(),
            "valid_from": (row.get("Gültig ab") or "").strip(),
            "valid_until": (row.get("Gültig bis") or "").strip(),
            "reference": (row.get("Referenz") or "").strip(),
            "image": images.get(short_number, ""),
        })
    return products


def _money(value: str) -> str:
    try:
        number = Decimal(value.replace(".", "").replace(",", "."))
        return f"{number:.2f}".replace(".", ",")
    except (InvalidOperation, AttributeError):
        return value


def _register_fonts():
    """Registriert die Original-Titelschrift und eine Segoe-nahe PDF-Schrift."""
    if "OfferBauhaus" not in pdfmetrics.getRegisteredFontNames():
        pdfmetrics.registerFont(TTFont("OfferBauhaus", ASSET_ROOT / "bauhaus-93.ttf"))
    if "OfferBody" not in pdfmetrics.getRegisteredFontNames():
        # Bitstream Vera wird mit ReportLab ausgeliefert und steht damit auch im
        # Docker-Image stabil zur Verfügung. Metrik und Anmutung sind wesentlich
        # näher an Segoe UI als die bisherigen PDF-Basisschriften.
        reportlab_fonts = Path(__import__("reportlab").__file__).parent / "fonts"
        pdfmetrics.registerFont(TTFont("OfferBody", reportlab_fonts / "Vera.ttf"))
        pdfmetrics.registerFont(TTFont("OfferBodyBold", reportlab_fonts / "VeraBd.ttf"))
        pdfmetrics.registerFont(TTFont("OfferBodyItalic", reportlab_fonts / "VeraIt.ttf"))


def _fit_text(pdf, text, max_width, font="OfferBodyBold", max_size=10, min_size=6):
    size = max_size
    while size > min_size and stringWidth(text, font, size) > max_width:
        size -= .5
    pdf.setFont(font, size)


def _wrapped_lines(text: str, max_width: float, font: str, size: float):
    words = text.split()
    lines = []
    current = ""
    for word in words:
        candidate = f"{current} {word}".strip()
        if not current or stringWidth(candidate, font, size) <= max_width:
            current = candidate
        else:
            lines.append(current)
            current = word
    if current:
        lines.append(current)
    return lines


def _fit_wrapped_lines(text, max_width, font, max_size, line_limit, min_size=5):
    size = max_size
    while size > min_size:
        lines = _wrapped_lines(text, max_width, font, size)
        if len(lines) <= line_limit and all(stringWidth(line, font, size) <= max_width for line in lines):
            return lines, size
        size -= .5
    return _wrapped_lines(text, max_width, font, min_size), min_size


COUNTRY_ALIASES = (
    ("NZ", ("neuseeland",)), ("AR", ("argentinien",)), ("UY", ("uruguay",)),
    ("AU", ("australien",)), ("BR", ("brasilien",)), ("DE", ("deutschland",)),
    ("IT", ("italien",)), ("ES", ("spanien",)), ("NL", ("niederlande", "holland")),
    ("BE", ("belgien",)), ("FR", ("frankreich",)), ("GR", ("griechenland",)),
    ("TR", ("türkei", "turkei")), ("PL", ("polen",)), ("AT", ("österreich", "osterreich")),
    ("IE", ("irland",)), ("PT", ("portugal",)), ("DK", ("dänemark", "danemark")),
    ("SE", ("schweden",)), ("NO", ("norwegen",)), ("FI", ("finnland",)),
    ("CH", ("schweiz",)), ("GB", ("großbritannien", "grossbritannien", "england")),
    ("US", ("usa", "vereinigte staaten")),
)


def detect_country(description: str) -> str | None:
    normalized = description.casefold()
    for code, names in COUNTRY_ALIASES:
        if any(re.search(rf"(?<!\w){re.escape(name)}(?!\w)", normalized) for name in names):
            return code
    return None


def _draw_flag(
    pdf, code: str | None, x, y, width=13 * mm, height=8 * mm, angle=6,
):
    if not code:
        return
    pdf.saveState()
    # Wie ein leicht aufgestecktes Herkunfts-Badge statt eines sterilen Labels.
    pdf.translate(x + width / 2, y + height / 2)
    pdf.rotate(angle)
    x, y = -width / 2, -height / 2
    pdf.setFillColor(colors.white)
    pdf.setStrokeColor(colors.HexColor("#D2D6DC"))
    pdf.setLineWidth(.35)
    pdf.roundRect(x, y, width, height, .8 * mm, fill=1, stroke=1)
    inset = .45 * mm
    x, y, width, height = x + inset, y + inset, width - 2 * inset, height - 2 * inset

    horizontal = {
        "DE": ("#151515", "#DD0000", "#FFCE00"), "NL": ("#AE1C28", "#FFFFFF", "#21468B"),
        "AT": ("#ED2939", "#FFFFFF", "#ED2939"), "AR": ("#74ACDF", "#FFFFFF", "#74ACDF"),
        "ES": ("#AA151B", "#F1BF00", "#AA151B"), "PL": ("#FFFFFF", "#FFFFFF", "#DC143C"),
        "UY": ("#FFFFFF", "#5B9BD5", "#FFFFFF"),
    }
    vertical = {
        "IT": ("#009246", "#FFFFFF", "#CE2B37"), "FR": ("#0055A4", "#FFFFFF", "#EF4135"),
        "BE": ("#111111", "#FFD90C", "#EF3340"), "IE": ("#169B62", "#FFFFFF", "#FF883E"),
        "PT": ("#046A38", "#DA291C", "#DA291C"),
    }
    if code in horizontal:
        for index, color in enumerate(horizontal[code]):
            pdf.setFillColor(colors.HexColor(color)); pdf.rect(x, y + height * (2 - index) / 3, width, height / 3, fill=1, stroke=0)
    elif code in vertical:
        for index, color in enumerate(vertical[code]):
            pdf.setFillColor(colors.HexColor(color)); pdf.rect(x + width * index / 3, y, width / 3, height, fill=1, stroke=0)
    elif code in {"DK", "SE", "NO", "FI"}:
        base, cross = {"DK": ("#C8102E", "#FFFFFF"), "SE": ("#006AA7", "#FECC00"), "NO": ("#BA0C2F", "#FFFFFF"), "FI": ("#FFFFFF", "#003580")}[code]
        pdf.setFillColor(colors.HexColor(base)); pdf.rect(x, y, width, height, fill=1, stroke=0)
        pdf.setFillColor(colors.HexColor(cross)); pdf.rect(x + width * .31, y, width * .13, height, fill=1, stroke=0); pdf.rect(x, y + height * .42, width, height * .18, fill=1, stroke=0)
        if code == "NO":
            pdf.setFillColor(colors.HexColor("#00205B")); pdf.rect(x + width * .345, y, width * .06, height, fill=1, stroke=0); pdf.rect(x, y + height * .46, width, height * .09, fill=1, stroke=0)
    elif code == "CH":
        pdf.setFillColor(colors.HexColor("#D52B1E")); pdf.rect(x, y, width, height, fill=1, stroke=0)
        pdf.setFillColor(colors.white); pdf.rect(x + width * .42, y + height * .2, width * .16, height * .6, fill=1, stroke=0); pdf.rect(x + width * .28, y + height * .4, width * .44, height * .2, fill=1, stroke=0)
    else:
        base = {"GR": "#0D5EAF", "TR": "#E30A17", "BR": "#009C3B", "AU": "#012169", "NZ": "#012169", "GB": "#012169", "US": "#B22234"}.get(code, "#E5E7EB")
        pdf.setFillColor(colors.HexColor(base)); pdf.rect(x, y, width, height, fill=1, stroke=0)
        if code == "BR":
            pdf.setFillColor(colors.HexColor("#FFDF00")); path = pdf.beginPath(); path.moveTo(x + width/2, y + height*.88); path.lineTo(x + width*.9, y + height/2); path.lineTo(x + width/2, y + height*.12); path.lineTo(x + width*.1, y + height/2); path.close(); pdf.drawPath(path, fill=1, stroke=0)
            pdf.setFillColor(colors.HexColor("#002776")); pdf.circle(x + width/2, y + height/2, height*.2, fill=1, stroke=0)
        elif code == "TR":
            pdf.setFillColor(colors.white); pdf.circle(x + width*.45, y + height*.52, height*.25, fill=1, stroke=0); pdf.setFillColor(colors.HexColor(base)); pdf.circle(x + width*.51, y + height*.55, height*.2, fill=1, stroke=0)
        elif code in {"AU", "NZ", "US", "GB"}:
            pdf.setFillColor(colors.white); pdf.rect(x, y + height*.44, width, height*.12, fill=1, stroke=0); pdf.rect(x + width*.44, y, width*.12, height, fill=1, stroke=0)
    pdf.restoreState()


def _draw_image_placeholder(pdf, x, y, width, height):
    """Dezenter, druckbarer Ersatz für ein fehlendes Produktfoto."""
    pdf.saveState()
    pdf.setFillColor(colors.HexColor("#F4F5F7"))
    pdf.setStrokeColor(colors.HexColor("#B8BEC8"))
    pdf.setLineWidth(.65)
    pdf.roundRect(x, y, width, height, 2.5 * mm, fill=1, stroke=1)
    icon_x, icon_y = x + width / 2, y + height / 2 + 2 * mm
    pdf.setFillColor(colors.HexColor("#DDE1E7"))
    pdf.setStrokeColor(colors.HexColor("#929AA7"))
    pdf.roundRect(icon_x - 7 * mm, icon_y - 5 * mm, 14 * mm, 10 * mm, 1.3 * mm, fill=0, stroke=1)
    pdf.circle(icon_x + 3.5 * mm, icon_y + 2 * mm, 1.2 * mm, fill=1, stroke=0)
    path = pdf.beginPath()
    path.moveTo(icon_x - 5.5 * mm, icon_y - 3.5 * mm)
    path.lineTo(icon_x - 1.5 * mm, icon_y + .5 * mm)
    path.lineTo(icon_x + 1 * mm, icon_y - 2 * mm)
    path.lineTo(icon_x + 5.5 * mm, icon_y - 3.5 * mm)
    pdf.drawPath(path, fill=0, stroke=1)
    pdf.setFillColor(colors.HexColor("#747D8B"))
    pdf.setFont("OfferBody", 5.5)
    pdf.drawCentredString(icon_x, y + 2 * mm, "Kein Produktbild")
    pdf.restoreState()


@lru_cache(maxsize=256)
def _optimized_product_image_bytes(
    path_string: str, modified_ns: int, max_pixels: int, jpeg_quality: int,
) -> bytes:
    """Erzeugt eine kleine, drucktaugliche PDF-Fassung eines Produktbilds."""
    del modified_ns  # Bestandteil des Cache-Schlüssels; invalidiert geänderte Dateien.
    with PILImage.open(path_string) as source:
        image = ImageOps.exif_transpose(source)
        image.thumbnail((max_pixels, max_pixels), PILImage.Resampling.LANCZOS)
        if image.mode in {"RGBA", "LA"} or "transparency" in image.info:
            rgba = image.convert("RGBA")
            flattened = PILImage.new("RGB", rgba.size, "white")
            flattened.paste(rgba, mask=rgba.getchannel("A"))
            image = flattened
        else:
            image = image.convert("RGB")
        output = BytesIO()
        image.save(
            output, format="JPEG", quality=jpeg_quality, optimize=True,
            progressive=True, dpi=(300, 300),
        )
        return output.getvalue()


def _product_image_reader(path: Path) -> ImageReader:
    max_pixels = max(100, min(2000, settings.WEEKLY_OFFER_IMAGE_MAX_PIXELS))
    jpeg_quality = max(40, min(95, settings.WEEKLY_OFFER_IMAGE_JPEG_QUALITY))
    stat = path.stat()
    optimized = _optimized_product_image_bytes(
        str(path), stat.st_mtime_ns, max_pixels, jpeg_quality,
    )
    return ImageReader(BytesIO(optimized))


def _modern_background(pdf, page: str):
    """Vektorhintergrund des modernen Designs - scharf in jeder Auflösung."""
    pdf.saveState()
    pdf.setFillColor(colors.HexColor("#F5F8FB"))
    pdf.rect(0, 0, A4[0], A4[1], fill=1, stroke=0)
    if page == "front":
        # Der Logo-Bereich ist Teil der Seitenfläche und kein aufgesetzter Kasten.
        pdf.setFillColor(colors.white)
        pdf.rect(0, A4[1] - 49 * mm, A4[0], 49 * mm, fill=1, stroke=0)
        pdf.setFillColor(colors.HexColor("#0789D1"), alpha=.08)
        pdf.circle(A4[0] - 4 * mm, A4[1] - 9 * mm, 35 * mm, fill=1, stroke=0)
        pdf.setFillColor(colors.HexColor("#102A43"))
        path = pdf.beginPath()
        path.moveTo(0, A4[1] - 49 * mm)
        path.lineTo(A4[0], A4[1] - 49 * mm)
        path.lineTo(A4[0], A4[1] - 83 * mm)
        path.lineTo(0, A4[1] - 93 * mm)
        path.close()
        pdf.drawPath(path, fill=1, stroke=0)
        pdf.setFillColor(colors.HexColor("#0789D1"))
        pdf.rect(0, A4[1] - 51.2 * mm, A4[0] * .72, 2.2 * mm, fill=1, stroke=0)
        pdf.setFillColor(colors.HexColor("#8CCF28"))
        pdf.rect(A4[0] * .72, A4[1] - 51.2 * mm, A4[0] * .28, 2.2 * mm, fill=1, stroke=0)
        pdf.setFillColor(colors.HexColor("#8CCF28"), alpha=.16)
        pdf.circle(8 * mm, 31 * mm, 38 * mm, fill=1, stroke=0)
    else:
        pdf.setFillColor(colors.HexColor("#102A43"))
        pdf.rect(0, A4[1] - 7 * mm, A4[0], 7 * mm, fill=1, stroke=0)
        pdf.setFillColor(colors.HexColor("#0789D1"))
        pdf.rect(0, A4[1] - 9.5 * mm, A4[0] * .72, 2.5 * mm, fill=1, stroke=0)
        pdf.setFillColor(colors.HexColor("#8CCF28"))
        pdf.rect(A4[0] * .72, A4[1] - 9.5 * mm, A4[0] * .28, 2.5 * mm, fill=1, stroke=0)
        pdf.setStrokeColor(colors.HexColor("#DCE6EF"))
        pdf.setLineWidth(.35)
        for offset in range(18, 290, 12):
            pdf.line(0, offset * mm, A4[0], offset * mm)
    pdf.restoreState()


def _background(pdf, relative_path: str, design: OfferDesign, page: str):
    if design.style == "modern":
        _modern_background(pdf, page)
        return
    path = DESIGN_ROOT / relative_path
    if path.exists():
        pdf.drawImage(str(path), 0, 0, A4[0], A4[1], preserveAspectRatio=False)


def _logo(pdf, design: OfferDesign):
    logo = ASSET_ROOT / "3f-logo.png"
    if logo.exists():
        if design.style == "modern":
            pdf.drawImage(str(logo), 15 * mm, A4[1] - 42.6 * mm, 155 * mm, 35.7 * mm,
                          mask="auto", preserveAspectRatio=True)
            return
        # Entspricht dem Originaltemplate: 18 cm breit, 1.5 cm vom linken und
        # 1 cm vom oberen Seitenrand.
        pdf.drawImage(str(logo), 15 * mm, A4[1] - 51.4 * mm, 180 * mm, 41.4 * mm,
                      mask="auto", preserveAspectRatio=True)


def _front_card(pdf, product, number, design):
    column, row = (number - 1) % 3, (number - 1) // 3
    x, y = (7.5 + column * 67.5) * mm, A4[1] - (102.5 + row * 52.5) * mm
    width, height = 60 * mm, 45 * mm
    pdf.saveState()
    if design.style == "modern":
        pdf.setFillColor(colors.HexColor("#102A43"), alpha=.11)
        pdf.roundRect(x + 1.2 * mm, y - height - 1.2 * mm, width, height, 3 * mm, fill=1, stroke=0)
    pdf.setFillColor(colors.HexColor(design.card_fill), alpha=design.card_alpha)
    pdf.roundRect(x, y - height, width, height, 3 * mm, fill=1, stroke=0)
    if design.style == "modern":
        pdf.setFillColor(colors.HexColor(design.accent))
        pdf.roundRect(x, y - 2.2 * mm, width, 2.2 * mm, 1.1 * mm, fill=1, stroke=0)
    pdf.setFillColor(colors.HexColor(design.text_color))
    lines, title_size = _fit_wrapped_lines(
        product["description"], width - 4 * mm, "OfferBody", 10.5, 3, min_size=4,
    )
    pdf.setFont("OfferBody", title_size)
    for line_number, line in enumerate(lines):
        pdf.drawCentredString(x + width / 2, y - (6 + line_number * 4.4) * mm, line)
    image = Path(product.get("image") or "")
    box_x, box_y, box_w, box_h = x + 10 * mm, y - 35.5 * mm, 30 * mm, 19.5 * mm
    pdf.setFillColor(colors.white)
    pdf.roundRect(box_x, box_y, box_w, box_h, 1.5 * mm, fill=1, stroke=0)
    if image.is_file():
        reader = _product_image_reader(image)
        iw, ih = reader.getSize()
        scale = min(box_w / iw, box_h / ih)
        rendered_width, rendered_height = iw * scale, ih * scale
        pdf.drawImage(
            reader,
            box_x + (box_w - rendered_width) / 2,
            box_y + (box_h - rendered_height) / 2,
            rendered_width, rendered_height,
                      mask="auto", preserveAspectRatio=True)
    else:
        _draw_image_placeholder(pdf, box_x, box_y, box_w, box_h)
    _draw_flag(
        pdf, detect_country(product["description"]),
        box_x + box_w - 8 * mm, box_y + box_h - 7.5 * mm, 13 * mm, 7.5 * mm,
    )
    pdf.setFont("OfferBodyItalic", 6.5)
    pdf.drawString(x + 2 * mm, y - height + 2.5 * mm, product["short_number"])
    pdf.setFillColor(colors.HexColor(design.text_color))
    pdf.translate(x + width - 2 * mm, y - height + 11.5 * mm)
    pdf.rotate(20)
    pdf.setFont("OfferBody", 15)
    pdf.drawRightString(0, 0, f'{_money(product["price"])} € / {product["unit"]}')
    pdf.restoreState()


def _back_row(pdf, product, number, design):
    x, width, height = 10 * mm, 190 * mm, 8.5 * mm
    y = A4[1] - (23 + (number - 1) * 12.4) * mm
    pdf.saveState()
    pdf.setFillColor(colors.HexColor(design.card_fill), alpha=.78)
    pdf.roundRect(x, y - height, width, height, 2 * mm, fill=1, stroke=0)
    if design.style == "modern":
        pdf.setFillColor(colors.HexColor(design.accent))
        pdf.roundRect(x, y - height, 2.2 * mm, height, 1 * mm, fill=1, stroke=0)
    pdf.setFillColor(colors.HexColor(design.text_color))
    pdf.setFont("OfferBodyItalic", 9.5)
    pdf.drawString(x + 2 * mm, y - 5.6 * mm, product["short_number"])
    country = detect_country(product["description"])
    description_x = x + (34 if country else 20) * mm
    if country:
        _draw_flag(pdf, country, x + 20 * mm, y - 7.4 * mm, 11.5 * mm, 6.4 * mm, angle=4)
    _fit_text(
        pdf, product["description"], x + 154 * mm - description_x,
        font="OfferBodyBold", max_size=12.5, min_size=4,
    )
    pdf.drawString(description_x, y - 5.8 * mm, product["description"])
    pdf.setFont("OfferBody", 12.5)
    pdf.setFillColor(colors.HexColor(design.text_color))
    pdf.drawRightString(x + width - 2 * mm, y - 5.8 * mm,
                        f'{_money(product["price"])} € / {product["unit"]}')
    pdf.restoreState()


def _draw_contact_icon(pdf, kind: str, center_x, center_y, color: str):
    """Kleine, an Lucide angelehnte Vektorpiktogramme für den PDF-Druck."""
    pdf.saveState()
    pdf.setFillColor(colors.HexColor(color))
    pdf.circle(center_x, center_y, 3 * mm, fill=1, stroke=0)
    pdf.setStrokeColor(colors.white)
    pdf.setFillColor(colors.white)
    pdf.setLineWidth(.75)
    pdf.setLineCap(1)
    pdf.setLineJoin(1)
    if kind == "mail":
        icon_x, icon_y = center_x - 1.8 * mm, center_y - 1.25 * mm
        pdf.roundRect(icon_x, icon_y, 3.6 * mm, 2.5 * mm, .35 * mm, fill=0, stroke=1)
        pdf.line(icon_x + .25 * mm, icon_y + 2.15 * mm, center_x, center_y - .15 * mm)
        pdf.line(icon_x + 3.35 * mm, icon_y + 2.15 * mm, center_x, center_y - .15 * mm)
    elif kind == "phone":
        path = pdf.beginPath()
        path.moveTo(center_x - 1.55 * mm, center_y + 1.7 * mm)
        path.curveTo(
            center_x - 2.1 * mm, center_y + 1.1 * mm,
            center_x - 1.55 * mm, center_y - .45 * mm,
            center_x - .45 * mm, center_y - 1.25 * mm,
        )
        path.curveTo(
            center_x + .65 * mm, center_y - 2.05 * mm,
            center_x + 1.65 * mm, center_y - 1.9 * mm,
            center_x + 1.85 * mm, center_y - 1.35 * mm,
        )
        path.lineTo(center_x + .85 * mm, center_y - .5 * mm)
        path.curveTo(
            center_x + .55 * mm, center_y - .25 * mm,
            center_x + .25 * mm, center_y - .3 * mm,
            center_x - .05 * mm, center_y - .55 * mm,
        )
        path.lineTo(center_x - .8 * mm, center_y + .2 * mm)
        path.curveTo(
            center_x - 1.05 * mm, center_y + .5 * mm,
            center_x - 1.1 * mm, center_y + .8 * mm,
            center_x - .85 * mm, center_y + 1.05 * mm,
        )
        path.close()
        pdf.drawPath(path, fill=1, stroke=0)
    else:
        whatsapp = ASSET_ROOT / "whatsapp.png"
        if whatsapp.is_file():
            pdf.drawImage(
                str(whatsapp), center_x - 2.05 * mm, center_y - 2.05 * mm,
                4.1 * mm, 4.1 * mm, mask="auto", preserveAspectRatio=True,
            )
    pdf.restoreState()


def _draw_slaughterhouse_contact_block(pdf):
    x, y, width, height = 10 * mm, 13 * mm, 190 * mm, 18 * mm
    pdf.saveState()
    pdf.setFillColor(colors.HexColor("#102A43"), alpha=.14)
    pdf.roundRect(
        x + 1 * mm, y - 1 * mm, width, height, 2.5 * mm, fill=1, stroke=0,
    )
    pdf.setFillColor(colors.white, alpha=.95)
    pdf.roundRect(x, y, width, height, 2.5 * mm, fill=1, stroke=0)
    pdf.setFillColor(colors.HexColor("#8CCF28"))
    pdf.roundRect(x, y, 3 * mm, height, 1.5 * mm, fill=1, stroke=0)

    pdf.setFillColor(colors.HexColor("#102A43"))
    pdf.setFont("OfferBodyBold", 8.5)
    pdf.drawString(x + 7 * mm, y + 10.5 * mm, "BESTELLEN")
    pdf.setFont("OfferBody", 7)
    pdf.drawString(x + 7 * mm, y + 5 * mm, "& KONTAKT")

    columns = (
        (55, "mail", "per Mail", "info@3f-berleburg.de", "#0789D1"),
        (103, "phone", "per Telefon", "02751 9361-0", "#0789D1"),
        (151, "message", "per WhatsApp", "02571 9361-0", "#3A9D23"),
    )
    pdf.setStrokeColor(colors.HexColor("#D9E2EA"))
    pdf.setLineWidth(.4)
    for offset in (49, 97, 145):
        pdf.line(x + offset * mm, y + 3 * mm, x + offset * mm, y + height - 3 * mm)
    for offset, icon, label, value, color in columns:
        _draw_contact_icon(pdf, icon, x + offset * mm, y + 9 * mm, color)
        pdf.setFillColor(colors.HexColor(color))
        pdf.setFont("OfferBodyBold", 6.2)
        pdf.drawString(x + (offset + 6) * mm, y + 10.4 * mm, label)
        pdf.setFillColor(colors.HexColor("#263A4D"))
        pdf.setFont("OfferBodyBold", 7.8)
        pdf.drawString(x + (offset + 6) * mm, y + 4.2 * mm, value)
    pdf.restoreState()


def _draw_slaughterhouse_header(pdf, page_number: int, page_count: int, validity: str):
    pdf.setFillColor(colors.HexColor("#F4EFE7"))
    pdf.rect(0, 0, A4[0], A4[1], fill=1, stroke=0)
    background = ASSET_ROOT / SLAUGHTERHOUSE_BACKGROUNDS[
        (page_number - 1) % len(SLAUGHTERHOUSE_BACKGROUNDS)
    ]
    if background.is_file():
        pdf.saveState()
        reader = ImageReader(str(background))
        source_width, source_height = reader.getSize()
        scale = max(A4[0] / source_width, A4[1] / source_height)
        rendered_width, rendered_height = source_width * scale, source_height * scale
        pdf.drawImage(
            reader, (A4[0] - rendered_width) / 2, (A4[1] - rendered_height) / 2,
            rendered_width, rendered_height, preserveAspectRatio=True,
        )
        # Das Motiv soll die Fläche beleben, aber nicht mit den Produktkarten konkurrieren.
        pdf.setFillColor(colors.HexColor("#F4EFE7"), alpha=.72)
        pdf.rect(0, 0, A4[0], A4[1], fill=1, stroke=0)
        pdf.restoreState()
    pdf.setFillColor(colors.HexColor("#102A43"))
    pdf.rect(0, A4[1] - 36 * mm, A4[0], 36 * mm, fill=1, stroke=0)
    pdf.setFillColor(colors.HexColor("#075D91"))
    path = pdf.beginPath()
    path.moveTo(A4[0] - 66 * mm, A4[1])
    path.lineTo(A4[0], A4[1])
    path.lineTo(A4[0], A4[1] - 36 * mm)
    path.lineTo(A4[0] - 83 * mm, A4[1] - 36 * mm)
    path.close()
    pdf.drawPath(path, fill=1, stroke=0)
    logo = ASSET_ROOT / "3f-logo.png"
    if logo.exists():
        pdf.drawImage(
            str(logo), 10 * mm, A4[1] - 28 * mm, 76 * mm, 17.5 * mm,
            mask="auto", preserveAspectRatio=True,
        )
    pdf.setFillColor(colors.white)
    pdf.setFont("OfferBodyBold", 23)
    pdf.drawRightString(A4[0] - 10 * mm, A4[1] - 16 * mm, "WOCHENANGEBOT")
    pdf.setFont("OfferBody", 7.5)
    pdf.drawRightString(A4[0] - 10 * mm, A4[1] - 24 * mm, validity)
    pdf.setFillColor(colors.HexColor("#8CCF28"))
    pdf.rect(0, A4[1] - 38 * mm, A4[0], 2 * mm, fill=1, stroke=0)
    pdf.setFillColor(colors.HexColor("#6B5A55"))
    pdf.setFont("OfferBody", 7)
    pdf.drawRightString(A4[0] - 10 * mm, 5.5 * mm, f"Seite {page_number} / {page_count}")
    pdf.drawString(
        10 * mm, 5.5 * mm,
        "3F Handelsgesellschaft mbH · Angebote freibleibend und solange der Vorrat reicht",
    )
    _draw_slaughterhouse_contact_block(pdf)


def _draw_slaughterhouse_hero(pdf):
    image = ASSET_ROOT / "slaughterhouse-hero.jpg"
    x, y, width, height = 10 * mm, A4[1] - 112 * mm, 190 * mm, 67 * mm
    pdf.saveState()
    clip = pdf.beginPath()
    clip.roundRect(x, y, width, height, 4 * mm)
    pdf.clipPath(clip, stroke=0, fill=0)
    if image.exists():
        reader = ImageReader(str(image))
        source_width, source_height = reader.getSize()
        scale = max(width / source_width, height / source_height)
        rendered_width, rendered_height = source_width * scale, source_height * scale
        pdf.drawImage(
            reader, x + (width - rendered_width) / 2, y + (height - rendered_height) / 2,
            rendered_width, rendered_height, preserveAspectRatio=True,
        )
    pdf.setFillColor(colors.HexColor("#102A43"), alpha=.78)
    pdf.rect(x, y, 95 * mm, height, fill=1, stroke=0)
    pdf.restoreState()
    pdf.setFillColor(colors.white)
    pdf.setFont("OfferBodyBold", 23)
    pdf.drawString(x + 8 * mm, y + 46 * mm, "FRISCHE")
    pdf.drawString(x + 8 * mm, y + 35 * mm, "ANGEBOTE")
    pdf.setFillColor(colors.HexColor("#8CCF28"))
    pdf.roundRect(x + 8 * mm, y + 28 * mm, 29 * mm, 3 * mm, 1.5 * mm, fill=1, stroke=0)
    pdf.setFillColor(colors.white)
    pdf.setFont("OfferBody", 8)
    pdf.drawString(x + 8 * mm, y + 20 * mm, "Qualität für Küche und Gastronomie")
    pdf.setFont("OfferBodyBold", 8)
    pdf.drawString(x + 8 * mm, y + 8 * mm, "IHR PARTNER SEIT 1979")


def _draw_slaughterhouse_card(
    pdf, product: dict, index_on_page: int, start_mm=45, row_step_mm=47,
    x_override=None, column_override=None, row_override=None,
):
    column = index_on_page % 2 if column_override is None else column_override
    row = index_on_page // 2 if row_override is None else row_override
    x = x_override if x_override is not None else (10 + column * 97) * mm
    y_top = A4[1] - (start_mm + row * row_step_mm) * mm
    width, height = 90 * mm, 42 * mm
    # Schatten und tag-förmige Karte.
    pdf.setFillColor(colors.HexColor("#102A43"), alpha=.13)
    pdf.roundRect(x + 1.2 * mm, y_top - height - 1.2 * mm, width, height, 3 * mm, fill=1, stroke=0)
    pdf.setFillColor(colors.white)
    pdf.roundRect(x, y_top - height, width, height, 3 * mm, fill=1, stroke=0)
    pdf.setStrokeColor(colors.HexColor("#E3D9CE"))
    pdf.setLineWidth(.55)
    pdf.roundRect(x, y_top - height, width, height, 3 * mm, fill=0, stroke=1)
    pdf.setFillColor(colors.HexColor("#0789D1"))
    pdf.roundRect(x, y_top - 2.3 * mm, width, 2.3 * mm, 1.1 * mm, fill=1, stroke=0)

    image_x, image_y, image_w, image_h = x + 3 * mm, y_top - height + 3 * mm, 39 * mm, 34 * mm
    # Transparente und weich freigestellte Bildränder laufen damit immer in
    # dieselbe weiße Fläche wie die Artikelkarte aus.
    pdf.setFillColor(colors.white)
    pdf.roundRect(image_x, image_y, image_w, image_h, 2 * mm, fill=1, stroke=0)
    image = Path(product.get("image") or "")
    if image.is_file():
        reader = _product_image_reader(image)
        source_width, source_height = reader.getSize()
        scale = min(image_w / source_width, image_h / source_height)
        rendered_width, rendered_height = source_width * scale, source_height * scale
        pdf.drawImage(
            reader,
            image_x + (image_w - rendered_width) / 2,
            image_y + (image_h - rendered_height) / 2,
            rendered_width, rendered_height,
            mask="auto", preserveAspectRatio=True,
        )
    else:
        _draw_image_placeholder(pdf, image_x, image_y, image_w, image_h)
    _draw_flag(
        pdf, detect_country(product["description"]),
        image_x + image_w - 8 * mm, image_y + 1.5 * mm, 15 * mm, 8.5 * mm,
    )

    text_x, text_width = x + 46 * mm, 40 * mm
    pdf.setFillColor(colors.HexColor("#7C6A62"))
    pdf.setFont("OfferBodyItalic", 7)
    pdf.drawString(text_x, y_top - 7 * mm, f'Art. {product["short_number"]}')
    lines, description_size = _fit_wrapped_lines(
        product["description"], text_width, "OfferBodyBold", 10.5, 4, min_size=3.5,
    )
    pdf.setFillColor(colors.HexColor("#2A2020"))
    pdf.setFont("OfferBodyBold", description_size)
    for line_number, line in enumerate(lines):
        pdf.drawString(text_x, y_top - (13 + line_number * 4.5) * mm, line)
    pdf.setFillColor(colors.HexColor("#075D91"))
    pdf.setFont("OfferBodyBold", 17)
    pdf.drawRightString(
        x + width - 4 * mm, y_top - height + 8 * mm,
        f'{_money(product["price"])} €',
    )
    pdf.setFillColor(colors.HexColor("#6B5A55"))
    pdf.setFont("OfferBody", 8)
    pdf.drawRightString(x + width - 4 * mm, y_top - height + 3.5 * mm, f'je {product["unit"]}')


def _slot_order(product: dict) -> int:
    slot = product.get("slot", "")
    match = re.fullmatch(r"(front|back)-(\d+)", slot)
    if not match:
        return 999
    return int(match.group(2)) if match.group(1) == "front" else 9 + int(match.group(2))


def _render_slaughterhouse_pdf(parameters: dict) -> bytes:
    products = sorted(parameters.get("products", []), key=_slot_order)[:29]
    title_page_count = min(5, len(products))
    remaining = max(0, len(products) - title_page_count)
    following_pages = math.ceil(remaining / 8) if remaining else 0
    page_count = 1 + following_pages
    buffer = BytesIO()
    pdf = canvas.Canvas(buffer, pagesize=A4, pageCompression=1)
    pdf.setTitle("Schlachthof · Wochenangebot")
    pdf.setAuthor("3F Handelsgesellschaft mbH")
    for page_number in range(1, page_count + 1):
        _draw_slaughterhouse_header(pdf, page_number, page_count, parameters.get("validity", ""))
        if page_number == 1:
            _draw_slaughterhouse_hero(pdf)
            page_products = products[:title_page_count]
            start_mm, row_step_mm = 119, 47
        else:
            page_index = page_number - 2
            offset = title_page_count + page_index * 8
            page_products = products[offset:offset + 8]
            start_mm, row_step_mm = 50, 51
        for index_on_page, product in enumerate(page_products):
            x_override = column_override = row_override = None
            if page_number == 1:
                # Titelseite bewusst als 2-1-2 statt 2-2-1 aufbauen.
                row_override = (0, 0, 1, 2, 2)[index_on_page]
                if index_on_page == 2:
                    x_override = (A4[0] - 90 * mm) / 2
                elif index_on_page >= 3:
                    column_override = index_on_page - 3
            _draw_slaughterhouse_card(
                pdf, product, index_on_page, start_mm=start_mm,
                row_step_mm=row_step_mm, x_override=x_override,
                column_override=column_override, row_override=row_override,
            )
        if page_number < page_count:
            pdf.showPage()
    pdf.save()
    return buffer.getvalue()


def render_pdf(parameters: dict) -> bytes:
    _register_fonts()
    design = DESIGNS[parameters.get("design", "fruechte")]
    if design.style == "slaughterhouse":
        return _render_slaughterhouse_pdf(parameters)
    selected = {item["slot"]: item for item in parameters.get("products", [])}
    buffer = BytesIO()
    pdf = canvas.Canvas(buffer, pagesize=A4, pageCompression=1)
    pdf.setTitle("Wochenangebot")
    pdf.setAuthor("3F Handelsgesellschaft mbH")

    dates = parameters.get("validity", "")
    _background(pdf, design.front_background, design, "front")
    _logo(pdf, design)
    if design.style == "modern":
        pdf.setFillColor(colors.HexColor("#8CCF28"))
        pdf.roundRect(12 * mm, A4[1] - 81 * mm, 26 * mm, 3 * mm, 1.5 * mm, fill=1, stroke=0)
        pdf.setFillColor(colors.white)
        pdf.setFont("OfferBodyBold", 31)
        pdf.drawString(12 * mm, A4[1] - 72 * mm, "TOP ANGEBOTE")
        pdf.setFillColor(colors.HexColor("#102A43"))
        pdf.roundRect(112 * mm, A4[1] - 98 * mm, 86 * mm, 9 * mm, 4.5 * mm, fill=1, stroke=0)
        pdf.setFillColor(colors.white)
        pdf.setFont("OfferBodyBold", 8)
        pdf.drawCentredString(155 * mm, A4[1] - 94.8 * mm, dates)
    else:
        pdf.setFillColor(colors.HexColor(design.accent))
        pdf.setFont("OfferBauhaus", 78)
        pdf.drawCentredString(A4[0] / 2, A4[1] - 80 * mm, "Top-Angebote")
        pdf.setFont("OfferBauhaus", 9)
        pdf.drawRightString(A4[0] - 10 * mm, A4[1] - 91 * mm, dates)
    for number in range(1, 10):
        product = selected.get(f"front-{number}")
        if product:
            _front_card(pdf, product, number, design)
    pdf.showPage()

    _background(pdf, design.back_background, design, "back")
    for number in range(1, 21):
        product = selected.get(f"back-{number}")
        if product:
            _back_row(pdf, product, number, design)
    if design.style == "modern":
        pdf.setFillColor(colors.HexColor("#102A43"))
        pdf.rect(0, 0, A4[0], 14 * mm, fill=1, stroke=0)
        pdf.setFillColor(colors.HexColor("#8CCF28"))
        pdf.rect(0, 14 * mm, A4[0], 2 * mm, fill=1, stroke=0)
    pdf.setFillColor(colors.white)
    pdf.setFont("OfferBodyBold", 9)
    pdf.drawCentredString(A4[0] / 2, 7 * mm, "3F Handelsgesellschaft mbH · Nur solange der Vorrat reicht")
    pdf.save()
    return buffer.getvalue()


def default_validity(products: list[dict]) -> str:
    if not products:
        return ""
    start, end = products[0]["valid_from"], products[0]["valid_until"]
    return f"gültig von {start} bis {end}" if start or end else ""
