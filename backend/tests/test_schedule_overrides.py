"""Schedule overrides + availability E2E backend tests."""
import os
import pytest
import requests

BASE = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")
API = f"{BASE}/api"

ADMIN_USER = "+58BarberStudio"
ADMIN_PASS = "Y1129086F"

FUT_WED = "2026-09-16"  # Wednesday
FUT_THU = "2026-09-17"  # Thursday
FUT_CLOSED = "2026-09-18"  # Friday, will close it


@pytest.fixture(scope="module")
def token():
    r = requests.post(f"{API}/auth/login", json={"username": ADMIN_USER, "password": ADMIN_PASS})
    assert r.status_code == 200, r.text
    return r.json()["token"]


@pytest.fixture(scope="module")
def h(token):
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture(scope="module")
def service_id():
    r = requests.get(f"{API}/services")
    assert r.status_code == 200
    svcs = r.json()
    assert len(svcs) > 0, "no services"
    return svcs[0]["id"]


def _cleanup(h, date):
    requests.delete(f"{API}/schedule-overrides/{date}", headers=h)


def test_login_ok(token):
    assert isinstance(token, str) and len(token) > 10


def test_day_schedule_public_base(h):
    _cleanup(h, FUT_WED)
    r = requests.get(f"{API}/day-schedule/{FUT_WED}")
    assert r.status_code == 200
    d = r.json()
    assert d["source"] == "base"
    # base is 10:00 per DEFAULT_WORKING_HOURS
    assert d["start"] == "10:00"


def test_create_override_and_availability(h, service_id):
    _cleanup(h, FUT_WED)
    # base availability first slot
    r = requests.get(f"{API}/availability", params={"service_id": service_id, "date": FUT_WED})
    assert r.status_code == 200
    base_slots = r.json()["slots"]
    assert base_slots and base_slots[0] == "10:00"

    # create override 08:00
    body = {"date": FUT_WED, "enabled": True, "start": "08:00", "end": "20:00", "reason": "test"}
    r = requests.post(f"{API}/schedule-overrides", json=body, headers=h)
    assert r.status_code == 200, r.text

    # day-schedule reflects override
    r = requests.get(f"{API}/day-schedule/{FUT_WED}")
    assert r.json()["source"] == "override"
    assert r.json()["start"] == "08:00"

    # availability first slot is 08:00
    r = requests.get(f"{API}/availability", params={"service_id": service_id, "date": FUT_WED})
    slots = r.json()["slots"]
    assert slots[0] == "08:00", f"expected 08:00 got {slots[:3]}"


def test_thursday_no_override_stays_base(h, service_id):
    _cleanup(h, FUT_THU)
    r = requests.get(f"{API}/availability", params={"service_id": service_id, "date": FUT_THU})
    slots = r.json()["slots"]
    assert slots and slots[0] == "10:00"


def test_delete_override_returns_to_base(h, service_id):
    # ensure override present
    body = {"date": FUT_WED, "enabled": True, "start": "08:00", "end": "20:00", "reason": ""}
    requests.post(f"{API}/schedule-overrides", json=body, headers=h)
    r = requests.delete(f"{API}/schedule-overrides/{FUT_WED}", headers=h)
    assert r.status_code == 200
    r = requests.get(f"{API}/availability", params={"service_id": service_id, "date": FUT_WED})
    slots = r.json()["slots"]
    assert slots[0] == "10:00"


def test_closed_day_override_empty_slots(h, service_id):
    body = {"date": FUT_CLOSED, "enabled": False, "start": "10:00", "end": "20:00", "reason": "cerrado"}
    r = requests.post(f"{API}/schedule-overrides", json=body, headers=h)
    assert r.status_code == 200
    r = requests.get(f"{API}/availability", params={"service_id": service_id, "date": FUT_CLOSED})
    assert r.json()["slots"] == []
    _cleanup(h, FUT_CLOSED)


def test_list_overrides_requires_auth():
    r = requests.get(f"{API}/schedule-overrides")
    assert r.status_code in (401, 403)


def test_list_overrides_range(h):
    body = {"date": FUT_WED, "enabled": True, "start": "08:00", "end": "20:00", "reason": ""}
    requests.post(f"{API}/schedule-overrides", json=body, headers=h)
    r = requests.get(f"{API}/schedule-overrides", params={"from_date": "2026-09-01", "to_date": "2026-09-30"}, headers=h)
    assert r.status_code == 200
    dates = [d["date"] for d in r.json()]
    assert FUT_WED in dates
    _cleanup(h, FUT_WED)
