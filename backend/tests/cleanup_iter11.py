"""One-off cleanup of TEST_/TEST appointments created during iteration 11 UI testing."""
import os

import requests
from dotenv import dotenv_values

base = (os.environ.get("REACT_APP_BACKEND_URL") or dotenv_values("/app/frontend/.env")["REACT_APP_BACKEND_URL"]).rstrip("/")
s = requests.Session()
r = s.post(f"{base}/api/auth/login", json={"email": "pititagomez31@gmail.com", "password": "58Barber2025!"})
tok = r.json().get("token")
h = {"Authorization": f"Bearer {tok}"}
appts = s.get(f"{base}/api/appointments", params={"from_date": "2026-01-01"}, headers=h).json()
cleaned = 0
for a in appts:
    if a.get("client_name", "").upper().startswith("TEST") and a.get("status") != "cancelled":
        res = s.post(f"{base}/api/appointments/{a['id']}/admin-cancel", headers=h)
        cleaned += 1 if res.status_code == 200 else 0
print("cancelled test appointments:", cleaned, "of", len(appts))
