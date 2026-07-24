import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse

from reports.catalog import get_definition
from reports.models import ReportJob
from reports.services.duckdb_engine import execute_report


PRICE_HEADER = (
    "Artikel-Nr.", "Suchbegriff", "Bezeichnung 1", "Typ", "Referenz",
    "Zeitpunkt", "Benutzer", "Ab Menge", "Preis", "Preis neu", "Währung",
)
SPECIAL_HEADER = (
    "Artikel-Nr.", "Beschreibung 1", "EK-Kalk", "Kunden-Nr.", "Name1",
    "Kundenpreis", "Prozent von EK-Kalk",
)


def write_sources(tmp_path):
    prices = tmp_path / "preise.csv"
    prices.write_text(
        ";".join(PRICE_HEADER) + "\n"
        "90-1;Artikel;Später Artikel;supplierArticle;Lieferant B;7920996852379;user;0;8,0000;8,8000;EUR\n"
        "10-1;Artikel;Früher Artikel;supplierArticle;Lieferant A;7920947255856;user;0;10,0000;9,0000;EUR\n",
        encoding="utf-8",
    )
    special = tmp_path / "sonderpreise.csv"
    special.write_text(
        ";".join(SPECIAL_HEADER) + "\n"
        "10-1;Früher Artikel;10,0000;10001;Kunde Eins;11,5000;15,00\n"
        "10-1;Früher Artikel;10,0000;10002;Kunde Zwei;12,0000;20,00\n"
        "50-1;Nicht geändert;5,0000;10003;Anderer Kunde;6,0000;20,00\n",
        encoding="utf-8",
    )
    return prices, special


def test_combined_report_groups_changes_and_special_prices(tmp_path):
    prices, special = write_sources(tmp_path)

    result = execute_report(
        prices,
        get_definition("preisaenderungen-mit-sonderpreisen"),
        additional_sources={"sonderpreise": special},
    )

    group_index = result.columns.index("AID")
    entry_index = result.columns.index("Eintrag")
    reference_index = result.columns.index("Lieferant / Kunde")
    assert [row[group_index] for row in result.rows] == [
        "[10-1] Früher Artikel",
        "[10-1] Früher Artikel",
        "[10-1] Früher Artikel",
        "[90-1] Später Artikel",
    ]
    assert [row[entry_index] for row in result.rows] == [
        "EK-Änderung", "Kundensonderpreis", "Kundensonderpreis", "EK-Änderung",
    ]
    assert [row[reference_index] for row in result.rows[1:3]] == [
        "[10001] Kunde Eins", "[10002] Kunde Zwei",
    ]
    assert all("Nicht geändert" not in str(row) for row in result.rows)


@pytest.mark.django_db
def test_combined_report_requests_second_csv_after_selection(client, settings, tmp_path):
    settings.MEDIA_ROOT = tmp_path / "media"
    prices, special = write_sources(tmp_path)
    upload = SimpleUploadedFile("preise.csv", prices.read_bytes())
    response = client.post(reverse("reports:dashboard"), {"source_file": upload})
    job = ReportJob.objects.get()

    selection = client.get(response.url)
    assert "Preisänderungen mit Kundensonderpreisen" in selection.content.decode()
    response = client.post(response.url, {
        "report_key": "preisaenderungen-mit-sonderpreisen",
    })

    assert response.url == reverse("reports:configure-report", args=[job.pk])
    configuration = client.get(response.url)
    content = configuration.content.decode()
    assert "CSV für EK Sonderpreise" in content
    assert "Gespeicherte Abfragen / EK Sonderpreise" in content
    assert "data-file-dropzone" in content

    response = client.post(response.url, {
        "source__sonderpreise": SimpleUploadedFile(
            "sonderpreise.csv", special.read_bytes(),
        ),
    })
    job.refresh_from_db()
    assert response.url == reverse("reports:job-detail", args=[job.pk])
    assert job.status == ReportJob.Status.SUCCEEDED
    assert job.result_pdf
