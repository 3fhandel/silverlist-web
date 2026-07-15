import pytest
from io import BytesIO
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse
from PIL import Image
from reports.catalog import matching_definitions
from reports.models import ReportJob, ReportJobSource
from reports.report_modules.weekly_offer import DESIGNS, load_products, render_pdf, short_article_number


HEADER = (
    "Artikel-Nr.;Warengruppe;Ab Menge;Preis;Währung;EK-Kalk;S.-Einheit;"
    "Bezeichnung 1;Rabatt;Rabattfähig;Bezeichnung 2;Suchbegriff;"
    "Gültig ab;Gültig bis;Referenz;Archiv Artikel\n"
)
ROW = "10-60-61590;;0;6,66;EUR;6,19;BX;Vanilleeis;0;Ja;;Vanille;15.03.2026;21.03.2026;X;0\n"


def test_weekly_offer_matches_pricelist_definition_header():
    header = tuple(HEADER.strip().split(";"))
    matches = [item for item in matching_definitions(header) if item.key == "wochenangebot"]
    assert len(matches) == 1
    assert matches[0].renderer == "weekly-offer"


def test_product_import_uses_csv_names_and_short_number(settings, tmp_path):
    settings.WEEKLY_OFFER_IMAGE_DIR = None
    source = tmp_path / "offer.csv"
    source.write_bytes((HEADER + ROW).encode("cp1252"))
    product = load_products(source)[0]
    assert product["description"] == "Vanilleeis"
    assert product["short_number"] == "61590"
    assert product["reference"] == "X"
    assert short_article_number("10-90-20-908156") == "908156"


def test_weekly_offer_pdf_has_two_a4_pages(settings):
    pdf = render_pdf({
        "design": "fruechte", "validity": "gültig von 15.03. bis 21.03.",
        "products": [{
            "slot": "front-1", "description": "Vanilleeis", "price": "6,66",
            "unit": "BX", "short_number": "61590", "image": "",
        }],
    })
    assert pdf.startswith(b"%PDF")
    assert pdf.count(b"/Type /Page\n") == 2
    assert b"/MediaBox [ 0 0 595.2756 841.8898 ]" in pdf


def test_modern_design_is_available_and_renders():
    assert DESIGNS["modern-3f"].name == "Modern 3F"
    pdf = render_pdf({"design": "modern-3f", "validity": "diese Woche", "products": []})
    assert pdf.startswith(b"%PDF")
    assert pdf.count(b"/Type /Page\n") == 2


@pytest.mark.django_db
def test_weekly_offer_workflow_opens_custom_editor(client, settings, tmp_path):
    settings.MEDIA_ROOT = tmp_path / "media"
    settings.WEEKLY_OFFER_IMAGE_DIR = None
    upload = SimpleUploadedFile("angebot.csv", (HEADER + ROW).encode("cp1252"))
    response = client.post(reverse("reports:dashboard"), {"source_file": upload})
    job = ReportJob.objects.get()
    response = client.post(response.url, {"report_key": "wochenangebot"})
    assert response.url == reverse("reports:configure-report", args=[job.pk])
    editor = client.get(response.url)
    assert editor.status_code == 200
    assert "Automatisch zuordnen" in editor.content.decode()
    assert "Produktbildordner auswählen" in editor.content.decode()
    assert "showDirectoryPicker" in editor.content.decode()
    assert 'enctype="multipart/form-data"' in editor.content.decode()
    assert 'data-front-priority="1"' in editor.content.decode()
    image_buffer = BytesIO()
    Image.new("RGB", (20, 20), "green").save(image_buffer, format="PNG")
    result = client.post(response.url, {
        "design": "fruechte",
        "validity": "gültig von 15.03.2026 bis 21.03.2026",
        "slot_0": "front-1",
        "description_0": "Vanilleeis",
        "price_0": "6,66",
        "unit_0": "BX",
        "image_0": SimpleUploadedFile(
            "61590-produkt.png", image_buffer.getvalue(), content_type="image/png",
        ),
    })
    job.refresh_from_db()
    assert result.url == reverse("reports:job-detail", args=[job.pk])
    assert job.status == ReportJob.Status.SUCCEEDED, job.error_message
    assert job.result_pdf
    image_source = ReportJobSource.objects.get(job=job, name="weekly-image-0")
    assert image_source.source_file.name.endswith("61590-produkt.png")
    assert job.parameters["products"][0]["image"] == image_source.source_file.path
    detail = client.get(result.url)
    assert "Wochenangebot bearbeiten" in detail.content.decode()

    editor_again = client.get(reverse("reports:configure-report", args=[job.pk]))
    form = editor_again.context["form"]
    assert form["slot_0"].value() == "front-1"
    assert form["description_0"].value() == "Vanilleeis"
    assert form["price_0"].value() == "6,66"
    assert form["unit_0"].value() == "BX"
