import csv
import json
from datetime import date, datetime
from decimal import Decimal

from django.contrib import messages
from django.contrib.auth.hashers import make_password
from django.http import Http404, HttpResponse
from django.shortcuts import redirect, render

from . import db, forms
from .auth import permiso
from .util import password_valida

ROLES = lambda: [(r["id"], r["nombre"]) for r in db.q("SELECT id, nombre FROM rol ORDER BY id")]


@permiso("USR_GESTIONAR")
def usuarios(request):
    t = request.GET.get("q", "").strip()
    sql = """SELECT u.*, r.nombre AS rol, (u.bloqueado_hasta IS NOT NULL AND u.bloqueado_hasta > now()) AS bloqueado
             FROM usuario u JOIN rol r ON r.id=u.rol_id"""
    par = []
    if t:
        sql += " WHERE u.username ILIKE %s OR u.email ILIKE %s OR u.nombres ILIKE %s OR u.apellidos ILIKE %s"
        par = [f"%{t}%"] * 4
    return render(request, "admin/usuarios.html", {"lista": db.q(sql + " ORDER BY u.rol_id DESC, u.username", par), "texto": t})


@permiso("USR_GESTIONAR")
def usuario_nuevo(request):
    campos = [
        forms.campo("nombres", "Nombres", largo=80), forms.campo("apellidos", "Apellidos", largo=80),
        forms.campo("username", "Usuario", patron=r"^[A-Za-z0-9_.]{4,30}$", ayuda="De 4 a 30 caracteres: letras, números, punto o guion bajo."),
        forms.campo("email", "Correo", "email"),
        forms.campo("rol_id", "Rol", "select", opciones=ROLES()),
        forms.campo("password", "Contraseña inicial", "password", ayuda="Mínimo 8 caracteres, letras y números."),
    ]
    vals, errs = {"rol_id": "2"}, {}
    if request.method == "POST":
        vals, errs = forms.leer(request.POST, campos)
        if not errs.get("password"):
            e = password_valida(vals["password"] or "")
            if e:
                errs["password"] = e
        if not errs:
            with db.accion() as a:
                uid = db.ex_ret("INSERT INTO usuario(rol_id, username, email, password_hash, nombres, apellidos) VALUES (%s,%s,%s,%s,%s,%s) RETURNING id",
                                [vals["rol_id"], vals["username"], vals["email"], make_password(vals["password"]), vals["nombres"], vals["apellidos"]])
            if a.error:
                messages.error(request, a.error)
            else:
                messages.success(request, "Usuario creado.")
                return redirect("usuario_detalle", pk=uid)
        else:
            messages.error(request, "Revise los campos marcados.")
        vals.pop("password", None)
    return render(request, "staff/form.html", {"titulo": "Nuevo usuario", "campos": campos, "valores": vals, "errores": errs, "volver": "/admin-sistema/usuarios/"})


@permiso("USR_GESTIONAR")
def usuario_detalle(request, pk):
    def cargar():
        return db.q1("""SELECT u.*, r.nombre AS rol_nombre, r.codigo AS rol_codigo, (u.bloqueado_hasta IS NOT NULL AND u.bloqueado_hasta > now()) AS bloqueado
                        FROM usuario u JOIN rol r ON r.id=u.rol_id WHERE u.id=%s""", [pk])
    u = cargar()
    if not u:
        raise Http404()
    if request.method == "POST":
        accion = request.POST.get("accion")
        with db.accion() as a:
            if accion == "rol":
                if pk == request.usuario["id"]:
                    messages.error(request, "No puede cambiar su propio rol.")
                else:
                    db.ex("UPDATE usuario SET rol_id=%s WHERE id=%s", [request.POST["rol_id"], pk])
                    messages.success(request, "Rol actualizado.")
            elif accion == "activo":
                if pk == request.usuario["id"]:
                    messages.error(request, "No puede desactivar su propia cuenta.")
                else:
                    db.ex("UPDATE usuario SET activo = NOT activo WHERE id=%s", [pk])
                    messages.success(request, "Estado de la cuenta actualizado.")
            elif accion == "desbloquear":
                db.ex("UPDATE usuario SET intentos_fallidos=0, bloqueado_hasta=NULL WHERE id=%s", [pk])
                db.ex("INSERT INTO bitacora_acceso(usuario_id, username_intentado, evento, exito, detalle) VALUES (%s,%s,'DESBLOQUEO',true,%s)",
                      [pk, u["username"], f"Desbloqueado por {request.usuario['username']}"])
                messages.success(request, "Cuenta desbloqueada.")
            elif accion == "password":
                nueva = request.POST.get("password", "")
                err = password_valida(nueva)
                if err:
                    messages.error(request, err)
                else:
                    db.ex("UPDATE usuario SET password_hash=%s, intentos_fallidos=0, bloqueado_hasta=NULL WHERE id=%s", [make_password(nueva), pk])
                    messages.success(request, "Contraseña restablecida.")
        if a.error:
            messages.error(request, a.error)
        return redirect("usuario_detalle", pk=pk)
    eventos = db.q("SELECT * FROM bitacora_acceso WHERE usuario_id=%s ORDER BY id DESC LIMIT 15", [pk])
    return render(request, "admin/usuario.html", {"u": u, "roles": ROLES(), "eventos": eventos})


@permiso("USR_GESTIONAR")
def bitacora(request):
    ev = request.GET.get("evento", "")
    sql = "SELECT b.*, u.nombres||' '||u.apellidos AS nombre FROM bitacora_acceso b LEFT JOIN usuario u ON u.id=b.usuario_id"
    par = []
    if ev:
        sql += " WHERE b.evento::text = %s"
        par.append(ev)
    eventos = [e["e"] for e in db.q("SELECT unnest(enum_range(NULL::evento_acceso))::text AS e")]
    return render(request, "admin/bitacora.html", {"lista": db.q(sql + " ORDER BY b.id DESC LIMIT 200", par), "ev": ev, "eventos": eventos})


REPORTES = {
    "ventas_mensuales": ("Ventas mensuales", "SELECT * FROM v_ventas_mensuales ORDER BY mes"),
    "cobros_mensuales": ("Cobros mensuales", "SELECT * FROM v_cobros_mensuales ORDER BY mes"),
    "servicios_mas_solicitados": ("Servicios más solicitados", "SELECT * FROM v_servicios_mas_solicitados ORDER BY reservas DESC"),
    "clientes_frecuentes": ("Clientes frecuentes", "SELECT * FROM v_clientes_frecuentes ORDER BY reservas DESC, total_gastado DESC"),
    "saldos_reservas": ("Saldos de reservas", "SELECT * FROM v_reserva_saldo ORDER BY reserva_id"),
    "cotizaciones_por_vencer": ("Cotizaciones por vencer", "SELECT * FROM v_cotizaciones_por_vencer ORDER BY dias_restantes"),
}


def _json_seguro(o):
    if isinstance(o, Decimal):
        return float(o)
    if isinstance(o, (date, datetime)):
        return o.strftime("%Y-%m-%d")
    return str(o)


@permiso("REP_VER")
def reportes(request):
    ventas = db.q("SELECT * FROM v_ventas_mensuales ORDER BY mes")
    cobros = db.q("SELECT * FROM v_cobros_mensuales ORDER BY mes")
    serv = db.q("SELECT * FROM v_servicios_mas_solicitados ORDER BY reservas DESC, unidades DESC LIMIT 8")
    cli = db.q("SELECT * FROM v_clientes_frecuentes ORDER BY reservas DESC, total_gastado DESC LIMIT 8")
    resumen = db.q1("""SELECT COALESCE(sum(ventas),0) AS ventas, COALESCE(sum(comision),0) AS comision, COALESCE(sum(impuestos),0) AS impuestos, COALESCE(sum(reservas),0) AS reservas FROM v_ventas_mensuales""")
    por_estado = db.q("SELECT estado::text AS estado, count(*) AS n FROM reserva GROUP BY estado ORDER BY estado")
    datos = {
        "meses": [v["mes"].strftime("%m/%Y") for v in ventas], "ventas": [float(v["ventas"]) for v in ventas], "comision": [float(v["comision"]) for v in ventas],
        "cobros_meses": [c["mes"].strftime("%m/%Y") for c in cobros], "cobros": [float(c["cobrado"]) for c in cobros],
        "serv_n": [s["nombre"] for s in serv], "serv_v": [s["reservas"] for s in serv],
        "est_n": [e["estado"] for e in por_estado], "est_v": [e["n"] for e in por_estado],
    }
    return render(request, "admin/reportes.html", {"ventas": ventas, "cobros": cobros, "serv": serv, "cli": cli, "resumen": resumen,
                                                   "datos_json": datos, "reportes": REPORTES})


@permiso("REP_VER")
def reporte_csv(request, nombre):
    if nombre not in REPORTES:
        raise Http404()
    titulo, sql = REPORTES[nombre]
    filas = db.q(sql)
    resp = HttpResponse(content_type="text/csv; charset=utf-8")
    resp["Content-Disposition"] = f'attachment; filename="{nombre}.csv"'
    resp.write("﻿")   # BOM para que Excel respete los acentos
    if filas:
        w = csv.writer(resp, delimiter=";")
        w.writerow(filas[0].keys())
        for f in filas:
            w.writerow([str(v) if v is not None else "" for v in f.values()])
    return resp


@permiso("USR_GESTIONAR")
def parametros(request):
    if request.method == "POST":
        with db.accion() as a:
            for p in db.q("SELECT clave FROM parametro_sistema"):
                if p["clave"] in request.POST and p["clave"] != "moneda":
                    db.ex("UPDATE parametro_sistema SET valor=%s WHERE clave=%s", [request.POST[p["clave"]].strip(), p["clave"]])
        messages.error(request, a.error) if a.error else messages.success(request, "Parámetros guardados.")
        return redirect("parametros")
    return render(request, "admin/parametros.html", {"lista": db.q("SELECT * FROM parametro_sistema ORDER BY clave")})
