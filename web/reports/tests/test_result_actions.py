import pytest
from django.core.files.base import ContentFile
from django.urls import reverse

from reports.models import ReportJob


@pytest.mark.django_db
def test_finished_pdf_report_offers_print_and_mail_actions(client):
    job = ReportJob.objects.create(report_key="preisliste")
    job.result_html.save("report.html", ContentFile(b"<p>Bericht</p>"))
    job.result_pdf.save("report.pdf", ContentFile(b"%PDF-1.4\n"))

    response = client.get(reverse("reports:job-detail", args=[job.pk]))
    content = response.content.decode()

    assert "Drucken" in content
    assert "Per E-Mail senden" in content
    assert "navigator.share" in content
    assert "mailto:" in content
