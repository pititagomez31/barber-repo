from dotenv import load_dotenv
from pathlib import Path

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

import os
import uuid
import logging
import bcrypt
import jwt
from datetime import datetime, timezone, timedelta
from typing import List, Optional
from fastapi import FastAPI, APIRouter, HTTPException, Depends, Request, status
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
    status: str
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
@api.post("/appointments", response_model=AppointmentOut)
async def create_appointment(body: AppointmentIn):
    if not body.accepted_policy:
        raise HTTPException(400, "Debes aceptar la política del 50%")
    svc = await db.services.find_one({"id": body.service_id}, {"_id": 0})
    if not svc:
        raise HTTPException(404, "Servicio no encontrado")

    # Re-check availability atomically-ish
    slots = await _compute_slots(body.date, svc["duration_min"])
    if body.start not in slots:
        raise HTTPException(409, "Esa hora ya no está disponible, elige otra")

    start_m = parse_hhmm(body.start)
    end_m = start_m + svc["duration_min"]

    # Upsert client
    client_doc = await db.clients.find_one({"phone": body.client_phone}, {"_id": 0})
    if not client_doc:
        client_doc = {
            "id": new_id(),
            "name": body.client_name,
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
        "status": "confirmed",
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


# --- Business info (public) ---
@api.get("/business")
async def business_info():
    return {
        "name": os.environ.get("BUSINESS_NAME", "+58 BarberStudio"),
        "phone": os.environ.get("BUSINESS_PHONE", ""),
        "whatsapp": os.environ.get("BUSINESS_WHATSAPP", ""),
        "instagram": os.environ.get("BUSINESS_INSTAGRAM", ""),
        "address": os.environ.get("BUSINESS_ADDRESS", ""),
        "reviews_url": os.environ.get("BUSINESS_REVIEWS_URL", ""),
        "barber_name": os.environ.get("BUSINESS_BARBER_NAME", "Heber"),
    }

@api.get("/")
async def root():
    return {"message": "+58 BarberStudio API"}


app.include_router(api)

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
