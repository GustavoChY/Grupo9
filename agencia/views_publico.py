import secrets
from datetime import timedelta
from django.contrib import messages
from django.contrib.auth.hashers import check_password, make_password
from django.http import FileResponse, Http404
from django.shortcuts import redirect, render
from django.utils import timezone

from . import db, forms
from .auth import login_requerido
from .util import destino_notificacion, hash_token, ip_cliente, password_valida


# ------------------------------------------------------------------ catálogo público
def inicio(request):
    paquetes = db.q("""SELECT p.id, p.nombre, p.descripcion, p.duracion_dias, COALESCE(p.imagen, d.imagen) AS foto, d.nombre AS destino, d.pais, d.ambito, vp.precio_final
                       FROM paquete p JOIN destino d ON d.id = p.destino_id JOIN v_paquete_precio vp ON vp.paquete_id = p.id
                       WHERE p.activo AND CURRENT_DATE BETWEEN p.vigente_desde AND p.vigente_hasta ORDER BY p.id LIMIT 6""")
    stats = db.q1("""SELECT (SELECT count(*) FROM destino) AS destinos, (SELECT count(*) FROM paquete WHERE activo) AS paquetes,
                     (SELECT count(*) FROM reserva WHERE estado IN ('PAGADA','FINALIZADA')) AS viajes""")
    return render(request, "public/inicio.html", {"paquetes": paquetes, "stats": stats})


def _paquetes_filtrados(request):
    ambito = request.GET.get("ambito", "")
    texto = request.GET.get("q", "").strip()
    sql = """SELECT p.id, p.nombre, p.descripcion, p.duracion_dias, p.vigente_hasta, COALESCE(p.imagen, d.imagen) AS foto, d.nombre AS destino, d.pais, d.ambito, vp.precio_final
             FROM paquete p JOIN destino d ON d.id = p.destino_id JOIN v_paquete_precio vp ON vp.paquete_id = p.id
             WHERE p.activo AND CURRENT_DATE BETWEEN p.vigente_desde AND p.vigente_hasta"""
    par = []
    if ambito in ("NACIONAL", "INTERNACIONAL"):
        sql += " AND d.ambito = %s"
        par.append(ambito)
    if texto:
        sql += " AND (p.nombre ILIKE %s OR d.nombre ILIKE %s OR d.pais ILIKE %s)"
        par += [f"%{texto}%"] * 3
    return db.q(sql + " ORDER BY vp.precio_final", par), ambito, texto


def paquetes(request):
    lista, ambito, texto = _paquetes_filtrados(request)
    return render(request, "public/paquetes.html", {"paquetes": lista, "ambito": ambito, "texto": texto})


def paquete_detalle(request, pk):
    p = db.q1("""SELECT p.*, COALESCE(p.imagen, d.imagen) AS foto, d.nombre AS destino, d.pais, d.ambito, vp.precio_final, vp.costo_proveedor, vp.comision, vp.impuestos
                 FROM paquete p JOIN destino d ON d.id = p.destino_id JOIN v_paquete_precio vp ON vp.paquete_id = p.id WHERE p.id = %s AND p.activo""", [pk])
    if not p:
        raise Http404()
    servicios = db.q("""SELECT s.nombre, s.tipo, s.descripcion, s.categoria, ps.cantidad, pr.nombre AS proveedor
                        FROM paquete_servicio ps JOIN servicio s ON s.id = ps.servicio_id JOIN proveedor pr ON pr.id = s.proveedor_id
                        WHERE ps.paquete_id = %s ORDER BY s.tipo, s.nombre""", [pk])
    return render(request, "public/paquete_detalle.html", {"p": p, "servicios": servicios})


# ------------------------------------------------------------------ acceso
def _destino_seguro(next_):
    return next_ if next_ and next_.startswith("/") and not next_.startswith("//") else "/panel/"


def ingresar(request):
    if request.usuario:
        return redirect("panel")
    next_ = request.GET.get("next") or request.POST.get("next") or ""
    if request.method == "POST":
        username = request.POST.get("username", "").strip()
        clave = request.POST.get("password", "")
        u = db.q1("SELECT id, password_hash FROM usuario WHERE username = %s", [username]) if username else None
        correcta = bool(u) and check_password(clave, u["password_hash"])
        with db.accion() as a:
            resultado = db.escalar("SELECT fn_registrar_intento_acceso(%s, %s, %s::inet)", [username, correcta, ip_cliente(request)])
        if a.error:
            resultado = "FALLIDO"
        if resultado == "OK":
            request.session.flush()
            request.session["uid"] = u["id"]
            messages.success(request, "¡Bienvenido de nuevo!")
            return redirect(_destino_seguro(next_))
        if resultado == "BLOQUEADO":
            mins = db.escalar("SELECT fn_param('minutos_bloqueo')")
            messages.error(request, f"Su cuenta está bloqueada temporalmente por demasiados intentos fallidos. Intente de nuevo en {mins} minutos.")
        elif resultado == "INACTIVO":
            messages.error(request, "Su cuenta está desactivada. Comuníquese con la agencia.")
        else:
            fila = db.q1("SELECT intentos_fallidos, bloqueado_hasta FROM usuario WHERE username = %s", [username])
            if fila and fila["bloqueado_hasta"]:
                messages.error(request, "Demasiados intentos fallidos: su cuenta quedó bloqueada temporalmente.")
            elif fila:
                restan = int(db.escalar("SELECT fn_param('max_intentos_fallidos')")) - fila["intentos_fallidos"]
                messages.error(request, f"Usuario o contraseña incorrectos. Le quedan {restan} intento(s) antes del bloqueo temporal.")
            else:
                messages.error(request, "Usuario o contraseña incorrectos.")
    return render(request, "public/ingresar.html", {"next": next_})


def salir(request):
    if request.usuario:
        db.ex("INSERT INTO bitacora_acceso(usuario_id, username_intentado, evento, exito, ip) VALUES (%s,%s,'LOGOUT',true,%s::inet)",
              [request.usuario["id"], request.usuario["username"], ip_cliente(request)])
    request.session.flush()
    messages.info(request, "Sesión cerrada. ¡Hasta pronto!")
    return redirect("inicio")


CAMPOS_REGISTRO = [
    forms.campo("nombres", "Nombres", largo=80),
    forms.campo("apellidos", "Apellidos", largo=80),
    forms.campo("tipo_documento", "Tipo de documento", "select", opciones=[("CI", "Cédula de identidad"), ("PASAPORTE", "Pasaporte"), ("CEX", "Cédula de extranjero"), ("OTRO", "Otro")]),
    forms.campo("nro_documento", "Nro. de documento", largo=30),
    forms.campo("fecha_nacimiento", "Fecha de nacimiento", "date", req=False),
    forms.campo("telefono", "Teléfono", req=False, largo=30),
    forms.campo("username", "Nombre de usuario", patron=r"^[A-Za-z0-9_.]{4,30}$", ayuda="De 4 a 30 caracteres: letras, números, punto o guion bajo."),
    forms.campo("email", "Correo electrónico", "email"),
    forms.campo("password", "Contraseña", "password", ayuda="Mínimo 8 caracteres, con letras y números."),
    forms.campo("password2", "Repita la contraseña", "password"),
]


def registrarse(request):
    if request.usuario:
        return redirect("panel")
    vals, errs = {}, {}
    if request.method == "POST":
        vals, errs = forms.leer(request.POST, CAMPOS_REGISTRO)
        if not errs.get("password"):
            e = password_valida(vals["password"] or "")
            if e:
                errs["password"] = e
        if vals.get("password") != vals.get("password2"):
            errs["password2"] = "Las contraseñas no coinciden."
        if not errs:
            with db.accion() as a:
                uid = db.ex_ret("""INSERT INTO usuario(rol_id, username, email, password_hash, nombres, apellidos)
                                   VALUES ((SELECT id FROM rol WHERE codigo='CLIENTE'), %s,%s,%s,%s,%s) RETURNING id""",
                                [vals["username"], vals["email"], make_password(vals["password"]), vals["nombres"], vals["apellidos"]])
                existente = db.q1("SELECT id, usuario_id FROM cliente WHERE tipo_documento=%s AND nro_documento=%s", [vals["tipo_documento"], vals["nro_documento"]])
                if existente and existente["usuario_id"] is None:
                    db.ex("UPDATE cliente SET usuario_id=%s, correo=%s, telefono=COALESCE(%s, telefono) WHERE id=%s", [uid, vals["email"], vals["telefono"], existente["id"]])
                else:
                    db.ex("""INSERT INTO cliente(usuario_id, tipo_documento, nro_documento, nombres, apellidos, fecha_nacimiento, telefono, correo)
                             VALUES (%s,%s,%s,%s,%s,%s,%s,%s)""",
                          [uid, vals["tipo_documento"], vals["nro_documento"], vals["nombres"], vals["apellidos"], vals["fecha_nacimiento"], vals["telefono"], vals["email"]])
            if a.error:
                messages.error(request, "No se pudo crear la cuenta: " + a.error)
            else:
                messages.success(request, "¡Cuenta creada! Ya puede iniciar sesión.")
                return redirect("ingresar")
        else:
            messages.error(request, "Revise los campos marcados.")
    return render(request, "public/registro.html", {"campos": CAMPOS_REGISTRO, "valores": {k: v for k, v in vals.items() if "password" not in k}, "errores": errs})


def recuperar(request):
    enlace = None
    if request.method == "POST":
        email = request.POST.get("email", "").strip().lower()
        u = db.q1("SELECT id, username FROM usuario WHERE lower(email) = %s AND activo", [email])
        if u:
            token = secrets.token_urlsafe(32)
            db.ex("INSERT INTO token_recuperacion(usuario_id, token_hash, expira_en) VALUES (%s,%s,%s)", [u["id"], hash_token(token), timezone.now() + timedelta(minutes=30)])
            db.ex("INSERT INTO bitacora_acceso(usuario_id, username_intentado, evento, exito, ip) VALUES (%s,%s,'RECUPERACION_SOLICITADA',true,%s::inet)", [u["id"], u["username"], ip_cliente(request)])
            enlace = request.build_absolute_uri(f"/recuperar/{token}/")
        messages.info(request, "Si el correo está registrado, se generó un enlace de recuperación válido por 30 minutos.")
    # Instalación local sin servidor de correo: el enlace se muestra en pantalla.
    return render(request, "public/recuperar.html", {"enlace": enlace})


def restablecer(request, token):
    t = db.q1("SELECT id, usuario_id FROM token_recuperacion WHERE token_hash=%s AND NOT usado AND expira_en > now()", [hash_token(token)])
    if not t:
        messages.error(request, "El enlace no es válido o ya venció. Solicite uno nuevo.")
        return redirect("recuperar")
    if request.method == "POST":
        p1, p2 = request.POST.get("password", ""), request.POST.get("password2", "")
        err = password_valida(p1) or (None if p1 == p2 else "Las contraseñas no coinciden.")
        if err:
            messages.error(request, err)
        else:
            db.ex("UPDATE usuario SET password_hash=%s, intentos_fallidos=0, bloqueado_hasta=NULL WHERE id=%s", [make_password(p1), t["usuario_id"]])
            db.ex("UPDATE token_recuperacion SET usado=true WHERE id=%s", [t["id"]])
            messages.success(request, "Contraseña actualizada. Ya puede ingresar.")
            return redirect("ingresar")
    return render(request, "public/restablecer.html")


# ------------------------------------------------------------------ zona autenticada común
@login_requerido
def panel(request):
    if request.usuario["rol"] in ("AGENTE", "ADMIN"):
        return redirect("gestion")
    return _panel_cliente(request)


def _panel_cliente(request):
    c = request.cliente
    if not c:
        return render(request, "403.html", status=403)
    datos = {
        "solicitudes": db.q("SELECT * FROM solicitud_cotizacion WHERE cliente_id=%s ORDER BY id DESC LIMIT 5", [c["id"]]),
        "cotizaciones": db.q("SELECT * FROM cotizacion WHERE cliente_id=%s AND estado IN ('ENVIADA','ACEPTADA') ORDER BY id DESC LIMIT 5", [c["id"]]),
        "reservas": db.q("SELECT s.*, r.fecha_inicio, r.fecha_fin FROM v_reserva_saldo s JOIN reserva r ON r.id = s.reserva_id WHERE s.cliente_id=%s ORDER BY s.reserva_id DESC LIMIT 5", [c["id"]]),
        "notifs": db.q("SELECT * FROM notificacion WHERE usuario_id=%s AND NOT leida ORDER BY id DESC LIMIT 5", [request.usuario["id"]]),
        "paquetes": db.q("""SELECT p.id, p.nombre, p.duracion_dias, d.nombre AS destino, vp.precio_final FROM paquete p JOIN destino d ON d.id=p.destino_id
                            JOIN v_paquete_precio vp ON vp.paquete_id=p.id WHERE p.activo AND CURRENT_DATE BETWEEN p.vigente_desde AND p.vigente_hasta ORDER BY random() LIMIT 3"""),
    }
    return render(request, "cliente/panel.html", datos)


@login_requerido
def notificaciones(request):
    if request.method == "POST":
        db.ex("UPDATE notificacion SET leida=true WHERE usuario_id=%s", [request.usuario["id"]])
        return redirect("notificaciones")
    lista = db.q("SELECT * FROM notificacion WHERE usuario_id=%s ORDER BY id DESC LIMIT 100", [request.usuario["id"]])
    staff = request.usuario["rol"] in ("AGENTE", "ADMIN")
    for n in lista:
        n["url"] = destino_notificacion(n, staff)
    ids = [n["id"] for n in lista if not n["leida"]]
    resp = render(request, "partials/notificaciones.html", {"lista": lista, "sin_leer": len(ids)})
    return resp


CAMPOS_CLIENTE_PERFIL = [
    forms.campo("telefono", "Teléfono", req=False, largo=30),
    forms.campo("correo", "Correo de contacto", "email", req=False),
    forms.campo("direccion", "Dirección", req=False, col=12, largo=200),
    forms.campo("preferencias", "Preferencias de viaje", "textarea", req=False, col=12),
]
CAMPOS_STAFF_PERFIL = [
    forms.campo("nombres", "Nombres", largo=80),
    forms.campo("apellidos", "Apellidos", largo=80),
]


@login_requerido
def cuenta(request):
    es_cliente = bool(request.cliente)
    campos = CAMPOS_CLIENTE_PERFIL if es_cliente else CAMPOS_STAFF_PERFIL
    vals = dict(request.cliente) if es_cliente else {"nombres": request.usuario["nombres"], "apellidos": request.usuario["apellidos"]}
    errs = {}
    if request.method == "POST":
        vals, errs = forms.leer(request.POST, campos)
        if not errs:
            with db.accion() as a:
                if es_cliente:
                    db.ex("UPDATE cliente SET telefono=%s, correo=%s, direccion=%s, preferencias=%s WHERE id=%s",
                          [vals["telefono"], vals["correo"], vals["direccion"], vals["preferencias"], request.cliente["id"]])
                else:
                    db.ex("UPDATE usuario SET nombres=%s, apellidos=%s WHERE id=%s", [vals["nombres"], vals["apellidos"], request.usuario["id"]])
            if a.error:
                messages.error(request, a.error)
            else:
                messages.success(request, "Sus datos fueron actualizados.")
                return redirect("cuenta")
    return render(request, "partials/cuenta.html", {"campos": campos, "valores": vals, "errores": errs})


@login_requerido
def cambiar_password(request):
    if request.method == "POST":
        actual = db.escalar("SELECT password_hash FROM usuario WHERE id=%s", [request.usuario["id"]])
        p1, p2 = request.POST.get("nueva", ""), request.POST.get("nueva2", "")
        if not check_password(request.POST.get("actual", ""), actual):
            messages.error(request, "La contraseña actual no es correcta.")
        else:
            err = password_valida(p1) or (None if p1 == p2 else "Las contraseñas nuevas no coinciden.")
            if err:
                messages.error(request, err)
            else:
                db.ex("UPDATE usuario SET password_hash=%s WHERE id=%s", [make_password(p1), request.usuario["id"]])
                messages.success(request, "Contraseña actualizada correctamente.")
                return redirect("cuenta")
    return render(request, "partials/password.html")


@login_requerido
def ver_comprobante(request, pk):
    from django.conf import settings
    p = db.q1("SELECT p.comprobante_archivo, r.cliente_id FROM pago p JOIN reserva r ON r.id = p.reserva_id WHERE p.id=%s", [pk])
    if not p or not p["comprobante_archivo"]:
        raise Http404()
    es_dueno = request.cliente and request.cliente["id"] == p["cliente_id"]
    if not (es_dueno or "PAGO_VERIFICAR" in request.permisos):
        return render(request, "403.html", status=403)
    ruta = (settings.MEDIA_ROOT / p["comprobante_archivo"]).resolve()
    if settings.MEDIA_ROOT.resolve() not in ruta.parents or not ruta.exists():
        raise Http404()
    return FileResponse(open(ruta, "rb"))
