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

class LunchBreakIn(BaseModel):
    enabled: bool = True
    start: str = "13:00"   # "HH:MM"
    end: str = "14:00"

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

DEFAULT_LUNCH = {"enabled": True, "start": "13:00", "end": "14:00"}

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
        return {"days": DEFAULT_WORKING_HOURS, "lunch": DEFAULT_LUNCH}
    return {"days": doc.get("days", DEFAULT_WORKING_HOURS), "lunch": doc.get("lunch", DEFAULT_LUNCH)}

@api.put("/working-hours")
async def set_working_hours(body: WorkingHoursIn, admin=Depends(get_current_admin)):
    await db.working_hours.update_one(
        {"id": "default"},
        {"$set": {"id": "default", "days": body.days, "updated_at": now_iso()}},
        upsert=True,
    )
    return {"days": body.days}

@api.put("/lunch-break")
async def set_lunch_break(body: LunchBreakIn, admin=Depends(get_current_admin)):
    lunch = body.model_dump()
    await db.working_hours.update_one(
        {"id": "default"},
        {"$set": {"id": "default", "lunch": lunch, "updated_at": now_iso()}},
        upsert=True,
    )
    return {"lunch": lunch}


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

    # Descanso de almuerzo (se aplica todos los días si está activado)
    wh_doc = await db.working_hours.find_one({"id": "default"}, {"_id": 0})
    lunch = (wh_doc or {}).get("lunch") or {"enabled": False}
    if lunch.get("enabled") and lunch.get("start") and lunch.get("end"):
        busy.append((parse_hhmm(lunch["start"]), parse_hhmm(lunch["end"])))

    slots = []
    # If today, don't offer past slots (Europe/Madrid ~ UTC+1 winter; keep simple with local now)
    now = datetime.now()
    today_min = now.hour * 60 + now.minute if d == now.date() else -1

    t = start_m
    while t + duration_min <= end_m:
        if today_min < t:
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
    created = []
    for p in parsed:
        try:
            result = await create_appointment(p)
            created.append(result)
        except HTTPException as e:
            logger.warning(f"Batch item failed: {e.detail}")
            continue
    return {"ok": True, "created": created, "count": len(created)}


class ForceAppointmentIn(BaseModel):
    service_id: str
    date: str
    start: str
    client_name: str
    client_phone: str
    client_nickname: Optional[str] = ""


@api.post("/appointments/force")
async def force_appointment(body: ForceAppointmentIn, admin=Depends(get_current_admin)):
    """Fuerza una cita sin validar disponibilidad (admin only)."""
    svc = await db.services.find_one({"id": body.service_id}, {"_id": 0})
    if not svc:
        raise HTTPException(404, "Servicio no encontrado")
    
    start_m = parse_hhmm(body.start)
    end_m = start_m + svc["duration_min"]
    
    # Upsert client
    identity_name = body.client_name
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
        "client_email": "",
        "booker_name": "",
        "status": "confirmed",
        "confirmado": False,
        "recordatorio_enviado": False,
        "opt_in_whatsapp": False,
        "opt_in_fecha": now_iso(),
        "created_at": now_iso(),
    }
    await db.appointments.insert_one(appt.copy())
    appt.pop("_id", None)
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
    elif to_date:
        q["date"] = {"$lte": to_date}
    docs = await db.appointments.find(q, {"_id": 0}).sort("date", 1).to_list(1000)
    return docs

@api.post("/appointments/{aid}/cancel")
async def cancel_by_client(aid: str, phone: str):
    appt = await db.appointments.find_one({"id": aid}, {"_id": 0})
    if not appt:
        raise HTTPException(404, "Cita no encontrada")
    if appt["client_phone"] != phone:
        raise HTTPException(403, "Teléfono no coincide")
    appt_time = datetime.fromisoformat(f"{appt['date']}T{appt['start']}")
    if (appt_time - datetime.now()).total_seconds() < 12 * 3600:
        raise HTTPException(400, "No puedes cancelar menos de 12 horas antes")
    await db.appointments.update_one({"id": aid}, {"$set": {"status": "cancelled"}})
    appt["status"] = "cancelled"
    asyncio.create_task(whatsapp_bot.notificar_cambio_cita(appt, "cancelacion"))
    return {"ok": True}

@api.post("/appointments/gestionar")
async def gestionar_lookup(body: dict):
    code = body.get("code", "")
    phone = body.get("phone", "")
    # Busca por ID (primeros 8 chars) y teléfono
    appt = await db.appointments.find_one({
        "id": {"$regex": f"^{re.escape(code)}"},
        "client_phone": phone,
    }, {"_id": 0})
    if not appt:
        raise HTTPException(404, "Cita no encontrada")
    return appt

@api.post("/appointments/{aid}/modificar")
async def modificar_cita(aid: str, body: dict):
    phone = body.get("phone", "")
    new_date = body.get("date")
    new_start = body.get("start")
    
    appt = await db.appointments.find_one({"id": aid}, {"_id": 0})
    if not appt:
        raise HTTPException(404, "Cita no encontrada")
    if appt["client_phone"] != phone:
        raise HTTPException(403, "Teléfono no coincide")
    
    # Check 12h rule
    appt_time = datetime.fromisoformat(f"{appt['date']}T{appt['start']}")
    if (appt_time - datetime.now()).total_seconds() < 12 * 3600:
        raise HTTPException(400, "No puedes modificar menos de 12 horas antes")
    
    # Verify new slot available
    svc = await db.services.find_one({"id": appt["service_id"]}, {"_id": 0})
    slots = await _compute_slots(new_date, svc["duration_min"])
    if new_start not in slots:
        raise HTTPException(409, "La hora no está disponible")
    
    # Update
    start_m = parse_hhmm(new_start)
    end_m = start_m + svc["duration_min"]
    await db.appointments.update_one({"id": aid}, {"$set": {
        "date": new_date,
        "start": new_start,
        "end": fmt_hhmm(end_m),
    }})
    
    appt["date"] = new_date
    appt["start"] = new_start
    appt["end"] = fmt_hhmm(end_m)
    asyncio.create_task(whatsapp_bot.notificar_cambio_cita(appt, "modificacion"))
    return appt

@api.post("/appointments/{aid}/admin-cancel")
async def cancel_by_admin(aid: str, admin=Depends(get_current_admin)):
    await db.appointments.update_one({"id": aid}, {"$set": {"status": "cancelled"}})
    appt = await db.appointments.find_one({"id": aid}, {"_id": 0})
    if appt:
        asyncio.create_task(whatsapp_bot.notificar_cambio_cita(appt, "cancelacion"))
    return {"ok": True}


# --- Clients ---
@api.get("/clients")
async def list_clients(admin=Depends(get_current_admin)):
    docs = await db.clients.find({}, {"_id": 0}).sort("created_at", -1).to_list(500)
    return docs

@api.get("/clients/{cid}/appointments")
async def client_appointments(cid: str, admin=Depends(get_current_admin)):
    docs = await db.appointments.find({"client_id": cid}, {"_id": 0}).sort("date", -1).to_list(500)
    return docs

@api.delete("/clients/{cid}")
async def delete_client(cid: str, admin=Depends(get_current_admin)):
    await db.clients.delete_one({"id": cid})
    return {"ok": True}


# --- Confirmación y recordatorios ---
def _reminder_msg(a: dict) -> str:
    return f"¡Hola {a['client_name']}! Mañana te espero en +58 BarberStudio a las {a['start']}. Código: {a['id'][:8]}"

@api.post("/appointments/{aid}/confirmar")
async def confirmar_cita(aid: str, admin=Depends(get_current_admin)):
    await db.appointments.update_one({"id": aid}, {"$set": {"confirmado": True}})
    return {"ok": True}

@api.post("/appointments/{aid}/recordatorio")
async def recordatorio_send(aid: str, admin=Depends(get_current_admin)):
    appt = await db.appointments.find_one({"id": aid}, {"_id": 0})
    if not appt:
        raise HTTPException(404, "Cita no encontrada")
    if await is_opted_out(appt["client_phone"]):
        return {"ok": False, "sent": False, "error": "El cliente está dado de baja de WhatsApp (STOP)"}
    sent = await whatsapp_bot.enviar_a(appt["client_phone"], "recordatorio", appt)
    if sent:
        await db.appointments.update_one({"id": aid}, {"$set": {"recordatorio_enviado": True}})
    return {"ok": True, "sent": sent}


# --- Email ---
EMAIL_FROM_NAME = os.environ.get("EMAIL_FROM_NAME", "+58 BarberStudio")
EMAIL_REPLY_TO = os.environ.get("EMAIL_REPLY_TO")

_SHORTENERS = ("bit.ly", "tinyurl.com", "t.co", "is.gd", "cutt.ly", "goo.gl", "rebrand.ly")
_CRED_ASK = ("reply with your password", "reply with the code", "send your password", "cvv",
             "contraseña", "código", "clave", "cvv", "tarjeta", "card")
_HOSTISH = re.compile(r"\b(?:https?://)?((?:[a-z0-9-]+\.)+[a-z]{2,})", re.I)

def _host_ok(host: str) -> bool:
    """Whitelist of trusted domains."""
    trusted = ("58barberstudio.com", "google.com", "github.com", "railway.app", "emergentagent.com")
    return any(host.endswith(t) for t in trusted)

def _same_site(shown: str, real: str) -> bool:
    return shown == real or real.endswith("." + shown) or shown.endswith("." + real)

class _EmailScan(HTMLParser):
    def __init__(self):
        super().__init__()
        self._href = None
        self._text = []
        self.links = []
    
    def handle_starttag(self, tag, attrs):
        if tag == "a":
            self._href = dict(attrs).get("href")
    
    def handle_data(self, data):
        if self._href is not None:
            self._text.append(data)
    
    def handle_endtag(self, tag):
        if tag == "a" and self._href:
            self.links.append((self._href, "".join(self._text).strip()))
            self._href = None
            self._text = []

def _assert_safe_email(subject: str, html: str) -> None:
    """Detect phishing patterns in email."""
    if any(w.lower() in subject.lower() for w in _CRED_ASK):
        raise ValueError("Subject requests credentials (phishing risk)")
    
    scan = _EmailScan()
    try:
        scan.feed(html)
    except Exception:
        pass
    
    for href, text in scan.links:
        try:
            parsed = urlparse(href)
            shown_host = text.split("://")[-1].split("/")[0] if text.startswith(("http", "www")) else text
            real_host = parsed.netloc or parsed.path.split("/")[0]
            
            if not _host_ok(real_host) or not _same_site(shown_host, real_host):
                raise ValueError(f"Link mismatch: shown={shown_host}, real={real_host}")
        except Exception as e:
            raise ValueError(f"Link validation failed: {e}")

async def send_email(*, to: str, subject: str, html: str, reply_to: Optional[str] = None) -> bool:
    """Send email via SMTP."""
    _assert_safe_email(subject, html)
    
    smtp_host = os.environ.get("SMTP_HOST", "")
    smtp_port = int(os.environ.get("SMTP_PORT", "465"))
    smtp_user = os.environ.get("SMTP_USER", "")
    smtp_password = os.environ.get("SMTP_PASSWORD", "")
    
    if not all([smtp_host, smtp_user, smtp_password]):
        logger.warning("Email no configurado (falta SMTP_*)")
        return False
    
    try:
        import aiosmtplib
        from email.mime.text import MIMEText
        from email.mime.multipart import MIMEMultipart
        
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = f"{EMAIL_FROM_NAME} <{smtp_user}>"
        msg["To"] = to
        if reply_to:
            msg["Reply-To"] = reply_to
        
        msg.attach(MIMEText(html, "html"))
        
        async with aiosmtplib.SMTP(hostname=smtp_host, port=smtp_port) as smtp:
            await smtp.login(smtp_user, smtp_password)
            await smtp.send_message(msg)
        return True
    except Exception as e:
        logger.error(f"Email error: {e}")
        return False


# --- Cron ---
WEBHOOK_CRON_SECRET = os.environ.get("WEBHOOK_CRON_SECRET", "")

async def run_recordatorios() -> int:
    """Envía recordatorios a citas de mañana."""
    tomorrow = (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d")
    appts = await db.appointments.find({
        "date": tomorrow,
        "status": "confirmed",
        "recordatorio_enviado": False,
    }, {"_id": 0}).to_list(500)
    
    sent = 0
    for a in appts:
        if await is_opted_out(a["client_phone"]):
            continue
        if await whatsapp_bot.enviar_a(a["client_phone"], "recordatorio", a):
            await db.appointments.update_one({"id": a["id"]}, {"$set": {"recordatorio_enviado": True}})
            sent += 1
    
    logger.info(f"Recordatorios enviados: {sent}/{len(appts)}")
    return sent

@api.post("/cron/recordatorios")
async def cron_recordatorios(request: Request, background: BackgroundTasks):
    """Webhook de cron (requiere bearer token)."""
    auth = request.headers.get("Authorization", "")
    expected = os.environ.get("WEBHOOK_CRON_SECRET", "")
    if not expected or not auth.startswith("Bearer "):
        raise HTTPException(401, "Sin autenticación")
    
    token = auth.split(" ", 1)[1]
    if not hmac.compare_digest(token, expected):
        raise HTTPException(401, "Token inválido")
    
    background.add_task(run_recordatorios)
    return {"ok": True}

@api.post("/send-reminders")
async def send_reminders(request: Request, background: BackgroundTasks):
    """Endpoint interno para enviar recordatorios."""
    background.add_task(run_recordatorios)
    return {"ok": True}


# --- Backup ---
BACKUP_EMAIL_TO = os.environ.get("BACKUP_EMAIL_TO", "info@58barberstudio.com")
SMTP_HOST = os.environ.get("SMTP_HOST", "")
SMTP_PORT = int(os.environ.get("SMTP_PORT", "465"))
SMTP_USER = os.environ.get("SMTP_USER", "")
SMTP_PASSWORD = os.environ.get("SMTP_PASSWORD", "")
BACKUP_EMAIL_FROM = os.environ.get("BACKUP_EMAIL_FROM", SMTP_USER)
BACKUP_DIR = ROOT_DIR.parent / "memory"

def _appointments_to_csv(appts: list) -> str:
    """Convert appointments to CSV."""
    import csv
    import io
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=["id", "date", "start", "end", "client_name", "client_phone", "service_name", "status"])
    writer.writeheader()
    for a in appts:
        writer.writerow({
            "id": a["id"],
            "date": a["date"],
            "start": a["start"],
            "end": a["end"],
            "client_name": a["client_name"],
            "client_phone": a["client_phone"],
            "service_name": a["service_name"],
            "status": a["status"],
        })
    return output.getvalue()

def _appointments_to_html(appts: list) -> str:
    """Convert appointments to HTML table."""
    html = "<table border='1'><tr><th>Fecha</th><th>Hora</th><th>Cliente</th><th>Teléfono</th><th>Servicio</th><th>Estado</th></tr>"
    for a in appts:
        html += f"<tr><td>{a['date']}</td><td>{a['start']}-{a['end']}</td><td>{a['client_name']}</td><td>{a['client_phone']}</td><td>{a['service_name']}</td><td>{a['status']}</td></tr>"
    html += "</table>"
    return html

async def _send_backup_email(subject: str, html: str, attachments: list) -> bool:
    """Send backup email."""
    if not SMTP_HOST or not SMTP_USER:
        logger.warning("SMTP no configurado para backup")
        return False
    
    try:
        import aiosmtplib
        from email.mime.text import MIMEText
        from email.mime.multipart import MIMEMultipart
        from email.mime.base import MIMEBase
        from email import encoders
        
        msg = MIMEMultipart()
        msg["Subject"] = subject
        msg["From"] = BACKUP_EMAIL_FROM
        msg["To"] = BACKUP_EMAIL_TO
        
        msg.attach(MIMEText(html, "html"))
        
        for filename, content in attachments:
            part = MIMEBase("application", "octet-stream")
            part.set_payload(content)
            encoders.encode_base64(part)
            part.add_header("Content-Disposition", f"attachment; filename= {filename}")
            msg.attach(part)
        
        async with aiosmtplib.SMTP(hostname=SMTP_HOST, port=SMTP_PORT) as smtp:
            await smtp.login(SMTP_USER, SMTP_PASSWORD)
            await smtp.send_message(msg)
        return True
    except Exception as e:
        logger.error(f"Backup email error: {e}")
        return False

async def run_backup() -> dict:
    """Create and send backup."""
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    today = datetime.now().strftime("%Y-%m-%d")
    
    appts = await db.appointments.find({}, {"_id": 0}).to_list(5000)
    
    # JSON backup
    json_file = BACKUP_DIR / f"backup_citas_{today}.json"
    json_file.write_text(json.dumps(appts, indent=2, default=str))
    
    # CSV backup
    csv_content = _appointments_to_csv(appts)
    
    # Send email
    html = _appointments_to_html(appts)
    await _send_backup_email(
        f"Backup citas {today}",
        f"<p>Backup de citas del {today}. Total: {len(appts)}</p>{html}",
        [
            (f"citas_{today}.json", json.dumps(appts, indent=2, default=str).encode()),
            (f"citas_{today}.csv", csv_content.encode()),
        ]
    )
    
    return {"ok": True, "count": len(appts), "file": str(json_file)}

@api.post("/cron/backup")
async def cron_backup(request: Request, background: BackgroundTasks):
    """Backup cron endpoint."""
    auth = request.headers.get("Authorization", "")
    expected = os.environ.get("WEBHOOK_CRON_SECRET", "")
    if not expected or not auth.startswith("Bearer "):
        raise HTTPException(401, "Sin autenticación")
    
    token = auth.split(" ", 1)[1]
    if not hmac.compare_digest(token, expected):
        raise HTTPException(401, "Token inválido")
    
    background.add_task(run_backup)
    return {"ok": True}


# --- Public endpoints ---
@api.get("/business")
async def business_info():
    return {
        "name": "+58 BarberStudio",
        "phone": "+34922 252 090",
        "whatsapp": "+34664 345 827",
        "address": "Avenida de Los Majuelos 51C, 38008, Taco, Santa Cruz de Tenerife",
        "barber_name": "Heber",
    }

@api.get("/")
async def root():
    return {"message": "+58 BarberStudio API"}


# --- WhatsApp ---
WHATSAPP_VERIFY_TOKEN = os.environ.get("WHATSAPP_VERIFY_TOKEN", "")
META_APP_SECRET = os.environ.get("META_APP_SECRET", "")

@api.get("/whatsapp/webhook")
async def whatsapp_webhook_verify(request: Request):
    """WhatsApp webhook verification."""
    mode = request.query_params.get("hub.mode")
    token = request.query_params.get("hub.verify_token")
    challenge = request.query_params.get("hub.challenge")
    
    if mode == "subscribe" and token == WHATSAPP_VERIFY_TOKEN:
        return PlainTextResponse(challenge)
    
    raise HTTPException(403, "Webhook verification failed")

@api.post("/whatsapp/webhook")
async def whatsapp_webhook_receive(request: Request, background: BackgroundTasks):
    """Receive WhatsApp messages."""
    body = await request.json()
    # Validate signature
    sig = request.headers.get("X-Hub-Signature-256", "")
    payload = await request.body()
    expected = f"sha256={hmac.new(META_APP_SECRET.encode(), payload, hashlib.sha256).hexdigest()}"
    if not hmac.compare_digest(sig, expected):
        raise HTTPException(403, "Invalid signature")
    
    # Process message (background task)
    background.add_task(_process_whatsapp_message, body)
    return {"ok": True}

async def _process_whatsapp_message(body: dict):
    """Process incoming WhatsApp message."""
    try:
        entry = body.get("entry", [{}])[0]
        changes = entry.get("changes", [{}])
        if not changes:
            return
        
        messages = changes[0].get("value", {}).get("messages", [])
        if not messages:
            return
        
        msg = messages[0]
        de = msg.get("from")
        texto = msg.get("text", {}).get("body", "")
        
        if not de or not texto:
            return
        
        # Log webhook
        await db.whatsapp_webhook_log.insert_one({
            "from": de,
            "text": texto,
            "ts": now_iso(),
        })
        
        # Get client name from DB
        client = await db.clients.find_one({"phone": de}, {"_id": 0})
        nombre = client["name"] if client else f"Cliente {de[-4:]}"
        
        # Forward to barber
        await whatsapp_bot.reenviar_respuesta_cliente(de, nombre, texto)
    except Exception as e:
        logger.error(f"WhatsApp webhook error: {e}")

async def wa_opt_out(telefono: str) -> bool:
    """Mark phone as opted out."""
    tel_norm = whatsapp_bot.normalizar_telefono(telefono)
    await db.whatsapp_optout.update_one(
        {"phone": tel_norm},
        {"$set": {"phone": tel_norm, "opt_out": True, "ts": now_iso()}},
        upsert=True,
    )
    return True

async def is_opted_out(telefono: str) -> bool:
    """Comprueba (sin modificar nada) si el teléfono está dado de baja de WhatsApp."""
    tel_norm = whatsapp_bot.normalizar_telefono(telefono)
    doc = await db.whatsapp_optout.find_one({"phone": tel_norm}, {"_id": 0})
    return bool(doc and doc.get("opt_out"))

async def gestionar_opt_out(de_telefono: str, baja: bool) -> None:
    """Handle opt-out requests."""
    if baja:
        await wa_opt_out(de_telefono)

AUTOREPLY_MSG = (
    "¡Hola! Gracias por tu mensaje. En breve nos pondremos en contacto contigo. "
    "Si tienes una cita, puedes modificarla o cancelarla aquí: "
    "https://www.58barberstudio.com/reservar#gestionar"
)

async def autoresponder_cliente(de_telefono: str) -> None:
    """Send autoresponse to client."""
    await whatsapp_bot.enviar_whatsapp(de_telefono, AUTOREPLY_MSG)

@api.post("/whatsapp/test-envio")
async def whatsapp_test_envio(body: dict, admin=Depends(get_current_admin)):
    """Test WhatsApp sending."""
    telefono = body.get("phone", "")
    plantilla = body.get("template", "")
    params = body.get("params", [])
    texto = body.get("text", "")
    
    result = await whatsapp_bot.probar_envio(telefono, plantilla, "", params, texto)
    return result

@api.get("/whatsapp/webhook-log")
async def whatsapp_webhook_log(admin=Depends(get_current_admin)):
    """Get WhatsApp webhook log."""
    logs = await db.whatsapp_webhook_log.find({}, {"_id": 0}).sort("ts", -1).limit(100).to_list(100)
    return logs


# --- App lifecycle ---
@api.get("/app")
async def app_root():
    return {"message": "+58 BarberStudio"}

async def _recordatorios_scheduler():
    """Lanza run_recordatorios() todos los días a las 18:00 (Atlantic/Canary),
    sustituyendo la dependencia de cron-job.org por un scheduler interno."""
    tz = ZoneInfo("Atlantic/Canary")
    while True:
        try:
            now = datetime.now(tz)
            target = now.replace(hour=18, minute=0, second=0, microsecond=0)
            if target <= now:
                target += timedelta(days=1)
            wait_seconds = (target - now).total_seconds()
            logger.info("Recordatorios: próxima ejecución en %.0f s (%s)", wait_seconds, target.isoformat())
            await asyncio.sleep(wait_seconds)
            sent = await run_recordatorios()
            logger.info("Recordatorios (scheduler interno): %d enviados", sent)
        except Exception as e:
            logger.error("Error en scheduler de recordatorios: %s", e)
            await asyncio.sleep(60)  # evita bucle de error inmediato; reintenta en 1 min

@app.on_event("startup")
async def on_start():
    logger.info("Backend iniciado")
    # Ensure indexes
    await db.appointments.create_index("date")
    await db.appointments.create_index("client_phone")
    await db.services.create_index("id", unique=True)
    await db.users.create_index("username", unique=True)
    asyncio.create_task(_recordatorios_scheduler())

@app.on_event("shutdown")
async def shutdown_db_client():
    client.close()

# Register API router
app.include_router(api)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
