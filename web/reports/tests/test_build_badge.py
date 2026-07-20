import pytest

from django.test import override_settings
from django.urls import reverse


@pytest.mark.django_db
@override_settings(SILVERLISTS_BUILD="20260720-1010")
def test_build_badge_is_visible_next_to_brand(client):
    response = client.get(reverse("reports:dashboard"))

    assert response.status_code == 200
    content = response.content.decode()
    assert "Build 20260720-1010" in content
    assert 'class="build-badge"' in content
