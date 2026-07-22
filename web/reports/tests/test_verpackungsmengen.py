import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse

from reports.models import ReportJob


ARTICLE_CSV = (
    "Artikel-Nr.;Bezeichnung 1;S-Einheit;A:Meldepflichtig;A:Gewicht Karton;A:Gewicht Kunststoff\n"
    "100;Testartikel;ST;1;0.044417;0.007863\n"
    "200;Nicht melden;ST;0;9;9\n"
).encode("cp1252")


@pytest.mark.django_db
def test_packaging_report_two_file_workflow(client, settings, tmp_path):
    settings.MEDIA_ROOT = tmp_path / "media"
    response = client.post(reverse("reports:dashboard"), {
        "source_file": SimpleUploadedFile("artikel.csv", ARTICLE_CSV),
    })
    job = ReportJob.objects.get()
    selection = client.get(response.url)
    assert "Verpackungsmengen (Meldepflicht)" in selection.content.decode()

    response = client.post(response.url, {"report_key": "verpackungsmengen"})
    assert response.url == reverse("reports:configure-report", args=[job.pk])
    configuration = client.get(response.url)
    assert "Controlling / Artikel-Umsätze" in configuration.content.decode()
    assert 'data-file-dropzone' in configuration.content.decode()
    assert "CSV hier ablegen" in configuration.content.decode()

    sales = b"Artikel-Nr.;Menge\n100;10\n100;2,5\n200;100\n"
    response = client.post(response.url, {
        "source__umsatz": SimpleUploadedFile("umsatz.csv", sales),
    })
    assert response.url == reverse("reports:job-detail", args=[job.pk])
    job.refresh_from_db()
    assert job.status == ReportJob.Status.SUCCEEDED
    html = job.result_html.read().decode("utf-8")
    assert "0,555" in html
    assert "0,098" in html
    assert "Nicht melden" not in html
    assert html.index("Testartikel") < html.index("Summe")
    assert "0,555 kg" in html
    assert "0,098 kg" in html


@pytest.mark.django_db
def test_packaging_report_accepts_actual_article_sales_header(client, settings, tmp_path):
    settings.MEDIA_ROOT = tmp_path / "media"
    client.post(reverse("reports:dashboard"), {
        "source_file": SimpleUploadedFile("artikel.csv", ARTICLE_CSV),
    })
    job = ReportJob.objects.get()
    client.post(reverse("reports:select-report", args=[job.pk]), {
        "report_key": "verpackungsmengen",
    })
    sales = (
        "Warengruppennummer;Warengruppe;Artikelnummer;GTIN / EANCode;"
        "Bezeichnung 1;Bezeichnung 2;Umsatz;Menge;S-Einheit;Marge;Ums. 2025;M. 2025\n"
        "10;Test;100;;Testartikel;;33.018;9.746;ST;20%;0;0\n"
    ).encode("cp1252")
    response = client.post(reverse("reports:configure-report", args=[job.pk]), {
        "source__umsatz": SimpleUploadedFile("infoGrid.csv", sales),
    })
    assert response.url == reverse("reports:job-detail", args=[job.pk])
    job.refresh_from_db()
    assert job.status == ReportJob.Status.SUCCEEDED
    html = job.result_html.read().decode("utf-8")
    assert "9746,000" in html
    assert "432,888" in html
    assert "76,633" in html


@pytest.mark.django_db
def test_packaging_report_rejects_wrong_second_export(client, settings, tmp_path):
    settings.MEDIA_ROOT = tmp_path / "media"
    client.post(reverse("reports:dashboard"), {
        "source_file": SimpleUploadedFile("artikel.csv", ARTICLE_CSV),
    })
    job = ReportJob.objects.get()
    client.post(reverse("reports:select-report", args=[job.pk]), {
        "report_key": "verpackungsmengen",
    })
    response = client.post(reverse("reports:configure-report", args=[job.pk]), {
        "source__umsatz": SimpleUploadedFile("falsch.csv", b"Foo;Bar\n1;2\n"),
    })
    assert response.status_code == 200
    assert "Fehlende Spalten: Artikel-Nr., Menge" in response.content.decode()
