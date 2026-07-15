from pathlib import Path

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile

from reports.models import ReportJob
from reports.services.processor import process_job


@pytest.mark.django_db
def test_processes_ordersatz_to_grouped_html(settings, tmp_path: Path):
    settings.MEDIA_ROOT = tmp_path / "media"
    source = (
        "Warengruppe;Artikel-Nr.;Bezeichnung 1;S-Einheit;PG:VK1\r\n"
        "Obst;2;Birne;kg;2,40\r\n"
        "Gemüse;1;Karotte;kg;1,20\r\n"
    ).encode("cp1252")
    job = ReportJob.objects.create(
        report_key="ordersatz-vk1",
        source_file=SimpleUploadedFile("artikel.csv", source),
    )

    process_job(job)
    job.refresh_from_db()

    assert job.status == ReportJob.Status.SUCCEEDED
    assert Path(job.result_pdf.path).read_bytes().startswith(b"%PDF")
    html = Path(job.result_html.path).read_text(encoding="utf-8")
    assert "Gemüse" in html
    assert "Karotte" in html
    assert "Obst" in html
    assert "Birne" in html


@pytest.mark.django_db
def test_marks_invalid_export_as_failed(settings, tmp_path: Path):
    settings.MEDIA_ROOT = tmp_path / "media"
    job = ReportJob.objects.create(
        report_key="ordersatz-vk1",
        source_file=SimpleUploadedFile("falsch.csv", b"Foo;Bar\n1;2\n"),
    )

    process_job(job)
    job.refresh_from_db()

    assert job.status == ReportJob.Status.FAILED
    assert "CSV-Spalten fehlen" in job.error_message


@pytest.mark.django_db
def test_uses_vk_netto_when_selected_price_group_is_empty(settings, tmp_path: Path):
    settings.MEDIA_ROOT = tmp_path / "media"
    source = (
        "Warengruppe;Artikel-Nr.;Bezeichnung 1;S-Einheit;PG:VK1;VK-Netto\n"
        "Obst;4711;Birne;kg;;2,49\n"
    ).encode("cp1252")
    job = ReportJob.objects.create(
        report_key="ordersatz-vk1",
        detected_header=["Warengruppe", "Artikel-Nr.", "Bezeichnung 1", "S-Einheit", "PG:VK1", "VK-Netto"],
        source_file=SimpleUploadedFile("artikel.csv", source),
    )

    process_job(job)
    job.refresh_from_db()

    html = Path(job.result_html.path).read_text(encoding="utf-8")
    assert "2,49" in html
