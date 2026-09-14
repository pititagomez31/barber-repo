from fastapi import FastAPI, APIRouter, HTTPException, Query
from dotenv import load_dotenv
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
import os
import logging
from pathlib import Path
from pydantic import BaseModel, Field, ConfigDict
from typing import List, Optional, Dict
import uuid
from datetime import datetime, timezone


ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

# MongoDB connection
mongo_url = os.environ['MONGO_URL']
client = AsyncIOMotorClient(mongo_url)
db = client[os.environ['DB_NAME']]

app = FastAPI()
api_router = APIRouter(prefix="/api")

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Defaults & helpers
# ---------------------------------------------------------------------------
# weekday(): Monday=0 ... Sunday=6
DEFAULT_WORKING_HOURS: Dict[str, dict] = {
    "0": {"enabled": True, "start": "10:00", "end": "20:00"},   # Lunes
    "1": {"enabled": True, "start": "10:00", "end": "20:00"},   # Martes
    "2": {"enabled": True, "start": "10:00", "end": "20:00"},   # Miércoles
    "3": {"enabled": True, "start": "10:00", "end": "20:00"},   # Jueves
    "4": {"enabled": True, "start": "10:00", "end": "20:00"},   # Viernes
    "5": {"enabled": True, "start": "09:00", "end": "18:00"},   # Sábado
    "6": {"enabled": False, "start": "10:00", "end": "14:00"},  # Domingo
}

DEFAULT_SERVICES = [
    {"id": str(uuid.uuid4()), "name": "Corte de cabello", "duration_min": 30, "price": 10.0},
    {"id": str(uuid.uuid4()), "name": "Corte + Barba", "duration_min": 45, "price": 15.0},
    {"id": str(uuid.uuid4()), "name": "Arreglo de barba", "duration_min": 20, "price": 7.0},
    {"id": str(uuid.uuid4()), "name": "Corte niño", "duration_min": 25, "price": 8.0},
]

SLOT_STEP_MIN = 30


def parse_hhmm(value: str) -> int:
    h, m = value.split(":")
    return int(h) * 60 + int(m)


def minutes_to_hhmm(total: int) -> str:
    return f"{total // 60:02d}:{total % 60:02d}"


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------
class Service(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str
    duration_min: int = 30
    price: float = 0.0


class ServiceCreate(BaseModel):
    name: str
    duration_min: int = 30
    price: float = 0.0


class DayConfig(BaseModel):
    enabled: bool = True
    start: str = "10:00"
    end: str = "20:00"


class WorkingHoursIn(BaseModel):
    days: Dict[str, DayConfig]


class ScheduleOverrideIn(BaseModel):
    date: str                 # "YYYY-MM-DD"
    enabled: bool = True
    start: str = "10:00"      # "HH:MM"
    end: str = "20:00"        # "HH:MM"
    reason: str = ""


class AppointmentCreate(BaseModel):
    service_id: str
    date: str                 # "YYYY-MM-DD"
    time: str                 # "HH:MM"
    client_name: str
    client_phone: str


class Appointment(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    service_id: str
    service_name: str = ""
    date: str
    time: str
    duration_min: int = 30
    client_name: str
    client_phone: str
    status: str = "confirmed"
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class BlockerIn(BaseModel):
    date: str
    start: str
    end: str
    reason: str = ""


# ---------------------------------------------------------------------------
# Core availability logic
# ---------------------------------------------------------------------------
async def _get_effective_schedule(date_str: str) -> dict:
    """Return {source, enabled, start, end, reason} for a given date."""
    d = datetime.strptime(date_str, "%Y-%m-%d").date()
    weekday = str(d.weekday())

    override = await db.schedule_overrides.find_one({"date": date_str}, {"_id": 0})
    if override:
        return {
            "source": "override",
            "enabled": override.get("enabled", True),
            "start": override.get("start", "10:00"),
            "end": override.get("end", "20:00"),
            "reason": override.get("reason", ""),
        }

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
    sched = await _get_effective_schedule(date_str)
    if not sched["enabled"]:
        return []

    start_m = parse_hhmm(sched["start"])
    end_m = parse_hhmm(sched["end"])

    # Existing appointments for the day -> busy intervals
    busy: List[tuple] = []
    appts = await db.appointments.find(
        {"date": date_str, "status": {"$ne": "cancelled"}}, {"_id": 0}
    ).to_list(1000)
    for a in appts:
        a_start = parse_hhmm(a["time"])
        busy.append((a_start, a_start + int(a.get("duration_min", 30))))

    # Blockers for the day
    blockers = await db.blockers.find({"date": date_str}, {"_id": 0}).to_list(1000)
    for b in blockers:
        busy.append((parse_hhmm(b["start"]), parse_hhmm(b["end"])))

    slots: List[str] = []
    candidate = start_m
    while candidate + duration_min <= end_m:
        c_end = candidate + duration_min
        overlaps = any(candidate < b_end and c_end > b_start for b_start, b_end in busy)
        if not overlaps:
            slots.append(minutes_to_hhmm(candidate))
        candidate += SLOT_STEP_MIN
    return slots


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------
@api_router.get("/")
async def root():
    return {"message": "+58 BarberStudio API"}


# ----- Services -----
@api_router.get("/services", response_model=List[Service])
async def list_services():
    docs = await db.services.find({}, {"_id": 0}).to_list(1000)
    return docs


@api_router.post("/services", response_model=Service)
async def create_service(payload: ServiceCreate):
    svc = Service(**payload.model_dump())
    await db.services.insert_one(svc.model_dump())
    return svc


@api_router.delete("/services/{service_id}")
async def delete_service(service_id: str):
    await db.services.delete_one({"id": service_id})
    return {"ok": True}


# ----- Working hours (weekly base) -----
@api_router.get("/working-hours")
async def get_working_hours():
    doc = await db.working_hours.find_one({"id": "default"}, {"_id": 0})
    if not doc:
        return {"id": "default", "days": DEFAULT_WORKING_HOURS}
    return doc


@api_router.put("/working-hours")
async def update_working_hours(payload: WorkingHoursIn):
    days = {k: v.model_dump() for k, v in payload.days.items()}
    await db.working_hours.update_one(
        {"id": "default"}, {"$set": {"id": "default", "days": days}}, upsert=True
    )
    return {"id": "default", "days": days}


# ----- Schedule overrides (date exceptions) -----
@api_router.get("/schedule-overrides")
async def list_overrides(
    from_date: Optional[str] = Query(None),
    to_date: Optional[str] = Query(None),
):
    query: dict = {}
    if from_date or to_date:
        query["date"] = {}
        if from_date:
            query["date"]["$gte"] = from_date
        if to_date:
            query["date"]["$lte"] = to_date
    docs = await db.schedule_overrides.find(query, {"_id": 0}).sort("date", 1).to_list(1000)
    return docs


@api_router.get("/schedule-overrides/{date}")
async def get_override(date: str):
    doc = await db.schedule_overrides.find_one({"date": date}, {"_id": 0})
    if not doc:
        raise HTTPException(status_code=404, detail="No hay excepción para esta fecha")
    return doc


@api_router.post("/schedule-overrides")
async def upsert_override(payload: ScheduleOverrideIn):
    doc = payload.model_dump()
    await db.schedule_overrides.update_one(
        {"date": payload.date}, {"$set": doc}, upsert=True
    )
    return doc


@api_router.delete("/schedule-overrides/{date}")
async def delete_override(date: str):
    await db.schedule_overrides.delete_one({"date": date})
    return {"ok": True}


# ----- Public day schedule (booking side) -----
@api_router.get("/day-schedule/{date}")
async def get_day_schedule(date: str):
    """Devuelve el horario efectivo de un día (override o base)."""
    sched = await _get_effective_schedule(date)
    return {"date": date, **sched}


# ----- Availability -----
@api_router.get("/availability")
async def availability(service_id: str, date: str):
    svc = await db.services.find_one({"id": service_id}, {"_id": 0})
    if not svc:
        raise HTTPException(status_code=404, detail="Servicio no encontrado")
    slots = await _compute_slots(date, int(svc.get("duration_min", 30)))
    sched = await _get_effective_schedule(date)
    return {"date": date, "service_id": service_id, "slots": slots, "schedule": sched}


# ----- Appointments -----
@api_router.post("/appointments", response_model=Appointment)
async def create_appointment(payload: AppointmentCreate):
    svc = await db.services.find_one({"id": payload.service_id}, {"_id": 0})
    if not svc:
        raise HTTPException(status_code=404, detail="Servicio no encontrado")

    duration = int(svc.get("duration_min", 30))
    available = await _compute_slots(payload.date, duration)
    if payload.time not in available:
        raise HTTPException(status_code=409, detail="Ese horario ya no está disponible")

    appt = Appointment(
        service_id=payload.service_id,
        service_name=svc.get("name", ""),
        date=payload.date,
        time=payload.time,
        duration_min=duration,
        client_name=payload.client_name,
        client_phone=payload.client_phone,
    )
    await db.appointments.insert_one(appt.model_dump())
    return appt


@api_router.get("/appointments", response_model=List[Appointment])
async def list_appointments(date: Optional[str] = Query(None)):
    query: dict = {}
    if date:
        query["date"] = date
    docs = await db.appointments.find(query, {"_id": 0}).sort("time", 1).to_list(1000)
    return docs


@api_router.delete("/appointments/{appointment_id}")
async def delete_appointment(appointment_id: str):
    await db.appointments.delete_one({"id": appointment_id})
    return {"ok": True}


# ----- Blockers -----
@api_router.get("/blockers")
async def list_blockers(date: Optional[str] = Query(None)):
    query: dict = {}
    if date:
        query["date"] = date
    docs = await db.blockers.find(query, {"_id": 0}).to_list(1000)
    return docs


@api_router.post("/blockers")
async def create_blocker(payload: BlockerIn):
    doc = {"id": str(uuid.uuid4()), **payload.model_dump()}
    await db.blockers.insert_one(doc)
    doc.pop("_id", None)
    return doc


@api_router.delete("/blockers/{blocker_id}")
async def delete_blocker(blocker_id: str):
    await db.blockers.delete_one({"id": blocker_id})
    return {"ok": True}


# ---------------------------------------------------------------------------
# App wiring
# ---------------------------------------------------------------------------
app.include_router(api_router)

app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=os.environ.get('CORS_ORIGINS', '*').split(','),
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
async def startup():
    await db.schedule_overrides.create_index("date", unique=True)
    if await db.services.count_documents({}) == 0:
        await db.services.insert_many([dict(s) for s in DEFAULT_SERVICES])
        logger.info("Seeded default services")
    if await db.working_hours.count_documents({"id": "default"}) == 0:
        await db.working_hours.insert_one({"id": "default", "days": DEFAULT_WORKING_HOURS})
        logger.info("Seeded default working hours")


@app.on_event("shutdown")
async def shutdown_db_client():
    client.close()
