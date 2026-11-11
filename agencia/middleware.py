from . import db


class UsuarioMiddleware:
    """Carga al usuario de la sesión, sus permisos y avisa a la BD quién está operando."""
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        db.asegurar_esquema()
        request.usuario = None
        request.permisos = set()
        request.cliente = None
        uid = request.session.get("uid")
        if uid:
            u = db.q1("""SELECT u.id, u.username, u.email, u.nombres, u.apellidos, u.activo, r.codigo AS rol, r.nombre AS rol_nombre
                         FROM usuario u JOIN rol r ON r.id = u.rol_id WHERE u.id = %s""", [uid])
            if u and u["activo"]:
                request.usuario = u
                request.permisos = {p["codigo"] for p in db.q(
                    "SELECT p.codigo FROM usuario u JOIN rol_permiso rp ON rp.rol_id = u.rol_id JOIN permiso p ON p.id = rp.permiso_id WHERE u.id = %s", [uid])}
                if u["rol"] == "CLIENTE":
                    request.cliente = db.q1("SELECT * FROM cliente WHERE usuario_id = %s", [uid])
                db.fijar_usuario(uid)
            else:
                request.session.flush()
        if not request.usuario:
            db.fijar_usuario(None)
        return self.get_response(request)
