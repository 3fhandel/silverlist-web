import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse

from reports.models import ReportJob


@pytest.mark.django_db
def test_upload_detect_select_and_process(client, settings, tmp_path):
    settings.MEDIA_ROOT = tmp_path / "media"
    source = (
        "Warengruppe;Artikel-Nr.;Bezeichnung 1;S-Einheit;PG:VK1\n"
        "Obst;4711;Birne;kg;2,40\n"
    ).encode("cp1252")

    response = client.post(
        reverse("reports:dashboard"),
        {"source_file": SimpleUploadedFile("artikel.csv", source)},
    )
    job = ReportJob.objects.get()
    assert response.status_code == 302
    assert response.url == reverse("reports:select-report", args=[job.pk])

    selection = client.get(response.url)
    assert b"Ordersatz VK1" in selection.content

    result = client.post(response.url, {"report_key": "ordersatz-vk1"})
    job.refresh_from_db()
    assert result.status_code == 302
    assert job.status == ReportJob.Status.SUCCEEDED
    assert job.result_html
    assert job.result_pdf
