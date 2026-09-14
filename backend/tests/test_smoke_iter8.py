"""Iteration 8 smoke tests: verify backend still works after trimming requirements.txt.
Tests: business, services, auth, availability, appointments create+slot removal, requirements validation.
"""
import os
import re
import pytest
import requests
from datetime import datetime, timedelta

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")
if not BASE_URL:
    with open("/app/frontend/.env") as f:
        for line in f:
            if line.startswith("REACT_APP_BACKEND_URL="):
                BASE_URL = line.split("=", 1)[1].strip().rstrip("/")

ADMIN_EMAIL = "pititagomez31@gmail.com"
ADMIN_PASSWORD = "58Barber2025!"

EXPECTED_SERVICES = {
    ("Solo Corte", 35),
    ("Corte y Barba", 50),
    ("Corte Barba y Cejas", 60),
    ("Corte y Cejas", 40),
    ("Solo Arreglo de Barba", 15),
    ("Perfilado de Cejas", 10),
}


@pytest.fixture(scope="module")
def api():
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    return s


# ---- requirements.txt validation ----

def test_requirements_txt_trimmed():
    with open("/app/backend/requirements.txt") as f:
        content = f.read().lower()
    forbidden = ["emergentintegrations", "boto3", "pandas", "numpy", "python-jose", "jq", "typer"]
    for pkg in forbidden:
        assert pkg not in content, f"forbidden package '{pkg}' still present in requirements.txt"
    required = ["fastapi", "uvicorn", "motor", "pymongo", "pydantic", "python-dotenv", "pyjwt", "bcrypt", "email-validator"]
    for pkg in required:
        assert pkg in content, f"required package '{pkg}' missing from requirements.txt"


# ---- Business ----

def test_business_endpoint(api):
    r = api.get(f"{BASE_URL}/api/business")
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["name"] == "+58 BarberStudio"
    assert "phone" in data and data["phone"]
    assert "whatsapp" in data and data["whatsapp"]
    assert data["address"] == "Av. Los Majuelos 51 (dentro de Multitienda Veloz), Tenerife"
    assert data["barber_name"] == "Heber"


# ---- Services ----

def test_services_count_and_content(api):
    r = api.get(f"{BASE_URL}/api/services")
    assert r.status_code == 200, r.text
    services = r.json()
    assert len(services) == 6, f"expected 6 services, got {len(services)}"
    got = {(s["name"], s["duration_min"]) for s in services}
    assert got == EXPECTED_SERVICES, f"service mismatch. got={got}"


# ---- Auth ----

@pytest.fixture(scope="module")
def admin_token(api):
    r = api.post(f"{BASE_URL}/api/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD})
    assert r.status_code == 200, f"admin login failed: {r.text}"
    tok = r.json().get("token")
    assert tok and isinstance(tok, str) and len(tok) > 20
    return tok


def test_auth_login(admin_token):
    assert admin_token


def test_auth_me(api, admin_token):
    r = api.get(f"{BASE_URL}/api/auth/me", headers={"Authorization": f"Bearer {admin_token}"})
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["email"].lower() == ADMIN_EMAIL.lower()
    assert data.get("role") == "admin" or data.get("is_admin") is True or "admin" in str(data).lower()


# ---- Availability ----

@pytest.fixture(scope="module")
def service_id(api):
    r = api.get(f"{BASE_URL}/api/services")
    services = r.json()
    services.sort(key=lambda s: s["duration_min"])
    return services[0]["id"]


def test_availability_returns_slots(api, service_id):
    for delta in range(1, 15):
        d = (datetime.now() + timedelta(days=delta)).strftime("%Y-%m-%d")
        r = api.get(f"{BASE_URL}/api/availability?service_id={service_id}&date={d}")
        assert r.status_code == 200, r.text
        data = r.json()
        assert "slots" in data and isinstance(data["slots"], list)
        if data["slots"]:
            return
    pytest.skip("no availability found in next 14 days")


# ---- End-to-end appointment ----

created_ids = []


@pytest.fixture(scope="module", autouse=True)
def cleanup(api, admin_token):
    yield
    admin = requests.Session()
    admin.headers.update({"Content-Type": "application/json", "Authorization": f"Bearer {admin_token}"})
    for aid in created_ids:
        try:
            admin.post(f"{BASE_URL}/api/appointments/{aid}/admin-cancel")
        except Exception:
            pass


def test_appointment_create_and_slot_removed(api, service_id):
    # find a slot
    date_found, slot_found = None, None
    for delta in range(1, 15):
        d = (datetime.now() + timedelta(days=delta)).strftime("%Y-%m-%d")
        r = api.get(f"{BASE_URL}/api/availability?service_id={service_id}&date={d}")
        if r.status_code == 200 and r.json()["slots"]:
            date_found = d
            slot_found = r.json()["slots"][0]
            break
    assert date_found and slot_found, "no slots available"

    payload = {
        "service_id": service_id,
        "date": date_found,
        "start": slot_found,
        "client_name": "SmokeTest User",
        "client_nickname": "",
        "client_phone": "+34600555801",
        "booker_name": "",
        "accepted_policy": True,
    }
    r = api.post(f"{BASE_URL}/api/appointments", json=payload)
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["status"] == "confirmed"
    assert data["date"] == date_found
    assert data["start"] == slot_found
    created_ids.append(data["id"])

    # verify slot removed
    r2 = api.get(f"{BASE_URL}/api/availability?service_id={service_id}&date={date_found}")
    assert r2.status_code == 200
    assert slot_found not in r2.json()["slots"], "slot still available after booking"
