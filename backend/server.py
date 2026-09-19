import os
import logging
import httpx
from datetime import datetime, timedelta
import pytz
from fastapi import FastAPI
from motor.motor_asyncio import AsyncIOMotorClient
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from contextlib import asynccontextmanager

# Configuración de Logs detallada para Railway
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger(__name__)

# Configuración de Zona Horaria y DB
CANARY_TZ = pytz.timezone('Atlantic/Canary')
MONGO_URL = os.environ.get("MONGO_URL", "mongodb://localhost:27017")
WHATSAPP_API_URL = os.environ.get("WHATSAPP_API_URL")
WHATSAPP_TOKEN = os.environ.get("WHATSAPP_TOKEN")

client = AsyncIOMotorClient(MONGO_URL)
db = client.barber_db

async def send_whatsapp_reminder(appointment):
    """
    Envía el recordatorio vía WhatsApp API.
    """
    if not WHATSAPP_API_URL or not WHATSAPP_TOKEN:
        logger.error("Faltan variables de entorno WHATSAPP_API_URL o WHATSAPP_TOKEN")
        return False

    payload = {
        "messaging_product": "whatsapp",
        "to": appointment['phone'],
        "type": "template",
        "template": {
            "name": "recordatorio_cita_24h",
            "language": {"code": "es"},
            "components": [
                {
                    "type": "body",
                    "parameters": [
                        {"type": "text", "text": appointment['name']},
                        {"type": "text", "text": appointment['time']}
                    ]
                }
            ]
        }
    }

    try:
        async with httpx.AsyncClient() as client_http:
            response = await client_http.post(
                WHATSAPP_API_URL,
                json=payload,
                headers={"Authorization": f"Bearer {WHATSAPP_TOKEN}"},
                timeout=10.0
            )
            
            if response.status_code == 200:
                logger.info(f"Recordatorio enviado con éxito a {appointment['phone']}")
                return True
            else:
                logger.error(f"Error API WhatsApp ({response.status_code}): {response.text}")
                return False
    except Exception as e:
        logger.error(f"Error crítico en envío WhatsApp a {appointment['phone']}: {str(e)}")
        return False

async def check_and_send_reminders():
    """
    Busca citas que ocurren en aproximadamente 24 horas y envía recordatorio.
    """
    try:
        now_canary = datetime.now(CANARY_TZ)
        # Buscamos citas para mañana (24h después de ahora)
        target_day = (now_canary + timedelta(days=1)).strftime("%Y-%m-%d")
        
        logger.info(f"Ejecutando job de recordatorios para el día: {target_day}")

        # Buscamos citas del día objetivo que no tengan el flag reminder_sent
        cursor = db.appointments.find({
            "date": target_day,
            "reminder_sent": {"$ne": True}
        })

        count = 0
        async for appointment in cursor:
            success = await send_whatsapp_reminder(appointment)
            if success:
                await db.appointments.update_one(
                    {"_id": appointment["_id"]},
                    {
                        "$set": {
                            "reminder_sent": True, 
                            "reminder_sent_at": datetime.now(CANARY_TZ).isoformat()
                        }
                    }
                )
                count += 1
        
        if count > 0:
            logger.info(f"Proceso finalizado. Se enviaron {count} recordatorios.")
            
    except Exception as e:
        logger.error(f"Error en el job de recordatorios: {str(e)}")

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Iniciar el scheduler al arrancar
    scheduler = AsyncIOScheduler(timezone=CANARY_TZ)
    # Se ejecuta cada 30 minutos para cubrir posibles fallos de red
    scheduler.add_job(check_and_send_reminders, 'interval', minutes=30)
    scheduler.start()
    logger.info("Scheduler de recordatorios iniciado (Zona: Atlantic/Canary)")
    
    # Ejecución inmediata al arrancar para verificar estado
    await check_and_send_reminders()
    
    yield
    scheduler.shutdown()

app = FastAPI(lifespan=lifespan)

@app.get("/")
async def root():
    return {
        "status": "58 Barber Studio API Running", 
        "timezone": "Atlantic/Canary",
        "server_time": datetime.now(CANARY_TZ).isoformat()
    }
