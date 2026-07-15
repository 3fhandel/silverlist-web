import pytest
from django.core.files.base import ContentFile
from django.urls import reverse

from reports.models import ReportJob


@pytest.mark.django_db
def test_pdf_preview_can_be_framed_by_same_origin(client, settings, tmp_path):
    settings.MEDIA_ROOT = tmp_path / "media"
    job = ReportJob.objects.create(report_key="ordersatz-vk1", source_file="source.csv")
    job.result_pdf.save("result.pdf", ContentFile(b"%PDF-1.4\n"))

    response = client.get(reverse("reports:result-pdf", args=[job.pk]))

    assert response.status_code == 200
    assert response.headers["X-Frame-Options"] == "SAMEORIGIN"
