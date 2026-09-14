"""Tests for +58 BarberStudio - booker_name feature and 2-limit per phone."""
import os
import pytest
import requests
from datetime import datetime, timedelta

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")
if not BASE_URL:
    # fallback: read from frontend/.env
    with open("/app/frontend/.env") as f:
        for line in f:
            if line.startswith("REACT_APP_BACKEND_URL="):
                BASE_URL = line.split("=", 1)[1].strip().rstrip("/")

ADMIN_EMAIL = "pititagomez31@gmail.com"
ADMIN_PASSWORD = "58Barber2025!"

PHONE_A = "+34600555901"  # unique for this test run
PHONE_B = "+34600555902"
PHONE_C = "+34600555903"
PHONE_D = "+34600555904"


@pytest.fixture(scope="module")
def api():
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    return s


@pytest.fixture(scope="module")
def admin_token(api):
    r = api.post(f"{BASE_URL}/api/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD})
    assert r.status_code == 200, f"admin login failed: {r.text}"
    return r.json()["token"]


@pytest.fixture(scope="module")
def admin(api, admin_token):
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json", "Authorization": f"Bearer {admin_token}"})
    return s


@pytest.fixture(scope="module")
def service_id(api):
    r = api.get(f"{BASE_URL}/api/services")
    assert r.status_code == 200
    services = r.json()
    # pick a short-duration service to fit many slots
    services.sort(key=lambda s: s["duration_min"])
    return services[0]["id"]


def _find_future_slot(api, service_id, days_ahead=1, exclude=None):
    exclude = exclude or set()
    for delta in range(days_ahead, days_ahead + 30):
        d = (datetime.now() + timedelta(days=delta)).strftime("%Y-%m-%d")
        r = api.get(f"{BASE_URL}/api/availability?service_id={service_id}&date={d}")
        if r.status_code != 200:
            continue
        slots = r.json()["slots"]
        for slot in slots:
            if (d, slot) not in exclude:
                return d, slot
    return None, None


created_ids = []


@pytest.fixture(scope="module", autouse=True)
def cleanup(admin):
    yield
    # Cancel all appointments we created
    for aid in created_ids:
        try:
            admin.post(f"{BASE_URL}/api/appointments/{aid}/admin-cancel")
        except Exception:
            pass


def _book(api, service_id, phone, client_name="Guest Test", booker_name="", used=None):
    used = used or set()
    d, slot = _find_future_slot(api, service_id, exclude=used)
    assert d and slot, "no slots available"
    payload = {
        "service_id": service_id,
        "date": d,
        "start": slot,
        "client_name": client_name,
        "client_nickname": "",
        "client_phone": phone,
        "booker_name": booker_name,
        "accepted_policy": True,
    }
    r = api.post(f"{BASE_URL}/api/appointments", json=payload)
    used.add((d, slot))
    return r, used


# ---- Backend: booker_name feature ----

def test_booking_without_booker_name(api, service_id):
    r, _ = _book(api, service_id, PHONE_A, client_name="Solo Client")
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["booker_name"] == ""
    assert data["client_name"] == "Solo Client"
    assert data["status"] == "confirmed"
    created_ids.append(data["id"])


def test_booking_with_booker_name(api, admin, service_id):
    used = set()
    r, used = _book(api, service_id, PHONE_B, client_name="Little Kid", booker_name="Dad Booker", used=used)
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["client_name"] == "Little Kid"
    assert data["booker_name"] == "Dad Booker"
    created_ids.append(data["id"])

    # Client upsert must use booker_name identity
    clients = admin.get(f"{BASE_URL}/api/clients").json()
    match = [c for c in clients if c["phone"] == PHONE_B]
    assert match, "client not created"
    assert match[0]["name"] == "Dad Booker", f"client name should be booker; got {match[0]}"


# ---- Backend: 2-active-limit ----

def test_two_limit_blocks_third(api, service_id):
    used = set()
    r1, used = _book(api, service_id, PHONE_C, client_name="C1", used=used)
    assert r1.status_code == 200, r1.text
    created_ids.append(r1.json()["id"])

    r2, used = _book(api, service_id, PHONE_C, client_name="C2", used=used)
    assert r2.status_code == 200, r2.text
    created_ids.append(r2.json()["id"])

    # third should fail 409
    r3, used = _book(api, service_id, PHONE_C, client_name="C3", used=used)
    assert r3.status_code == 409, f"expected 409 got {r3.status_code}: {r3.text}"
    body = r3.json()
    detail = body.get("detail", "")
    assert "2 citas" in detail or "2" in detail, f"unexpected error message: {detail}"


def test_cancelled_do_not_count(api, admin, service_id):
    used = set()
    r1, used = _book(api, service_id, PHONE_D, client_name="D1", used=used)
    assert r1.status_code == 200
    a1 = r1.json()["id"]
    created_ids.append(a1)

    r2, used = _book(api, service_id, PHONE_D, client_name="D2", used=used)
    assert r2.status_code == 200
    created_ids.append(r2.json()["id"])

    # Third should be blocked
    r3, used = _book(api, service_id, PHONE_D, client_name="D3", used=used)
    assert r3.status_code == 409

    # Cancel one via admin
    cancel = admin.post(f"{BASE_URL}/api/appointments/{a1}/admin-cancel")
    assert cancel.status_code == 200

    # Now third booking should succeed
    r4, used = _book(api, service_id, PHONE_D, client_name="D4", used=used)
    assert r4.status_code == 200, f"expected success after cancel, got {r4.status_code}: {r4.text}"
    created_ids.append(r4.json()["id"])
