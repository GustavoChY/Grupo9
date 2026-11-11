"""Acceso a datos: SQL directo sobre PostgreSQL. Las reglas de negocio viven en triggers y funciones."""
from django.db import connection, DatabaseError, transaction


def _filas(cur):
    cols = [c.name for c in cur.description]
    return [dict(zip(cols, r)) for r in cur.fetchall()]


def q(sql, params=None):
    """Devuelve una lista de diccionarios."""
    with connection.cursor() as cur:
        cur.execute(sql, params or [])
        return _filas(cur)


def q1(sql, params=None):
    filas = q(sql, params)
    return filas[0] if filas else None


def escalar(sql, params=None):
    with connection.cursor() as cur:
        cur.execute(sql, params or [])
        r = cur.fetchone()
        return r[0] if r else None


def ex(sql, params=None):
    """Ejecuta una sentencia; devuelve filas afectadas."""
    with connection.cursor() as cur:
        cur.execute(sql, params or [])
        return cur.rowcount


def ex_ret(sql, params=None):
    """Ejecuta INSERT/UPDATE ... RETURNING y devuelve la primera columna."""
    return escalar(sql, params)


def fijar_usuario(uid):
    """Comunica a la base de datos quién actúa (lo leen fn_usuario_app() y los triggers de auditoría)."""
    with connection.cursor() as cur:
        cur.execute("SELECT set_config('app.usuario_id', %s, false)", [str(uid) if uid else ""])


def mensaje_error(e):
    """Extrae el mensaje legible de una excepción RAISE de PostgreSQL."""
    cause = getattr(e, "__cause__", None) or e
    diag = getattr(cause, "diag", None)
    msg = getattr(diag, "message_primary", None) if diag else None
    if msg:
        detalle = getattr(diag, "message_detail", None)
        if "violates check constraint" in msg or "violates unique constraint" in msg or "violates foreign key" in msg:
            return traducir_restriccion(msg, detalle)
        return msg
    return str(e).split("\n")[0]


def traducir_restriccion(msg, detalle):
    if "unique" in msg:
        return "Ya existe un registro con esos datos (valor duplicado)." + (f" {detalle}" if detalle else "")
    if "foreign key" in msg:
        return "El registro está relacionado con otros datos y no se puede modificar o eliminar así."
    return "Los datos no cumplen una regla de validación: " + msg.split('"')[1].replace("_", " ") if '"' in msg else msg


class Accion:
    """Bloque transaccional con punto de guardado: captura errores de la BD y los convierte en mensaje."""
    def __init__(self):
        self.error = None

    def __enter__(self):
        self._sp = transaction.atomic()
        self._sp.__enter__()
        return self

    def __exit__(self, tipo, valor, tb):
        if tipo is None:
            self._sp.__exit__(None, None, None)
            return False
        self._sp.__exit__(tipo, valor, tb)       # revierte hasta el punto de guardado
        if issubclass(tipo, DatabaseError):
            self.error = mensaje_error(valor)
            return True                           # se traga el error: la vista decide qué mostrar
        return False


def accion():
    return Accion()


_esquema_ok = False


def asegurar_esquema():
    """Agrega (una sola vez) las columnas de imagen si la base se instaló con una versión anterior."""
    global _esquema_ok
    if _esquema_ok:
        return
    with connection.cursor() as cur:
        cur.execute("ALTER TABLE paquete ADD COLUMN IF NOT EXISTS imagen varchar(255)")
        cur.execute("ALTER TABLE destino ADD COLUMN IF NOT EXISTS imagen varchar(255)")
    _esquema_ok = True
