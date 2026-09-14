"""Iter15 tests: username login, multi-booking, 365d calendar, MAX_ACTIVE 6, cron."""
import os
import requests
import pytest
from datetime import date, timedelta

BASE = os.environ.get("REACT_APP_BACKEND_URL", "https://barber-v2-preview.preview.emergentagent.com").rstrip("/")
API = f"{BASE}/api"
CRON = "9f3c7a2e5b8d4f1a6c0e3b7d9a2f5c8e1b4d6a0f3c7e9b2d5a8c1e4f6b0d3a7c"

ADMIN_USER = "+58BarberStudio"
ADMIN_PASS = "Y1129086F"


@pytest.fixture(scope="module")
def token():
    r = requests.post(f"{API}/auth/login", json={"username": ADMIN_USER, "password": ADMIN_PASS})
    assert r.status_code == 200, r.text
    return r.json()["token"]


@pytest.fixture(scope="module")
def services():
    r = requests.get(f"{API}/services")
    assert r.status_code == 200
    return r.json()


# ---------- Login ----------
def test_login_with_username_ok():
    r = requests.post(f"{API}/auth/login", json={"username": ADMIN_USER, "password": ADMIN_PASS})
    assert r.status_code == 200
    assert "token" in r.json()


def test_login_old_email_rejected():
    r = requests.post(f"{API}/auth/login", json={"email": "pititagomez31@gmail.com", "password": ADMIN_PASS})
    assert r.status_code >= 400


def test_login_old_password_rejected():
    r = requests.post(f"{API}/auth/login", json={"username": ADMIN_USER, "password": "58Barber2025!"})
    assert r.status_code == 401


# ---------- 365-day availability ----------
def test_availability_within_1year(services):
    s = services[0]
    # try a date 300 days from now
    d = (date.today() + timedelta(days=300)).isoformat()
    r = requests.get(f"{API}/availability", params={"service_id": s["id"], "date": d})
    assert r.status_code == 200
    body = r.json()
    assert "slots" in body


# ---------- Cron endpoint ----------
def test_cron_requires_auth():
    r = requests.post(f"{API}/cron/recordatorios")
    assert r.status_code == 401


def test_cron_with_bearer():
    r = requests.post(f"{API}/cron/recordatorios", headers={"Authorization": f"Bearer {CRON}"})
    assert r.status_code == 200


# ---------- Multi-booking + MAX 6 active per phone ----------
def _find_slot(service_id, days_ahead_start=7):
    for d_off in range(days_ahead_start, 60):
        d = (date.today() + timedelta(days=d_off)).isoformat()
        r = requests.get(f"{API}/availability", params={"service_id": service_id, "date": d})
        if r.status_code == 200:
            slots = r.json().get("slots", [])
            if slots:
                return d, slots
    return None, []


@pytest.fixture(scope="module")
def test_phone():
    # unique phone per test run
    import time
    return f"+34699{int(time.time()) % 1000000:06d}"


def test_max_active_appts_6(token, services, test_phone):
    s = services[0]
    created_ids = []
    used_slots = set()
    day_off = 7
    while len(created_ids) < 6 and day_off < 90:
        d = (date.today() + timedelta(days=day_off)).isoformat()
        r = requests.get(f"{API}/availability", params={"service_id": s["id"], "date": d})
        slots = r.json().get("slots", []) if r.status_code == 200 else []
        for slot in slots:
            if len(created_ids) >= 6:
                break
            key = (d, slot)
            if key in used_slots:
                continue
            used_slots.add(key)
            payload = {
                "service_id": s["id"], "date": d, "start": slot,
                "client_name": "TEST_MAX", "client_phone": test_phone,
                "client_email": "", "client_nickname": "", "booker_name": "",
                "accepted_policy": True,
            }
            rr = requests.post(f"{API}/appointments", json=payload)
            if rr.status_code == 200 or rr.status_code == 201:
                created_ids.append(rr.json()["id"])
            elif rr.status_code == 409:
                # slot conflict, try next
                pass
            else:
                print("unexpected", rr.status_code, rr.text)
        day_off += 1

    assert len(created_ids) == 6, f"Only created {len(created_ids)} appts"

    # 7th must fail with 409
    d = (date.today() + timedelta(days=day_off + 1)).isoformat()
    r = requests.get(f"{API}/availability", params={"service_id": s["id"], "date": d})
    slots = r.json().get("slots", [])
    if slots:
        payload = {
            "service_id": s["id"], "date": d, "start": slots[0],
            "client_name": "TEST_MAX", "client_phone": test_phone,
            "client_email": "", "client_nickname": "", "booker_name": "",
            "accepted_policy": True,
        }
        rr = requests.post(f"{API}/appointments", json=payload)
        assert rr.status_code == 409, f"Expected 409 on 7th, got {rr.status_code} {rr.text}"

    # cleanup
    headers = {"Authorization": f"Bearer {token}"}
    for aid in created_ids:
        requests.post(f"{API}/appointments/{aid}/admin-cancel", headers=headers)


# ---------- Anti double-book ----------
def test_availability_excludes_booked_slot(token, services):
    s = services[0]
    d, slots = _find_slot(s["id"], 5)
    if not slots:
        pytest.skip("no slots")
    slot = slots[0]
    import time
    phone = f"+34699{int(time.time()*1000) % 1000000:06d}"
    payload = {
        "service_id": s["id"], "date": d, "start": slot,
        "client_name": "TEST_DBL", "client_phone": phone,
        "client_email": "", "client_nickname": "", "booker_name": "",
        "accepted_policy": True,
    }
    r = requests.post(f"{API}/appointments", json=payload)
    assert r.status_code in (200, 201)
    aid = r.json()["id"]
    # re-fetch availability
    r2 = requests.get(f"{API}/availability", params={"service_id": s["id"], "date": d})
    assert slot not in r2.json().get("slots", [])
    # cleanup
    requests.post(f"{API}/appointments/{aid}/admin-cancel", headers={"Authorization": f"Bearer {token}"})
