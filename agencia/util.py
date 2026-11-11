import hashlib
import os
import uuid
from django.conf import settings

EXT_OK = {".jpg", ".jpeg", ".png", ".pdf"}
MAX_BYTES = 5 * 1024 * 1024


def ip_cliente(request):
    return request.META.get("REMOTE_ADDR") or "127.0.0.1"


def hash_token(t):
    return hashlib.sha256(t.encode()).hexdigest()


def password_valida(p):
    if len(p) < 8:
        return "La contraseña debe tener al menos 8 caracteres."
    if not any(c.isalpha() for c in p) or not any(c.isdigit() for c in p):
        return "La contraseña debe combinar letras y números."
    return None


def guardar_comprobante(archivo):
    """Valida (jpg/png/pdf, máx. 5 MB) y guarda el archivo. Devuelve (ruta_relativa, error)."""
    ext = os.path.splitext(archivo.name)[1].lower()
    if ext not in EXT_OK:
        return None, "El comprobante debe ser JPG, PNG o PDF."
    if archivo.size > MAX_BYTES:
        return None, "El comprobante no puede superar los 5 MB."
    carpeta = settings.MEDIA_ROOT / "comprobantes"
    carpeta.mkdir(parents=True, exist_ok=True)
    nombre = f"{uuid.uuid4().hex}{ext}"
    with open(carpeta / nombre, "wb") as f:
        for parte in archivo.chunks():
            f.write(parte)
    return f"comprobantes/{nombre}", None


def destino_notificacion(n, es_staff):
    """Devuelve la URL a la que lleva una notificación."""
    from . import db
    t, rid = n["referencia_tabla"], n["referencia_id"]
    if not rid:
        return None
    if t == "cotizacion":
        return f"/gestion/cotizaciones/{rid}/" if es_staff else f"/cliente/cotizaciones/{rid}/"
    if t == "reserva":
        return f"/gestion/reservas/{rid}/" if es_staff else f"/cliente/reservas/{rid}/"
    if t == "solicitud_cotizacion":
        return f"/gestion/solicitudes/{rid}/" if es_staff else "/cliente/solicitudes/"
    if t == "pago":
        r = db.escalar("SELECT reserva_id FROM pago WHERE id = %s", [rid])
        if r:
            return f"/gestion/reservas/{r}/" if es_staff else f"/cliente/reservas/{r}/"
    return None


IMG_EXT = {".jpg", ".jpeg", ".png", ".webp"}
IMG_MAX = 3 * 1024 * 1024


def guardar_imagen(archivo, carpeta):
    """Guarda una foto (jpg/png/webp, máx. 3 MB) en media/<carpeta>/. Devuelve (ruta_relativa, error)."""
    ext = os.path.splitext(archivo.name)[1].lower()
    if ext not in IMG_EXT:
        return None, "La imagen debe ser JPG, PNG o WEBP."
    if archivo.size > IMG_MAX:
        return None, "La imagen no puede superar los 3 MB."
    destino = settings.MEDIA_ROOT / carpeta
    destino.mkdir(parents=True, exist_ok=True)
    nombre = f"{uuid.uuid4().hex}{ext}"
    with open(destino / nombre, "wb") as f:
        for parte in archivo.chunks():
            f.write(parte)
    return f"{carpeta}/{nombre}", None


def borrar_imagen(ruta):
    if ruta and ruta.startswith(("paquetes/", "destinos/")):
        try:
            (settings.MEDIA_ROOT / ruta).unlink()
        except OSError:
            pass
