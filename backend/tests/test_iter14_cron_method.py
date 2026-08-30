"""Iteration 14 — regresión del método HTTP del cron (/api/cron/recordatorios GET+POST)."""
import os
import re
import time
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest
import requests
from dotenv import dotenv_values

frontend_env = dotenv_values("/app/frontend/.env")
base_url = os.environ.get("REACT_APP_BACKEND_URL") or frontend_env.get("REACT_APP_BACKEND_URL")
if not base_url:
    raise RuntimeError("REACT_APP_BACKEND_URL missing")
BASE_URL = base_url.rstrip("/")
API = f"{BASE_URL}/api"

CRON_SECRET = "9f3c7a2e5b8d4f1a6c0e3b7d9a2f5c8e1b4d6a0f3c7e9b2d5a8c1e4f6b0d3a7c"
TEST_EMAIL = "delivered@resend.dev"
CRON_URL = f"{API}/cron/recordatorios"


def madrid_now():
    return datetime.now(ZoneInfo("Europe/Madrid"))


@pytest.fixture(scope="session")
def client():
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    return s


@pytest.fixture(scope="session")
def creds():
    content = Path("/app/memory/test_credentials.md").read_text(encoding="utf-8")
    email = re.search(r"(?im)^\s*(?:[-*]\s*)?(?:\*\*)?email(?:\*\*)?\s*:\s*`?([^`\s]+)", content).group(1)
    pwd = re.search(r"(?im)^\s*(?:[-*]\s*)?(?:\*\*)?password(?:\*\*)?\s*:\s*`?([^`\s]+)", content).group(1)
    return {"email": email, "password": pwd}


@pytest.fixture(scope="session")
def admin_headers(client, creds):
    r = client.post(f"{API}/auth/login", json=creds)
    if r.status_code != 200:
        pytest.fail(f"admin login failed {r.status_code}: {r.text[:300]}")
    t = r.json().get("token") or r.json().get("access_token")
    assert t, r.text
    return {"Authorization": f"Bearer {t}", "Content-Type": "application/json"}


@pytest.fixture(scope="session")
def created(client, admin_headers):
    ids = []
    yield ids
    for aid in ids:
        client.post(f"{API}/appointments/{aid}/admin-cancel", headers=admin_headers)


# --- 1. Auth guards on both methods ---
class TestCronMethodAuth:
    def test_get_no_auth_401(self, client):
        r = client.get(CRON_URL)
        assert r.status_code == 401, f"{r.status_code} {r.text[:200]}"

    def test_post_no_auth_401(self, client):
        r = client.post(CRON_URL)
        assert r.status_code == 401, f"{r.status_code} {r.text[:200]}"

    def test_get_bad_token_401(self, client):
        r = client.get(CRON_URL, headers={"Authorization": "Bearer wrong-secret"})
        assert r.status_code == 401, f"{r.status_code} {r.text[:200]}"

    def test_post_bad_token_401(self, client):
        r = client.post(CRON_URL, headers={"Authorization": "Bearer wrong-secret"})
        assert r.status_code == 401, f"{r.status_code} {r.text[:200]}"

    def test_get_good_token_200(self, client):
        r = client.get(CRON_URL, headers={"Authorization": f"Bearer {CRON_SECRET}"})
        assert r.status_code == 200, f"{r.status_code} {r.text[:300]}"
        assert r.json() == {"ok": True}

    def test_post_good_token_200(self, client):
        r = client.post(CRON_URL, headers={"Authorization": f"Bearer {CRON_SECRET}"})
        assert r.status_code == 200, f"{r.status_code} {r.text[:300]}"
        assert r.json() == {"ok": True}

    def test_put_not_allowed(self, client):
        r = client.put(CRON_URL, headers={"Authorization": f"Bearer {CRON_SECRET}"})
        assert r.status_code == 405, f"expected 405 for PUT, got {r.status_code}"


# --- 2. E2E: cita de mañana + GET cron -> recordatorio_enviado ---
class TestCronGetEndToEnd:
    def test_get_triggers_reminder(self, client, created):
        tomorrow = (madrid_now() + timedelta(days=1)).strftime("%Y-%m-%d")
        svcs = client.get(f"{API}/services").json()
        svc = svcs[0]
        slots = client.get(f"{API}/availability", params={"date": tomorrow, "service_id": svc["id"]}).json()
        slots = slots.get("slots", slots) if isinstance(slots, dict) else slots
        if not slots:
            pytest.skip(f"no free slots tomorrow ({tomorrow})")
        r = None
        for slot in slots:
            r = client.post(f"{API}/appointments", json={
                "service_id": svc["id"], "date": tomorrow, "start": slot,
                "client_name": "TEST_Cron GET QA", "client_phone": "+34699100555",
                "client_email": TEST_EMAIL, "accepted_policy": True,
            })
            if r.status_code == 200:
                break
        assert r is not None and r.status_code == 200, r.text
        a = r.json()
        created.append(a["id"])
        assert a["recordatorio_enviado"] is False
        # regression: whatsapp_links still present
        assert isinstance(a.get("whatsapp_links"), dict), a
        assert a["whatsapp_links"]["cliente"].startswith("https://wa.me/34699100555?text=")

        cr = client.get(CRON_URL, headers={"Authorization": f"Bearer {CRON_SECRET}"})
        assert cr.status_code == 200, cr.text
        assert cr.json() == {"ok": True}

        ok = False
        for _ in range(10):
            time.sleep(2)
            g = client.get(f"{API}/appointments/{a['id']}")
            if g.status_code == 200 and g.json().get("recordatorio_enviado") is True:
                ok = True
                break
        assert ok, "recordatorio_enviado not True after GET cron trigger"
