from pathlib import Path

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile

from reports.catalog import get_catalog, get_definition, matching_definitions
from reports.models import ReportJob
from reports.services.duckdb_engine import inspect_csv_header
from reports.services.processor import process_job


def test_all_legacy_silverlists_reports_are_registered():
    legacy = [item for item in get_catalog() if item.key not in {
        "example-generic-report", "ordersatz-vk1", "ordersatz-vk2", "ordersatz-vk3",
        "ordersatz-vk4", "ordersatz-vk5", "ordersatz-vk6", "ordersatz-ohne-preise",
    }]
    assert len(legacy) == 25


def price_list_csv() -> bytes:
    definition = get_definition("preisliste")
    values = {column: "" for column in definition.required_columns}
    values.update({
        "Artikel-Nr.": "60-10-10001", "Bezeichnung 1": "Testartikel",
        "S.-Einheit": "kg", "Preis": "2,50", "Archiv Artikel": "0",
        "Gültig ab": "01.01.2026", "Gültig bis": "31.12.2026",
    })
    header = ";".join(definition.required_columns)
    row = ";".join(values[column] for column in definition.required_columns)
    return f"{header}\n{row}\n".encode("utf-8")


def test_price_list_export_is_recognized(tmp_path):
    source = tmp_path / "preisliste.csv"
    source.write_bytes(price_list_csv())
    keys = {item.key for item in matching_definitions(inspect_csv_header(source))}
    assert {"preisliste", "wochenangebot", "postangebot"}.issubset(keys)


@pytest.mark.django_db
def test_generic_price_list_creates_pdf(settings, tmp_path):
    settings.MEDIA_ROOT = tmp_path / "media"
    source = price_list_csv()
    definition = get_definition("preisliste")
    job = ReportJob.objects.create(
        report_key="preisliste",
        parameters={"preiseZeigen": True},
        detected_header=list(definition.required_columns),
        source_file=SimpleUploadedFile("preisliste.csv", source),
    )

    process_job(job)
    job.refresh_from_db()

    assert job.status == ReportJob.Status.SUCCEEDED, job.error_message
    assert Path(job.result_pdf.path).read_bytes().startswith(b"%PDF")
