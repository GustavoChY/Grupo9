from django.contrib import messages
from django.http import Http404
from django.shortcuts import redirect, render

from . import db, forms
from .auth import permiso, solo_cliente
from .util import guardar_comprobante


def _reserva_propia(request, pk):
    r = db.q1("""SELECT r.*, s.pagado_verificado, s.pendiente_verificacion, s.saldo FROM reserva r JOIN v_reserva_saldo s ON s.reserva_id = r.id
                 WHERE r.id=%s AND r.cliente_id=%s""", [pk, request.cliente["id"]])
    if not r:
        raise Http404()
    return r


# ------------------------------------------------------------------ solicitar cotización
@solo_cliente
@permiso("COT_SOLICITAR")
def solicitar(request):
    paquetes = db.q("""SELECT p.id, p.nombre, d.nombre AS destino FROM paquete p JOIN destino d ON d.id=p.destino_id
                       WHERE p.activo AND CURRENT_DATE BETWEEN p.vigente_desde AND p.vigente_hasta ORDER BY p.nombre""")
    destinos = db.q("SELECT id, nombre, pais FROM destino ORDER BY nombre")
    vals = {"paquete_id": request.GET.get("paquete", ""), "nro_pasajeros": 1}
    errs = {}
    if request.method == "POST":
        p = request.POST
        vals = {k: p.get(k, "").strip() for k in ("paquete_id", "destino_id", "fecha_viaje_inicio", "fecha_viaje_fin", "nro_pasajeros", "observaciones")}
        try:
            n = int(vals["nro_pasajeros"])
            if n < 1 or n > 50:
                raise ValueError
        except ValueError:
            errs["nro_pasajeros"] = "Indique entre 1 y 50 pasajeros."
        if not vals["paquete_id"] and not vals["destino_id"]:
            errs["paquete_id"] = "Elija un paquete o un destino."
        ini, fin = vals["fecha_viaje_inicio"] or None, vals["fecha_viaje_fin"] or None
        if ini and fin and fin < ini:
            errs["fecha_viaje_fin"] = "La fecha de regreso no puede ser anterior a la de salida."
        if not errs:
            with db.accion() as a:
                db.ex("""INSERT INTO solicitud_cotizacion(cliente_id, paquete_id, destino_id, fecha_viaje_inicio, fecha_viaje_fin, nro_pasajeros, observaciones)
                         VALUES (%s,%s,%s,%s,%s,%s,%s)""",
                      [request.cliente["id"], vals["paquete_id"] or None, (vals["destino_id"] or None) if not vals["paquete_id"] else None,
                       ini, fin, n, vals["observaciones"] or None])
            if a.error:
                messages.error(request, a.error)
            else:
                messages.success(request, "¡Solicitud enviada! Un agente la atenderá y le enviará su cotización.")
                return redirect("mis_solicitudes")
        else:
            messages.error(request, "Revise los campos marcados.")
    return render(request, "cliente/solicitar.html", {"paquetes": paquetes, "destinos": destinos, "v": vals, "errores": errs})


@solo_cliente
def mis_solicitudes(request):
    lista = db.q("""SELECT s.*, p.nombre AS paquete, d.nombre AS destino, (SELECT c.id FROM cotizacion c WHERE c.solicitud_id=s.id ORDER BY c.id DESC LIMIT 1) AS cotizacion_id
                    FROM solicitud_cotizacion s LEFT JOIN paquete p ON p.id=s.paquete_id LEFT JOIN destino d ON d.id=s.destino_id
                    WHERE s.cliente_id=%s ORDER BY s.id DESC""", [request.cliente["id"]])
    return render(request, "cliente/solicitudes.html", {"lista": lista})


@solo_cliente
def mis_cotizaciones(request):
    lista = db.q("""SELECT c.*, p.nombre AS paquete FROM cotizacion c LEFT JOIN paquete p ON p.id=c.paquete_id
                    WHERE c.cliente_id=%s AND c.estado <> 'BORRADOR' ORDER BY c.id DESC""", [request.cliente["id"]])
    return render(request, "cliente/cotizaciones.html", {"lista": lista})


@solo_cliente
def mi_cotizacion(request, pk):
    c = db.q1("""SELECT c.*, p.nombre AS paquete, (SELECT r.id FROM reserva r WHERE r.cotizacion_id=c.id) AS reserva_id
                 FROM cotizacion c LEFT JOIN paquete p ON p.id=c.paquete_id WHERE c.id=%s AND c.cliente_id=%s AND c.estado <> 'BORRADOR'""", [pk, request.cliente["id"]])
    if not c:
        raise Http404()
    if request.method == "POST":
        accion = request.POST.get("accion")
        with db.accion() as a:
            if accion == "reservar":
                if c["estado"] != "ENVIADA":
                    raise_msg = "Esta cotización ya no admite solicitar la reserva."
                    messages.error(request, raise_msg)
                else:
                    db.ex("UPDATE cotizacion SET reserva_solicitada_en = now() WHERE id=%s AND reserva_solicitada_en IS NULL", [pk])
                    messages.success(request, "Solicitud de reserva enviada. El agente la confirmará a la brevedad.")
            elif accion == "rechazar":
                db.ex("UPDATE cotizacion SET estado='RECHAZADA' WHERE id=%s", [pk])
                messages.info(request, "Cotización rechazada.")
        if a.error:
            messages.error(request, a.error)
        return redirect("mi_cotizacion", pk=pk)
    detalle = db.q("""SELECT d.*, s.nombre, s.tipo FROM cotizacion_detalle d JOIN servicio s ON s.id=d.servicio_id WHERE d.cotizacion_id=%s ORDER BY s.tipo, s.nombre""", [pk])
    return render(request, "cliente/cotizacion.html", {"c": c, "detalle": detalle})


@solo_cliente
def mis_reservas(request):
    lista = db.q("""SELECT s.*, r.fecha_inicio, r.fecha_fin, r.nro_pasajeros FROM v_reserva_saldo s JOIN reserva r ON r.id=s.reserva_id
                    WHERE s.cliente_id=%s ORDER BY s.reserva_id DESC""", [request.cliente["id"]])
    return render(request, "cliente/reservas.html", {"lista": lista})


CAMPOS_PASAJERO = [
    forms.campo("tipo", "Tipo", "select", opciones=[("ADULTO", "Adulto"), ("MENOR", "Menor"), ("INFANTE", "Infante")], col=4),
    forms.campo("nombres", "Nombres", col=4, largo=80),
    forms.campo("apellidos", "Apellidos", col=4, largo=80),
    forms.campo("tipo_documento", "Documento", "select", opciones=[("CI", "CI"), ("PASAPORTE", "Pasaporte"), ("CEX", "CEX"), ("OTRO", "Otro")], col=3),
    forms.campo("nro_documento", "Nro. documento", col=3, largo=30),
    forms.campo("nacionalidad", "Nacionalidad", col=3, req=False, largo=60),
    forms.campo("fecha_nacimiento", "Nacimiento", "date", col=3),
]
CAMPOS_PAGO = [
    forms.campo("monto", "Monto (Bs)", "number", minimo=0.01, col=4, step="0.01"),
    forms.campo("metodo", "Método", "select", opciones=[("TRANSFERENCIA", "Transferencia"), ("DEPOSITO", "Depósito")], col=4),
    forms.campo("fecha_pago", "Fecha del pago", "date", col=4),
    forms.campo("nro_comprobante", "Nro. de comprobante", col=6, largo=60),
]


@solo_cliente
def mi_reserva(request, pk):
    r = _reserva_propia(request, pk)
    errores_p, errores_g = {}, {}
    vp, vg = {}, {}
    if request.method == "POST":
        accion = request.POST.get("accion")
        if accion == "pasajero":
            vp, errores_p = forms.leer(request.POST, CAMPOS_PASAJERO)
            if not errores_p:
                with db.accion() as a:
                    db.ex("""INSERT INTO pasajero(reserva_id,tipo,nombres,apellidos,tipo_documento,nro_documento,nacionalidad,fecha_nacimiento)
                             VALUES (%s,%s,%s,%s,%s,%s,COALESCE(%s,'Boliviana'),%s)""",
                          [pk, vp["tipo"], vp["nombres"], vp["apellidos"], vp["tipo_documento"], vp["nro_documento"], vp["nacionalidad"], vp["fecha_nacimiento"]])
                if a.error:
                    messages.error(request, a.error)
                else:
                    messages.success(request, "Pasajero agregado.")
                    return redirect("mi_reserva", pk=pk)
            else:
                messages.error(request, "Revise los datos del pasajero.")
        elif accion == "quitar_pasajero":
            with db.accion() as a:
                db.ex("DELETE FROM pasajero WHERE id=%s AND reserva_id=%s", [request.POST.get("pasajero_id"), pk])
            messages.error(request, a.error) if a.error else messages.info(request, "Pasajero eliminado.")
            return redirect("mi_reserva", pk=pk)
        elif accion == "pago":
            vg, errores_g = forms.leer(request.POST, CAMPOS_PAGO)
            if vg.get("metodo") != "EFECTIVO" and not vg.get("nro_comprobante") and "nro_comprobante" not in errores_g:
                errores_g["nro_comprobante"] = "Indique el número de comprobante."
            archivo = request.FILES.get("archivo")
            ruta = None
            if archivo:
                ruta, err = guardar_comprobante(archivo)
                if err:
                    errores_g["archivo"] = err
            if not errores_g:
                with db.accion() as a:
                    db.ex("""INSERT INTO pago(reserva_id, registrado_por, monto, metodo, nro_comprobante, comprobante_archivo, fecha_pago)
                             VALUES (%s,%s,%s,%s,%s,%s,%s)""",
                          [pk, request.usuario["id"], vg["monto"], vg["metodo"], vg["nro_comprobante"], ruta, vg["fecha_pago"]])
                if a.error:
                    messages.error(request, a.error)
                else:
                    messages.success(request, "Pago registrado. Un agente lo verificará y le avisaremos.")
                    return redirect("mi_reserva", pk=pk)
            else:
                messages.error(request, "Revise los datos del pago.")
        elif accion == "cancelar":
            motivo = request.POST.get("motivo", "").strip()
            if len(motivo) < 5:
                messages.error(request, "Indique el motivo de la cancelación.")
            else:
                with db.accion() as a:
                    db.ex("UPDATE reserva SET estado='CANCELADA', motivo_cancelacion=%s WHERE id=%s", [motivo, pk])
                messages.error(request, a.error) if a.error else messages.success(request, "Reserva cancelada.")
                return redirect("mi_reserva", pk=pk)
        r = _reserva_propia(request, pk)
    contexto = _contexto_reserva(pk)
    contexto.update({"r": r, "campos_pasajero": CAMPOS_PASAJERO, "campos_pago": CAMPOS_PAGO,
                     "vp": vp, "ep": errores_p, "vg": vg, "eg": errores_g, "es_staff": False})
    return render(request, "cliente/reserva.html", contexto)


def _contexto_reserva(pk):
    return {
        "detalle": db.q("""SELECT d.*, s.nombre, s.tipo FROM reserva_detalle d JOIN servicio s ON s.id=d.servicio_id WHERE d.reserva_id=%s ORDER BY s.tipo, s.nombre""", [pk]),
        "pasajeros": db.q("SELECT * FROM pasajero WHERE reserva_id=%s ORDER BY id", [pk]),
        "pagos": db.q("""SELECT p.*, u.nombres||' '||u.apellidos AS verificador FROM pago p LEFT JOIN usuario u ON u.id=p.verificado_por WHERE p.reserva_id=%s ORDER BY p.id DESC""", [pk]),
        "historial": db.q("""SELECT h.*, u.nombres||' '||u.apellidos AS usuario FROM historial_estado_reserva h LEFT JOIN usuario u ON u.id=h.usuario_id WHERE h.reserva_id=%s ORDER BY h.id""", [pk]),
    }


@solo_cliente
def historial(request):
    lista = db.q("SELECT * FROM v_historial_viajes WHERE cliente_id=%s ORDER BY fecha_inicio DESC", [request.cliente["id"]])
    return render(request, "cliente/historial.html", {"lista": lista})
