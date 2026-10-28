from pathlib import Path

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse

from reports.catalog import get_definition, matching_definitions
from reports.models import ReportJob
from reports.services.duckdb_engine import execute_report, inspect_csv_header
from reports.services.pdf_renderer import render_delivery_note_pdf


SOURCE = (
    "Pos.;Artikel-Nr.;Bezeichnung 1;Bezeichnung 2;Menge;Einheit;Lieferdatum\n"
    "2;80-2;Zweiter Artikel;;3;KT;28.10.2026\n"
    "1;40-1;Erster Artikel;Restmenge geliefert;12;ST;28.10.2026\n"
).encode("cp1252")


def test_delivery_note_export_is_recognized_and_sorted(tmp_path: Path):
    source = tmp_path / "positionen.csv"
    source.write_bytes(SOURCE)
    definition = get_definition("vorlaeufiger-lieferschein")

    assert definition in matching_definitions(inspect_csv_header(source))
    result = execute_report(source, definition, {"empfaenger": "", "referenz": ""})

    assert result.columns == ("Pos.", "Artikel-Nr.", "Bezeichnung", "Menge", "Einheit")
    assert result.rows[0] == (
        "1", "40-1", "Erster Artikel\nRestmenge geliefert", "12", "ST",
    )
    assert result.variables["lieferdatum"] == "28.10.2026"
    assert render_delivery_note_pdf(definition, result).startswith(b"%PDF-")


@pytest.mark.django_db
def test_delivery_note_workflow_requests_optional_document_data(client, settings, tmp_path):
    settings.MEDIA_ROOT = tmp_path / "media"
    response = client.post(reverse("reports:dashboard"), {
        "source_file": SimpleUploadedFile("positionen.csv", SOURCE),
    })
    job = ReportJob.objects.get()
    selection = client.get(response.url)
    assert "Vorläufiger Lieferschein" in selection.content.decode()

    response = client.post(response.url, {"report_key": "vorlaeufiger-lieferschein"})
    assert response.url == reverse("reports:configure-report", args=[job.pk])
    form = client.get(response.url).content.decode()
    assert "Empfänger / Lieferanschrift" in form
    assert "Referenz / Auftragsnummer" in form

    response = client.post(response.url, {
        "empfaenger": "Testkunde\nTeststraße 1\n57319 Bad Berleburg",
        "referenz": "Auftrag 4711",
    })
    job.refresh_from_db()
    assert response.url == reverse("reports:job-detail", args=[job.pk])
    assert job.status == ReportJob.Status.SUCCEEDED
    assert job.result_pdf
