from dotenv import load_dotenv
from pathlib import Path

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

import os
import re
import uuid
import hmac
import hashlib
import json
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
from fastapi.responses import PlainTextResponse

import asyncio
import bot as whatsapp_bot
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
from pydantic import BaseModel, Field, ConfigDict


# --- Config ---
JWT_SECRET = os.environ["JWT_SECRET"]
JWT_ALG = "HS256"
ADMIN_USER = os.environ.get("ADMIN_USER", "+58BarberStudio")
ADMIN_EMAIL = os.environ.get("ADMIN_EMAIL", "")  # email del propietario (solo referencia; el acceso es por usuario)
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
        return {"id": user["id"], "username": user.get("username"), "email": user.get("email", ""), "role": user.get("role", "admin")}
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
    username: str
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

class ScheduleOverrideIn(BaseModel):
    date: str              # "YYYY-MM-DD"
    enabled: bool = True
    start: str = "10:00"   # "HH:MM"
    end: str = "20:00"     # "HH:MM"
    reason: str = ""

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
    opt_in_whatsapp: bool = False

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
    opt_in_whatsapp: bool = False
    opt_in_fecha: Optional[str] = ""
    created_at: str


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
    user = await db.users.find_one({"username": body.username.strip()})
    if not user or not verify_pw(body.password, user["password_hash"]):
        raise HTTPException(401, "Credenciales incorrectas")
    token = create_token(user["id"], user.get("email", ""))
    return {"token": token, "user": {"id": user["id"], "username": user.get("username"), "email": user.get("email", ""), "role": user.get("role", "admin")}}

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


# --- Schedule overrides (excepciones por fecha concreta) ---
@api.get("/schedule-overrides")
async def list_overrides(from_date: Optional[str] = None, to_date: Optional[str] = None, admin=Depends(get_current_admin)):
    q = {}
    if from_date and to_date:
        q["date"] = {"$gte": from_date, "$lte": to_date}
    elif from_date:
        q["date"] = {"$gte": from_date}
    elif to_date:
        q["date"] = {"$lte": to_date}
    return await db.schedule_overrides.find(q, {"_id": 0}).sort("date", 1).to_list(500)

@api.get("/schedule-overrides/{date}")
async def get_override(date: str, admin=Depends(get_current_admin)):
    doc = await db.schedule_overrides.find_one({"date": date}, {"_id": 0})
    if not doc:
        raise HTTPException(404, "No hay excepción para esta fecha")
    return doc

@api.post("/schedule-overrides")
async def upsert_override(body: ScheduleOverrideIn, admin=Depends(get_current_admin)):
    doc = body.model_dump()
    await db.schedule_overrides.update_one({"date": body.date}, {"$set": doc}, upsert=True)
    return doc

@api.delete("/schedule-overrides/{date}")
async def delete_override(date: str, admin=Depends(get_current_admin)):
    await db.schedule_overrides.delete_one({"date": date})
    return {"ok": True}


# --- Horario efectivo de un día (público, lado reserva) ---
@api.get("/day-schedule/{date}")
async def day_schedule(date: str):
    try:
        datetime.strptime(date, "%Y-%m-%d")
    except ValueError:
        raise HTTPException(400, "Fecha inválida")
    eff = await _effective_schedule(date)
    return {"date": date, **eff}


# --- Availability calculation ---
SLOT_STEP = 15  # minutes granularity for booking

async def _effective_schedule(date_str: str) -> dict:
    """Horario efectivo de una fecha: la excepción manda sobre el horario semanal base."""
    d = datetime.strptime(date_str, "%Y-%m-%d").date()
    weekday = str(d.weekday())  # 0=Mon
    # PRIORIDAD 1: excepción por fecha
    override = await db.schedule_overrides.find_one({"date": date_str}, {"_id": 0})
    if override:
        return {
            "source": "override",
            "enabled": override.get("enabled", True),
            "start": override.get("start", "10:00"),
            "end": override.get("end", "20:00"),
            "reason": override.get("reason", ""),
        }
    # PRIORIDAD 2: horario semanal base
    wh_doc = await db.working_hours.find_one({"id": "default"}, {"_id": 0})
    wh = (wh_doc or {}).get("days", DEFAULT_WORKING_HOURS)
    day_cfg = wh.get(weekday, DEFAULT_WORKING_HOURS[weekday])
    return {
        "source": "base",
        "enabled": day_cfg.get("enabled", False),
        "start": day_cfg.get("start", "10:00"),
        "end": day_cfg.get("end", "20:00"),
        "reason": "",
    }

async def _compute_slots(date_str: str, duration_min: int) -> List[str]:
    try:
        d = datetime.strptime(date_str, "%Y-%m-%d").date()
    except ValueError:
        raise HTTPException(400, "Fecha inválida")

    eff = await _effective_schedule(date_str)
    if not eff["enabled"]:
        return []

    start_m = parse_hhmm(eff["start"])
    end_m = parse_hhmm(eff["end"])

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
MAX_ACTIVE_APPTS_PER_PHONE = 6

@api.post("/appointments", response_model=AppointmentOut)
async def create_appointment(body: AppointmentIn):
    if not body.accepted_policy:
        raise HTTPException(400, "Debes aceptar la política del 50%")
    if not body.opt_in_whatsapp:
        raise HTTPException(400, "Debes aceptar recibir confirmaciones y recordatorios por WhatsApp")
    svc = await db.services.find_one({"id": body.service_id}, {"_id": 0})
    if not svc:
        raise HTTPException(404, "Servicio no encontrado")

    # Limit: max active future appointments per phone (multi-booking allowed)
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
        "opt_in_whatsapp": True,
        "opt_in_fecha": now_iso(),
        "created_at": now_iso(),
    }
    await db.appointments.insert_one(appt.copy())
    appt.pop("_id", None)
    # Opt-in explícito al reservar: limpia una posible baja (STOP) anterior y reactiva los mensajes
    tel_norm = whatsapp_bot.normalizar_telefono(body.client_phone)
    await db.whatsapp_optout.update_one(
        {"phone": tel_norm},
        {"$set": {"phone": tel_norm, "opt_out": False, "ts": now_iso()}},
        upsert=True,
    )
    asyncio.create_task(whatsapp_bot.notificar_nueva_cita(appt))
    return appt


class AppointmentBatchIn(BaseModel):
    items: list  # cada item con los campos de AppointmentIn


@api.post("/appointments/batch")
async def create_appointments_batch(body: AppointmentBatchIn):
    if not body.items:
        raise HTTPException(400, "No hay citas en el lote")
    parsed = [AppointmentIn(**raw) for raw in body.items]
    for it in parsed:
        if not it.accepted_policy:
            raise HTTPException(400, "Debes aceptar la política del 50%")
        if not it.opt_in_whatsapp:
            raise HTTPException(400, "Debes aceptar recibir confirmaciones y recordatorios por WhatsApp")
    # Validar disponibilidad y límites de TODAS antes de crear ninguna
    today_str = datetime.now().strftime("%Y-%m-%d")
    per_phone_new = {}
    lote_slots = {}
    for it in parsed:
        svc = await db.services.find_one({"id": it.service_id}, {"_id": 0})
        if not svc:
            raise HTTPException(404, "Servicio no encontrado")
        slots = await _compute_slots(it.date, svc["duration_min"])
        if it.start not in slots:
            raise HTTPException(409, f"La hora {it.start} del {it.date} ya no está disponible, elige otra")
        start_m = parse_hhmm(it.start)
        end_m = start_m + svc["duration_min"]
        for (b0, b1) in lote_slots.get(it.date, []):
            if not (end_m <= b0 or start_m >= b1):
                raise HTTPException(409, f"Dos citas del lote se solapan el {it.date} a las {it.start}")
        lote_slots.setdefault(it.date, []).append((start_m, end_m))
        per_phone_new[it.client_phone] = per_phone_new.get(it.client_phone, 0) + 1
    for phone, nuevas in per_phone_new.items():
        active_count = await db.appointments.count_documents({
            "client_phone": phone, "status": {"$ne": "cancelled"}, "date": {"$gte": today_str},
        })
        if active_count + nuevas > MAX_ACTIVE_APPTS_PER_PHONE:
            raise HTTPException(409, f"Máximo {MAX_ACTIVE_APPTS_PER_PHONE} citas activas por teléfono")
    created = []
    for it in parsed:
        svc = await db.services.find_one({"id": it.service_id}, {"_id": 0})
        start_m = parse_hhmm(it.start)
        end_m = start_m + svc["duration_min"]
        identity_name = (it.booker_name or "").strip() or it.client_name
        client_doc = await db.clients.find_one({"phone": it.client_phone}, {"_id": 0})
        if not client_doc:
            client_doc = {
                "id": new_id(), "name": identity_name, "nickname": it.client_nickname or "",
                "phone": it.client_phone, "created_at": now_iso(),
            }
            await db.clients.insert_one(client_doc.copy())
        appt = {
            "id": new_id(), "service_id": svc["id"], "service_name": svc["name"], "price_eur": svc["price_eur"],
            "duration_min": svc["duration_min"], "date": it.date, "start": it.start, "end": fmt_hhmm(end_m),
            "client_id": client_doc["id"], "client_name": it.client_name, "client_nickname": it.client_nickname or "",
            "client_phone": it.client_phone, "client_email": (it.client_email or "").strip(),
            "booker_name": (it.booker_name or "").strip(), "status": "confirmed", "confirmado": False,
            "recordatorio_enviado": False, "opt_in_whatsapp": True, "opt_in_fecha": now_iso(), "created_at": now_iso(),
        }
        await db.appointments.insert_one(appt.copy())
        appt.pop("_id", None)
        created.append(appt)
        tel_norm = whatsapp_bot.normalizar_telefono(it.client_phone)
        await db.whatsapp_optout.update_one(
            {"phone": tel_norm}, {"$set": {"phone": tel_norm, "opt_out": False, "ts": now_iso()}}, upsert=True,
        )
    # Notificaciones consolidadas por teléfono: 2-3 citas → un solo mensaje
    grupos = {}
    for a in created:
        grupos.setdefault(a["client_phone"], []).append(a)
    for grupo in grupos.values():
        if 2 <= len(grupo) <= 3:
            asyncio.create_task(whatsapp_bot.notificar_multi(grupo))
        else:
            for a in grupo:
                asyncio.create_task(whatsapp_bot.notificar_nueva_cita(a))
    return created


class ForceAppointmentIn(BaseModel):
    service_id: str
    date: str
    start: str
    client_name: str
    client_phone: str
    client_nickname: Optional[str] = ""


@api.post("/admin/appointments/force", response_model=AppointmentOut)
async def force_appointment(body: ForceAppointmentIn, admin=Depends(get_current_admin)):
    # El barbero fuerza la agenda: se crea sin chequeo de conflicto ni límites.
    svc = await db.services.find_one({"id": body.service_id}, {"_id": 0})
    if not svc:
        raise HTTPException(404, "Servicio no encontrado")
    start_m = parse_hhmm(body.start)
    end_m = start_m + svc["duration_min"]
    client_doc = await db.clients.find_one({"phone": body.client_phone}, {"_id": 0})
    if not client_doc:
        client_doc = {
            "id": new_id(), "name": body.client_name, "nickname": body.client_nickname or "",
            "phone": body.client_phone, "created_at": now_iso(),
        }
        await db.clients.insert_one(client_doc.copy())
    appt = {
        "id": new_id(), "service_id": svc["id"], "service_name": svc["name"], "price_eur": svc["price_eur"],
        "duration_min": svc["duration_min"], "date": body.date, "start": body.start, "end": fmt_hhmm(end_m),
        "client_id": client_doc["id"], "client_name": body.client_name, "client_nickname": body.client_nickname or "",
        "client_phone": body.client_phone, "client_email": "", "booker_name": "forzada por barbero",
        "status": "confirmed", "confirmado": True, "recordatorio_enviado": False,
        "opt_in_whatsapp": False, "opt_in_fecha": "", "created_at": now_iso(),
    }
    await db.appointments.insert_one(appt.copy())
    appt.pop("_id", None)
    asyncio.create_task(whatsapp_bot.notificar_nueva_cita(appt))
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
    asyncio.create_task(whatsapp_bot.notificar_cambio_cita(doc, "cancelacion"))
    return {"ok": True}

@api.post("/appointments/gestionar")
async def gestionar_lookup(body: dict):
    code = (body.get("code") or "").strip().lower()
    phone = (body.get("phone") or "").strip()
    if len(code) < 6 or not phone:
        raise HTTPException(400, "Introduce el código de tu reserva y tu teléfono")
    doc = await db.appointments.find_one(
        {"client_phone": phone, "status": {"$ne": "cancelled"}, "id": {"$regex": f"^{re.escape(code)}"}},
        {"_id": 0},
    )
    if not doc:
        raise HTTPException(404, "No encontramos ninguna cita activa con ese código y teléfono")
    return doc

@api.post("/appointments/{aid}/modificar")
async def modificar_cita(aid: str, body: dict):
    phone = (body.get("phone") or "").strip()
    new_date = (body.get("date") or "").strip()
    new_start = (body.get("start") or "").strip()
    doc = await db.appointments.find_one({"id": aid}, {"_id": 0})
    if not doc:
        raise HTTPException(404, "Cita no encontrada")
    if doc["client_phone"] != phone:
        raise HTTPException(403, "Teléfono no coincide")
    if doc.get("status") == "cancelled":
        raise HTTPException(400, "La cita ya está cancelada")
    try:
        appt_dt = datetime.strptime(f"{doc['date']} {doc['start']}", "%Y-%m-%d %H:%M")
    except ValueError:
        raise HTTPException(400, "Cita corrupta")
    if appt_dt - datetime.now() < timedelta(hours=12):
        raise HTTPException(400, "No se puede modificar con menos de 12 horas de antelación")
    slots = await _compute_slots(new_date, doc["duration_min"])
    if new_start not in slots:
        raise HTTPException(409, "Esa hora ya no está disponible")
    hh, mm = map(int, new_start.split(":"))
    end_total = hh * 60 + mm + doc["duration_min"]
    new_end = f"{end_total // 60:02d}:{end_total % 60:02d}"
    await db.appointments.update_one({"id": aid}, {"$set": {"date": new_date, "start": new_start, "end": new_end}})
    updated = await db.appointments.find_one({"id": aid}, {"_id": 0})
    asyncio.create_task(whatsapp_bot.notificar_cambio_cita(updated, "modificacion"))
    return updated

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

@api.delete("/clients/{cid}")
async def delete_client(cid: str, admin=Depends(get_current_admin)):
    res = await db.clients.delete_one({"id": cid})
    if not res.deleted_count:
        raise HTTPException(404, "Cliente no encontrado")
    return {"ok": True}


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
async def recordatorio_send(aid: str, admin=Depends(get_current_admin)):
    doc = await db.appointments.find_one({"id": aid}, {"_id": 0})
    if not doc:
        raise HTTPException(404, "Cita no encontrada")
    if await wa_opt_out(doc["client_phone"]):
        return {"ok": False, "sent": False, "error": "El cliente está dado de baja de WhatsApp (STOP)"}
    ok = await whatsapp_bot.enviar_a(doc["client_phone"], "recordatorio", doc)
    return {"ok": ok, "sent": ok}


# --- Email (SMTP propio, p.ej. Nominalia) ---
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

async def send_email(*, to: str, subject: str, html: str, reply_to: Optional[str] = None) -> bool:
    _assert_safe_email(subject, html)
    if not SMTP_HOST or not SMTP_USER or not SMTP_PASSWORD:
        logger.warning("SMTP no configurado; email no enviado a %s", to)
        return False
    import aiosmtplib
    from email.message import EmailMessage
    msg = EmailMessage()
    msg["From"] = f"{EMAIL_FROM_NAME} <{SMTP_USER}>"
    msg["To"] = to
    msg["Subject"] = subject
    if reply_to or EMAIL_REPLY_TO:
        msg["Reply-To"] = reply_to or EMAIL_REPLY_TO
    msg.set_content("Este mensaje requiere un cliente compatible con HTML.")
    msg.add_alternative(html, subtype="html")
    kwargs = {"hostname": SMTP_HOST, "port": SMTP_PORT, "username": SMTP_USER, "password": SMTP_PASSWORD}
    if SMTP_PORT == 465:
        kwargs["use_tls"] = True
    else:
        kwargs["start_tls"] = True
    try:
        await aiosmtplib.send(msg, **kwargs)
        return True
    except Exception as e:
        logger.error("Email send error a %s: %s", to, str(e))
        return False


# --- Recordatorios automáticos (cron diario 10:00 Atlantic/Canary) ---
WEBHOOK_CRON_SECRET = os.environ.get("WEBHOOK_CRON_SECRET", "")

async def run_recordatorios() -> int:
    tomorrow = (datetime.now(ZoneInfo("Europe/Madrid")) + timedelta(days=1)).strftime("%Y-%m-%d")
    appts = await db.appointments.find(
        {"date": tomorrow, "status": {"$ne": "cancelled"}, "recordatorio_enviado": {"$ne": True}},
        {"_id": 0},
    ).to_list(500)
    claimed_count = 0
    for a in appts:
        if await wa_opt_out(a["client_phone"]):
            logger.info("Recordatorio omitido (opt-out WhatsApp): ***%s", a["client_phone"][-4:])
            continue
        claimed = await db.appointments.find_one_and_update(
            {"id": a["id"], "recordatorio_enviado": {"$ne": True}},
            {"$set": {"recordatorio_enviado": True}},
        )
        if not claimed:
            continue
        claimed_count += 1
        await whatsapp_bot.enviar_a(a["client_phone"], "recordatorio", a)
        if a.get("client_email"):
            subject = f"Recordatorio de tu cita — {EMAIL_FROM_NAME}"
            gestionar = os.environ.get("GESTIONAR_URL", "https://www.58barberstudio.com/reservar#gestionar")
            html = (
                f'<table role="presentation" width="100%"><tr><td style="padding:24px;font-family:Arial,sans-serif">'
                f"<p>Hola {escape(a['client_name'])},</p>"
                f"<p>Te recordamos tu cita en <strong>{escape(EMAIL_FROM_NAME)}</strong> mañana "
                f"<strong>{escape(a['date'])}</strong> a las <strong>{escape(a['start'])}</strong> "
                f"({escape(a['service_name'])}).</p>"
                f'<p><a href="{escape(gestionar)}">Modificar o cancelar tu cita</a></p>'
                f'<p style="font-size:12px;color:#888">Enviado por {escape(EMAIL_FROM_NAME)}. '
                "Si no puedes venir, cancela con al menos 12h de antelación.</p></td></tr></table>"
            )
            await send_email(to=a["client_email"], subject=subject, html=html)
    logger.info("Recordatorios: %d citas procesadas para %s", claimed_count, tomorrow)
    return claimed_count

@api.api_route("/cron/recordatorios", methods=["GET", "POST"])
async def cron_recordatorios(request: Request, background: BackgroundTasks):
    # Cron endpoints must ack 2xx immediately; enqueue/background the actual work.
    auth = request.headers.get("authorization", "")
    token = auth.removeprefix("Bearer ").strip()
    if not WEBHOOK_CRON_SECRET or not token or not hmac.compare_digest(token, WEBHOOK_CRON_SECRET):
        raise HTTPException(401, "No autorizado")
    background.add_task(run_recordatorios)
    return {"ok": True}


# Alias publico para cron-job.org (misma proteccion Bearer y mismo trabajo en background)
@api.api_route("/send-reminders", methods=["GET", "POST"])
async def send_reminders(request: Request, background: BackgroundTasks):
    auth = request.headers.get("authorization", "")
    token = auth.removeprefix("Bearer ").strip()
    if not WEBHOOK_CRON_SECRET or not token or not hmac.compare_digest(token, WEBHOOK_CRON_SECRET):
        raise HTTPException(401, "No autorizado")
    background.add_task(run_recordatorios)
    return {"ok": True}


# --- Backup diario de citas (JSON en memory/ + copia por email SMTP) ---
BACKUP_EMAIL_TO = os.environ.get("BACKUP_EMAIL_TO", "info@58barberstudio.com")
SMTP_HOST = os.environ.get("SMTP_HOST", "")
SMTP_PORT = int(os.environ.get("SMTP_PORT", "465"))
SMTP_USER = os.environ.get("SMTP_USER", "")
SMTP_PASSWORD = os.environ.get("SMTP_PASSWORD", "")
BACKUP_EMAIL_FROM = os.environ.get("BACKUP_EMAIL_FROM", SMTP_USER)
BACKUP_DIR = ROOT_DIR.parent / "memory"


def _appointments_to_csv(appts: list) -> str:
    import csv, io
    cols = ["id", "date", "start", "end", "service_name", "duration_min",
            "client_name", "client_nickname", "client_phone", "client_email",
            "booker_name", "status", "confirmado", "created_at"]
    buf = io.StringIO()
    w = csv.DictWriter(buf, fieldnames=cols, extrasaction="ignore")
    w.writeheader()
    for a in appts:
        w.writerow({k: a.get(k, "") for k in cols})
    return buf.getvalue()


def _appointments_to_html(appts: list) -> str:
    head = "".join(f"<th style='border:1px solid #ddd;padding:6px;text-align:left'>{escape(h)}</th>"
                    for h in ["Fecha", "Hora", "Servicio", "Cliente", "Teléfono", "Estado"])
    rows = []
    for a in appts:
        cells = [a.get("date", ""), f"{a.get('start','')}–{a.get('end','')}", a.get("service_name", ""),
                 a.get("client_name", ""), a.get("client_phone", ""), a.get("status", "")]
        rows.append("<tr>" + "".join(
            f"<td style='border:1px solid #ddd;padding:6px'>{escape(str(c))}</td>" for c in cells) + "</tr>")
    return (f"<table style='border-collapse:collapse;font-family:Arial,sans-serif;font-size:13px'>"
            f"<thead><tr>{head}</tr></thead><tbody>{''.join(rows)}</tbody></table>")


async def _send_backup_email(subject: str, html: str, attachments: list) -> bool:
    if not SMTP_HOST or not SMTP_USER or not SMTP_PASSWORD:
        logger.warning("SMTP no configurado (SMTP_HOST/SMTP_USER/SMTP_PASSWORD); backup no enviado por email")
        return False
    import aiosmtplib
    from email.message import EmailMessage
    msg = EmailMessage()
    msg["From"] = f"{EMAIL_FROM_NAME} <{BACKUP_EMAIL_FROM}>"
    msg["To"] = BACKUP_EMAIL_TO
    msg["Subject"] = subject
    msg.set_content("Backup diario de citas de +58 BarberStudio. Abre este correo en un cliente compatible con HTML.")
    msg.add_alternative(html, subtype="html")
    for filename, data, mime in attachments:
        maintype, subtype = mime.split("/", 1)
        msg.add_attachment(data.encode("utf-8"), maintype=maintype, subtype=subtype, filename=filename)
    kwargs = {"hostname": SMTP_HOST, "port": SMTP_PORT, "username": SMTP_USER, "password": SMTP_PASSWORD}
    if SMTP_PORT == 465:
        kwargs["use_tls"] = True
    else:
        kwargs["start_tls"] = True
    try:
        await aiosmtplib.send(msg, **kwargs)
        logger.info("Backup enviado por email a %s vía %s", BACKUP_EMAIL_TO, SMTP_HOST)
        return True
    except Exception as e:
        logger.error("Error enviando backup por SMTP (%s:%s): %s", SMTP_HOST, SMTP_PORT, e)
        return False


async def run_backup() -> dict:
    import json
    appts = await db.appointments.find({}, {"_id": 0}).sort([("date", 1), ("start", 1)]).to_list(10000)
    today = datetime.now(ZoneInfo("Atlantic/Canary")).strftime("%Y-%m-%d")
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    fname = f"backup_citas_{today}.json"
    json_text = json.dumps(appts, ensure_ascii=False, indent=2)
    (BACKUP_DIR / fname).write_text(json_text, encoding="utf-8")
    csv_text = _appointments_to_csv(appts)
    html = (
        f'<div style="font-family:Arial,sans-serif">'
        f"<p>Backup diario de <strong>{escape(EMAIL_FROM_NAME)}</strong> — {escape(today)}.</p>"
        f"<p>Total de citas: <strong>{len(appts)}</strong>. "
        "Adjunto el JSON completo (restaurable) y el CSV. Tabla resumen debajo.</p>"
        f"{_appointments_to_html(appts)}"
        '<p style="font-size:12px;color:#888;margin-top:16px">Copia automática de seguridad. '
        "Consérvala por si necesitas restaurar citas modificadas o canceladas.</p></div>"
    )
    emailed = await _send_backup_email(
        subject=f"Backup de citas {today} — {EMAIL_FROM_NAME}",
        html=html,
        attachments=[(fname, json_text, "application/json"),
                     (f"backup_citas_{today}.csv", csv_text, "text/csv")],
    )
    logger.info("Backup: %d citas exportadas a %s (email=%s)", len(appts), fname, emailed)
    return {"count": len(appts), "file": fname, "emailed": emailed}


@api.api_route("/cron/backup", methods=["GET", "POST"])
async def cron_backup(request: Request, background: BackgroundTasks):
    # Cron endpoints must ack 2xx immediately; enqueue/background the actual work.
    auth = request.headers.get("authorization", "")
    token = auth.removeprefix("Bearer ").strip()
    if not WEBHOOK_CRON_SECRET or not token or not hmac.compare_digest(token, WEBHOOK_CRON_SECRET):
        raise HTTPException(401, "No autorizado")
    background.add_task(run_backup)
    return {"ok": True}


@api.get("/business")
async def business_info():
    return {
        "name": os.environ.get("BUSINESS_NAME", "+58 BarberStudio"),
        "phone": os.environ.get("BUSINESS_PHONE", ""),
        "whatsapp": os.environ.get("BUSINESS_WHATSAPP", ""),
        "instagram": os.environ.get("BUSINESS_INSTAGRAM", ""),
        "address": os.environ.get("BUSINESS_ADDRESS", "Avenida de Los Majuelos 51C, 38008, Taco, Santa Cruz de Tenerife"),
        "maps_query": os.environ.get("BUSINESS_MAPS_QUERY", "Multitienda Veloz 24hr, Avenida de Los Majuelos 51C, 38008, Taco, Santa Cruz de Tenerife"),
        "reviews_url": os.environ.get("BUSINESS_REVIEWS_URL", "https://g.page/r/Ccfra4SBDdjCEBM/review"),
        "rating": os.environ.get("BUSINESS_RATING", "5,0"),
        "reviews_count": os.environ.get("BUSINESS_REVIEWS_COUNT", ""),
        "barber_name": os.environ.get("BUSINESS_BARBER_NAME", "Heber"),
    }

@api.get("/")
async def root():
    return {"message": "+58 BarberStudio API"}


# --- WhatsApp Webhook (Meta) ---
WHATSAPP_VERIFY_TOKEN = os.environ.get("WHATSAPP_VERIFY_TOKEN", "")
META_APP_SECRET = os.environ.get("META_APP_SECRET", "")

@api.get("/whatsapp/webhook")
async def whatsapp_webhook_verify(request: Request):
    # Meta llama con GET para verificar. Devolvemos hub.challenge si el token coincide.
    params = request.query_params
    mode = params.get("hub.mode")
    token = params.get("hub.verify_token")
    challenge = params.get("hub.challenge", "")
    if mode == "subscribe" and token and WHATSAPP_VERIFY_TOKEN and hmac.compare_digest(token, WHATSAPP_VERIFY_TOKEN):
        return PlainTextResponse(content=challenge, status_code=200)
    raise HTTPException(403, "Verificación fallida")

@api.post("/whatsapp/webhook")
async def whatsapp_webhook_receive(request: Request, background: BackgroundTasks):
    # Validamos la firma de Meta con el App Secret y respondemos 200 rápido.
    raw = await request.body()
    signature = request.headers.get("x-hub-signature-256", "")
    firma_ok = True
    if META_APP_SECRET:
        expected = "sha256=" + hmac.new(META_APP_SECRET.encode(), raw, hashlib.sha256).hexdigest()
        firma_ok = bool(signature) and hmac.compare_digest(signature, expected)
    try:
        await db.webhook_log.insert_one({
            "id": new_id(), "ts": now_iso(), "firma_ok": firma_ok,
            "payload": raw[:400].decode("utf-8", "replace"),
        })
    except Exception as e:
        logger.error("webhook_log error: %s", e)
    if not firma_ok:
        raise HTTPException(403, "Firma inválida")
    # Reenvío de mensajes entrantes al barbero (los 'status' de entrega/lectura se ignoran).
    try:
        data = json.loads(raw)
    except Exception:
        return {"ok": True}
    for entry in data.get("entry", []):
        for change in entry.get("changes", []):
            value = change.get("value", {})
            contacts = {c.get("wa_id"): (c.get("profile") or {}).get("name", "") for c in value.get("contacts", [])}
            for msg in value.get("messages", []):
                de = msg.get("from", "")
                tipo = msg.get("type", "")
                texto = (msg.get("text") or {}).get("body", "") if tipo == "text" else f"[mensaje de tipo {tipo}]"
                if not de or not texto:
                    continue
                palabra = texto.strip().lower()
                if tipo == "text" and palabra in ("stop", "baja"):
                    background.add_task(gestionar_opt_out, de, True)
                    continue
                if tipo == "text" and palabra == "alta":
                    background.add_task(gestionar_opt_out, de, False)
                    continue
                background.add_task(whatsapp_bot.reenviar_respuesta_cliente, de, contacts.get(de, "Cliente"), texto)
                background.add_task(autoresponder_cliente, de)
    return {"ok": True}


async def wa_opt_out(telefono: str) -> bool:
    tel = whatsapp_bot.normalizar_telefono(telefono)
    doc = await db.whatsapp_optout.find_one({"phone": tel}, {"_id": 0})
    return bool(doc and doc.get("opt_out"))


async def gestionar_opt_out(de_telefono: str, baja: bool) -> None:
    # STOP/BAJA: marca opt-out y confirma (la ventana 24h está abierta porque el cliente acaba de escribir).
    # ALTA: reactiva los mensajes.
    tel = whatsapp_bot.normalizar_telefono(de_telefono)
    await db.whatsapp_optout.update_one(
        {"phone": tel},
        {"$set": {"phone": tel, "opt_out": baja, "ts": now_iso()}},
        upsert=True,
    )
    logger.info("WhatsApp opt-out=%s para ***%s", baja, tel[-4:])
    if baja:
        await whatsapp_bot.enviar_whatsapp(tel, "Has sido dado de baja de los mensajes de WhatsApp de +58 BarberStudio. Responde ALTA para reactivarlos.")
    else:
        await whatsapp_bot.enviar_whatsapp(tel, "Has reactivado los mensajes de WhatsApp de +58 BarberStudio ✅")


AUTOREPLY_MSG = (
    "💈 ¡Hola! Gracias por escribir a +58 BarberStudio ✂️\n\n"
    "El barbero está trabajando en dejar bello a otro cliente 💇‍♂️✨, por eso este número es solo para enviar "
    "confirmaciones y recordatorios de citas. Por favor, no respondas a este mensaje, ya que no será leído.\n\n"
    "📅 Si necesitas gestionar, cancelar o agregar una cita, hazlo fácilmente a través de nuestra web:\n"
    "👉 https://www.58barberstudio.com\n\n"
    "📞 Si necesitas ayuda personal, puedes llamar al barbero al 614 18 40 14.\n\n"
    "¡Gracias por tu comprensión! 🙏💙"
)


async def autoresponder_cliente(de_telefono: str) -> None:
    # Auto-respuesta a cualquier mensaje del cliente (texto libre: la ventana 24h la abre su propio mensaje).
    # Máximo una vez cada 24h por número para no spamear.
    tel = whatsapp_bot.normalizar_telefono(de_telefono)
    try:
        ultimo = await db.autoreplies.find_one({"phone": tel}, {"_id": 0})
        if ultimo:
            try:
                if datetime.now() - datetime.fromisoformat(ultimo["ts"]) < timedelta(hours=24):
                    return
            except Exception:
                pass
        await db.autoreplies.update_one({"phone": tel}, {"$set": {"phone": tel, "ts": now_iso()}}, upsert=True)
        await whatsapp_bot.enviar_whatsapp(tel, AUTOREPLY_MSG)
    except Exception as e:
        logger.error("autoresponder_cliente error: %s", e)


@api.post("/whatsapp/test")
async def whatsapp_test_envio(body: dict, admin=Depends(get_current_admin)):
    # Diagnóstico (admin): envía plantilla de prueba y devuelve la respuesta exacta de Meta.
    telefono = (body.get("telefono") or "").strip()
    if not telefono:
        raise HTTPException(400, "Falta 'telefono'")
    return await whatsapp_bot.probar_envio(
        telefono,
        (body.get("plantilla") or "").strip(),
        (body.get("lang") or "").strip(),
        body.get("params"),
        (body.get("texto") or "").strip(),
    )


@api.get("/whatsapp/webhook-log")
async def whatsapp_webhook_log(admin=Depends(get_current_admin)):
    # Diagnóstico (admin): últimos 20 eventos recibidos en el webhook, con resultado de firma.
    return await db.webhook_log.find({}, {"_id": 0}).sort("ts", -1).to_list(20)


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
    allow_origin_regex=os.environ.get("CORS_ORIGIN_REGEX", r"https?://.*"),
    allow_methods=["*"],
    allow_headers=["*"],
)


# --- Startup: seed ---
@app.on_event("startup")
async def on_start():
    await db.schedule_overrides.create_index("date", unique=True)
    # Seed admin (acceso por nombre de usuario, sin email)
    existing = await db.users.find_one({"username": ADMIN_USER})
    if not existing:
        old = await db.users.find_one({"role": "admin"})
        if old:
            await db.users.update_one(
                {"id": old["id"]},
                {"$set": {"username": ADMIN_USER, "email": ADMIN_EMAIL.lower(), "password_hash": hash_pw(ADMIN_PASSWORD)}},
            )
            logger.info("Admin migrado a usuario: %s", ADMIN_USER)
        else:
            await db.users.insert_one({
                "id": new_id(),
                "username": ADMIN_USER,
                "email": ADMIN_EMAIL.lower(),
                "password_hash": hash_pw(ADMIN_PASSWORD),
                "role": "admin",
                "name": "Barbero",
                "created_at": now_iso(),
            })
            logger.info("Admin seeded: %s", ADMIN_USER)
    else:
        # Keep password and owner email in sync with .env
        upd = {}
        if not verify_pw(ADMIN_PASSWORD, existing["password_hash"]):
            upd["password_hash"] = hash_pw(ADMIN_PASSWORD)
        if ADMIN_EMAIL and existing.get("email") != ADMIN_EMAIL.lower():
            upd["email"] = ADMIN_EMAIL.lower()
        if upd:
            await db.users.update_one({"username": ADMIN_USER}, {"$set": upd})
            logger.info("Admin actualizado desde env")

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
