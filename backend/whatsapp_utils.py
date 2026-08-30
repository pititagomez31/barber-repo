import re
import urllib.parse


def generar_enlace_whatsapp(telefono: str, mensaje: str) -> str:
    telefono_limpio = re.sub(r"\D", "", telefono)
    mensaje_codificado = urllib.parse.quote(mensaje)
    return f"https://wa.me/{telefono_limpio}?text={mensaje_codificado}"
