"""Cancel TEST_ appointments created during iteration 13."""
import os
import re
from pathlib import Path

import requests
from dotenv import dotenv_values

BASE = (os.environ.get("REACT_APP_BACKEND_URL") or dotenv_values("/app/frontend/.env")["REACT_APP_BACKEND_URL"]).rstrip("/")
API = f"{BASE}/api"
c = Path("/app/memory/test_credentials.md").read_text(encoding="utf-8")
email = re.search(r"(?im)^\s*[-*]?\s*(?:\*\*)?email(?:\*\*)?\s*:\s*`?([^`\s]+)", c).group(1)
pwd = re.search(r"(?im)^\s*[-*]?\s*(?:\*\*)?password(?:\*\*)?\s*:\s*`?([^`\s]+)", c).group(1)

tok = requests.post(f"{API}/auth/login", json={"email": email, "password": pwd}).json()["token"]
H = {"Authorization": f"Bearer {tok}"}
appts = requests.get(f"{API}/appointments", headers=H).json()
n = 0
for a in appts:
    if a.get("client_name", "").startswith("TEST_") and a.get("status") != "cancelled":
        r = requests.post(f"{API}/appointments/{a['id']}/admin-cancel", headers=H)
        n += 1
        print("cancelled", a["id"], a["date"], a["start"], a["client_name"], r.status_code)
print(f"total cancelled: {n}")
