import json
import os
import subprocess
import sys


def test_base_url_configures_host_origin_and_url_prefix():
    environment = os.environ | {
        "SILVERLISTS_BASE_URL": "https://sandbox.3f-blb.local/silverlists/",
        "DJANGO_SETTINGS_MODULE": "config.settings",
    }
    code = """
import json
import django
django.setup()
from django.conf import settings
from django.urls import reverse
print(json.dumps({
    'hosts': settings.ALLOWED_HOSTS,
    'origins': settings.CSRF_TRUSTED_ORIGINS,
    'prefix': settings.FORCE_SCRIPT_NAME,
    'static': settings.STATIC_URL,
    'session_path': settings.SESSION_COOKIE_PATH,
    'dashboard': reverse('reports:dashboard'),
}))
"""
    result = subprocess.run(
        [sys.executable, "-c", code], check=True, capture_output=True,
        text=True, env=environment,
    )
    configured = json.loads(result.stdout)
    assert "sandbox.3f-blb.local" in configured["hosts"]
    assert "https://sandbox.3f-blb.local" in configured["origins"]
    assert configured["prefix"] == "/silverlists"
    assert configured["static"] == "/silverlists/static/"
    assert configured["session_path"] == "/silverlists/"
    assert configured["dashboard"] == "/silverlists/"
