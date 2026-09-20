import os
import re
import logging
import httpx

logger = logging.getLogger(__name__)

ADMIN_URL = os.environ.get("ADMIN_PANEL_URL", "https://www.58barberstudio.com/admin")
GESTIONAR_URL = os.environ.get("GESTIONAR_URL", "https://www.58barberstudio.com/reservar#gestionar")


def normalizar_telefono(telefono: str) -> str:
    """Normaliza un teléfono al formato E.164 sin + ni 0 inicial."""
    limpio = re.sub(r"\D", "", telefono or "")
    if limpio.startswith("00"):
        limpio = limpio[2:]
    limpio = limpio.lstrip("0")
    if len(limpio) == 9 and limpio[0] in "679":
        limpio = "34" + limpio
    return limpio


async def _post_meta(payload: dict) -> bool:
    """Envía un payload a Meta y devuelve éxito lógico; nunca rompe el flujo."""
    token = os.environ.get("WHATSAPP_TOKEN", "")
    phone_id = os.environ.get("PHONE_NUMBER_ID", "")
    if not token or not phone_id:
        logger.warning("WhatsApp no configurado (WHATSAPP_TOKEN/PHONE_NUMBER_ID); mensaje no enviado")
        return False

    version = os.environ.get("WHATSAPP_API_VERSION", "v25.0")
    url = f"https://graph.facebook.com/{version}/{phone_id}/messages"
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.post(url, headers={"Authorization": f"Bearer {token}"}, json=payload)

        if resp.is_error:
            logger.error("WhatsApp API %s: %s", resp.status_code, resp.text[:300])
            return False

        try:
            body = resp.json()
        except Exception:
            body = {"raw": resp.text[:300]}

        msgs = body.get("messages", []) if isinstance(body, dict) else []
        status = msgs[0].get("message_status") if msgs else None
        logger.info(
            "WhatsApp a ***%s | plantilla=%s | meta_status=%s | respuesta=%s",
            (payload.get("to") or "")[-4:],
            (payload.get("template") or {}).get("name", "(texto libre)"),
            status,
            body,
        )

        if status not in (None, "accepted"):
            logger.warning(
                "WhatsApp devolvió 200 pero message_status=%s (no aceptado) para ***%s",
                status,
                (payload.get("to") or "")[-4:],
            )
        return True
    except Exception as exc:
        logger.error("WhatsApp request error: %s", exc)
        return False


async def enviar_whatsapp(telefono: str, mensaje: str) -> bool:
    return await _post_meta({
        "messaging_product": "whatsapp",
        "recipient_type": "individual",
        "to": normalizar_telefono(telefono),
        "type": "text",
        "text": {"preview_url": True, "body": mensaje[:4096]},
    })


async def enviar_whatsapp_template(telefono: str, template: str, params: list) -> bool:
    return await _post_meta({
        "messaging_product": "whatsapp",
        "recipient_type": "individual",
        "to": normalizar_telefono(telefono),
        "type": "template",
        "template": {
            "name": template,
            "language": {"code": os.environ.get("WHATSAPP_TEMPLATE_LANG", "es_ES")},
            "components": [
                {"type": "body", "parameters": [{"type": "text", "text": str(p)[:1000]} for p in params]}
            ],
        },
    })


def _plantilla(tipo: str, cita: dict) -> str:
    codigo = str(cita.get("id", ""))[:8]
    if tipo == "recordatorio":
        return (
            f"¡Hola {cita['client_name']}! Mañana te espero en +58 BarberStudio: "
            f"{cita['service_name']} a las {cita['start']} ({cita['date']}).\n"
            f"Tu código: {codigo}. Modifícala o cancélala (hasta 12h antes): {GESTIONAR_URL}"
        )
    if tipo == "barbero":
        return (
            f"📋 Nueva cita: {cita['client_name']} ({cita['client_phone']}) — "
            f"{cita['service_name']}, {cita['date']} {cita['start']}–{cita['end']}. "
            f"Agenda: {ADMIN_URL}"
        )
    return (
        f"¡Hola {cita['client_name']}! Tu cita en +58 BarberStudio está confirmada: "
        f"{cita['service_name']}, {cita['date']} a las {cita['start']}.\n"
        f"Tu código para cambios: {codigo}\n"
        f"Modificar o cancelar (hasta 12h antes): {GESTIONAR_URL}"
    )


async def generar_mensaje_gemini(tipo: str, cita: dict) -> str:
    api_key = os.environ.get("GEMINI_API_KEY", "")
    fallback = _plantilla(tipo, cita)
    if not api_key:
        return fallback

    link = ADMIN_URL if tipo == "barbero" else GESTIONAR_URL
    try:
        import google.generativeai as genai

        genai.configure(api_key=api_key)
        model = genai.GenerativeModel(os.environ.get("GEMINI_MODEL", "gemini-3.6-flash"))
        prompt = (
            f"Escribe un mensaje de WhatsApp de {tipo} para una cita de la barbería +58 BarberStudio. "
            f"Cliente: {cita['client_name']}. Servicio: {cita['service_name']}. "
            f"Fecha: {cita['date']}. Hora: {cita['start']}. "
            "Español de Canarias, tono cercano, cálido y profesional, máximo 50 palabras, "
            "máximo 2 emojis, responde solo con el texto del mensaje, sin enlaces."
        )
        resp = await model.generate_content_async(prompt)
        texto = (resp.text or "").strip()
        if not texto:
            return fallback
        cola = (
            f"\n\nAgenda: {link}" if tipo == "barbero"
            else f"\n\nTu código: {str(cita.get('id', ''))[:8]}\nModificar o cancelar: {link}"
        )
        return texto + cola
    except Exception as exc:
        logger.error("Gemini error (%s); usando plantilla estatica", exc)
        return fallback


_TPL_ENV = {
    "confirmación": "WA_TPL_CONFIRM",
    "confirmacion": "WA_TPL_CONFIRM",
    "barbero": "WA_TPL_BARBER",
    "recordatorio": "WA_TPL_REMINDER",
    "cancelacion": "WA_TPL_CANCEL",
    "cancelacion_barbero": "WA_TPL_CANCEL_BARBER",
    "modificacion": "WA_TPL_MOD",
    "modificacion_barbero": "WA_TPL_MOD_BARBER",
}


def _params_tipo(tipo: str, cita: dict) -> list:
    if tipo.endswith("barbero"):
        return [cita["client_name"], cita["client_phone"], cita["service_name"], cita["date"], cita["start"]]
    if tipo == "cancelacion":
        return [cita["client_name"], cita["service_name"], cita["date"], cita["start"]]
    return [cita["client_name"], cita["service_name"], cita["date"], cita["start"], str(cita.get("id", ""))[:8]]


async def enviar_a(telefono: str, tipo: str, cita: dict) -> bool:
    """Si hay plantilla Meta configurada para este tipo, se usa (modo fiable fuera de ventana 24h)."""
    env_key = _TPL_ENV.get(tipo)
    if not env_key:
        logger.warning("No hay configuración de plantilla para tipo %r", tipo)
        return await enviar_whatsapp(telefono, await generar_mensaje_gemini(tipo, cita))

    tpl = os.environ.get(env_key, "")
    if tpl:
        return await enviar_whatsapp_template(telefono, tpl, _params_tipo(tipo, cita))
    return await enviar_whatsapp(telefono, await generar_mensaje_gemini(tipo, cita))


async def notificar_nueva_cita(cita: dict) -> None:
    try:
        barbero = os.environ.get("BUSINESS_WHATSAPP", "")
        if barbero:
            await enviar_a(barbero, "barbero", cita)
        await enviar_a(cita["client_phone"], "confirmación", cita)
    except Exception as exc:
        logger.error("notificar_nueva_cita error: %s", exc)


async def notificar_cambio_cita(cita: dict, accion: str) -> None:
    try:
        barbero = os.environ.get("BUSINESS_WHATSAPP", "")
        if barbero:
            await enviar_a(barbero, f"{accion}_barbero", cita)
        await enviar_a(cita["client_phone"], accion, cita)
    except Exception as exc:
        logger.error("notificar_cambio_cita error: %s", exc)


async def notificar_multi(citas: list) -> None:
    n = len(citas)
    if n < 2 or n > 3:
        for c in citas:
            await notificar_nueva_cita(c)
        return

    tpl_cli = os.environ.get(f"WA_TPL_CONFIRM_{n}", "")
    tpl_bar = os.environ.get(f"WA_TPL_BARBER_{n}", "")
    try:
        cli = citas[0]["client_phone"]
        ok_cli = False
        if tpl_cli:
            params = [citas[0]["client_name"]]
            for c in citas:
                params += [c["service_name"], c["date"], c["start"]]
            params.append(" / ".join(str(c.get("id", ""))[:8] for c in citas))
            ok_cli = await enviar_whatsapp_template(cli, tpl_cli, params)
        if not ok_cli:
            for c in citas:
                await enviar_a(cli, "confirmación", c)

        barbero = os.environ.get("BUSINESS_WHATSAPP", "")
        ok_bar = False
        if tpl_bar and barbero:
            params = [citas[0]["client_name"], cli]
            for c in citas:
                params += [c["service_name"], c["date"], c["start"]]
            ok_bar = await enviar_whatsapp_template(barbero, tpl_bar, params)
        if barbero and not ok_bar:
            for c in citas:
                await enviar_a(barbero, "barbero", c)
    except Exception as exc:
        logger.error("notificar_multi error: %s", exc)


async def probar_envio(telefono: str, plantilla: str = "", lang: str = "", params: list = None, texto: str = "") -> dict:
    token = os.environ.get("WHATSAPP_TOKEN", "")
    phone_id = os.environ.get("PHONE_NUMBER_ID", "")
    if not token or not phone_id:
        return {"ok": False, "error": "WHATSAPP_TOKEN o PHONE_NUMBER_ID no configurados en Railway"}

    version = os.environ.get("WHATSAPP_API_VERSION", "v25.0")
    url = f"https://graph.facebook.com/{version}/{phone_id}/messages"
    if texto:
        payload = {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": normalizar_telefono(telefono),
            "type": "text",
            "text": {"body": texto},
        }
        template_name = "(texto libre)"
    else:
        tpl = plantilla or os.environ.get("WA_TPL_CONFIRM", "")
        if tpl and tpl != "hello_world":
            template_name = tpl
            template = {
                "name": tpl,
                "language": {"code": lang or os.environ.get("WHATSAPP_TEMPLATE_LANG", "es_ES")},
            }
            if params is None:
                params = ["Cliente Prueba", "Corte y Barba", "2026-06-16", "10:00", "abc12345"]
            if params:
                template["components"] = [{
                    "type": "body",
                    "parameters": [{"type": "text", "text": str(p)[:1000]} for p in params],
                }]
        else:
            template_name = "hello_world"
            template = {"name": "hello_world", "language": {"code": "en_US"}}
        payload = {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": normalizar_telefono(telefono),
            "type": "template",
            "template": template,
        }

    try:
        async with httpx.AsyncClient(timeout=15) as client:
            info_resp = await client.get(
                f"https://graph.facebook.com/{version}/{phone_id}",
                params={"fields": "display_phone_number,verified_name"},
                headers={"Authorization": f"Bearer {token}"},
            )
            try:
                emisor = info_resp.json()
            except Exception:
                emisor = {"error": info_resp.text[:200]}
            emisor["phone_number_id_usado"] = phone_id
            resp = await client.post(url, headers={"Authorization": f"Bearer {token}"}, json=payload)

        try:
            body = resp.json()
        except Exception:
            body = resp.text[:500]

        msgs = body.get("messages", []) if isinstance(body, dict) else []
        entregado = bool(msgs and msgs[0].get("message_status") == "accepted")
        aviso = ""
        if resp.is_success and not entregado:
            aviso = (
                "Meta aceptó la petición pero NO encoló el mensaje (falta message_status=accepted): "
                "el texto libre fuera de la ventana 24h se descarta en silencio; usa una plantilla aprobada "
                "o haz que el cliente escriba primero."
            )
        return {
            "ok": resp.is_success,
            "entregado": entregado,
            "aviso": aviso,
            "status": resp.status_code,
            "plantilla_usada": template_name,
            "emisor": emisor,
            "meta_response": body,
        }
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


async def reenviar_respuesta_cliente(de_telefono: str, nombre: str, texto: str) -> bool:
    barbero = os.environ.get("BUSINESS_WHATSAPP", "")
    if not barbero:
        logger.warning("BUSINESS_WHATSAPP no configurado; respuesta de cliente no reenviada")
        return False

    tpl = os.environ.get("WA_TPL_FORWARD", "")
    if tpl:
        return await enviar_whatsapp_template(barbero, tpl, [f"{nombre} (+{de_telefono})", texto[:900]])
    return await enviar_whatsapp(barbero, f"💬 Respuesta de cliente\n👤 {nombre} (+{de_telefono}):\n\n{texto[:3000]}")
