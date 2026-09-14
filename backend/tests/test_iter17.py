"""iter17: DELETE /api/clients/{cid} + Home regression"""
import os
import requests
import pytest

BASE = os.environ.get("REACT_APP_BACKEND_URL", "https://barber-v2-preview.preview.emergentagent.com").rstrip("/")
ADMIN_U = "+58BarberStudio"
ADMIN_P = "Y1129086F"


@pytest.fixture(scope="module")
def token():
    r = requests.post(f"{BASE}/api/auth/login", json={"username": ADMIN_U, "password": ADMIN_P}, timeout=15)
    assert r.status_code == 200, r.text
    return r.json()["token"]


@pytest.fixture(scope="module")
def headers(token):
    return {"Authorization": f"Bearer {token}"}


def test_delete_client_unauthenticated():
    r = requests.delete(f"{BASE}/api/clients/nonexistent-id", timeout=10)
    assert r.status_code in (401, 403), f"expected 401/403 got {r.status_code}"


def test_delete_client_not_found(headers):
    r = requests.delete(f"{BASE}/api/clients/does-not-exist-xyz", headers=headers, timeout=10)
    assert r.status_code == 404


def test_delete_client_full_flow(headers):
    # Get services
    svc = requests.get(f"{BASE}/api/services", timeout=10).json()
    assert len(svc) > 0
    service_id = svc[0]["id"]

    # Create appointment (which creates the client)
    phone = "+34699105777"
    payload = {
        "client_name": "TEST_iter17_delete",
        "client_phone": phone,
        "service_id": service_id,
        "date": "2026-09-08",
        "start": "10:00",
        "accepted_policy": True,
    }
    r = requests.post(f"{BASE}/api/appointments", json=payload, timeout=15)
    assert r.status_code == 200, r.text
    appt = r.json()
    appt_id = appt["id"]

    # List clients
    r = requests.get(f"{BASE}/api/clients", headers=headers, timeout=10)
    assert r.status_code == 200
    clients = r.json()
    match = [c for c in clients if c["phone"] == phone]
    assert match, f"client not found among {len(clients)} clients"
    cid = match[0]["id"]

    # Delete client
    r = requests.delete(f"{BASE}/api/clients/{cid}", headers=headers, timeout=10)
    assert r.status_code == 200
    assert r.json().get("ok") is True

    # Verify gone
    r = requests.get(f"{BASE}/api/clients", headers=headers, timeout=10)
    remaining = [c for c in r.json() if c["id"] == cid]
    assert not remaining

    # Cleanup appointment
    requests.post(f"{BASE}/api/appointments/{appt_id}/admin-cancel", headers=headers, timeout=10)


def test_business_and_services():
    r = requests.get(f"{BASE}/api/business", timeout=10)
    assert r.status_code == 200
    b = r.json()
    assert "name" in b
    r = requests.get(f"{BASE}/api/services", timeout=10)
    assert r.status_code == 200
    assert isinstance(r.json(), list)
