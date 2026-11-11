# Definitively Bolivia — Sistema web de la agencia de viajes

Sistema desarrollado a partir del informe Scrum: **Django 5 + PostgreSQL 16**, arquitectura MVC.
Las reglas de negocio (cálculo de cotizaciones, transiciones de estado, bloqueo de cuenta, límites de pasajeros,
verificación de pagos, notificaciones, auditoría) viven en la base de datos (triggers, funciones y vistas del script `sql/agencia_viajes.sql`).

## Qué necesita en su laptop (Windows)

1. **Python 3.10 o superior** — https://www.python.org/downloads/  (marque **"Add python.exe to PATH"**).
2. **PostgreSQL 16** (o 14/15) — https://www.postgresql.org/download/windows/
   Durante la instalación anote la **contraseña** del usuario `postgres`; la pedirá el instalador. Deje el puerto 5432.
3. Conexión a internet solo la primera vez (para descargar Django).

## Instalación (una sola vez)

1. Descomprima la carpeta `agencia_web` (por ejemplo en el Escritorio).
2. Haga doble clic en **`instalar.bat`**.
   - Le preguntará los datos de PostgreSQL (casi siempre basta con ENTER y escribir la contraseña).
   - Crea la base `agencia_viajes`, carga tablas, triggers, vistas y datos de ejemplo.

## Uso diario

Doble clic en **`iniciar.bat`** → se abre el navegador en http://127.0.0.1:8000

| Rol | Usuario | Contraseña |
|---|---|---|
| Administrador | `admin.agencia` | `Admin2026` |
| Agente | `agente.uno` | `Agente2026` |
| Cliente | `pvargas` | `Cliente2026` |

Otros clientes de ejemplo: `arojas`, `cmamani`, `mquispe` (misma contraseña de cliente). También puede crear su propia cuenta en «Crear cuenta».

## Flujo para probar todo (3 minutos)

1. **Cliente** `pvargas`: *Paquetes* → *Solicitar cotización*.
2. **Agente** `agente.uno`: *Solicitudes* → *Atender* → *Crear cotización* → ajustar servicios/comisión → *Enviar al cliente*.
3. **Cliente**: *Mis cotizaciones* → *Quiero reservar*.
4. **Agente**: en la cotización → *Crear reserva* (fechas) → *Confirmar reserva*.
5. **Cliente**: en la reserva → agregar pasajeros → registrar pago (con comprobante JPG/PNG/PDF).
6. **Agente**: *Pagos* → *Verificar*. Al cubrir el total la reserva pasa sola a **PAGADA**.
7. **Administrador**: *Reportes* (gráficos + exportar CSV), *Usuarios*, *Bitácora de acceso*, *Parámetros*.

## Funciones incluidas

- Catálogo público de paquetes con precio final calculado por la base de datos.
- Registro, ingreso, recuperación de contraseña, bloqueo temporal tras 5 intentos fallidos (parámetro configurable), bitácora de acceso.
- Permisos por rol (Cliente / Agente / Administrador) verificados en cada pantalla.
- Solicitudes → cotizaciones (borrador, enviada, aceptada, rechazada, vencida) → reservas → pasajeros → pagos.
- Notificaciones internas, historial de estados de cada reserva, historial de cambios de tarifa.
- CRUD de clientes, proveedores, servicios y paquetes. Reportes con gráficos y exportación a CSV (Excel).

## Problemas frecuentes

- **«No se pudo conectar a PostgreSQL»**: verifique que el servicio PostgreSQL esté iniciado y que la contraseña en el archivo `.env` sea correcta (bórrelo y vuelva a ejecutar `instalar.bat` para reconfigurar).
- **Quiero reiniciar los datos de ejemplo**: en una consola dentro de la carpeta ejecute `venv\Scripts\python manage.py instalar_bd --reset` (**borra** la base y la recrea).
- **«Recuperar contraseña»**: como no hay servidor de correo, el enlace se muestra en pantalla.
- **Linux/Mac**: use `./instalar.sh` y `./iniciar.sh`.

## Estructura

```
config/        configuración de Django
agencia/       vistas (controladores), middleware, acceso a datos (db.py), formularios
templates/     vistas HTML (Bootstrap 5)      static/   estilos, Bootstrap, iconos y Chart.js locales (funciona sin internet)
sql/           script de base de datos del informe
media/         comprobantes de pago subidos
```

## Destinos e imágenes (Agente / Administrador)

- **Destinos:** menú *Catálogo → Destinos* → *Nuevo destino* (nombre, país, nacional/internacional y foto opcional).
- **Imágenes de paquetes:** *Catálogo → Paquetes* → *Editar* (o *Nuevo*) → sección «Imagen». Si el paquete no tiene foto, usa la del destino.
- Formatos JPG, PNG o WEBP, máximo 3 MB (ideal 1200 × 600 px). Se guardan en la carpeta `media/`.
