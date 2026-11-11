"""Asistente de configuración: pregunta los datos de PostgreSQL y crea el archivo .env"""
import getpass
from pathlib import Path

print("\n=== Configuración de la base de datos PostgreSQL ===")
print("(Pulse ENTER para aceptar el valor entre corchetes)\n")
host = input("Servidor [localhost]: ").strip() or "localhost"
puerto = input("Puerto [5432]: ").strip() or "5432"
usuario = input("Usuario [postgres]: ").strip() or "postgres"
clave = getpass.getpass("Contraseña de PostgreSQL (la que eligió al instalarlo): ")
nombre = input("Nombre de la base de datos a crear [agencia_viajes]: ").strip() or "agencia_viajes"

Path(__file__).with_name(".env").write_text(
    f"DB_NAME={nombre}\nDB_USER={usuario}\nDB_PASSWORD={clave}\nDB_HOST={host}\nDB_PORT={puerto}\nDEBUG=1\n",
    encoding="utf-8")
print("\nArchivo .env guardado.")
