from zipfile import ZipFile

import pytest
from django.urls import reverse


@pytest.mark.django_db
def test_dashboard_offers_extension_download(client):
    response = client.get(reverse("reports:dashboard"))

    assert reverse("reports:extension-download") in response.content.decode()
    assert "ZIP herunterladen" in response.content.decode()


def test_extension_zip_is_downloaded_as_attachment(client, settings, tmp_path):
    package = tmp_path / "silverlists-web-extension-1.2.3.zip"
    with ZipFile(package, "w") as archive:
        archive.writestr("manifest.json", '{"manifest_version": 3}')
    settings.SILVERLISTS_EXTENSION_PACKAGE = package

    response = client.get(reverse("reports:extension-download"))

    assert response.status_code == 200
    assert response["Content-Type"] == "application/zip"
    assert "attachment;" in response["Content-Disposition"]
    assert package.name in response["Content-Disposition"]
    assert b"".join(response.streaming_content).startswith(b"PK")
