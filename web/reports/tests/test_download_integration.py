import pytest
from django.urls import reverse


@pytest.mark.django_db
def test_dashboard_contains_local_download_integration(client):
    response = client.get(reverse("reports:dashboard") + "?open_download=export.csv")
    content = response.content.decode()
    assert "Downloadordner für SilverLists Web verbinden" in content
    assert "showDirectoryPicker" in content
    assert "open_download" in content
