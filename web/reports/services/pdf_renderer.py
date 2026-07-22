from collections import OrderedDict
from collections.abc import Iterable
from datetime import datetime
from html import escape
from io import BytesIO
from pathlib import Path
import re

from django.conf import settings
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.graphics.shapes import Drawing, Polygon, String
from reportlab.platypus import (
    BaseDocTemplate, Frame, Image, PageBreak, PageTemplate, Paragraph,
    SimpleDocTemplate, Spacer, Table, TableStyle,
)
from reportlab.platypus.tableofcontents import TableOfContents



BLUE = colors.HexColor("#0093DD")
GREEN = colors.HexColor("#99CC00")
INK = colors.HexColor("#172033")
LIGHT = colors.HexColor("#E8EDF3")


def _asset(name: str) -> Path:
    return settings.REPORT_ASSET_DIR / name


class NumberedDocument(BaseDocTemplate):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        frame = Frame(
            14 * mm, 17 * mm, A4[0] - 28 * mm, A4[1] - 38 * mm,
            leftPadding=0, rightPadding=0, topPadding=0, bottomPadding=0,
        )
        self.addPageTemplates(PageTemplate(id="content", frames=frame, onPage=self.decorate))

    def decorate(self, canvas, document):
        if document.page == 1:
            return
        canvas.saveState()
        logo = _asset("3f-logo-minibw.png")
        if logo.exists():
            canvas.drawImage(str(logo), 14 * mm, A4[1] - 18 * mm, 10 * mm, 10 * mm, mask="auto", preserveAspectRatio=True)
        canvas.setFillColor(INK)
        canvas.setFont("Helvetica-Bold", 9)
        canvas.drawString(27 * mm, A4[1] - 13 * mm, "Ordersatz")
        canvas.setStrokeColor(BLUE)
        canvas.setLineWidth(1.2)
        canvas.line(14 * mm, A4[1] - 20 * mm, A4[0] - 14 * mm, A4[1] - 20 * mm)
        canvas.setFillColor(colors.HexColor("#667085"))
        canvas.setFont("Helvetica", 7.5)
        canvas.drawString(14 * mm, 9 * mm, "3F Handelsgesellschaft mbH · Ederstraße 72 · 57319 Bad Berleburg")
        canvas.drawRightString(A4[0] - 14 * mm, 9 * mm, f"Seite {document.page}")
        canvas.restoreState()

    def afterFlowable(self, flowable):
        if isinstance(flowable, Paragraph) and flowable.style.name == "Group":
            text = flowable.getPlainText()
            key = getattr(flowable, "_bookmarkName", None)
            if key:
                self.canv.bookmarkPage(key)
                self.canv.addOutlineEntry(text, key, level=0, closed=False)
                self.notify("TOCEntry", (0, text, self.page, key))


def _paragraph(value: object, style):
    text = escape("" if value is None else str(value)).replace("\n", "<br/>")
    return Paragraph(text, style)


def _warning_icon():
    drawing = Drawing(12, 11)
    drawing.add(Polygon(
        [6, 10.5, .8, .8, 11.2, .8],
        fillColor=colors.HexColor("#FFF4CC"),
        strokeColor=colors.HexColor("#B76E00"), strokeWidth=1,
    ))
    drawing.add(String(
        6, 2.2, "!", textAnchor="middle", fontName="Helvetica-Bold",
        fontSize=7, fillColor=colors.HexColor("#8A5300"),
    ))
    return drawing


def _trend_cell(value, direction, style):
    color = colors.HexColor("#C2413B") if direction == "up" else colors.HexColor("#3A7D44")
    drawing = Drawing(9, 10)
    if direction == "up":
        points = [4.5, 10, 0.5, 5.5, 3.1, 5.5, 3.1, 0, 5.9, 0, 5.9, 5.5, 8.5, 5.5]
    else:
        points = [4.5, 0, 0.5, 4.5, 3.1, 4.5, 3.1, 10, 5.9, 10, 5.9, 4.5, 8.5, 4.5]
    drawing.add(Polygon(points, fillColor=color, strokeColor=None))
    table = Table(
        [[drawing, _paragraph(value, style)]],
        colWidths=[4 * mm, 15 * mm],
        hAlign="LEFT",
    )
    table.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("RIGHTPADDING", (0, 0), (-1, -1), 0),
        ("TOPPADDING", (0, 0), (-1, -1), 0),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
    ]))
    return table


def render_ordersatz_pdf(groups: Iterable, position_count: int) -> bytes:
    buffer = BytesIO()
    document = NumberedDocument(buffer, pagesize=A4, title="Ordersatz", author="3F Handelsgesellschaft mbH")
    styles = getSampleStyleSheet()
    body = ParagraphStyle("Body3F", parent=styles["BodyText"], fontName="Helvetica", fontSize=9, leading=12, textColor=INK)
    small = ParagraphStyle("Small3F", parent=body, fontSize=7.5, leading=9)
    center = ParagraphStyle("Center3F", parent=body, alignment=TA_CENTER)
    right = ParagraphStyle("Right3F", parent=body, alignment=TA_RIGHT)
    title = ParagraphStyle("Title3F", parent=styles["Title"], fontName="Helvetica-Bold", fontSize=34, leading=38, textColor=INK, alignment=TA_CENTER)
    story = []

    header = _asset("header.png")
    if header.exists():
        story.append(Image(str(header), width=182 * mm, height=41.2 * mm))
    story.extend([Spacer(1, 12 * mm), Paragraph("Ordersatz", title), Spacer(1, 8 * mm)])
    notice = (
        "<b>Lieferzeit für Ordersatzaufträge: mindestens 2 Tage</b><br/><br/>"
        "Alle Preise zzgl. gesetzlicher Mehrwertsteuer.<br/><br/>"
        "<b>Wichtiger Hinweis</b><br/>Aufgrund starker Marktschwankungen sind kurzfristige "
        "Preisänderungen möglich. Nicht alle Artikel sind sofort verfügbar. Aktuelle Preise "
        "und Verfügbarkeiten erfahren Sie bei unserem Team.<br/><br/>"
        "Der Mindestbestellwert beträgt 150 € netto."
    )
    notice_table = Table([[Paragraph(notice, center)]], colWidths=[160 * mm])
    notice_table.setStyle(TableStyle([
        ("BOX", (0, 0), (-1, -1), 3, BLUE), ("INNERGRID", (0, 0), (-1, -1), 1, GREEN),
        ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#F8FAFC")),
        ("LEFTPADDING", (0, 0), (-1, -1), 10 * mm), ("RIGHTPADDING", (0, 0), (-1, -1), 10 * mm),
        ("TOPPADDING", (0, 0), (-1, -1), 8 * mm), ("BOTTOMPADDING", (0, 0), (-1, -1), 8 * mm),
    ]))
    story.extend([notice_table, Spacer(1, 14 * mm)])
    company = [
        Paragraph("<b>3F Handelsgesellschaft mbH</b><br/>Ederstraße 72<br/>57319 Bad Berleburg<br/><br/>Telefon 02751 9361-0<br/>info@3f-berleburg.de", small),
        Paragraph("<b>Geschäftsdaten</b><br/>HRB 6416 Amtsgericht Siegen<br/>Geschäftsführer: Robin Walter<br/>USt-IdNr.: DE 126 586 913<br/><br/>Sparkasse Wittgenstein<br/>IBAN: DE46 4605 3480 0000 0026 26", ParagraphStyle("CompanyRight", parent=small, alignment=TA_RIGHT)),
    ]
    company_table = Table([company], colWidths=[80 * mm, 80 * mm])
    company_table.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP")]))
    story.extend([company_table, PageBreak()])

    story.append(Paragraph("Inhaltsverzeichnis", ParagraphStyle("TocTitle", parent=title, fontSize=24, leading=28, alignment=TA_LEFT)))
    story.append(Spacer(1, 6 * mm))
    toc = TableOfContents(tableStyle=TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("RIGHTPADDING", (0, 0), (-1, -1), 0),
        ("TOPPADDING", (0, 0), (-1, -1), 1.2),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 1.2),
    ]))
    toc.levelStyles = [ParagraphStyle(
        "TOCGroup", parent=body, fontSize=8.5, leading=10.5, leftIndent=0,
        firstLineIndent=0, spaceBefore=0, spaceAfter=0, textColor=INK,
    )]
    story.extend([toc, PageBreak()])

    story.append(Paragraph(f"Ordersatz · {position_count} Artikel · {datetime.now():%d.%m.%Y}", ParagraphStyle("Section", parent=body, fontName="Helvetica-Bold", fontSize=13, leading=16, spaceAfter=5 * mm)))
    widths = [25 * mm, 82 * mm, 16 * mm, 22 * mm, 28 * mm]
    for group_index, (group, positions) in enumerate(groups):
        group_heading = Paragraph(escape(str(group)), ParagraphStyle(
            "Group", parent=body, fontName="Helvetica-Bold", fontSize=12,
            leading=16, textColor=colors.white, backColor=BLUE,
            borderPadding=(7, 7, 7, 7), spaceBefore=4 * mm, spaceAfter=2 * mm,
        ))
        group_heading._bookmarkName = f"group-{group_index}"
        story.append(group_heading)
        rows = [[_paragraph("Art.-Nr.", small), _paragraph("Artikel", small), _paragraph("Einheit", small), _paragraph("Preis", right), _paragraph("Bestellmenge", small)]]
        for position in positions:
            rows.append([
                _paragraph(position.get("Artikelnummer"), small), _paragraph(position.get("Bezeichnung"), body),
                _paragraph(position.get("Einheit"), center), _paragraph(position.get("Preis"), right), "",
            ])
        table = Table(rows, colWidths=widths, repeatRows=1, hAlign="LEFT")
        table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), LIGHT), ("TEXTCOLOR", (0, 0), (-1, 0), INK),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("LINEBELOW", (0, 0), (-1, -1), .3, colors.HexColor("#BFC8D4")),
            ("LINEBELOW", (4, 1), (4, -1), .7, INK),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("LEFTPADDING", (0, 0), (-1, -1), 2.5), ("RIGHTPADDING", (0, 0), (-1, -1), 2.5),
            ("TOPPADDING", (0, 1), (-1, -1), 4), ("BOTTOMPADDING", (0, 1), (-1, -1), 4),
        ]))
        story.append(table)
    document.multiBuild(story)
    return buffer.getvalue()


def render_two_column_pricelist_pdf(definition, result) -> bytes:
    """Kompakte Preisliste mit gemeinsamem Kopf und zwei fließenden Spalten."""
    buffer = BytesIO()
    document = BaseDocTemplate(
        buffer, pagesize=A4,
        title=str(result.variables.get("title", definition.name)),
        author="3F Handelsgesellschaft mbH",
    )
    horizontal_margin, column_gap = 12 * mm, 0
    bottom = 15 * mm
    regular_content_top = A4[1] - 73 * mm
    first_content_top = A4[1] - 78 * mm
    column_width = (A4[0] - 2 * horizontal_margin - column_gap) / 2
    first_frames = [
        Frame(
            horizontal_margin, bottom, column_width, first_content_top - bottom,
            leftPadding=0, rightPadding=0, topPadding=0, bottomPadding=0,
        ),
        Frame(
            horizontal_margin + column_width + column_gap, bottom,
            column_width, first_content_top - bottom,
            leftPadding=0, rightPadding=0, topPadding=0, bottomPadding=0,
        ),
    ]
    later_frames = [
        Frame(
            horizontal_margin, bottom, column_width, regular_content_top - bottom,
            leftPadding=0, rightPadding=0, topPadding=0, bottomPadding=0,
        ),
        Frame(
            horizontal_margin + column_width + column_gap, bottom,
            column_width, regular_content_top - bottom,
            leftPadding=0, rightPadding=0, topPadding=0, bottomPadding=0,
        ),
    ]

    def decorate(canvas, doc):
        canvas.saveState()
        header = _asset("header.png")
        if header.exists():
            canvas.drawImage(
                str(header), 14 * mm, A4[1] - 52 * mm,
                182 * mm, 41.2 * mm, mask="auto", preserveAspectRatio=True,
            )
        canvas.setFillColor(INK)
        canvas.setFont("Helvetica-Bold", 16)
        canvas.drawString(
            horizontal_margin, A4[1] - 59 * mm,
            str(result.variables.get("title", definition.name)),
        )
        subtitle = result.variables.get("subtitle")
        if subtitle:
            canvas.setFillColor(colors.HexColor("#5F6B7A"))
            canvas.setFont("Helvetica", 7.5)
            canvas.drawRightString(
                A4[0] - horizontal_margin, A4[1] - 59 * mm, str(subtitle),
            )
        canvas.setStrokeColor(BLUE)
        canvas.setLineWidth(1.1)
        canvas.line(
            horizontal_margin, A4[1] - 64 * mm,
            A4[0] - horizontal_margin, A4[1] - 64 * mm,
        )
        if doc.page == 1:
            notice_style = ParagraphStyle(
                "TwoColumnNotice", fontName="Helvetica", fontSize=7,
                leading=8.5, textColor=colors.HexColor("#4B5563"),
            )
            notice = _paragraph(
                "   ·   ".join((definition.options or {}).get("list_notices", ())),
                notice_style,
            )
            _, notice_height = notice.wrapOn(
                canvas, A4[0] - 2 * horizontal_margin, 12 * mm,
            )
            notice.drawOn(
                canvas, horizontal_margin, A4[1] - 68 * mm - notice_height,
            )
        canvas.setFillColor(colors.HexColor("#667085"))
        canvas.setFont("Helvetica", 7)
        canvas.drawString(
            horizontal_margin, 8 * mm,
            "3F Handelsgesellschaft mbH · Ederstraße 72 · 57319 Bad Berleburg",
        )
        canvas.drawRightString(A4[0] - horizontal_margin, 8 * mm, f"Seite {doc.page}")
        canvas.restoreState()

    document.addPageTemplates([
        PageTemplate(
            id="two-column-pricelist-first", frames=first_frames,
            onPage=decorate, autoNextPageTemplate="two-column-pricelist-later",
        ),
        PageTemplate(
            id="two-column-pricelist-later", frames=later_frames,
            onPage=decorate,
        ),
    ])

    styles = getSampleStyleSheet()
    cell = ParagraphStyle(
        "TwoColumnPriceCell", parent=styles["BodyText"],
        fontSize=6.4, leading=7.6, textColor=INK,
    )
    cell_header = ParagraphStyle(
        "TwoColumnPriceHeader", parent=cell, fontName="Helvetica-Bold",
        fontSize=6, leading=7,
    )
    group_style = ParagraphStyle(
        "TwoColumnPriceGroup", parent=cell, fontName="Helvetica-Bold",
        fontSize=8, leading=9.5, textColor=colors.white,
    )
    right = ParagraphStyle("TwoColumnPriceRight", parent=cell, alignment=TA_RIGHT)
    center = ParagraphStyle("TwoColumnPriceCenter", parent=cell, alignment=TA_CENTER)
    badge = ParagraphStyle(
        "TwoColumnPriceBadge", parent=center, fontName="Helvetica-Bold",
        fontSize=5.5, leading=6.5, textColor=colors.white,
    )

    options = definition.options or {}
    group_columns = [group["column"] for group in definition.groups]
    hidden_columns = set(options.get("hidden_columns", ()))
    visible_columns = [
        column for column in result.columns
        if column not in group_columns and column not in hidden_columns
    ]
    indexes = {column: result.columns.index(column) for column in result.columns}
    configured_widths = options.get("column_width_weights", {})
    weights = [float(configured_widths.get(column, 1)) for column in visible_columns]
    weight_total = sum(weights) or 1
    widths = [column_width * weight / weight_total for weight in weights]

    grouped = OrderedDict()
    if group_columns:
        group_index = result.columns.index(group_columns[0])
        for row in result.rows:
            grouped.setdefault(row[group_index], []).append(row)
    else:
        grouped[""] = list(result.rows)

    story = []
    show_header = options.get("show_header", True)
    for group, rows in grouped.items():
        data = [[_paragraph(group, group_style), *([""] * (len(visible_columns) - 1))]]
        if show_header:
            data.append([
                _paragraph("" if column == "VB" else column, cell_header)
                for column in visible_columns
            ])
        for row in rows:
            rendered = []
            for column in visible_columns:
                style = badge if column == "VB" else right if column == "Preis" else center if column in {"ME", "Menge"} else cell
                rendered.append(_paragraph(row[indexes[column]], style))
            data.append(rendered)
        repeated_rows = 2 if show_header else 1
        table = Table(
            data, colWidths=widths, repeatRows=repeated_rows,
            hAlign="LEFT", splitByRow=1,
        )
        commands = [
            ("SPAN", (0, 0), (-1, 0)),
            ("BACKGROUND", (0, 0), (-1, 0), BLUE),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("LEFTPADDING", (0, 0), (-1, -1), 2.5),
            ("RIGHTPADDING", (0, 0), (-1, -1), 2.5),
            ("TOPPADDING", (0, 0), (-1, -1), 2.2),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 2.2),
            ("ROWBACKGROUNDS", (0, repeated_rows), (-1, -1), [colors.white, colors.HexColor("#F3F6F8")]),
            ("LINEBELOW", (0, repeated_rows), (-1, -1), .25, colors.HexColor("#CBD3DC")),
        ]
        if show_header:
            commands.extend([
                ("BACKGROUND", (0, 1), (-1, 1), LIGHT),
                ("LINEBELOW", (0, 1), (-1, 1), .45, colors.HexColor("#AEB9C6")),
            ])
        if "VB" in visible_columns:
            badge_column = visible_columns.index("VB")
            first_data_row = repeated_rows
            for row_offset, row in enumerate(rows):
                if str(row[indexes["VB"]]).strip():
                    table_row = first_data_row + row_offset
                    badge_color = GREEN if str(row[indexes["VB"]]).strip() == "NEU" else colors.HexColor("#D97706")
                    commands.extend([
                        ("BACKGROUND", (badge_column, table_row), (badge_column, table_row), badge_color),
                        ("BOX", (badge_column, table_row), (badge_column, table_row), .4, colors.white),
                    ])
        table.setStyle(TableStyle(commands))
        story.append(table)

    closing_notice = options.get("closing_notice")
    if closing_notice:
        story.extend([
            Spacer(1, 2 * mm),
            _paragraph(closing_notice, ParagraphStyle(
                "TwoColumnClosingNotice", parent=cell,
                fontName="Helvetica-Oblique", fontSize=6.5, leading=8,
                textColor=colors.HexColor("#4B5563"),
            )),
        ])

    document.build(story)
    return buffer.getvalue()


def render_generic_pdf(definition, result) -> bytes:
    buffer = BytesIO()
    page_size = A4
    layout = (definition.options or {}).get("layout", "standard-table")
    if layout == "two-column-pricelist":
        return render_two_column_pricelist_pdf(definition, result)
    if layout == "internal-table":
        profile = "internal"
    elif layout in {"pricelist", "private-pricelist"}:
        profile = "pricelist"
    else:
        profile = "branded"

    horizontal_margin = 8 * mm if profile == "internal" else 12 * mm
    document = SimpleDocTemplate(
        buffer, pagesize=page_size,
        leftMargin=horizontal_margin, rightMargin=horizontal_margin,
        topMargin=(22 * mm if profile == "internal" else 12 * mm),
        bottomMargin=(12 * mm if profile == "internal" else 16 * mm),
        title=str(result.variables.get("title", definition.name)),
        author="3F Handelsgesellschaft mbH",
    )
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle("ReportTitle", parent=styles["Title"], fontSize=20, leading=24, textColor=INK)
    subtitle_style = ParagraphStyle("ReportSubtitle", parent=styles["BodyText"], fontSize=9, leading=12, textColor=colors.HexColor("#5F6B7A"))
    dense = len(result.columns) > 5
    options = definition.options or {}
    cell_font_size = float(options.get("cell_font_size", 6.5 if dense else 7.5))
    cell_leading = float(options.get("cell_leading", 7.8 if dense else 9))
    cell = ParagraphStyle(
        "ReportCell", parent=styles["BodyText"],
        fontSize=cell_font_size, leading=cell_leading,
    )
    cell_header = ParagraphStyle("ReportCellHeader", parent=cell, fontName="Helvetica-Bold")
    cell_bold_italic = ParagraphStyle(
        "ReportCellBoldItalic", parent=cell, fontName="Helvetica-BoldOblique"
    )
    story = []
    if profile != "internal":
        header = _asset("header.png")
        if header.exists():
            story.extend([Image(str(header), width=182 * mm, height=41.2 * mm), Spacer(1, 5 * mm)])
    story.append(Paragraph(escape(str(result.variables.get("title", definition.name))), title_style))
    if result.variables.get("subtitle"):
        story.extend([_paragraph(result.variables["subtitle"], subtitle_style), Spacer(1, 5 * mm)])

    group_columns = [group["column"] for group in definition.groups]
    hidden_columns = set(options.get("hidden_columns", ()))
    visible_columns = [
        column for column in result.columns
        if column not in group_columns and column not in hidden_columns
    ]
    indexes_by_column = {
        column: result.columns.index(column) for column in result.columns
    }
    conditional_styles = options.get("conditional_styles", ())
    width = page_size[0] - 2 * horizontal_margin
    configured_widths = options.get("column_width_weights", {})
    weights = [float(configured_widths.get(column, 1)) for column in visible_columns]
    weight_total = sum(weights) or 1
    column_widths = [width * weight / weight_total for weight in weights]

    def add_table(rows):
        data = [[_paragraph(column, cell_header) for column in visible_columns]]
        for row in rows:
            rendered = []
            for column in visible_columns:
                style = cell
                for rule in conditional_styles:
                    if (rule.get("target_column") == column and
                            row[indexes_by_column[rule["when_column"]]] == rule.get("equals")):
                        if rule.get("style") == "warning-icon":
                            style = "warning-icon"
                        elif rule.get("style") == "bold-italic":
                            style = cell_bold_italic
                        elif rule.get("style") in {"trend-up", "trend-down"}:
                            style = rule["style"]
                        break
                rendered.append(
                    _warning_icon() if style == "warning-icon"
                    else _trend_cell(
                        row[indexes_by_column[column]],
                        "up" if style == "trend-up" else "down",
                        cell,
                    ) if style in {"trend-up", "trend-down"}
                    else _paragraph(row[indexes_by_column[column]], style)
                )
            data.append(rendered)
        total_row = options.get("total_row")
        if total_row:
            def total_value(column):
                value = str(total_row.get(column, ""))
                for name, variable in result.variables.items():
                    value = value.replace("{{ " + name + " }}", str(variable or ""))
                return value

            data.append([
                _paragraph(total_value(column), cell_header)
                for column in visible_columns
            ])
        table = Table(data, colWidths=column_widths, repeatRows=1, hAlign="LEFT")
        commands = [
            ("BACKGROUND", (0, 0), (-1, 0), LIGHT),
            ("TEXTCOLOR", (0, 0), (-1, 0), INK),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F2F2F2")]),
            ("LINEBELOW", (0, 0), (-1, -1), .3, colors.HexColor("#C9D1DC")),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("LEFTPADDING", (0, 0), (-1, -1), 3), ("RIGHTPADDING", (0, 0), (-1, -1), 3),
            ("TOPPADDING", (0, 0), (-1, -1), 3), ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ]
        if total_row:
            commands.extend([
                ("BACKGROUND", (0, -1), (-1, -1), LIGHT),
                ("LINEABOVE", (0, -1), (-1, -1), 1.2, INK),
            ])
        table.setStyle(TableStyle(commands))
        story.append(table)

    if group_columns:
        group_index = result.columns.index(group_columns[0])
        grouped = OrderedDict()
        for row in result.rows:
            grouped.setdefault(row[group_index], []).append(row)
        for number, (group, rows) in enumerate(grouped.items()):
            if number and definition.groups[0].get("page_break"):
                story.append(PageBreak())
            story.append(Paragraph(escape(str(group)), ParagraphStyle(
                "GenericGroup", parent=subtitle_style, fontName="Helvetica-Bold",
                fontSize=11, leading=14, textColor=colors.white, backColor=BLUE,
                borderPadding=6, spaceBefore=4 * mm, spaceAfter=2 * mm,
            )))
            add_table(rows)
    else:
        add_table(result.rows)

    def footer(canvas, doc):
        canvas.saveState()
        if profile == "internal":
            logo = _asset("3f-logo-minibw.png")
            if logo.exists():
                canvas.drawImage(
                    str(logo), horizontal_margin, page_size[1] - 16 * mm,
                    8 * mm, 8 * mm, mask="auto", preserveAspectRatio=True,
                )
            canvas.setFillColor(INK)
            canvas.setFont("Helvetica", 7.5)
            canvas.drawString(
                18 * mm, page_size[1] - 11.5 * mm,
                "3F Handelsgesellschaft mbH · Ederstraße 72 · 57319 Bad Berleburg",
            )
            canvas.setFillColor(colors.HexColor("#4B5563"))
            canvas.setFont("Helvetica-Bold", 7)
            canvas.drawRightString(
                page_size[0] - horizontal_margin, page_size[1] - 11.5 * mm,
                "NUR FÜR DEN INTERNEN GEBRAUCH",
            )
            canvas.setStrokeColor(colors.HexColor("#6B7280"))
            canvas.setLineWidth(.6)
            canvas.line(
                18 * mm, page_size[1] - 18 * mm,
                page_size[0] - horizontal_margin, page_size[1] - 18 * mm,
            )
        canvas.setFont("Helvetica", 7)
        canvas.setFillColor(colors.HexColor("#667085"))
        canvas.drawString(horizontal_margin, 6.5 * mm, "3F Handelsgesellschaft mbH")
        canvas.drawRightString(page_size[0] - horizontal_margin, 6.5 * mm, f"Seite {doc.page}")
        canvas.restoreState()

    document.build(story, onFirstPage=footer, onLaterPages=footer)
    return buffer.getvalue()


def render_address_labels_pdf(definition, result) -> bytes:
    """Avery/Zweckform 3474: 3 Spalten x 8 Etiketten, 70 x 37 mm."""
    from reportlab.pdfgen import canvas

    buffer = BytesIO()
    pdf = canvas.Canvas(buffer, pagesize=A4, pageCompression=1)
    pdf.setTitle(str(result.variables.get("title", definition.name)))
    label_width, label_height = 70 * mm, 37 * mm
    left, top = 0 * mm, 0.5 * mm
    for index, row in enumerate(result.rows):
        slot = index % 24
        if index and slot == 0:
            pdf.showPage()
        column, line = slot % 3, slot // 3
        x = left + column * label_width + 6 * mm
        y_top = A4[1] - top - line * label_height - 9 * mm
        value = " ".join("" if item is None else str(item) for item in row)
        lines = value.splitlines()
        pdf.setFillColor(INK)
        pdf.setFont("Helvetica", 9)
        for offset, text in enumerate(lines[:5]):
            pdf.drawString(x, y_top - offset * 4.2 * mm, text)
    pdf.save()
    return buffer.getvalue()
