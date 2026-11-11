from . import db


def base(request):
    u = getattr(request, "usuario", None)
    ctx = {"usuario": u, "permisos": getattr(request, "permisos", set()), "es_staff": False, "n_notif": 0}
    if u:
        ctx["es_staff"] = u["rol"] in ("AGENTE", "ADMIN")
        ctx["n_notif"] = db.escalar("SELECT count(*) FROM notificacion WHERE usuario_id = %s AND NOT leida", [u["id"]])
    return ctx
