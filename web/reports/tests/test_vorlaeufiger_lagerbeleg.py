from pathlib import Path

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse
from reports.catalog import get_definition, matching_definitions
from reports.models import ReportJob
from reports.services.duckdb_engine import execute_report, inspect_csv_header
from reports.services.pdf_renderer import render_warehouse_note_pdf


SOURCE = (
    "Pos.;Artikel-Nr.;Bezeichnung 1;Bezeichnung 2;Bezeichnung 4;Menge;Einheit;Termin;Deckung;Status;Disponierbar\n"
    "2;80-2;Normaler Artikel;;;3;KT;04.11.2026;1;offen;1\n"
    "1;40-1;Artikel mit Hinweis;;Nur gekühlt lagern;12;ST;04.11.2026;1;offen;1\n"
).encode("cp1252")


def test_warehouse_note_is_recognized_and_prepares_writing_column(tmp_path: Path):
    source = tmp_path / "lagerpositionen.csv"
    source.write_bytes(SOURCE)
    definition = get_definition("vorlaeufiger-lagerbeleg")

    assert definition in matching_definitions(inspect_csv_header(source))
    result = execute_report(source, definition, {
        "kundennummer": "4711", "lagerbelegnummer": "A-12345",
        "kundenanschrift": "Musterkunde GmbH\nTeststraße 1\n57319 Bad Berleburg",
    })

    assert result.columns == (
        "Pos.", "Artikel-Nr.", "Bezeichnung", "Menge", "Einheit", "Komm", "__fett",
    )
    assert result.rows[0] == (
        "1", "40-1", "Artikel mit Hinweis\nNur gekühlt lagern", "12", "ST", "", "1",
    )
    assert result.rows[1][-1] == "0"
    pdf = render_warehouse_note_pdf(definition, result)
    assert pdf.startswith(b"%PDF-")


@pytest.mark.django_db
def test_warehouse_note_workflow_requests_customer_number(client, settings, tmp_path):
    settings.MEDIA_ROOT = tmp_path / "media"
    response = client.post(reverse("reports:dashboard"), {
        "source_file": SimpleUploadedFile("lagerpositionen.csv", SOURCE),
    })
    job = ReportJob.objects.get()
    selection = client.get(response.url).content.decode()
    assert "Vorläufiger Lagerbeleg" in selection
    assert "Vorläufiger Lieferschein" not in selection

    response = client.post(response.url, {"report_key": "vorlaeufiger-lagerbeleg"})
    assert response.url == reverse("reports:configure-report", args=[job.pk])
    form = client.get(response.url).content.decode()
    assert "Kundennummer" in form
    assert "Kundenname und Anschrift" in form
    assert "Lagerbelegnummer / Auftragsnummer" in form

    response = client.post(response.url, {
        "kundennummer": "4711", "lagerbelegnummer": "A-12345",
        "kundenanschrift": "Musterkunde GmbH\nTeststraße 1\n57319 Bad Berleburg",
    })
    job.refresh_from_db()
    assert response.url == reverse("reports:job-detail", args=[job.pk])
    assert job.status == ReportJob.Status.SUCCEEDED
    assert job.result_pdf
