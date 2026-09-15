"""Tests for lunch break feature."""
import os
import requests
import pytest

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://barber-date-hours.preview.emergentagent.com").rstrip("/")
API = f"{BASE_URL}/api"

ADMIN_USER = "+58BarberStudio"
ADMIN_PASS = "Y1129086F"

# Future dates (2026): Thursday 2026-02-05, Saturday 2026-02-07
THU = "2026-02-05"
SAT = "2026-02-07"


@pytest.fixture(scope="module")
def token():
    r = requests.post(f"{API}/auth/login", json={"username": ADMIN_USER, "password": ADMIN_PASS})
    assert r.status_code == 200, r.text
    return r.json().get("token") or r.json().get("access_token")


@pytest.fixture(scope="module")
def headers(token):
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture(scope="module")
def service_id():
    r = requests.get(f"{API}/services")
    assert r.status_code == 200
    services = r.json()
    # pick a service of ~30-50 min so 13:00 slot is meaningful
    return services[0]["id"]


def _set_lunch(headers, enabled, start="13:00", end="14:00"):
    r = requests.put(f"{API}/lunch-break", json={"enabled": enabled, "start": start, "end": end}, headers=headers)
    assert r.status_code == 200, r.text
    return r.json()


def test_working_hours_includes_lunch():
    r = requests.get(f"{API}/working-hours")
    assert r.status_code == 200
    data = r.json()
    assert "days" in data
    assert "lunch" in data
    assert set(data["lunch"].keys()) >= {"enabled", "start", "end"}


def test_lunch_break_requires_admin():
    r = requests.put(f"{API}/lunch-break", json={"enabled": False, "start": "13:00", "end": "14:00"})
    assert r.status_code in (401, 403)


def test_lunch_blocks_slots_when_enabled(headers, service_id):
    _set_lunch(headers, True, "13:00", "14:00")
    r = requests.get(f"{API}/availability", params={"service_id": service_id, "date": THU})
    assert r.status_code == 200
    slots = r.json().get("slots", [])
    assert "13:00" not in slots
    assert "13:30" not in slots
    # 14:00 should be available (assuming shop open until then)
    # depending on schedule but base config has afternoon session; verify
    assert "14:00" in slots or "14:15" in slots


def test_lunch_disabled_shows_slots(headers, service_id):
    _set_lunch(headers, False, "13:00", "14:00")
    r = requests.get(f"{API}/availability", params={"service_id": service_id, "date": THU})
    assert r.status_code == 200
    slots = r.json().get("slots", [])
    # With lunch off, at least one of 13:00/13:30 should show
    assert ("13:00" in slots) or ("13:30" in slots)


def test_lunch_reenabled_blocks_again(headers, service_id):
    _set_lunch(headers, True, "13:00", "14:00")
    r = requests.get(f"{API}/availability", params={"service_id": service_id, "date": THU})
    slots = r.json().get("slots", [])
    assert "13:00" not in slots
    assert "13:30" not in slots


def test_lunch_applies_all_days(headers, service_id):
    _set_lunch(headers, True, "13:00", "14:00")
    for d in [THU, SAT]:
        r = requests.get(f"{API}/availability", params={"service_id": service_id, "date": d})
        assert r.status_code == 200
        slots = r.json().get("slots", [])
        # Saturday may be closed; if slots empty accept it
        if slots:
            assert "13:00" not in slots
            assert "13:30" not in slots


def test_lunch_with_schedule_override(headers, service_id):
    # Create an override for a future date with open hours covering 13:00
    override_date = "2026-03-12"  # Thursday
    payload = {"date": override_date, "closed": False, "sessions": [{"start": "10:00", "end": "18:00"}]}
    r = requests.post(f"{API}/schedule-overrides", json=payload, headers=headers)
    assert r.status_code in (200, 201), r.text
    override_id = r.json().get("id")
    try:
        _set_lunch(headers, True, "13:00", "14:00")
        r = requests.get(f"{API}/availability", params={"service_id": service_id, "date": override_date})
        slots = r.json().get("slots", [])
        assert "13:00" not in slots
        assert "13:30" not in slots
        assert any(s.startswith("14:") or s.startswith("15:") for s in slots)
    finally:
        if override_id:
            requests.delete(f"{API}/schedule-overrides/{override_id}", headers=headers)
        # leave lunch ENABLED as requested
        _set_lunch(headers, True, "13:00", "14:00")
