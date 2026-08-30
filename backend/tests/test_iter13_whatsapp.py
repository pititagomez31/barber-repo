"""Iteration 13 — WhatsApp confirmation / reminders / cron / maps_query."""
import os
import re
import urllib.parse as up
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


def madrid_today():
    return datetime.now(ZoneInfo("Europe/Madrid"))


@pytest.fixture(scope="session")
def creds():
    content = Path("/app/memory/test_credentials.md").read_text(encoding="utf-8")
    email = re.search(r"(?im)^\s*(?:[-*]\s*)?(?:\*\*)?email(?:\*\*)?\s*:\s*`?([^`\s]+)", content).group(1)
    pwd = re.search(r"(?im)^\s*(?:[-*]\s*)?(?:\*\*)?password(?:\*\*)?\s*:\s*`?([^`\s]+)", content).group(1)
    return {"email": email, "password": pwd}


@pytest.fixture(scope="session")
def client():
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    return s


@pytest.fixture(scope="session")
def token(client, creds):
    r = client.post(f"{API}/auth/login", json=creds)
    if r.status_code != 200:
        pytest.fail(f"admin login failed {r.status_code}: {r.text[:300]}")
    t = r.json().get("token") or r.json().get("access_token")
    assert t
    return t


@pytest.fixture(scope="session")
def admin_headers(token):
    return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}


@pytest.fixture(scope="session")
def created(client, admin_headers):
    ids = []
    yield ids
    for aid in ids:
        client.post(f"{API}/appointments/{aid}/admin-cancel", headers=admin_headers)


def _services(client):
    r = client.get(f"{API}/services")
    assert r.status_code == 200
    return r.json()


def _free_slot(client, date, service_id):
    r = client.get(f"{API}/availability", params={"date": date, "service_id": service_id})
    assert r.status_code == 200, r.text
    data = r.json()
    slots = data.get("slots", data) if isinstance(data, dict) else data
    return slots


def _book(client, date, phone, email=TEST_EMAIL):
    svcs = _services(client)
    svc = svcs[0]
    for d_off in range(0, 8):
        d = (datetime.strptime(date, "%Y-%m-%d") + timedelta(days=d_off)).strftime("%Y-%m-%d")
        slots = _free_slot(client, d, svc["id"])
        r = None
        payload = None
        for slot in slots:
            payload = {
                "service_id": svc["id"],
                "date": d,
                "start": slot,
                "client_name": "TEST_Cliente QA",
                "client_phone": phone,
                "client_email": email,
                "accepted_policy": True,
            }
            r = client.post(f"{API}/appointments", json=payload)
            if r.status_code != 409 or "hora ya no" not in r.text:
                return r, payload
        if r is not None:
            return r, payload
    pytest.fail(f"no free slots found starting {date}")


# --- 1. business maps_query ---
class TestBusiness:
    def test_maps_query_present(self, client):
        r = client.get(f"{API}/business")
        assert r.status_code == 200
        data = r.json()
        assert "maps_query" in data, data
        assert "Multitienda Veloz 24hr" in data["maps_query"]
        assert "Avenida de Los Majuelos 51C" in data["maps_query"]


# --- 2. create appointment with email + whatsapp links ---
class TestCreateWithWhatsapp:
    def test_create_returns_links_and_persists(self, client, admin_headers, created):
        phone = "+34699100101"
        today = madrid_today().strftime("%Y-%m-%d")
        r, payload = _book(client, today, phone)
        assert r.status_code == 200, r.text
        a = r.json()
        created.append(a["id"])

        assert a["client_email"] == TEST_EMAIL
        assert a["confirmado"] is False
        assert a["recordatorio_enviado"] is False

        links = a.get("whatsapp_links")
        assert isinstance(links, dict), a
        assert links.get("barbero") is None, "BUSINESS_WHATSAPP empty -> barbero must be null"
        cli = links.get("cliente")
        assert cli and cli.startswith("https://wa.me/34699100101?text=")
        text = up.unquote(cli.split("text=", 1)[1])
        assert payload["date"] in text
        assert payload["start"] in text
        assert a["service_name"] in text

        # persistence
        g = client.get(f"{API}/appointments/{a['id']}")
        assert g.status_code == 200
        d = g.json()
        assert d["client_email"] == TEST_EMAIL
        assert d["confirmado"] is False
        assert d["recordatorio_enviado"] is False

    def test_create_without_email_ok(self, client, created):
        r, _ = _book(client, madrid_today().strftime("%Y-%m-%d"), "+34699100102", email="")
        assert r.status_code == 200, r.text
        a = r.json()
        created.append(a["id"])
        assert a["client_email"] == ""
        assert a["whatsapp_links"]["cliente"].startswith("https://wa.me/34699100102")


# --- 3. auth on confirmar / recordatorio ---
class TestAdminAuthGuards:
    def test_confirmar_requires_auth(self, client):
        r = client.put(f"{API}/appointments/fake-id/confirmar")
        assert r.status_code in (401, 403), r.status_code

    def test_recordatorio_requires_auth(self, client):
        r = client.post(f"{API}/appointments/fake-id/recordatorio")
        assert r.status_code in (401, 403), r.status_code

    def test_confirmar_bad_token(self, client):
        r = client.put(f"{API}/appointments/fake-id/confirmar", headers={"Authorization": "Bearer nope"})
        assert r.status_code in (401, 403)

    def test_confirmar_404_unknown_id(self, client, admin_headers):
        r = client.put(f"{API}/appointments/does-not-exist/confirmar", headers=admin_headers)
        assert r.status_code == 404, r.text

    def test_recordatorio_404_unknown_id(self, client, admin_headers):
        r = client.post(f"{API}/appointments/does-not-exist/recordatorio", headers=admin_headers)
        assert r.status_code == 404, r.text


# --- 4. confirmar + recordatorio happy path ---
class TestConfirmarRecordatorio:
    def test_flow(self, client, admin_headers, created):
        r, payload = _book(client, madrid_today().strftime("%Y-%m-%d"), "+34699100103")
        assert r.status_code == 200, r.text
        a = r.json()
        created.append(a["id"])

        c = client.put(f"{API}/appointments/{a['id']}/confirmar", headers=admin_headers)
        assert c.status_code == 200, c.text
        assert c.json()["confirmado"] is True

        g = client.get(f"{API}/appointments/{a['id']}")
        assert g.json()["confirmado"] is True

        rec = client.post(f"{API}/appointments/{a['id']}/recordatorio", headers=admin_headers)
        assert rec.status_code == 200, rec.text
        url = rec.json()["url"]
        assert url.startswith("https://wa.me/34699100103?text=")
        txt = up.unquote(url.split("text=", 1)[1])
        assert "cita de mañana" in txt
        assert a["date"] in txt and a["start"] in txt

        # idempotent confirm
        c2 = client.put(f"{API}/appointments/{a['id']}/confirmar", headers=admin_headers)
        assert c2.status_code == 200


# --- 5. cron auth ---
class TestCronAuth:
    def test_no_token(self, client):
        r = client.post(f"{API}/cron/recordatorios")
        assert r.status_code == 401, r.text

    def test_bad_token(self, client):
        r = client.post(f"{API}/cron/recordatorios", headers={"Authorization": "Bearer wrong-secret"})
        assert r.status_code == 401, r.text

    def test_good_token(self, client):
        r = client.post(f"{API}/cron/recordatorios", headers={"Authorization": f"Bearer {CRON_SECRET}"})
        assert r.status_code == 200, r.text
        assert r.json() == {"ok": True}


# --- 6. cron end-to-end for tomorrow's appointment ---
class TestCronEndToEnd:
    def test_reminder_marked(self, client, admin_headers, created):
        tomorrow = (madrid_today() + timedelta(days=1)).strftime("%Y-%m-%d")
        svc = _services(client)[0]
        slots = _free_slot(client, tomorrow, svc["id"])
        if not slots:
            pytest.skip(f"no free slots tomorrow ({tomorrow})")
        r = client.post(f"{API}/appointments", json={
            "service_id": svc["id"], "date": tomorrow, "start": slots[0],
            "client_name": "TEST_Cron QA", "client_phone": "+34699100104",
            "client_email": TEST_EMAIL, "accepted_policy": True,
        })
        assert r.status_code == 200, r.text
        a = r.json()
        created.append(a["id"])
        assert a["recordatorio_enviado"] is False

        cr = client.post(f"{API}/cron/recordatorios", headers={"Authorization": f"Bearer {CRON_SECRET}"})
        assert cr.status_code == 200

        import time
        ok = False
        for _ in range(15):
            time.sleep(2)
            g = client.get(f"{API}/appointments/{a['id']}")
            if g.status_code == 200 and g.json().get("recordatorio_enviado") is True:
                ok = True
                break
        assert ok, "recordatorio_enviado not set to True after cron run"
