"""Iteration 10 smoke tests: backend endpoints unchanged after frontend ErrorBoundary/URL sanitizer fix."""
import os
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://studio-citas.preview.emergentagent.com").rstrip("/")
API = f"{BASE_URL}/api"


def test_root_api():
    r = requests.get(f"{API}/", timeout=15)
    assert r.status_code == 200


def test_business():
    r = requests.get(f"{API}/business", timeout=15)
    assert r.status_code == 200
    data = r.json()
    assert "address" in data or "name" in data


def test_services():
    r = requests.get(f"{API}/services", timeout=15)
    assert r.status_code == 200
    data = r.json()
    assert isinstance(data, list)
    assert len(data) > 0
    assert "id" in data[0]
    assert "name" in data[0]
    assert "duration_min" in data[0]


def test_login_success():
    r = requests.post(f"{API}/auth/login",
                      json={"email": "pititagomez31@gmail.com", "password": "58Barber2025!"},
                      timeout=15)
    assert r.status_code == 200, r.text
    data = r.json()
    assert "token" in data
    assert "user" in data
    assert data["user"]["email"] == "pititagomez31@gmail.com"


def test_login_bad():
    r = requests.post(f"{API}/auth/login",
                      json={"email": "pititagomez31@gmail.com", "password": "wrongpass"},
                      timeout=15)
    assert r.status_code in (400, 401, 403)
