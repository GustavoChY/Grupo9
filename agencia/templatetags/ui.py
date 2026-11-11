from decimal import Decimal
from django import template
from django.utils.safestring import mark_safe

register = template.Library()

ESTADOS = {
    "RECIBIDA": ("info", "Recibida"), "EN_ATENCION": ("warning", "En atención"), "COTIZADA": ("success", "Cotizada"), "CERRADA": ("secondary", "Cerrada"),
    "BORRADOR": ("secondary", "Borrador"), "ENVIADA": ("primary", "Enviada"), "ACEPTADA": ("success", "Aceptada"),
    "RECHAZADA": ("danger", "Rechazada"), "VENCIDA": ("dark", "Vencida"),
    "PENDIENTE": ("warning", "Pendiente"), "CONFIRMADA": ("primary", "Confirmada"), "PAGADA": ("success", "Pagada"),
    "CANCELADA": ("danger", "Cancelada"), "FINALIZADA": ("dark", "Finalizada"),
    "PENDIENTE_VERIFICACION": ("warning", "Por verificar"), "VERIFICADO": ("success", "Verificado"), "RECHAZADO": ("danger", "Rechazado"),
}
ETIQUETAS = {
    "CI": "Cédula de identidad", "PASAPORTE": "Pasaporte", "CEX": "Cédula de extranjero", "OTRO": "Otro",
    "AEROLINEA": "Aerolínea", "HOTEL": "Hotel", "OPERADOR_TOUR": "Operador de tour", "TRANSPORTE": "Transporte", "ASEGURADORA": "Aseguradora",
    "AEREO": "Aéreo", "HOSPEDAJE": "Hospedaje", "TRASLADO": "Traslado", "TOUR": "Tour", "SEGURO": "Seguro",
    "ECONOMICA": "Económica", "ESTANDAR": "Estándar", "PREMIUM": "Premium", "ALTA": "Alta", "BAJA": "Baja", "TODO_ANO": "Todo el año",
    "NACIONAL": "Nacional", "INTERNACIONAL": "Internacional", "TRANSFERENCIA": "Transferencia", "DEPOSITO": "Depósito", "EFECTIVO": "Efectivo",
    "ADULTO": "Adulto", "MENOR": "Menor", "INFANTE": "Infante", "CLIENTE": "Cliente", "AGENTE": "Agente", "ADMIN": "Administrador",
    "LOGIN_OK": "Ingreso correcto", "LOGIN_FALLIDO": "Ingreso fallido", "BLOQUEO": "Bloqueo", "DESBLOQUEO": "Desbloqueo", "LOGOUT": "Cierre de sesión",
    "CAMBIO_PASSWORD": "Cambio de contraseña", "RECUPERACION_SOLICITADA": "Recuperación solicitada", "CAMBIO_ROL": "Cambio de rol", "USUARIO_DESACTIVADO": "Usuario desactivado",
}
ICONOS_SERV = {"AEREO": "airplane", "HOSPEDAJE": "building", "TRASLADO": "bus-front", "TOUR": "compass", "SEGURO": "shield-check"}


@register.filter
def bs(valor):
    if valor is None or valor == "":
        return "—"
    v = Decimal(valor).quantize(Decimal("0.01"))
    s = f"{v:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    return f"Bs {s}"


@register.filter
def fecha(valor):
    return valor.strftime("%d/%m/%Y") if valor else "—"


@register.filter
def fechahora(valor):
    if not valor:
        return "—"
    from django.utils import timezone
    return timezone.localtime(valor).strftime("%d/%m/%Y %H:%M")


@register.filter
def estado(valor):
    clase, texto = ESTADOS.get(valor, ("secondary", valor))
    return mark_safe(f'<span class="badge text-bg-{clase} estado">{texto}</span>')


@register.filter
def etiqueta(valor):
    return ETIQUETAS.get(valor, valor)


@register.filter
def icono_serv(valor):
    return ICONOS_SERV.get(valor, "tag")


@register.filter
def pct(valor):
    return f"{Decimal(valor).normalize():f}%" if valor is not None else "—"


@register.filter
def get(d, k):
    return d.get(k) if d else None


@register.filter
def avance(res):
    """Porcentaje pagado (verificado) de una reserva."""
    try:
        return int(min(100, round(float(res["pagado_verificado"]) * 100 / float(res["total"]))))
    except Exception:
        return 0


@register.filter
def split(valor):
    return valor.split()


@register.filter
def texto_estado(valor):
    return ESTADOS.get(valor, ("", valor))[1]
