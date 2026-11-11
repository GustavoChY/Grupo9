from django.conf import settings
from django.urls import path, re_path
from django.views.static import serve
from . import views_publico as P, views_cliente as C, views_staff as S, views_admin as A

urlpatterns = [
    # ---- Público y acceso
    path("", P.inicio, name="inicio"),
    path("paquetes/", P.paquetes, name="paquetes"),
    path("paquetes/<int:pk>/", P.paquete_detalle, name="paquete_detalle"),
    path("ingresar/", P.ingresar, name="ingresar"),
    path("salir/", P.salir, name="salir"),
    path("registrarse/", P.registrarse, name="registrarse"),
    path("recuperar/", P.recuperar, name="recuperar"),
    path("recuperar/<str:token>/", P.restablecer, name="restablecer"),
    path("panel/", P.panel, name="panel"),
    path("notificaciones/", P.notificaciones, name="notificaciones"),
    path("cuenta/", P.cuenta, name="cuenta"),
    path("cuenta/password/", P.cambiar_password, name="cambiar_password"),
    path("comprobante/<int:pk>/", P.ver_comprobante, name="comprobante"),

    # ---- Cliente
    path("cliente/solicitar/", C.solicitar, name="solicitar"),
    path("cliente/solicitudes/", C.mis_solicitudes, name="mis_solicitudes"),
    path("cliente/cotizaciones/", C.mis_cotizaciones, name="mis_cotizaciones"),
    path("cliente/cotizaciones/<int:pk>/", C.mi_cotizacion, name="mi_cotizacion"),
    path("cliente/reservas/", C.mis_reservas, name="mis_reservas"),
    path("cliente/reservas/<int:pk>/", C.mi_reserva, name="mi_reserva"),
    path("cliente/historial/", C.historial, name="historial"),

    # ---- Agente / administrador (gestión)
    path("gestion/", S.gestion, name="gestion"),
    path("gestion/solicitudes/", S.solicitudes, name="solicitudes"),
    path("gestion/solicitudes/<int:pk>/", S.solicitud_detalle, name="solicitud_detalle"),
    path("gestion/cotizaciones/", S.cotizaciones, name="cotizaciones"),
    path("gestion/cotizaciones/nueva/", S.cotizacion_nueva, name="cotizacion_nueva"),
    path("gestion/cotizaciones/<int:pk>/", S.cotizacion_detalle, name="cotizacion_detalle"),
    path("gestion/reservas/", S.reservas, name="reservas"),
    path("gestion/reservas/<int:pk>/", S.reserva_detalle, name="reserva_detalle"),
    path("gestion/pagos/", S.pagos, name="pagos"),
    path("gestion/pagos/<int:pk>/resolver/", S.pago_resolver, name="pago_resolver"),
    path("gestion/clientes/", S.clientes, name="clientes"),
    path("gestion/clientes/nuevo/", S.cliente_form, name="cliente_nuevo"),
    path("gestion/clientes/<int:pk>/", S.cliente_detalle, name="cliente_detalle"),
    path("gestion/clientes/<int:pk>/editar/", S.cliente_form, name="cliente_editar"),
    path("gestion/proveedores/", S.proveedores, name="proveedores"),
    path("gestion/proveedores/nuevo/", S.proveedor_form, name="proveedor_nuevo"),
    path("gestion/proveedores/<int:pk>/editar/", S.proveedor_form, name="proveedor_editar"),
    path("gestion/servicios/", S.servicios, name="servicios"),
    path("gestion/servicios/nuevo/", S.servicio_form, name="servicio_nuevo"),
    path("gestion/servicios/<int:pk>/editar/", S.servicio_form, name="servicio_editar"),
    path("gestion/paquetes/", S.paquetes_gestion, name="paquetes_gestion"),
    path("gestion/paquetes/nuevo/", S.paquete_form, name="paquete_nuevo"),
    path("gestion/paquetes/<int:pk>/editar/", S.paquete_form, name="paquete_editar"),
    path("gestion/destinos/", S.destinos, name="destinos"),
    path("gestion/destinos/nuevo/", S.destino_form, name="destino_nuevo"),
    path("gestion/destinos/<int:pk>/editar/", S.destino_form, name="destino_editar"),
    path("gestion/destinos/<int:pk>/eliminar/", S.destino_eliminar, name="destino_eliminar"),
    path("gestion/tareas/", S.tareas, name="tareas"),

    # ---- Administración
    path("admin-sistema/usuarios/", A.usuarios, name="usuarios"),
    path("admin-sistema/usuarios/nuevo/", A.usuario_nuevo, name="usuario_nuevo"),
    path("admin-sistema/usuarios/<int:pk>/", A.usuario_detalle, name="usuario_detalle"),
    path("admin-sistema/bitacora/", A.bitacora, name="bitacora"),
    path("admin-sistema/reportes/", A.reportes, name="reportes"),
    path("admin-sistema/reportes/<str:nombre>.csv", A.reporte_csv, name="reporte_csv"),
    path("admin-sistema/parametros/", A.parametros, name="parametros"),
]

# Fotos públicas de paquetes y destinos (los comprobantes de pago NO se exponen aquí)
urlpatterns += [re_path(r"^media/(?P<path>(?:paquetes|destinos)/[\w.-]+)$", serve, {"document_root": settings.MEDIA_ROOT})]
