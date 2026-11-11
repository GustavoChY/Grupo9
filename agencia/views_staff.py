from django.contrib import messages
from django.db import DatabaseError
from django.http import Http404
from django.shortcuts import redirect, render

from . import db, forms
from .auth import permiso
from .views_cliente import CAMPOS_PASAJERO, _contexto_reserva
from .util import guardar_comprobante, guardar_imagen, borrar_imagen

SI_NO = [("1", "Sí"), ("0", "No")]
TIPOS_DOC = [("CI", "Cédula de identidad"), ("PASAPORTE", "Pasaporte"), ("CEX", "Cédula de extranjero"), ("OTRO", "Otro")]


def _flash(request, a, ok, redirigir, **kw):
    """Muestra el error de BD o el mensaje de éxito y redirige."""
    if a.error:
        messages.error(request, a.error)
    else:
        messages.success(request, ok)
    return redirect(redirigir, **kw)


# ------------------------------------------------------------------ panel de gestión
@permiso("COT_GESTIONAR")
def gestion(request):
    k = db.q1("""SELECT
        (SELECT count(*) FROM solicitud_cotizacion WHERE estado IN ('RECIBIDA','EN_ATENCION')) AS solicitudes,
        (SELECT count(*) FROM cotizacion WHERE estado='ENVIADA') AS cot_enviadas,
        (SELECT count(*) FROM cotizacion WHERE estado='ENVIADA' AND reserva_solicitada_en IS NOT NULL) AS reservas_pedidas,
        (SELECT count(*) FROM reserva WHERE estado IN ('PENDIENTE','CONFIRMADA')) AS reservas_abiertas,
        (SELECT count(*) FROM pago WHERE estado='PENDIENTE_VERIFICACION') AS pagos_pendientes,
        (SELECT COALESCE(sum(monto),0) FROM pago WHERE estado='VERIFICADO' AND date_trunc('month',fecha_pago)=date_trunc('month',CURRENT_DATE)) AS cobrado_mes""")
    ctx = {
        "k": k,
        "solicitudes": db.q("""SELECT s.*, c.nombres||' '||c.apellidos AS cliente, COALESCE(p.nombre, d.nombre) AS interes FROM solicitud_cotizacion s
                               JOIN cliente c ON c.id=s.cliente_id LEFT JOIN paquete p ON p.id=s.paquete_id LEFT JOIN destino d ON d.id=s.destino_id
                               WHERE s.estado IN ('RECIBIDA','EN_ATENCION') ORDER BY s.id LIMIT 6"""),
        "pagos": db.q("SELECT * FROM v_pagos_por_verificar ORDER BY fecha_pago LIMIT 6"),
        "por_vencer": db.q("SELECT * FROM v_cotizaciones_por_vencer ORDER BY dias_restantes LIMIT 6"),
        "pedidas": db.q("""SELECT c.id, c.codigo, c.total, c.reserva_solicitada_en, cl.nombres||' '||cl.apellidos AS cliente FROM cotizacion c JOIN cliente cl ON cl.id=c.cliente_id
                           WHERE c.estado='ENVIADA' AND c.reserva_solicitada_en IS NOT NULL ORDER BY c.reserva_solicitada_en LIMIT 6"""),
    }
    return render(request, "staff/panel.html", ctx)


# ------------------------------------------------------------------ solicitudes
@permiso("COT_GESTIONAR")
def solicitudes(request):
    est = request.GET.get("estado", "")
    sql = """SELECT s.*, c.nombres||' '||c.apellidos AS cliente, COALESCE(p.nombre, d.nombre) AS interes FROM solicitud_cotizacion s
             JOIN cliente c ON c.id=s.cliente_id LEFT JOIN paquete p ON p.id=s.paquete_id LEFT JOIN destino d ON d.id=s.destino_id"""
    par = []
    if est in ("RECIBIDA", "EN_ATENCION", "COTIZADA", "CERRADA"):
        sql += " WHERE s.estado = %s"
        par.append(est)
    return render(request, "staff/solicitudes.html", {"lista": db.q(sql + " ORDER BY s.id DESC", par), "estado": est})


@permiso("COT_GESTIONAR")
def solicitud_detalle(request, pk):
    s = db.q1("""SELECT s.*, c.nombres||' '||c.apellidos AS cliente, c.telefono, c.correo, p.nombre AS paquete, d.nombre AS destino
                 FROM solicitud_cotizacion s JOIN cliente c ON c.id=s.cliente_id LEFT JOIN paquete p ON p.id=s.paquete_id LEFT JOIN destino d ON d.id=s.destino_id WHERE s.id=%s""", [pk])
    if not s:
        raise Http404()
    if request.method == "POST":
        accion = request.POST.get("accion")
        with db.accion() as a:
            if accion == "cotizar":
                cid = db.ex_ret("""INSERT INTO cotizacion(solicitud_id, cliente_id, agente_id, paquete_id, nro_pasajeros, observaciones)
                                   VALUES (%s,%s,%s,%s,%s,%s) RETURNING id""",
                                [pk, s["cliente_id"], request.usuario["id"], s["paquete_id"], s["nro_pasajeros"], s["observaciones"]])
                if s["paquete_id"]:
                    db.escalar("SELECT fn_generar_detalle_desde_paquete(%s)", [cid])
                db.ex("UPDATE solicitud_cotizacion SET estado='EN_ATENCION', atendida_por=%s WHERE id=%s AND estado='RECIBIDA'", [request.usuario["id"], pk])
            elif accion == "cerrar":
                db.ex("UPDATE solicitud_cotizacion SET estado='CERRADA', atendida_por=COALESCE(atendida_por,%s) WHERE id=%s", [request.usuario["id"], pk])
        if a.error:
            messages.error(request, a.error)
            return redirect("solicitud_detalle", pk=pk)
        if accion == "cotizar":
            messages.success(request, "Cotización en borrador creada. Revise los servicios y envíela al cliente.")
            return redirect("cotizacion_detalle", pk=cid)
        messages.info(request, "Solicitud cerrada.")
        return redirect("solicitud_detalle", pk=pk)
    cots = db.q("SELECT id, codigo, estado, total FROM cotizacion WHERE solicitud_id=%s ORDER BY id", [pk])
    return render(request, "staff/solicitud.html", {"s": s, "cots": cots})


# ------------------------------------------------------------------ cotizaciones
@permiso("COT_GESTIONAR")
def cotizaciones(request):
    est = request.GET.get("estado", "")
    sql = """SELECT c.*, cl.nombres||' '||cl.apellidos AS cliente, p.nombre AS paquete FROM cotizacion c JOIN cliente cl ON cl.id=c.cliente_id LEFT JOIN paquete p ON p.id=c.paquete_id"""
    par = []
    if est in ("BORRADOR", "ENVIADA", "ACEPTADA", "RECHAZADA", "VENCIDA"):
        sql += " WHERE c.estado = %s"
        par.append(est)
    return render(request, "staff/cotizaciones.html", {"lista": db.q(sql + " ORDER BY c.id DESC", par), "estado": est})


@permiso("COT_GESTIONAR")
def cotizacion_nueva(request):
    clientes = db.q("SELECT id, nombres||' '||apellidos||' ('||nro_documento||')' AS n FROM cliente ORDER BY nombres")
    paquetes = db.q("SELECT id, nombre FROM paquete WHERE activo ORDER BY nombre")
    if request.method == "POST":
        try:
            cliente, n = int(request.POST["cliente_id"]), int(request.POST["nro_pasajeros"])
            paquete = int(request.POST["paquete_id"]) if request.POST.get("paquete_id") else None
        except (ValueError, KeyError):
            messages.error(request, "Complete cliente y número de pasajeros.")
            return redirect("cotizacion_nueva")
        with db.accion() as a:
            cid = db.ex_ret("INSERT INTO cotizacion(cliente_id, agente_id, paquete_id, nro_pasajeros) VALUES (%s,%s,%s,%s) RETURNING id", [cliente, request.usuario["id"], paquete, n])
            if paquete:
                db.escalar("SELECT fn_generar_detalle_desde_paquete(%s)", [cid])
        if a.error:
            messages.error(request, a.error)
            return redirect("cotizacion_nueva")
        messages.success(request, "Cotización creada en borrador.")
        return redirect("cotizacion_detalle", pk=cid)
    return render(request, "staff/cotizacion_nueva.html", {"clientes": clientes, "paquetes": paquetes})


def _cot(pk):
    c = db.q1("""SELECT c.*, cl.nombres||' '||cl.apellidos AS cliente, cl.telefono, cl.correo, p.nombre AS paquete, u.nombres||' '||u.apellidos AS agente,
                 (SELECT r.id FROM reserva r WHERE r.cotizacion_id=c.id) AS reserva_id
                 FROM cotizacion c JOIN cliente cl ON cl.id=c.cliente_id LEFT JOIN paquete p ON p.id=c.paquete_id JOIN usuario u ON u.id=c.agente_id WHERE c.id=%s""", [pk])
    if not c:
        raise Http404()
    return c


@permiso("COT_GESTIONAR")
def cotizacion_detalle(request, pk):
    c = _cot(pk)
    if request.method == "POST":
        accion = request.POST.get("accion")
        p = request.POST
        with db.accion() as a:
            if accion == "agregar":
                sid, cant = int(p["servicio_id"]), int(p["cantidad"])
                if cant < 1:
                    messages.error(request, "La cantidad debe ser al menos 1.")
                else:
                    tarifa = db.escalar("SELECT tarifa_base FROM servicio WHERE id=%s AND activo", [sid])
                    if tarifa is None:
                        messages.error(request, "El servicio no está disponible.")
                    else:
                        if db.ex("UPDATE cotizacion_detalle SET cantidad = cantidad + %s WHERE cotizacion_id=%s AND servicio_id=%s", [cant, pk, sid]) == 0:
                            db.ex("INSERT INTO cotizacion_detalle(cotizacion_id, servicio_id, cantidad, tarifa_unitaria) VALUES (%s,%s,%s,%s)", [pk, sid, cant, tarifa])
            elif accion == "quitar":
                db.ex("DELETE FROM cotizacion_detalle WHERE id=%s AND cotizacion_id=%s", [p["detalle_id"], pk])
            elif accion == "desde_paquete":
                db.ex("DELETE FROM cotizacion_detalle WHERE cotizacion_id=%s", [pk])
                db.escalar("SELECT fn_generar_detalle_desde_paquete(%s)", [pk])
            elif accion == "condiciones":
                db.ex("UPDATE cotizacion SET comision_pct=%s, impuesto_pct=%s, vigencia_hasta=%s, observaciones=%s WHERE id=%s",
                      [p["comision_pct"], p["impuesto_pct"], p["vigencia_hasta"], p.get("observaciones") or None, pk])
                db.escalar("SELECT fn_recalcular_cotizacion(%s)", [pk])
            elif accion == "enviar":
                db.ex("UPDATE cotizacion SET estado='ENVIADA' WHERE id=%s", [pk])
            elif accion == "rechazar":
                db.ex("UPDATE cotizacion SET estado='RECHAZADA' WHERE id=%s", [pk])
            elif accion == "reservar":
                rid = db.escalar("SELECT fn_convertir_cotizacion_en_reserva(%s,%s,%s,%s)", [pk, p["fecha_inicio"], p["fecha_fin"], request.usuario["id"]])
        if a.error:
            messages.error(request, a.error)
        elif accion == "reservar":
            messages.success(request, "Reserva creada correctamente. Registre ahora los pasajeros y pagos.")
            return redirect("reserva_detalle", pk=rid)
        elif accion == "enviar":
            messages.success(request, "Cotización enviada al cliente (recibirá una notificación).")
        elif accion in ("agregar", "quitar", "desde_paquete", "condiciones"):
            if not list(messages.get_messages(request)):
                messages.success(request, "Cotización actualizada y recalculada.")
        return redirect("cotizacion_detalle", pk=pk)
    detalle = db.q("""SELECT d.*, s.nombre, s.tipo, pr.nombre AS proveedor FROM cotizacion_detalle d JOIN servicio s ON s.id=d.servicio_id
                      JOIN proveedor pr ON pr.id=s.proveedor_id WHERE d.cotizacion_id=%s ORDER BY s.tipo, s.nombre""", [pk])
    servicios = db.q("SELECT s.id, s.nombre, s.tarifa_base, pr.nombre AS proveedor FROM servicio s JOIN proveedor pr ON pr.id=s.proveedor_id WHERE s.activo AND pr.activo ORDER BY s.tipo, s.nombre")
    return render(request, "staff/cotizacion.html", {"c": c, "detalle": detalle, "servicios": servicios})


# ------------------------------------------------------------------ reservas
@permiso("RES_GESTIONAR")
def reservas(request):
    est = request.GET.get("estado", "")
    sql = """SELECT s.*, r.fecha_inicio, r.fecha_fin, r.nro_pasajeros, cl.nombres||' '||cl.apellidos AS cliente FROM v_reserva_saldo s
             JOIN reserva r ON r.id=s.reserva_id JOIN cliente cl ON cl.id=s.cliente_id"""
    par = []
    if est in ("PENDIENTE", "CONFIRMADA", "PAGADA", "CANCELADA", "FINALIZADA"):
        sql += " WHERE s.estado = %s"
        par.append(est)
    return render(request, "staff/reservas.html", {"lista": db.q(sql + " ORDER BY s.reserva_id DESC", par), "estado": est})


@permiso("RES_GESTIONAR")
def reserva_detalle(request, pk):
    def cargar():
        return db.q1("""SELECT r.*, s.pagado_verificado, s.pendiente_verificacion, s.saldo, cl.nombres||' '||cl.apellidos AS cliente, cl.telefono, cl.correo,
                        co.codigo AS cotizacion, u.nombres||' '||u.apellidos AS agente
                        FROM reserva r JOIN v_reserva_saldo s ON s.reserva_id=r.id JOIN cliente cl ON cl.id=r.cliente_id
                        JOIN cotizacion co ON co.id=r.cotizacion_id JOIN usuario u ON u.id=r.agente_id WHERE r.id=%s""", [pk])
    r = cargar()
    if not r:
        raise Http404()
    from .views_cliente import CAMPOS_PAGO
    campos_pago = [CAMPOS_PAGO[0], forms.campo("metodo", "Método", "select", opciones=[("EFECTIVO", "Efectivo"), ("TRANSFERENCIA", "Transferencia"), ("DEPOSITO", "Depósito")], col=4), CAMPOS_PAGO[2], CAMPOS_PAGO[3]]
    campos_pago[3] = forms.campo("nro_comprobante", "Nro. de comprobante (no requerido en efectivo)", req=False, col=6, largo=60)
    vp, vg, ep, eg = {}, {}, {}, {}
    if request.method == "POST":
        accion = request.POST.get("accion")
        p = request.POST
        if accion == "pasajero":
            vp, ep = forms.leer(p, CAMPOS_PASAJERO)
            if not ep:
                with db.accion() as a:
                    db.ex("""INSERT INTO pasajero(reserva_id,tipo,nombres,apellidos,tipo_documento,nro_documento,nacionalidad,fecha_nacimiento)
                             VALUES (%s,%s,%s,%s,%s,%s,COALESCE(%s,'Boliviana'),%s)""",
                          [pk, vp["tipo"], vp["nombres"], vp["apellidos"], vp["tipo_documento"], vp["nro_documento"], vp["nacionalidad"], vp["fecha_nacimiento"]])
                if not a.error:
                    messages.success(request, "Pasajero agregado.")
                    return redirect("reserva_detalle", pk=pk)
                messages.error(request, a.error)
            else:
                messages.error(request, "Revise los datos del pasajero.")
        elif accion == "quitar_pasajero":
            with db.accion() as a:
                db.ex("DELETE FROM pasajero WHERE id=%s AND reserva_id=%s", [p.get("pasajero_id"), pk])
            return _flash(request, a, "Pasajero eliminado.", "reserva_detalle", pk=pk)
        elif accion == "pago":
            vg, eg = forms.leer(p, campos_pago)
            if vg.get("metodo") and vg["metodo"] != "EFECTIVO" and not vg.get("nro_comprobante"):
                eg["nro_comprobante"] = "Indique el número de comprobante."
            ruta = None
            if request.FILES.get("archivo"):
                ruta, err = guardar_comprobante(request.FILES["archivo"])
                if err:
                    eg["archivo"] = err
            if not eg:
                with db.accion() as a:
                    db.ex("""INSERT INTO pago(reserva_id, registrado_por, monto, metodo, nro_comprobante, comprobante_archivo, fecha_pago) VALUES (%s,%s,%s,%s,%s,%s,%s)""",
                          [pk, request.usuario["id"], vg["monto"], vg["metodo"], vg["nro_comprobante"], ruta, vg["fecha_pago"]])
                return _flash(request, a, "Pago registrado: queda pendiente de verificación.", "reserva_detalle", pk=pk)
            messages.error(request, "Revise los datos del pago.")
        elif accion in ("confirmar", "finalizar", "cancelar"):
            nuevo = {"confirmar": "CONFIRMADA", "finalizar": "FINALIZADA", "cancelar": "CANCELADA"}[accion]
            motivo = p.get("motivo", "").strip() or None
            if accion == "cancelar" and (not motivo or len(motivo) < 5):
                messages.error(request, "Indique el motivo de la cancelación.")
                return redirect("reserva_detalle", pk=pk)
            with db.accion() as a:
                db.ex("UPDATE reserva SET estado=%s, motivo_cancelacion=COALESCE(%s, motivo_cancelacion) WHERE id=%s", [nuevo, motivo, pk])
            return _flash(request, a, f"Reserva {nuevo.lower()}.", "reserva_detalle", pk=pk)
        r = cargar()
    ctx = _contexto_reserva(pk)
    ctx.update({"r": r, "campos_pasajero": CAMPOS_PASAJERO, "campos_pago": campos_pago, "vp": vp, "ep": ep, "vg": vg, "eg": eg, "es_staff": True})
    return render(request, "staff/reserva.html", ctx)


# ------------------------------------------------------------------ pagos
@permiso("PAGO_VERIFICAR")
def pagos(request):
    pendientes = db.q("SELECT * FROM v_pagos_por_verificar ORDER BY fecha_pago, pago_id")
    for p in pendientes:
        p["reserva_id"] = db.escalar("SELECT id FROM reserva WHERE codigo=%s", [p["reserva"]])
        p["tiene_archivo"] = bool(db.escalar("SELECT comprobante_archivo FROM pago WHERE id=%s", [p["pago_id"]]))
    resueltos = db.q("""SELECT p.*, r.codigo AS reserva, r.id AS reserva_id, cl.nombres||' '||cl.apellidos AS cliente, u.nombres||' '||u.apellidos AS verificador
                        FROM pago p JOIN reserva r ON r.id=p.reserva_id JOIN cliente cl ON cl.id=r.cliente_id LEFT JOIN usuario u ON u.id=p.verificado_por
                        WHERE p.estado <> 'PENDIENTE_VERIFICACION' ORDER BY p.fecha_verificacion DESC NULLS LAST LIMIT 30""")
    return render(request, "staff/pagos.html", {"pendientes": pendientes, "resueltos": resueltos})


@permiso("PAGO_VERIFICAR")
def pago_resolver(request, pk):
    if request.method != "POST":
        return redirect("pagos")
    decision = request.POST.get("decision")
    obs = request.POST.get("observacion", "").strip() or None
    if decision == "rechazar" and not obs:
        messages.error(request, "Para rechazar un pago debe escribir el motivo.")
        return redirect(request.POST.get("volver") or "pagos")
    with db.accion() as a:
        db.ex("UPDATE pago SET estado=%s, observacion=COALESCE(%s, observacion) WHERE id=%s",
              ["VERIFICADO" if decision == "verificar" else "RECHAZADO", obs, pk])
    ok = "Pago verificado: el saldo de la reserva se actualizó." if decision == "verificar" else "Pago rechazado y cliente notificado."
    if a.error:
        messages.error(request, a.error)
    else:
        messages.success(request, ok)
    return redirect(request.POST.get("volver") or "pagos")


# ------------------------------------------------------------------ clientes
CAMPOS_CLIENTE = [
    forms.campo("nombres", "Nombres", largo=80),
    forms.campo("apellidos", "Apellidos", largo=80),
    forms.campo("tipo_documento", "Tipo de documento", "select", opciones=TIPOS_DOC),
    forms.campo("nro_documento", "Nro. de documento", largo=30),
    forms.campo("nacionalidad", "Nacionalidad", req=False, largo=60),
    forms.campo("fecha_nacimiento", "Fecha de nacimiento", "date", req=False),
    forms.campo("telefono", "Teléfono", req=False, largo=30),
    forms.campo("correo", "Correo", "email", req=False),
    forms.campo("direccion", "Dirección", req=False, col=12, largo=200),
    forms.campo("preferencias", "Preferencias de viaje", "textarea", req=False, col=12),
]


@permiso("CLI_GESTIONAR")
def clientes(request):
    t = request.GET.get("q", "").strip()
    sql = "SELECT c.*, (SELECT count(*) FROM reserva r WHERE r.cliente_id=c.id) AS reservas FROM cliente c"
    par = []
    if t:
        sql += " WHERE c.nombres ILIKE %s OR c.apellidos ILIKE %s OR c.nro_documento ILIKE %s"
        par = [f"%{t}%"] * 3
    return render(request, "staff/clientes.html", {"lista": db.q(sql + " ORDER BY c.apellidos, c.nombres", par), "texto": t})


@permiso("CLI_GESTIONAR")
def cliente_detalle(request, pk):
    c = db.q1("SELECT * FROM cliente WHERE id=%s", [pk])
    if not c:
        raise Http404()
    return render(request, "staff/cliente.html", {
        "c": c,
        "reservas": db.q("SELECT s.*, r.fecha_inicio, r.fecha_fin FROM v_reserva_saldo s JOIN reserva r ON r.id=s.reserva_id WHERE s.cliente_id=%s ORDER BY s.reserva_id DESC", [pk]),
        "cotizaciones": db.q("SELECT * FROM cotizacion WHERE cliente_id=%s ORDER BY id DESC", [pk]),
    })


def _formulario(request, titulo, campos, vals, guardar, volver, extra=None, plantilla="staff/form.html"):
    errs = {}
    if request.method == "POST":
        vals2, errs = forms.leer(request.POST, campos)
        vals.update(vals2)
        if not errs:
            with db.accion() as a:
                destino = guardar(vals)
            if a.error:
                messages.error(request, a.error)
            else:
                messages.success(request, "Datos guardados correctamente.")
                return redirect(destino or volver)
        else:
            messages.error(request, "Revise los campos marcados.")
    ctx = {"titulo": titulo, "campos": campos, "valores": vals, "errores": errs, "volver": volver}
    ctx.update(extra or {})
    return render(request, plantilla, ctx)


@permiso("CLI_GESTIONAR")
def cliente_form(request, pk=None):
    actual = db.q1("SELECT * FROM cliente WHERE id=%s", [pk]) if pk else None
    if pk and not actual:
        raise Http404()

    def guardar(v):
        cols = ["nombres", "apellidos", "tipo_documento", "nro_documento", "nacionalidad", "fecha_nacimiento", "telefono", "correo", "direccion", "preferencias"]
        v = dict(v)
        v["nacionalidad"] = v["nacionalidad"] or "Boliviana"
        if pk:
            db.ex("UPDATE cliente SET " + ",".join(f"{c}=%s" for c in cols) + " WHERE id=%s", [v[c] for c in cols] + [pk])
            return None
        db.ex(f"INSERT INTO cliente({','.join(cols)}) VALUES ({','.join(['%s'] * len(cols))})", [v[c] for c in cols])
        return "/gestion/clientes/"
    return _formulario(request, "Editar cliente" if pk else "Nuevo cliente", CAMPOS_CLIENTE, dict(actual or {"nacionalidad": "Boliviana"}), guardar, "/gestion/clientes/")


# ------------------------------------------------------------------ proveedores
CAMPOS_PROVEEDOR = [
    forms.campo("nombre", "Nombre / razón social", largo=120),
    forms.campo("tipo", "Tipo de proveedor", "select", opciones=[("AEROLINEA", "Aerolínea"), ("HOTEL", "Hotel"), ("OPERADOR_TOUR", "Operador de tour"), ("TRANSPORTE", "Transporte"), ("ASEGURADORA", "Aseguradora")]),
    forms.campo("nit", "NIT", largo=30),
    forms.campo("contacto_nombre", "Persona de contacto", req=False, largo=100),
    forms.campo("contacto_telefono", "Teléfono de contacto", req=False, largo=30),
    forms.campo("contacto_correo", "Correo de contacto", "email", req=False),
    forms.campo("politicas", "Políticas (cancelación, pagos…)", "textarea", req=False, col=12),
    forms.campo("activo", "Proveedor activo", "checkbox", req=False, col=12),
]


@permiso("PROV_GESTIONAR")
def proveedores(request):
    lista = db.q("SELECT p.*, (SELECT count(*) FROM servicio s WHERE s.proveedor_id=p.id) AS servicios FROM proveedor p ORDER BY p.nombre")
    return render(request, "staff/proveedores.html", {"lista": lista})


@permiso("PROV_GESTIONAR")
def proveedor_form(request, pk=None):
    actual = db.q1("SELECT * FROM proveedor WHERE id=%s", [pk]) if pk else None
    if pk and not actual:
        raise Http404()
    cols = ["nombre", "tipo", "nit", "contacto_nombre", "contacto_telefono", "contacto_correo", "politicas", "activo"]

    def guardar(v):
        if pk:
            db.ex("UPDATE proveedor SET " + ",".join(f"{c}=%s" for c in cols) + " WHERE id=%s", [v[c] for c in cols] + [pk])
        else:
            db.ex(f"INSERT INTO proveedor({','.join(cols)}) VALUES ({','.join(['%s'] * len(cols))})", [v[c] for c in cols])
        return "/gestion/proveedores/"
    return _formulario(request, "Editar proveedor" if pk else "Nuevo proveedor", CAMPOS_PROVEEDOR, dict(actual or {"activo": True}), guardar, "/gestion/proveedores/")


# ------------------------------------------------------------------ servicios
@permiso("PROV_GESTIONAR")
def servicios(request):
    lista = db.q("""SELECT s.*, p.nombre AS proveedor, d.nombre AS destino FROM servicio s JOIN proveedor p ON p.id=s.proveedor_id LEFT JOIN destino d ON d.id=s.destino_id ORDER BY s.tipo, s.nombre""")
    return render(request, "staff/servicios.html", {"lista": lista})


@permiso("PROV_GESTIONAR")
def servicio_form(request, pk=None):
    actual = db.q1("SELECT * FROM servicio WHERE id=%s", [pk]) if pk else None
    if pk and not actual:
        raise Http404()
    provs = [(p["id"], p["nombre"]) for p in db.q("SELECT id, nombre FROM proveedor ORDER BY nombre")]
    dests = [(d["id"], f"{d['nombre']} ({d['pais']})") for d in db.q("SELECT id, nombre, pais FROM destino ORDER BY nombre")]
    campos = [
        forms.campo("proveedor_id", "Proveedor", "select", opciones=provs),
        forms.campo("nombre", "Nombre del servicio", largo=150),
        forms.campo("tipo", "Tipo", "select", opciones=[("AEREO", "Aéreo"), ("HOSPEDAJE", "Hospedaje"), ("TRASLADO", "Traslado"), ("TOUR", "Tour"), ("SEGURO", "Seguro")]),
        forms.campo("destino_id", "Destino", "select", opciones=dests),
        forms.campo("categoria", "Categoría tarifaria", "select", opciones=[("ECONOMICA", "Económica"), ("ESTANDAR", "Estándar"), ("PREMIUM", "Premium")]),
        forms.campo("temporada", "Temporada", "select", opciones=[("TODO_ANO", "Todo el año"), ("ALTA", "Alta"), ("BAJA", "Baja")]),
        forms.campo("tarifa_base", "Tarifa base por unidad (Bs)", "number", minimo=0, step="0.01"),
        forms.campo("cupo_referencial", "Cupo referencial", "int", minimo=0),
        forms.campo("politica", "Política resumida", req=False, col=12, largo=250),
        forms.campo("descripcion", "Descripción", "textarea", req=False, col=12),
        forms.campo("activo", "Servicio activo", "checkbox", req=False, col=12),
    ]
    cols = ["proveedor_id", "nombre", "tipo", "destino_id", "categoria", "temporada", "tarifa_base", "cupo_referencial", "politica", "descripcion", "activo"]

    def guardar(v):
        v = dict(v)
        if pk:
            db.ex("UPDATE servicio SET " + ",".join(f"{c}=%s" for c in cols) + " WHERE id=%s", [v[c] for c in cols] + [pk])
        else:
            db.ex(f"INSERT INTO servicio({','.join(cols)}) VALUES ({','.join(['%s'] * len(cols))})", [v[c] for c in cols])
        return "/gestion/servicios/"
    base = dict(actual) if actual else {"activo": True, "categoria": "ESTANDAR", "temporada": "TODO_ANO", "cupo_referencial": 0}
    extra = {}
    if pk:
        extra["historial"] = db.q("""SELECT h.*, u.nombres||' '||u.apellidos AS usuario FROM historial_tarifa h LEFT JOIN usuario u ON u.id=h.usuario_id WHERE h.servicio_id=%s ORDER BY h.id DESC LIMIT 10""", [pk])
    return _formulario(request, "Editar servicio" if pk else "Nuevo servicio", campos, base, guardar, "/gestion/servicios/", extra)


class ErrorImagen(DatabaseError):
    """Error de validación de imagen: se muestra como mensaje al usuario."""


def raise_imagen(msg):
    raise ErrorImagen(msg)


# ------------------------------------------------------------------ paquetes
@permiso("PAQ_GESTIONAR")
def paquetes_gestion(request):
    lista = db.q("""SELECT p.*, COALESCE(p.imagen, d.imagen) AS foto, d.nombre AS destino, vp.precio_final, vp.costo_proveedor FROM paquete p JOIN destino d ON d.id=p.destino_id
                    JOIN v_paquete_precio vp ON vp.paquete_id=p.id ORDER BY p.id""")
    return render(request, "staff/paquetes.html", {"lista": lista})


@permiso("PAQ_GESTIONAR")
def paquete_form(request, pk=None):
    actual = db.q1("SELECT * FROM paquete WHERE id=%s", [pk]) if pk else None
    if pk and not actual:
        raise Http404()
    dests = [(d["id"], f"{d['nombre']} ({d['pais']})") for d in db.q("SELECT id, nombre, pais FROM destino ORDER BY nombre")]
    campos = [
        forms.campo("nombre", "Nombre del paquete", largo=150, col=8),
        forms.campo("destino_id", "Destino", "select", opciones=dests, col=4),
        forms.campo("duracion_dias", "Duración (días)", "int", minimo=1, col=3),
        forms.campo("comision_pct", "Comisión (%)", "number", minimo=0, maximo=100, step="0.01", col=3),
        forms.campo("impuesto_pct", "Impuesto (%)", "number", minimo=0, maximo=100, step="0.01", col=3),
        forms.campo("vigente_desde", "Vigente desde", "date", col=3),
        forms.campo("vigente_hasta", "Vigente hasta", "date", col=3),
        forms.campo("descripcion", "Descripción", "textarea", req=False, col=12),
        forms.campo("activo", "Paquete activo", "checkbox", req=False, col=12),
    ]
    todos = db.q("SELECT s.id, s.nombre, s.tipo, s.tarifa_base, pr.nombre AS proveedor FROM servicio s JOIN proveedor pr ON pr.id=s.proveedor_id WHERE s.activo ORDER BY s.tipo, s.nombre")
    elegidos = {r["servicio_id"]: r["cantidad"] for r in db.q("SELECT servicio_id, cantidad FROM paquete_servicio WHERE paquete_id=%s", [pk])} if pk else {}
    if request.method == "POST":
        elegidos = {}
        for s in todos:
            if f"srv_{s['id']}" in request.POST:
                try:
                    elegidos[s["id"]] = max(1, int(request.POST.get(f"cant_{s['id']}", "1")))
                except ValueError:
                    elegidos[s["id"]] = 1
    cols = ["nombre", "destino_id", "duracion_dias", "comision_pct", "impuesto_pct", "vigente_desde", "vigente_hasta", "descripcion", "activo"]
    imagen_actual = actual["imagen"] if actual else None

    def guardar(v):
        nonlocal pk
        if pk:
            db.ex("UPDATE paquete SET " + ",".join(f"{c}=%s" for c in cols) + " WHERE id=%s", [v[c] for c in cols] + [pk])
        else:
            pk = db.ex_ret(f"INSERT INTO paquete({','.join(cols)}) VALUES ({','.join(['%s'] * len(cols))}) RETURNING id", [v[c] for c in cols])
        archivo = request.FILES.get("imagen")
        if archivo:
            ruta, err = guardar_imagen(archivo, "paquetes")
            if err:
                raise_imagen(err)
            db.ex("UPDATE paquete SET imagen=%s WHERE id=%s", [ruta, pk])
            borrar_imagen(imagen_actual)
        elif request.POST.get("quitar_imagen") and imagen_actual:
            db.ex("UPDATE paquete SET imagen=NULL WHERE id=%s", [pk])
            borrar_imagen(imagen_actual)
        db.ex("DELETE FROM paquete_servicio WHERE paquete_id=%s", [pk])
        for sid, cant in elegidos.items():
            db.ex("INSERT INTO paquete_servicio(paquete_id, servicio_id, cantidad) VALUES (%s,%s,%s)", [pk, sid, cant])
        return "/gestion/paquetes/"
    base = dict(actual) if actual else {"activo": True, "comision_pct": 10, "impuesto_pct": 13}
    for s in todos:
        s["marcado"] = s["id"] in elegidos
        s["cant"] = elegidos.get(s["id"], 1)
    return _formulario(request, "Editar paquete" if pk else "Nuevo paquete", campos, base, guardar, "/gestion/paquetes/",
                       {"servicios": todos, "imagen": imagen_actual}, "staff/paquete_form.html")


# ------------------------------------------------------------------ tareas automáticas
@permiso("COT_GESTIONAR")
def tareas(request):
    if request.method == "POST":
        t = request.POST.get("tarea")
        with db.accion() as a:
            if t == "vencer":
                n = db.escalar("SELECT fn_vencer_cotizaciones()")
                msg = f"{n} cotización(es) vencida(s) actualizada(s)."
            else:
                n = db.escalar("SELECT fn_finalizar_reservas()")
                msg = f"{n} reserva(s) finalizada(s)."
        messages.error(request, a.error) if a.error else messages.success(request, msg)
        return redirect("tareas")
    return render(request, "staff/tareas.html")


# ------------------------------------------------------------------ destinos
@permiso("PAQ_GESTIONAR")
def destinos(request):
    lista = db.q("""SELECT d.*, (SELECT count(*) FROM paquete p WHERE p.destino_id=d.id) AS paquetes,
                    (SELECT count(*) FROM servicio s WHERE s.destino_id=d.id) AS servicios FROM destino d ORDER BY d.pais, d.nombre""")
    return render(request, "staff/destinos.html", {"lista": lista})


@permiso("PAQ_GESTIONAR")
def destino_form(request, pk=None):
    actual = db.q1("SELECT * FROM destino WHERE id=%s", [pk]) if pk else None
    if pk and not actual:
        raise Http404()
    campos = [
        forms.campo("nombre", "Nombre del destino", largo=100),
        forms.campo("pais", "País", largo=80),
        forms.campo("ambito", "Ámbito", "select", opciones=[("NACIONAL", "Nacional"), ("INTERNACIONAL", "Internacional")]),
    ]
    imagen_actual = actual["imagen"] if actual else None
    nuevo_pk = {"v": pk}

    def guardar(v):
        if pk:
            db.ex("UPDATE destino SET nombre=%s, pais=%s, ambito=%s WHERE id=%s", [v["nombre"], v["pais"], v["ambito"], pk])
        else:
            nuevo_pk["v"] = db.ex_ret("INSERT INTO destino(nombre, pais, ambito) VALUES (%s,%s,%s) RETURNING id", [v["nombre"], v["pais"], v["ambito"]])
        archivo = request.FILES.get("imagen")
        if archivo:
            ruta, err = guardar_imagen(archivo, "destinos")
            if err:
                raise_imagen(err)
            db.ex("UPDATE destino SET imagen=%s WHERE id=%s", [ruta, nuevo_pk["v"]])
            borrar_imagen(imagen_actual)
        elif request.POST.get("quitar_imagen") and imagen_actual:
            db.ex("UPDATE destino SET imagen=NULL WHERE id=%s", [pk])
            borrar_imagen(imagen_actual)
        return "/gestion/destinos/"
    return _formulario(request, "Editar destino" if pk else "Nuevo destino", campos, dict(actual or {"ambito": "NACIONAL"}), guardar,
                       "/gestion/destinos/", {"imagen": imagen_actual, "con_imagen": True})


@permiso("PAQ_GESTIONAR")
def destino_eliminar(request, pk):
    if request.method == "POST":
        img = db.escalar("SELECT imagen FROM destino WHERE id=%s", [pk])
        with db.accion() as a:
            db.ex("DELETE FROM destino WHERE id=%s", [pk])
        if a.error:
            messages.error(request, "No se puede eliminar: el destino está usado por paquetes, servicios o solicitudes. Puede editarlo en su lugar.")
        else:
            borrar_imagen(img)
            messages.success(request, "Destino eliminado.")
    return redirect("destinos")
