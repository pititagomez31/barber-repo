"""Backend API tests for +58 BarberStudio (schedule overrides feature)."""
import os
import pytest
import requests
from datetime import datetime

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL')
if not BASE_URL:
    # fallback: read from frontend/.env
    with open('/app/frontend/.env') as f:
        for line in f:
            if line.startswith('REACT_APP_BACKEND_URL='):
                BASE_URL = line.split('=', 1)[1].strip()
                break
BASE_URL = BASE_URL.rstrip('/')
API = f"{BASE_URL}/api"

TEST_DATE_WED = "2026-09-16"   # Wednesday (weekday 2) - base 10:00-20:00
TEST_DATE_THU = "2026-09-17"   # Thursday - base 10:00-20:00
TEST_DATE_SUN = "2026-09-20"   # Sunday - base disabled


@pytest.fixture(scope="module")
def s():
    sess = requests.Session()
    sess.headers.update({"Content-Type": "application/json"})
    return sess


@pytest.fixture(scope="module")
def service_id(s):
    r = s.get(f"{API}/services")
    assert r.status_code == 200
    data = r.json()
    assert len(data) > 0
    # pick 30-min service
    for svc in data:
        if svc["duration_min"] == 30:
            return svc["id"]
    return data[0]["id"]


@pytest.fixture(autouse=True)
def cleanup(s):
    # cleanup overrides & TEST_ appointments before each test
    for d in [TEST_DATE_WED, TEST_DATE_THU, TEST_DATE_SUN]:
        s.delete(f"{API}/schedule-overrides/{d}")
    # remove appointments for test dates
    for d in [TEST_DATE_WED, TEST_DATE_THU, TEST_DATE_SUN]:
        r = s.get(f"{API}/appointments", params={"date": d})
        if r.status_code == 200:
            for a in r.json():
                if a.get("client_name", "").startswith("TEST_"):
                    s.delete(f"{API}/appointments/{a['id']}")
    yield
    for d in [TEST_DATE_WED, TEST_DATE_THU, TEST_DATE_SUN]:
        s.delete(f"{API}/schedule-overrides/{d}")


# ---------- Services & working hours ----------
class TestBasics:
    def test_services_list(self, s):
        r = s.get(f"{API}/services")
        assert r.status_code == 200
        data = r.json()
        assert isinstance(data, list) and len(data) >= 1
        assert "id" in data[0] and "duration_min" in data[0]

    def test_working_hours_default(self, s):
        r = s.get(f"{API}/working-hours")
        assert r.status_code == 200
        d = r.json()
        assert d["id"] == "default"
        for k in "0123456":
            assert k in d["days"]


# ---------- Availability + overrides (KEY feature) ----------
class TestAvailabilityOverride:
    def test_base_availability(self, s, service_id):
        r = s.get(f"{API}/availability", params={"service_id": service_id, "date": TEST_DATE_WED})
        assert r.status_code == 200
        d = r.json()
        assert d["schedule"]["source"] == "base"
        assert d["slots"][0] == "10:00"

    def test_override_creates_earlier_slots(self, s, service_id):
        payload = {"date": TEST_DATE_WED, "enabled": True, "start": "08:00", "end": "20:00", "reason": "TEST_early"}
        r = s.post(f"{API}/schedule-overrides", json=payload)
        assert r.status_code == 200

        r = s.get(f"{API}/availability", params={"service_id": service_id, "date": TEST_DATE_WED})
        assert r.status_code == 200
        d = r.json()
        assert d["schedule"]["source"] == "override"
        assert d["slots"][0] == "08:00"

    def test_other_date_uses_base(self, s, service_id):
        s.post(f"{API}/schedule-overrides", json={"date": TEST_DATE_WED, "enabled": True, "start": "08:00", "end": "20:00"})
        r = s.get(f"{API}/availability", params={"service_id": service_id, "date": TEST_DATE_THU})
        d = r.json()
        assert d["schedule"]["source"] == "base"
        assert d["slots"][0] == "10:00"

    def test_delete_override_reverts_to_base(self, s, service_id):
        s.post(f"{API}/schedule-overrides", json={"date": TEST_DATE_WED, "enabled": True, "start": "08:00", "end": "20:00"})
        r = s.delete(f"{API}/schedule-overrides/{TEST_DATE_WED}")
        assert r.status_code == 200
        r = s.get(f"{API}/availability", params={"service_id": service_id, "date": TEST_DATE_WED})
        d = r.json()
        assert d["schedule"]["source"] == "base"
        assert d["slots"][0] == "10:00"

    def test_disabled_override_empty_slots(self, s, service_id):
        s.post(f"{API}/schedule-overrides", json={"date": TEST_DATE_WED, "enabled": False, "start": "10:00", "end": "20:00", "reason": "TEST_closed"})
        r = s.get(f"{API}/availability", params={"service_id": service_id, "date": TEST_DATE_WED})
        d = r.json()
        assert d["schedule"]["source"] == "override"
        assert d["schedule"]["enabled"] is False
        assert d["slots"] == []

    def test_list_overrides_range(self, s):
        s.post(f"{API}/schedule-overrides", json={"date": TEST_DATE_WED, "enabled": True, "start": "08:00", "end": "20:00"})
        r = s.get(f"{API}/schedule-overrides", params={"from_date": "2026-09-01", "to_date": "2026-09-30"})
        assert r.status_code == 200
        dates = [o["date"] for o in r.json()]
        assert TEST_DATE_WED in dates

    def test_get_override_404_when_missing(self, s):
        r = s.get(f"{API}/schedule-overrides/{TEST_DATE_THU}")
        assert r.status_code == 404

    def test_day_schedule_override_and_base(self, s):
        r = s.get(f"{API}/day-schedule/{TEST_DATE_THU}")
        assert r.status_code == 200
        assert r.json()["source"] == "base"

        s.post(f"{API}/schedule-overrides", json={"date": TEST_DATE_WED, "enabled": True, "start": "08:00", "end": "20:00"})
        r = s.get(f"{API}/day-schedule/{TEST_DATE_WED}")
        assert r.json()["source"] == "override"
        assert r.json()["start"] == "08:00"


# ---------- Appointments ----------
class TestAppointments:
    def test_book_and_reject_invalid_slot(self, s, service_id):
        # book valid slot at 10:00
        payload = {"service_id": service_id, "date": TEST_DATE_THU, "time": "10:00",
                   "client_name": "TEST_Juan", "client_phone": "555-1234"}
        r = s.post(f"{API}/appointments", json=payload)
        assert r.status_code == 200
        appt = r.json()
        assert appt["time"] == "10:00"
        appt_id = appt["id"]

        # slot now gone
        r = s.get(f"{API}/availability", params={"service_id": service_id, "date": TEST_DATE_THU})
        assert "10:00" not in r.json()["slots"]

        # rejected invalid slot (e.g. before opening)
        r = s.post(f"{API}/appointments", json={**payload, "time": "05:00"})
        assert r.status_code == 409

        # list contains
        r = s.get(f"{API}/appointments", params={"date": TEST_DATE_THU})
        assert any(a["id"] == appt_id for a in r.json())

        # delete
        r = s.delete(f"{API}/appointments/{appt_id}")
        assert r.status_code == 200
        r = s.get(f"{API}/appointments", params={"date": TEST_DATE_THU})
        assert not any(a["id"] == appt_id for a in r.json())
