from dotenv import load_dotenv
from pathlib import Path

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

import os
import re
import uuid
import hmac
import logging
import ipaddress
import bcrypt
import jwt
import httpx
from datetime import datetime, timezone, timedelta
from zoneinfo import ZoneInfo
from html import escape
from html.parser import HTMLParser
from urllib.parse import urlparse
from typing import List, Optional
from fastapi import FastAPI, APIRouter, HTTPException, Depends, Request, status, BackgroundTasks

from whatsapp_utils import generar_enlace_whatsapp
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
from pydantic import BaseModel, Field, ConfigDict


# --- Config ---
JWT_SECRET = os.environ["JWT_SECRET"]
JWT_ALG = "HS256"
ADMIN_EMAIL = os.environ["ADMIN_EMAIL"]
ADMIN_PASSWORD = os.environ["ADMIN_PASSWORD"]

mongo_url = os.environ['MONGO_URL']
client = AsyncIOMotorClient(mongo_url)
db = client[os.environ['DB_NAME']]

app = FastAPI(title="+58 BarberStudio API")
api = APIRouter(prefix="/api")

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger("58barber")


# --- Helpers ---
def hash_pw(pw: str) -> str:
    return bcrypt.hashpw(pw.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")

def verify_pw(pw: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(pw.encode("utf-8"), hashed.encode("utf-8"))
    except Exception:
        return False

def create_token(user_id: str, email: str) -> str:
    payload = {
        "sub": user_id, "email": email,
        "exp": datetime.now(timezone.utc) + timedelta(days=7),
        "type": "access",
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALG)

bearer = HTTPBearer(auto_error=False)

async def get_current_admin(creds: Optional[HTTPAuthorizationCredentials] = Depends(bearer)) -> dict:
    if not creds:
        raise HTTPException(401, "No autenticado")
    try:
        payload = jwt.decode(creds.credentials, JWT_SECRET, algorithms=[JWT_ALG])
        user = await db.users.find_one({"id": payload["sub"]})
        if not user:
            raise HTTPException(401, "Usuario no encontrado")
        return {"id": user["id"], "email": user["email"], "role": user.get("role", "admin")}
    except jwt.ExpiredSignatureError:
        raise HTTPException(401, "Sesión expirada")
    except jwt.InvalidTokenError:
        raise HTTPException(401, "Token inválido")


def new_id() -> str:
    return str(uuid.uuid4())

def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


# --- Models ---
class LoginIn(BaseModel):
    email: str
    password: str

class ServiceIn(BaseModel):
    name: str
    description: str = ""
    price_eur: float
    duration_min: int
    active: bool = True

class ServiceOut(ServiceIn):
    id: str

class WorkingHoursIn(BaseModel):
    # 0=Mon ... 6=Sun; each day: {enabled, start "HH:MM", end "HH:MM"}
    days: dict

class BlockerIn(BaseModel):
    date: str          # "YYYY-MM-DD"
    start: Optional[str] = None  # "HH:MM" - if null: whole day
    end: Optional[str] = None
    reason: str = ""

class BlockerOut(BlockerIn):
    id: str

class AppointmentIn(BaseModel):
    service_id: str
    date: str          # "YYYY-MM-DD"
    start: str         # "HH:MM"
    client_name: str
    client_nickname: Optional[str] = ""
    client_phone: str
    client_email: Optional[str] = ""
    booker_name: Optional[str] = ""  # nombre de quien reserva, si es para otra persona
    accepted_policy: bool

class AppointmentOut(BaseModel):
    id: str
    service_id: str
    service_name: str
    price_eur: float
    duration_min: int
    date: str
    start: str
    end: str
    client_name: str
    client_nickname: Optional[str] = ""
    client_phone: str
    client_email: Optional[str] = ""
    booker_name: Optional[str] = ""
    status: str
    confirmado: bool = False
    recordatorio_enviado: bool = False
    created_at: str
    whatsapp_links: Optional[dict] = None


# --- Utilities for slots ---
def parse_hhmm(s: str) -> int:
    """Return minutes since 00:00."""
    h, m = s.split(":")
    return int(h) * 60 + int(m)

def fmt_hhmm(mins: int) -> str:
    return f"{mins // 60:02d}:{mins % 60:02d}"

DEFAULT_WORKING_HOURS = {
    "0": {"enabled": True,  "start": "10:00", "end": "20:00"},  # Mon
    "1": {"enabled": True,  "start": "10:00", "end": "20:00"},
    "2": {"enabled": True,  "start": "10:00", "end": "20:00"},
    "3": {"enabled": True,  "start": "10:00", "end": "20:00"},
    "4": {"enabled": True,  "start": "10:00", "end": "21:00"},
    "5": {"enabled": True,  "start": "10:00", "end": "18:00"},
    "6": {"enabled": False, "start": "10:00", "end": "14:00"},  # Sun
}

DEFAULT_SERVICES = [
    {"name": "Solo Corte", "description": "", "price_eur": 0.0, "duration_min": 35, "active": True},
    {"name": "Corte y Barba", "description": "", "price_eur": 0.0, "duration_min": 50, "active": True},
    {"name": "Corte, Barba y Cejas", "description": "", "price_eur": 0.0, "duration_min": 60, "active": True},
    {"name": "Corte y Cejas", "description": "", "price_eur": 0.0, "duration_min": 40, "active": True},
    {"name": "Solo Arreglo de Barba", "description": "", "price_eur": 0.0, "duration_min": 15, "active": True},
    {"name": "Perfilado de Cejas", "description": "", "price_eur": 0.0, "duration_min": 10, "active": True},
]


# --- Auth endpoints ---
@api.post("/auth/login")
async def login(body: LoginIn):
    user = await db.users.find_one({"email": body.email.lower().strip()})
    if not user or not verify_pw(body.password, user["password_hash"]):
        raise HTTPException(401, "Credenciales incorrectas")
    token = create_token(user["id"], user["email"])
    return {"token": token, "user": {"id": user["id"], "email": user["email"], "role": user.get("role", "admin")}}

@api.get("/auth/me")
async def me(admin=Depends(get_current_admin)):
    return admin


# --- Services ---
@api.get("/services", response_model=List[ServiceOut])
async def list_services(all: bool = False):
    q = {} if all else {"active": True}
    docs = await db.services.find(q, {"_id": 0}).sort("price_eur", 1).to_list(200)
    return docs

@api.post("/services", response_model=ServiceOut)
async def create_service(body: ServiceIn, admin=Depends(get_current_admin)):
    doc = {"id": new_id(), **body.model_dump()}
    await db.services.insert_one(doc.copy())
    doc.pop("_id", None)
    return doc

@api.put("/services/{sid}", response_model=ServiceOut)
async def update_service(sid: str, body: ServiceIn, admin=Depends(get_current_admin)):
    res = await db.services.update_one({"id": sid}, {"$set": body.model_dump()})
    if not res.matched_count:
        raise HTTPException(404, "Servicio no encontrado")
    doc = await db.services.find_one({"id": sid}, {"_id": 0})
    return doc

@api.delete("/services/{sid}")
async def delete_service(sid: str, admin=Depends(get_current_admin)):
    await db.services.delete_one({"id": sid})
    return {"ok": True}


# --- Working Hours ---
@api.get("/working-hours")
async def get_working_hours():
    doc = await db.working_hours.find_one({"id": "default"}, {"_id": 0})
    if not doc:
        return {"days": DEFAULT_WORKING_HOURS}
    return {"days": doc.get("days", DEFAULT_WORKING_HOURS)}

@api.put("/working-hours")
async def set_working_hours(body: WorkingHoursIn, admin=Depends(get_current_admin)):
    await db.working_hours.update_one(
        {"id": "default"},
        {"$set": {"id": "default", "days": body.days, "updated_at": now_iso()}},
        upsert=True,
    )
    return {"days": body.days}


# --- Blockers ---
@api.get("/blockers", response_model=List[BlockerOut])
async def list_blockers(admin=Depends(get_current_admin)):
    docs = await db.blockers.find({}, {"_id": 0}).sort("date", 1).to_list(500)
    return docs

@api.post("/blockers", response_model=BlockerOut)
async def add_blocker(body: BlockerIn, admin=Depends(get_current_admin)):
    doc = {"id": new_id(), **body.model_dump()}
    await db.blockers.insert_one(doc.copy())
    doc.pop("_id", None)
    return doc

@api.delete("/blockers/{bid}")
async def delete_blocker(bid: str, admin=Depends(get_current_admin)):
    await db.blockers.delete_one({"id": bid})
    return {"ok": True}


# --- Availability calculation ---
SLOT_STEP = 15  # minutes granularity for booking

async def _compute_slots(date_str: str, duration_min: int) -> List[str]:
    try:
        d = datetime.strptime(date_str, "%Y-%m-%d").date()
    except ValueError:
        raise HTTPException(400, "Fecha inválida")

    weekday = str(d.weekday())  # 0=Mon
    wh_doc = await db.working_hours.find_one({"id": "default"}, {"_id": 0})
    wh = (wh_doc or {}).get("days", DEFAULT_WORKING_HOURS)
    day_cfg = wh.get(weekday, DEFAULT_WORKING_HOURS[weekday])
    if not day_cfg.get("enabled"):
        return []

    start_m = parse_hhmm(day_cfg["start"])
    end_m = parse_hhmm(day_cfg["end"])

    # Existing appointments that day
    appts = await db.appointments.find(
        {"date": date_str, "status": {"$ne": "cancelled"}}, {"_id": 0}
    ).to_list(500)
    busy = [(parse_hhmm(a["start"]), parse_hhmm(a["end"])) for a in appts]

    # Blockers
    blockers = await db.blockers.find({"date": date_str}, {"_id": 0}).to_list(200)
    for b in blockers:
        if not b.get("start") or not b.get("end"):
            return []  # full-day block
        busy.append((parse_hhmm(b["start"]), parse_hhmm(b["end"])))

    slots = []
    # If today, don't offer past slots (Europe/Madrid ~ UTC+1 winter; keep simple with local now)
    now = datetime.now()
    today_min = now.hour * 60 + now.minute if d == now.date() else -1

    t = start_m
    while t + duration_min <= end_m:
        if t > today_min:
            conflict = any(not (t + duration_min <= b0 or t >= b1) for (b0, b1) in busy)
            if not conflict:
                slots.append(fmt_hhmm(t))
        t += SLOT_STEP
    return slots

@api.get("/availability")
async def availability(service_id: str, date: str):
    svc = await db.services.find_one({"id": service_id}, {"_id": 0})
    if not svc:
        raise HTTPException(404, "Servicio no encontrado")
    slots = await _compute_slots(date, svc["duration_min"])
    return {"date": date, "service_id": service_id, "duration_min": svc["duration_min"], "slots": slots}


# --- Appointments ---
MAX_ACTIVE_APPTS_PER_PHONE = 2

@api.post("/appointments", response_model=AppointmentOut)
async def create_appointment(body: AppointmentIn):
    if not body.accepted_policy:
        raise HTTPException(400, "Debes aceptar la política del 50%")
    svc = await db.services.find_one({"id": body.service_id}, {"_id": 0})
    if not svc:
        raise HTTPException(404, "Servicio no encontrado")

    # Limit: max 2 active future appointments per phone
    today_str = datetime.now().strftime("%Y-%m-%d")
    active_count = await db.appointments.count_documents({
        "client_phone": body.client_phone,
        "status": {"$ne": "cancelled"},
        "date": {"$gte": today_str},
    })
    if active_count >= MAX_ACTIVE_APPTS_PER_PHONE:
        raise HTTPException(
            409,
            f"Ya tienes {MAX_ACTIVE_APPTS_PER_PHONE} citas activas con este teléfono. Cancela una para poder reservar otra.",
        )

    # Re-check availability atomically-ish
    slots = await _compute_slots(body.date, svc["duration_min"])
    if body.start not in slots:
        raise HTTPException(409, "Esa hora ya no está disponible, elige otra")

    start_m = parse_hhmm(body.start)
    end_m = start_m + svc["duration_min"]

    # Upsert client (identify by booker phone; name = booker_name if provided else client_name)
    identity_name = (body.booker_name or "").strip() or body.client_name
    client_doc = await db.clients.find_one({"phone": body.client_phone}, {"_id": 0})
    if not client_doc:
        client_doc = {
            "id": new_id(),
            "name": identity_name,
            "nickname": body.client_nickname or "",
            "phone": body.client_phone,
            "created_at": now_iso(),
        }
        await db.clients.insert_one(client_doc.copy())

    appt = {
        "id": new_id(),
        "service_id": svc["id"],
        "service_name": svc["name"],
        "price_eur": svc["price_eur"],
        "duration_min": svc["duration_min"],
        "date": body.date,
        "start": body.start,
        "end": fmt_hhmm(end_m),
        "client_id": client_doc["id"],
        "client_name": body.client_name,
        "client_nickname": body.client_nickname or "",
        "client_phone": body.client_phone,
        "client_email": (body.client_email or "").strip(),
        "booker_name": (body.booker_name or "").strip(),
        "status": "confirmed",
        "confirmado": False,
        "recordatorio_enviado": False,
        "created_at": now_iso(),
    }
    await db.appointments.insert_one(appt.copy())
    appt.pop("_id", None)
    appt["whatsapp_links"] = _wa_links(appt)
    return appt

@api.get("/appointments/{aid}", response_model=AppointmentOut)
async def get_appointment(aid: str):
    doc = await db.appointments.find_one({"id": aid}, {"_id": 0})
    if not doc:
        raise HTTPException(404, "Cita no encontrada")
    return doc

@api.get("/appointments")
async def list_appointments(from_date: Optional[str] = None, to_date: Optional[str] = None, admin=Depends(get_current_admin)):
    q = {}
    if from_date and to_date:
        q["date"] = {"$gte": from_date, "$lte": to_date}
    elif from_date:
        q["date"] = {"$gte": from_date}
    docs = await db.appointments.find(q, {"_id": 0}).sort([("date", 1), ("start", 1)]).to_list(2000)
    return docs

@api.post("/appointments/{aid}/cancel")
async def cancel_by_client(aid: str, phone: str):
    doc = await db.appointments.find_one({"id": aid}, {"_id": 0})
    if not doc:
        raise HTTPException(404, "Cita no encontrada")
    if doc["client_phone"] != phone:
        raise HTTPException(403, "Teléfono no coincide")
    # 12h rule
    try:
        appt_dt = datetime.strptime(f"{doc['date']} {doc['start']}", "%Y-%m-%d %H:%M")
    except ValueError:
        raise HTTPException(400, "Cita corrupta")
    if appt_dt - datetime.now() < timedelta(hours=12):
        raise HTTPException(400, "No se puede cancelar con menos de 12 horas de antelación")
    await db.appointments.update_one({"id": aid}, {"$set": {"status": "cancelled", "cancelled_at": now_iso()}})
    return {"ok": True}

@api.post("/appointments/{aid}/admin-cancel")
async def cancel_by_admin(aid: str, admin=Depends(get_current_admin)):
    res = await db.appointments.update_one({"id": aid}, {"$set": {"status": "cancelled", "cancelled_at": now_iso()}})
    if not res.matched_count:
        raise HTTPException(404, "Cita no encontrada")
    return {"ok": True}


# --- Clients ---
@api.get("/clients")
async def list_clients(admin=Depends(get_current_admin)):
    docs = await db.clients.find({}, {"_id": 0}).sort("name", 1).to_list(2000)
    # Add appointment count
    for c in docs:
        c["appointments_count"] = await db.appointments.count_documents({"client_phone": c["phone"]})
    return docs

@api.get("/clients/{cid}/appointments")
async def client_appointments(cid: str, admin=Depends(get_current_admin)):
    cli = await db.clients.find_one({"id": cid}, {"_id": 0})
    if not cli:
        raise HTTPException(404, "Cliente no encontrado")
    docs = await db.appointments.find({"client_phone": cli["phone"]}, {"_id": 0}).sort("date", -1).to_list(500)
    return {"client": cli, "appointments": docs}


# --- WhatsApp links (wa.me) ---
def _wa_links(a: dict) -> dict:
    cli_msg = (
        f"¡Hola! Confirmo mi cita en +58 BarberStudio:\n\n"
        f"📅 {a['date']} a las {a['start']}\n"
        f"✂️ {a['service_name']} ({a['duration_min']} min)\n"
        f"👤 {a['client_name']}\n\n"
        "Acepto la política del 50%. ¡Nos vemos!"
    )
    barber_msg = (
        f"📋 Nueva cita reservada:\n\n"
        f"👤 {a['client_name']} ({a['client_phone']})\n"
        f"📅 {a['date']} · {a['start']} – {a['end']}\n"
        f"✂️ {a['service_name']}"
    )
    links = {"cliente": generar_enlace_whatsapp(a["client_phone"], cli_msg)}
    barber_phone = os.environ.get("BUSINESS_WHATSAPP", "")
    links["barbero"] = generar_enlace_whatsapp(barber_phone, barber_msg) if barber_phone else None
    return links

def _reminder_msg(a: dict) -> str:
    return (
        f"¡Hola {a['client_name']}! Te recordamos tu cita de mañana en +58 BarberStudio:\n\n"
        f"📅 {a['date']} a las {a['start']}\n"
        f"✂️ {a['service_name']}\n\n"
        "Si no puedes venir, cancela con al menos 12h de antelación. ¡Te esperamos!"
    )


# --- Confirmación y recordatorios (admin) ---
@api.put("/appointments/{aid}/confirmar")
async def confirmar_cita(aid: str, admin=Depends(get_current_admin)):
    res = await db.appointments.update_one({"id": aid}, {"$set": {"confirmado": True}})
    if not res.matched_count:
        raise HTTPException(404, "Cita no encontrada")
    return {"ok": True, "confirmado": True}

@api.post("/appointments/{aid}/recordatorio")
async def recordatorio_link(aid: str, admin=Depends(get_current_admin)):
    doc = await db.appointments.find_one({"id": aid}, {"_id": 0})
    if not doc:
        raise HTTPException(404, "Cita no encontrada")
    return {"url": generar_enlace_whatsapp(doc["client_phone"], _reminder_msg(doc))}


# --- Email (Resend gestionado por Emergent) ---
EMAIL_BASE_URL = "https://integrations.emergentagent.com"
EMAIL_KEY = os.environ.get("EMERGENT_EMAIL_KEY", "")
EMAIL_FROM_NAME = os.environ.get("EMAIL_FROM_NAME", "+58 BarberStudio")
EMAIL_REPLY_TO = os.environ.get("EMAIL_REPLY_TO")

_SHORTENERS = ("bit.ly", "tinyurl.com", "t.co", "is.gd", "cutt.ly", "goo.gl", "rebrand.ly")
_CRED_ASK = ("reply with your password", "reply with the code", "send your password", "cvv",
             "send us your password", "enter your password below", "confirm your card number",
             "your full card number", "seed phrase", "recovery phrase", "verify your card",
             "social security number", "confirm your bank details")
_HOSTISH = re.compile(r"\b(?:https?://)?((?:[a-z0-9-]+\.)+[a-z]{2,})", re.I)

def _host_ok(host: str) -> bool:
    if not host or "xn--" in host:
        return False
    try:
        ipaddress.ip_address(host)
        return False
    except ValueError:
        pass
    return not any(host == s or host.endswith("." + s) for s in _SHORTENERS)

def _same_site(shown: str, real: str) -> bool:
    return shown == real or real.endswith("." + shown) or shown.endswith("." + real)

class _EmailScan(HTMLParser):
    def __init__(self):
        super().__init__()
        self.tags, self.urls, self.anchors = set(), [], []
        self._href, self._text = None, []
    def handle_starttag(self, tag, attrs):
        self.tags.add(tag.lower())
        self.urls += [v for k, v in attrs if k.lower() in ("href", "src") and v]
        if tag.lower() == "a":
            self._href = dict((k.lower(), v) for k, v in attrs).get("href")
            self._text = []
    def handle_data(self, data):
        if self._href is not None:
            self._text.append(data)
    def handle_endtag(self, tag):
        if tag.lower() == "a" and self._href is not None:
            self.anchors.append((self._href, "".join(self._text)))
            self._href, self._text = None, []

def _assert_safe_email(subject: str, html: str) -> None:
    scan = _EmailScan(); scan.feed(html)
    if scan.tags & {"form", "input", "textarea", "select"}:
        raise ValueError("No forms or input fields in email (G2)")
    body = f"{subject}\n{html}".lower()
    for p in _CRED_ASK:
        if p in body:
            raise ValueError(f"Email asks the recipient for credentials: {p!r} (G2)")
    for url in scan.urls:
        low = url.strip().lower()
        if low.startswith(("mailto:", "tel:", "cid:", "#")):
            continue
        if not low.startswith("https://"):
            raise ValueError(f"Email links/assets must be absolute https: {url!r} (G3)")
        host = urlparse(low).hostname or ""
        if not _host_ok(host) or urlparse(low).username is not None:
            raise ValueError(f"Shortened, numeric-host or credential-bearing URL: {url!r} (G3)")
    for href, text in scan.anchors:
        real = urlparse(href.strip().lower()).hostname or ""
        if not real:
            continue
        for m in _HOSTISH.finditer(text):
            if not _same_site(m.group(1).lower(), real):
                raise ValueError(f"Anchor text {m.group(1)!r} ≠ real link host {real!r} (G3)")

async def send_email(*, to: str, subject: str, html: str, reply_to: Optional[str] = None) -> Optional[str]:
    _assert_safe_email(subject, html)
    if not EMAIL_KEY:
        logger.warning("EMERGENT_EMAIL_KEY no configurada; email no enviado a %s", to)
        return None
    payload = {"to": [to], "subject": subject, "html": html, "from_name": EMAIL_FROM_NAME}
    if reply_to or EMAIL_REPLY_TO:
        payload["contact_email"] = reply_to or EMAIL_REPLY_TO
    try:
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(
                f"{EMAIL_BASE_URL}/api/v1/email/send",
                headers={"X-Email-Key": EMAIL_KEY},
                json=payload,
            )
        resp.raise_for_status()
        return resp.json().get("id")
    except Exception as e:
        logger.error("Email send error a %s: %s", to, str(e))
        return None


# --- Recordatorios automáticos (cron diario 8:00 Europe/Madrid) ---
WEBHOOK_CRON_SECRET = os.environ.get("WEBHOOK_CRON_SECRET", "")

async def run_recordatorios() -> int:
    tomorrow = (datetime.now(ZoneInfo("Europe/Madrid")) + timedelta(days=1)).strftime("%Y-%m-%d")
    appts = await db.appointments.find(
        {"date": tomorrow, "status": {"$ne": "cancelled"}, "recordatorio_enviado": {"$ne": True}},
        {"_id": 0},
    ).to_list(500)
    claimed_count = 0
    for a in appts:
        claimed = await db.appointments.find_one_and_update(
            {"id": a["id"], "recordatorio_enviado": {"$ne": True}},
            {"$set": {"recordatorio_enviado": True}},
        )
        if not claimed:
            continue
        claimed_count += 1
        url = generar_enlace_whatsapp(a["client_phone"], _reminder_msg(a))
        if a.get("client_email"):
            subject = f"Recordatorio de tu cita — {EMAIL_FROM_NAME}"
            html = (
                f'<table role="presentation" width="100%"><tr><td style="padding:24px;font-family:Arial,sans-serif">'
                f"<p>Hola {escape(a['client_name'])},</p>"
                f"<p>Te recordamos tu cita en <strong>{escape(EMAIL_FROM_NAME)}</strong> mañana "
                f"<strong>{escape(a['date'])}</strong> a las <strong>{escape(a['start'])}</strong> "
                f"({escape(a['service_name'])}).</p>"
                f'<p><a href="{url}">Confirmar asistencia por WhatsApp</a></p>'
                f'<p style="font-size:12px;color:#888">Enviado por {escape(EMAIL_FROM_NAME)}. '
                "Si no puedes venir, cancela con al menos 12h de antelación.</p></td></tr></table>"
            )
            await send_email(to=a["client_email"], subject=subject, html=html)
    logger.info("Recordatorios: %d citas procesadas para %s", claimed_count, tomorrow)
    return claimed_count

@api.post("/cron/recordatorios")
async def cron_recordatorios(request: Request, background: BackgroundTasks):
    # Cron endpoints must ack 2xx immediately; enqueue/background the actual work.
    auth = request.headers.get("authorization", "")
    token = auth.removeprefix("Bearer ").strip()
    if not WEBHOOK_CRON_SECRET or not token or not hmac.compare_digest(token, WEBHOOK_CRON_SECRET):
        raise HTTPException(401, "No autorizado")
    background.add_task(run_recordatorios)
    return {"ok": True}


# --- Business info (public) ---
@api.get("/business")
async def business_info():
    return {
        "name": os.environ.get("BUSINESS_NAME", "+58 BarberStudio"),
        "phone": os.environ.get("BUSINESS_PHONE", ""),
        "whatsapp": os.environ.get("BUSINESS_WHATSAPP", ""),
        "instagram": os.environ.get("BUSINESS_INSTAGRAM", ""),
        "address": os.environ.get("BUSINESS_ADDRESS", "Avenida de Los Majuelos 51C, 38008, Taco, Santa Cruz de Tenerife"),
        "maps_query": os.environ.get("BUSINESS_MAPS_QUERY", "Multitienda Veloz 24hr, Avenida de Los Majuelos 51C, 38008, Taco, Santa Cruz de Tenerife"),
        "reviews_url": os.environ.get("BUSINESS_REVIEWS_URL", ""),
        "barber_name": os.environ.get("BUSINESS_BARBER_NAME", "Heber"),
    }

@api.get("/")
async def root():
    return {"message": "+58 BarberStudio API"}


app.include_router(api)


@app.get("/")
async def app_root():
    return {
        "status": "ok",
        "service": "+58 BarberStudio API",
        "docs": "/docs",
        "message": "Esta es la API. La web de reserva está en el frontend."
    }

app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=os.environ.get('CORS_ORIGINS', '*').split(','),
    allow_methods=["*"],
    allow_headers=["*"],
)


# --- Startup: seed ---
@app.on_event("startup")
async def on_start():
    # Seed admin
    existing = await db.users.find_one({"email": ADMIN_EMAIL.lower()})
    if not existing:
        await db.users.insert_one({
            "id": new_id(),
            "email": ADMIN_EMAIL.lower(),
            "password_hash": hash_pw(ADMIN_PASSWORD),
            "role": "admin",
            "name": "Barbero",
            "created_at": now_iso(),
        })
        logger.info("Admin seeded: %s", ADMIN_EMAIL)
    else:
        # Keep password in sync with .env
        if not verify_pw(ADMIN_PASSWORD, existing["password_hash"]):
            await db.users.update_one({"email": ADMIN_EMAIL.lower()}, {"$set": {"password_hash": hash_pw(ADMIN_PASSWORD)}})
            logger.info("Admin password updated from env")

    # Seed default services
    if await db.services.count_documents({}) == 0:
        await db.services.insert_many([{"id": new_id(), **s} for s in DEFAULT_SERVICES])
        logger.info("Default services seeded")

    # Seed default working hours
    if not await db.working_hours.find_one({"id": "default"}):
        await db.working_hours.insert_one({"id": "default", "days": DEFAULT_WORKING_HOURS, "updated_at": now_iso()})
        logger.info("Default working hours seeded")


@app.on_event("shutdown")
async def shutdown_db_client():
    client.close()
