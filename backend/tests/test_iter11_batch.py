"""Iteration 11 - verify new address, admin login, services/working-hours regression, booking e2e."""
import os
import random
from datetime import date, timedelta

import pytest
import requests
from dotenv import dotenv_values

frontend_env = dotenv_values("/app/frontend/.env")
base_url = os.environ.get("REACT_APP_BACKEND_URL") or frontend_env.get("REACT_APP_BACKEND_URL")
if not base_url:
    raise RuntimeError("REACT_APP_BACKEND_URL missing")
BASE_URL = base_url.rstrip("/")

EXPECTED_ADDRESS = "Avenida de Los Majuelos 51C, 38008, Taco, Santa Cruz de Tenerife"
ADMIN_EMAIL = "pititagomez31@gmail.com"
ADMIN_PASSWORD = "58Barber2025!"


@pytest.fixture(scope="session")
def client():
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    return s


@pytest.fixture(scope="session")
def token(client):
    r = client.post(f"{BASE_URL}/api/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD})
    if r.status_code != 200:
        pytest.fail(f"admin login failed {r.status_code}: {r.text[:300]}")
    data = r.json()
    tok = data.get("token") or data.get("access_token")
    assert tok, f"no token in response: {data}"
    return tok


# --- business ---
class TestBusiness:
    def test_business_address(self, client):
        r = client.get(f"{BASE_URL}/api/business")
        assert r.status_code == 200
        d = r.json()
        assert d.get("address") == EXPECTED_ADDRESS, d
        assert "_id" not in d


# --- auth ---
class TestAuth:
    def test_login_ok(self, token):
        assert isinstance(token, str) and len(token) > 20

    def test_login_bad_password(self, client):
        r = client.post(f"{BASE_URL}/api/auth/login", json={"email": ADMIN_EMAIL, "password": "wrong"})
        assert r.status_code in (400, 401), r.text

    def test_me_with_token(self, client, token):
        r = client.get(f"{BASE_URL}/api/auth/me", headers={"Authorization": f"Bearer {token}"})
        assert r.status_code == 200, r.text
        assert r.json().get("email") == ADMIN_EMAIL

    def test_me_without_token(self, client):
        r = client.get(f"{BASE_URL}/api/auth/me")
        assert r.status_code in (401, 403), r.text

    def test_protected_endpoints_require_auth(self, client):
        for path in ("/api/appointments", "/api/clients", "/api/blockers"):
            r = client.get(f"{BASE_URL}{path}")
            assert r.status_code in (401, 403), f"{path} -> {r.status_code}"


# --- services / working hours regression ---
class TestCatalog:
    def test_services(self, client):
        r = client.get(f"{BASE_URL}/api/services")
        assert r.status_code == 200
        data = r.json()
        assert isinstance(data, list) and len(data) > 0
        for s in data:
            assert "id" in s and "name" in s and "duration_min" in s
            assert "_id" not in s

    def test_working_hours(self, client):
        r = client.get(f"{BASE_URL}/api/working-hours")
        assert r.status_code == 200
        days = r.json().get("days")
        assert isinstance(days, dict) and len(days) == 7
        for k, v in days.items():
            assert "enabled" in v and "start" in v and "end" in v

    def test_admin_lists(self, client, token):
        h = {"Authorization": f"Bearer {token}"}
        for path in ("/api/clients", "/api/blockers"):
            r = client.get(f"{BASE_URL}{path}", headers=h)
            assert r.status_code == 200, f"{path}: {r.text[:200]}"
            assert isinstance(r.json(), list)


def _find_slot(client, service):
    r0 = client.get(f"{BASE_URL}/api/working-hours")
    days = r0.json().get("days", {})
    for offset in range(1, 30):
        d = date.today() + timedelta(days=offset)
        cfg = days.get(str(d.weekday()))
        if not cfg or not cfg.get("enabled"):
            continue
        r = client.get(f"{BASE_URL}/api/availability", params={"date": d.isoformat(), "service_id": service["id"]})
        assert r.status_code == 200, r.text
        slots = r.json().get("slots") or []
        if slots:
            return d.isoformat(), slots[0]
    return None, None


# --- booking e2e regression ---
class TestBooking:
    created = []

    def test_availability_invalid_service(self, client):
        r = client.get(f"{BASE_URL}/api/availability", params={"date": "2026-12-01", "service_id": "nope"})
        assert r.status_code == 404

    def test_create_appointment_e2e(self, client, token):
        service = client.get(f"{BASE_URL}/api/services").json()[0]
        target, slot = _find_slot(client, service)
        assert slot, "no available slot found in next 30 days"

        phone = "6" + "".join(random.choice("0123456789") for _ in range(8))
        payload = {
            "service_id": service["id"],
            "date": target,
            "start": slot,
            "client_name": "TEST_QA Iter11",
            "client_phone": phone,
            "accepted_policy": True,
        }
        r = client.post(f"{BASE_URL}/api/appointments", json=payload)
        assert r.status_code in (200, 201), r.text
        appt = r.json()
        assert appt.get("id")
        assert appt["client_phone"] == phone
        assert appt["date"] == target and appt["start"] == slot
        assert appt["status"] == "confirmed"
        assert "_id" not in appt
        TestBooking.created.append(appt["id"])

        # GET persistence
        g = client.get(f"{BASE_URL}/api/appointments/{appt['id']}")
        assert g.status_code == 200
        assert g.json()["client_name"] == "TEST_QA Iter11"

        # anti double-booking (same slot, different phone)
        other = "6" + "".join(random.choice("0123456789") for _ in range(8))
        r2 = client.post(f"{BASE_URL}/api/appointments", json={**payload, "client_phone": other})
        assert r2.status_code == 409, f"double booking allowed: {r2.status_code} {r2.text[:200]}"

        # policy not accepted
        r3 = client.post(f"{BASE_URL}/api/appointments", json={**payload, "accepted_policy": False, "client_phone": other})
        assert r3.status_code == 400

        # admin listing contains it
        r4 = client.get(f"{BASE_URL}/api/appointments", params={"from_date": target, "to_date": target},
                        headers={"Authorization": f"Bearer {token}"})
        assert r4.status_code == 200, r4.text
        assert appt["id"] in [a["id"] for a in r4.json()]

    def test_max_two_active_per_phone(self, client):
        service = client.get(f"{BASE_URL}/api/services").json()[0]
        phone = "6" + "".join(random.choice("0123456789") for _ in range(8))
        booked = 0
        last_status = None
        for _ in range(3):
            target, slot = _find_slot(client, service)
            if not slot:
                pytest.skip("no slots available")
            r = client.post(f"{BASE_URL}/api/appointments", json={
                "service_id": service["id"], "date": target, "start": slot,
                "client_name": "TEST_QA Limit", "client_phone": phone, "accepted_policy": True,
            })
            last_status = r.status_code
            if r.status_code in (200, 201):
                booked += 1
                TestBooking.created.append(r.json()["id"])
            else:
                break
        assert booked == 2, f"expected 2 bookings before limit, got {booked} (last status {last_status})"
        assert last_status == 409

    @classmethod
    def teardown_class(cls):
        s = requests.Session()
        r = s.post(f"{BASE_URL}/api/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD})
        if r.status_code != 200:
            return
        tok = r.json().get("token") or r.json().get("access_token")
        for aid in cls.created:
            s.post(f"{BASE_URL}/api/appointments/{aid}/admin-cancel", headers={"Authorization": f"Bearer {tok}"})
