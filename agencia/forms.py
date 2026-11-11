"""Mini-sistema de formularios: definición declarativa, lectura y validación de campos."""
import re
from datetime import date, datetime
from decimal import Decimal, InvalidOperation

EMAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def campo(nombre, etiqueta, tipo="text", req=True, opciones=None, col=6, ayuda="", minimo=None, maximo=None, step=None, largo=None, patron=None):
    return dict(nombre=nombre, etiqueta=etiqueta, tipo=tipo, req=req, opciones=opciones or [], col=col, ayuda=ayuda,
                minimo=minimo, maximo=maximo, step=step, largo=largo, patron=patron)


def leer(post, campos, inicial=None):
    """Devuelve (valores, errores). Los valores ya vienen convertidos al tipo Python."""
    vals, errs = {}, {}
    for c in campos:
        n, t = c["nombre"], c["tipo"]
        if t == "checkbox":
            vals[n] = n in post
            continue
        crudo = (post.get(n) or "").strip()
        if crudo == "":
            if c["req"]:
                errs[n] = "Este campo es obligatorio."
            vals[n] = None
            continue
        try:
            if t == "number":
                v = Decimal(crudo.replace(",", "."))
                if c["minimo"] is not None and v < Decimal(str(c["minimo"])):
                    errs[n] = f"Debe ser mayor o igual a {c['minimo']}."
                if c["maximo"] is not None and v > Decimal(str(c["maximo"])):
                    errs[n] = f"Debe ser menor o igual a {c['maximo']}."
                vals[n] = v
            elif t == "int":
                v = int(crudo)
                if c["minimo"] is not None and v < c["minimo"]:
                    errs[n] = f"Debe ser al menos {c['minimo']}."
                if c["maximo"] is not None and v > c["maximo"]:
                    errs[n] = f"Debe ser como máximo {c['maximo']}."
                vals[n] = v
            elif t == "date":
                vals[n] = datetime.strptime(crudo, "%Y-%m-%d").date()
            elif t == "email":
                if not EMAIL.match(crudo):
                    errs[n] = "Escriba un correo válido."
                vals[n] = crudo.lower()
            elif t == "select":
                if crudo not in [str(o[0]) for o in c["opciones"]]:
                    errs[n] = "Elija una opción válida."
                vals[n] = crudo
            else:
                if c["largo"] and len(crudo) > c["largo"]:
                    errs[n] = f"Máximo {c['largo']} caracteres."
                if c["patron"] and not re.match(c["patron"], crudo):
                    errs[n] = c["ayuda"] or "Formato no válido."
                vals[n] = crudo
        except (InvalidOperation, ValueError):
            errs[n] = "Valor no válido."
            vals[n] = None
    return vals, errs


def valor_html(v):
    if isinstance(v, (date, datetime)):
        return v.strftime("%Y-%m-%d")
    return "" if v is None else v
