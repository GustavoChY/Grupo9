"""Crea la base de datos, carga el esquema del informe (tablas, triggers, funciones, vistas, datos) y fija las contraseñas de demostración."""
import sys
from pathlib import Path

import psycopg
from django.conf import settings
from django.contrib.auth.hashers import make_password
from django.core.management.base import BaseCommand, CommandError

CUENTAS_DEMO = {
    "admin.agencia": "Admin2026",
    "agente.uno": "Agente2026",
    "agente.dos": "Agente2026",
    "pvargas": "Cliente2026",
    "arojas": "Cliente2026",
    "cmamani": "Cliente2026",
    "mquispe": "Cliente2026",
}


class Command(BaseCommand):
    help = "Instala la base de datos del sistema Definitively Bolivia"

    def add_arguments(self, parser):
        parser.add_argument("--reset", action="store_true", help="BORRA la base y la vuelve a crear con los datos de ejemplo")
        parser.add_argument("--sin-datos-demo", action="store_true", help="(reservado) no cambia las contraseñas de demostración")

    def handle(self, *args, **o):
        cfg = settings.DATABASES["default"]
        base = dict(host=cfg["HOST"], port=cfg["PORT"], user=cfg["USER"], password=cfg["PASSWORD"])
        nombre = cfg["NAME"]
        sql = Path(settings.BASE_DIR, "sql", "agencia_viajes.sql").read_text(encoding="utf-8")

        try:
            admin = psycopg.connect(dbname="postgres", autocommit=True, **base)
        except psycopg.OperationalError as e:
            raise CommandError(
                "No se pudo conectar a PostgreSQL.\n"
                f"  Servidor: {cfg['HOST']}:{cfg['PORT']}  Usuario: {cfg['USER']}\n"
                "  Revise que PostgreSQL esté iniciado y que el archivo .env tenga la contraseña correcta.\n"
                f"  Detalle técnico: {str(e).strip()}")
        with admin:
            existe = admin.execute("SELECT 1 FROM pg_database WHERE datname=%s", [nombre]).fetchone()
            if existe and o["reset"]:
                admin.execute("SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname=%s AND pid<>pg_backend_pid()", [nombre])
                admin.execute(f'DROP DATABASE "{nombre}"')
                existe = None
                self.stdout.write("Base anterior eliminada.")
            if not existe:
                admin.execute(f'CREATE DATABASE "{nombre}" ENCODING \'UTF8\' TEMPLATE template0')
                self.stdout.write(f"Base de datos «{nombre}» creada.")

        with psycopg.connect(dbname=nombre, autocommit=False, **base) as con:
            hay = con.execute("SELECT to_regclass('public.usuario')").fetchone()[0]
            if hay:
                self.stdout.write("El esquema ya estaba instalado; no se vuelve a cargar (use --reset para empezar de cero).")
            else:
                self.stdout.write("Cargando tablas, funciones, triggers, vistas y datos de ejemplo…")
                try:
                    con.execute(sql)
                except psycopg.Error as e:
                    con.rollback()
                    raise CommandError(f"Falló la carga del script SQL: {e}")
                self.stdout.write(self.style.SUCCESS("Esquema cargado."))
            for usuario, clave in CUENTAS_DEMO.items():
                con.execute("UPDATE usuario SET password_hash=%s, intentos_fallidos=0, bloqueado_hasta=NULL WHERE username=%s", [make_password(clave), usuario])
            con.commit()

        self.stdout.write(self.style.SUCCESS("\nListo. Cuentas de demostración:"))
        self.stdout.write("   Administrador:  admin.agencia / Admin2026")
        self.stdout.write("   Agente:         agente.uno    / Agente2026")
        self.stdout.write("   Cliente:        pvargas       / Cliente2026")
