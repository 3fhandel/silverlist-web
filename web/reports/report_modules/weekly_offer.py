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
import re

from django.conf import settings
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


def _wrapped_lines(text: str, max_width: float, font: str, size: float, limit=2):
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
            if len(lines) == limit - 1:
                break
    if current and len(lines) < limit:
        remaining = " ".join(words[sum(len(line.split()) for line in lines):])
        while remaining and stringWidth(remaining, font, size) > max_width:
            remaining = remaining[:-1]
        if remaining != " ".join(words[sum(len(line.split()) for line in lines):]):
            remaining = remaining.rstrip() + "…"
        lines.append(remaining)
    return lines


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
    title_size = 10.5
    lines = _wrapped_lines(
        product["description"], width - 4 * mm, "OfferBody", title_size, limit=2,
    )
    pdf.setFont("OfferBody", title_size)
    for line_number, line in enumerate(lines):
        pdf.drawCentredString(x + width / 2, y - (6 + line_number * 4.4) * mm, line)
    image = Path(product.get("image") or "")
    box_x, box_y, box_w, box_h = x + 10 * mm, y - 35.5 * mm, 30 * mm, 23 * mm
    if image.is_file():
        reader = ImageReader(str(image))
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
    _fit_text(pdf, product["description"], 134 * mm, font="OfferBodyBold", max_size=12.5)
    pdf.drawString(x + 20 * mm, y - 5.8 * mm, product["description"])
    pdf.setFont("OfferBody", 12.5)
    pdf.setFillColor(colors.HexColor(design.text_color))
    pdf.drawRightString(x + width - 2 * mm, y - 5.8 * mm,
                        f'{_money(product["price"])} € / {product["unit"]}')
    pdf.restoreState()


def render_pdf(parameters: dict) -> bytes:
    _register_fonts()
    design = DESIGNS[parameters.get("design", "fruechte")]
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
