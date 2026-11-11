-- agencia_viajes.sql  (PostgreSQL 16)  Sistema de información para la gestión de la agencia "Definitively Bolivia"
-- ======================= TIPOS ENUMERADOS =======================
CREATE TYPE tipo_documento      AS ENUM ('CI','PASAPORTE','CEX','OTRO');
CREATE TYPE tipo_proveedor      AS ENUM ('AEROLINEA','HOTEL','OPERADOR_TOUR','TRANSPORTE','ASEGURADORA');
CREATE TYPE tipo_servicio       AS ENUM ('AEREO','HOSPEDAJE','TRASLADO','TOUR','SEGURO');
CREATE TYPE categoria_tarifaria AS ENUM ('ECONOMICA','ESTANDAR','PREMIUM');
CREATE TYPE temporada           AS ENUM ('ALTA','BAJA','TODO_ANO');
CREATE TYPE ambito_destino      AS ENUM ('NACIONAL','INTERNACIONAL');
CREATE TYPE estado_solicitud    AS ENUM ('RECIBIDA','EN_ATENCION','COTIZADA','CERRADA');
CREATE TYPE estado_cotizacion   AS ENUM ('BORRADOR','ENVIADA','ACEPTADA','RECHAZADA','VENCIDA');
CREATE TYPE estado_reserva      AS ENUM ('PENDIENTE','CONFIRMADA','PAGADA','CANCELADA','FINALIZADA');
CREATE TYPE metodo_pago         AS ENUM ('TRANSFERENCIA','DEPOSITO','EFECTIVO');
CREATE TYPE estado_pago         AS ENUM ('PENDIENTE_VERIFICACION','VERIFICADO','RECHAZADO');
CREATE TYPE evento_acceso       AS ENUM ('LOGIN_OK','LOGIN_FALLIDO','BLOQUEO','DESBLOQUEO','LOGOUT','CAMBIO_PASSWORD','RECUPERACION_SOLICITADA','CAMBIO_ROL','USUARIO_DESACTIVADO');
CREATE TYPE tipo_notificacion   AS ENUM ('NUEVA_SOLICITUD','COTIZACION_ENVIADA','SOLICITUD_RESERVA','PAGO_REGISTRADO','PAGO_VERIFICADO','PAGO_RECHAZADO','RESERVA_CANCELADA');
CREATE TYPE tipo_pasajero       AS ENUM ('ADULTO','MENOR','INFANTE');

-- ======================= CONFIGURACIÓN =======================
CREATE TABLE parametro_sistema (
  clave        varchar(40)  PRIMARY KEY,
  valor        varchar(100) NOT NULL,
  descripcion  varchar(200)
);
CREATE TABLE contador_codigo (
  prefijo  varchar(5)  NOT NULL,
  anio     smallint    NOT NULL,
  ultimo   integer     NOT NULL DEFAULT 0 CHECK (ultimo >= 0),
  PRIMARY KEY (prefijo, anio)
);

-- ======================= CONTROL DE ACCESO =======================
CREATE TABLE rol (
  id           smallint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  codigo       varchar(20) NOT NULL UNIQUE,
  nombre       varchar(50) NOT NULL,
  descripcion  varchar(200)
);
CREATE TABLE permiso (
  id           smallint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  codigo       varchar(30)  NOT NULL UNIQUE,
  descripcion  varchar(150) NOT NULL
);
CREATE TABLE rol_permiso (
  rol_id      smallint NOT NULL REFERENCES rol(id)     ON DELETE CASCADE,
  permiso_id  smallint NOT NULL REFERENCES permiso(id) ON DELETE CASCADE,
  PRIMARY KEY (rol_id, permiso_id)
);
CREATE TABLE usuario (
  id                 integer GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  rol_id             smallint     NOT NULL REFERENCES rol(id),
  username           varchar(30)  NOT NULL UNIQUE CHECK (username ~ '^[A-Za-z0-9_.]{4,30}$'),
  email              varchar(120) NOT NULL UNIQUE CHECK (email ~* '^[^@[:space:]]+@[^@[:space:]]+\.[^@[:space:]]+$'),
  password_hash      varchar(255) NOT NULL,
  nombres            varchar(80)  NOT NULL,
  apellidos          varchar(80)  NOT NULL,
  activo             boolean      NOT NULL DEFAULT true,
  intentos_fallidos  smallint     NOT NULL DEFAULT 0 CHECK (intentos_fallidos >= 0),
  bloqueado_hasta    timestamptz,
  ultimo_acceso      timestamptz,
  creado_en          timestamptz  NOT NULL DEFAULT now()
);
CREATE TABLE token_recuperacion (
  id          integer GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  usuario_id  integer      NOT NULL REFERENCES usuario(id) ON DELETE CASCADE,
  token_hash  varchar(128) NOT NULL UNIQUE,
  creado_en   timestamptz  NOT NULL DEFAULT now(),
  expira_en   timestamptz  NOT NULL,
  usado       boolean      NOT NULL DEFAULT false,
  CHECK (expira_en > creado_en)
);
CREATE TABLE bitacora_acceso (
  id                 bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  usuario_id         integer REFERENCES usuario(id) ON DELETE SET NULL,
  username_intentado varchar(30),
  evento             evento_acceso NOT NULL,
  exito              boolean       NOT NULL,
  ip                 inet,
  detalle            varchar(250),
  fecha              timestamptz   NOT NULL DEFAULT now()
);
CREATE INDEX ix_bitacora_usuario_fecha ON bitacora_acceso (usuario_id, fecha);
CREATE INDEX ix_bitacora_evento_fecha  ON bitacora_acceso (evento, fecha);

-- ======================= CLIENTES =======================
CREATE TABLE cliente (
  id               integer GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  usuario_id       integer UNIQUE REFERENCES usuario(id) ON DELETE SET NULL,
  tipo_documento   tipo_documento NOT NULL,
  nro_documento    varchar(20)    NOT NULL,
  nombres          varchar(80)    NOT NULL,
  apellidos        varchar(80)    NOT NULL,
  nacionalidad     varchar(50)    NOT NULL DEFAULT 'Boliviana',
  fecha_nacimiento date,
  telefono         varchar(20),
  correo           varchar(120),
  direccion        varchar(200),
  preferencias     text,
  creado_en        timestamptz    NOT NULL DEFAULT now(),
  UNIQUE (tipo_documento, nro_documento)
);

-- ======================= CATÁLOGO =======================
CREATE TABLE destino (
  id      integer GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  nombre  varchar(80) NOT NULL,
  pais    varchar(60) NOT NULL,
  ambito  ambito_destino NOT NULL,
  UNIQUE (nombre, pais)
);
CREATE TABLE proveedor (
  id                integer GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  nombre            varchar(100) NOT NULL UNIQUE,
  tipo              tipo_proveedor NOT NULL,
  nit               varchar(20) UNIQUE,
  contacto_nombre   varchar(100),
  contacto_telefono varchar(20),
  contacto_correo   varchar(120),
  politicas         text,
  activo            boolean NOT NULL DEFAULT true
);
CREATE TABLE servicio (
  id               integer GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  proveedor_id     integer NOT NULL REFERENCES proveedor(id),
  destino_id       integer NOT NULL REFERENCES destino(id),
  nombre           varchar(120) NOT NULL,
  tipo             tipo_servicio NOT NULL,
  descripcion      text,
  categoria        categoria_tarifaria NOT NULL DEFAULT 'ESTANDAR',
  temporada        temporada NOT NULL DEFAULT 'TODO_ANO',
  tarifa_base      numeric(12,2) NOT NULL CHECK (tarifa_base >= 0),
  cupo_referencial integer CHECK (cupo_referencial >= 0),
  politica         varchar(250),
  activo           boolean NOT NULL DEFAULT true,
  UNIQUE (proveedor_id, nombre)
);
CREATE INDEX ix_servicio_destino ON servicio (destino_id);
CREATE TABLE historial_tarifa (
  id              integer GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  servicio_id     integer NOT NULL REFERENCES servicio(id),
  tarifa_anterior numeric(12,2) NOT NULL,
  tarifa_nueva    numeric(12,2) NOT NULL,
  usuario_id      integer REFERENCES usuario(id) ON DELETE SET NULL,
  fecha           timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE paquete (
  id             integer GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  nombre         varchar(120) NOT NULL UNIQUE,
  descripcion    text,
  destino_id     integer NOT NULL REFERENCES destino(id),
  duracion_dias  smallint NOT NULL CHECK (duracion_dias > 0),
  comision_pct   numeric(5,2) NOT NULL CHECK (comision_pct BETWEEN 0 AND 100),
  impuesto_pct   numeric(5,2) NOT NULL DEFAULT 13 CHECK (impuesto_pct BETWEEN 0 AND 100),
  vigente_desde  date NOT NULL,
  vigente_hasta  date NOT NULL,
  activo         boolean NOT NULL DEFAULT true,
  CHECK (vigente_hasta >= vigente_desde)
);
CREATE TABLE paquete_servicio (
  paquete_id  integer NOT NULL REFERENCES paquete(id)  ON DELETE CASCADE,
  servicio_id integer NOT NULL REFERENCES servicio(id),
  cantidad    integer NOT NULL CHECK (cantidad > 0),   -- unidades por pasajero
  PRIMARY KEY (paquete_id, servicio_id)
);

-- ======================= VENTAS =======================
CREATE TABLE solicitud_cotizacion (
  id                 integer GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  codigo             varchar(20) NOT NULL UNIQUE,
  cliente_id         integer NOT NULL REFERENCES cliente(id),
  paquete_id         integer REFERENCES paquete(id),
  destino_id         integer REFERENCES destino(id),
  fecha_viaje_inicio date,
  fecha_viaje_fin    date,
  nro_pasajeros      smallint NOT NULL CHECK (nro_pasajeros > 0),
  observaciones      text,
  estado             estado_solicitud NOT NULL DEFAULT 'RECIBIDA',
  atendida_por       integer REFERENCES usuario(id),
  creado_en          timestamptz NOT NULL DEFAULT now(),
  CHECK (paquete_id IS NOT NULL OR destino_id IS NOT NULL),
  CHECK (fecha_viaje_fin IS NULL OR fecha_viaje_inicio IS NULL OR fecha_viaje_fin >= fecha_viaje_inicio)
);
CREATE TABLE cotizacion (
  id                    integer GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  codigo                varchar(20) NOT NULL UNIQUE,
  solicitud_id          integer REFERENCES solicitud_cotizacion(id),
  cliente_id            integer NOT NULL REFERENCES cliente(id),
  agente_id             integer NOT NULL REFERENCES usuario(id),
  paquete_id            integer REFERENCES paquete(id),
  nro_pasajeros         smallint NOT NULL CHECK (nro_pasajeros > 0),
  fecha_emision         date NOT NULL DEFAULT CURRENT_DATE,
  vigencia_hasta        date NOT NULL,
  estado                estado_cotizacion NOT NULL DEFAULT 'BORRADOR',
  comision_pct          numeric(5,2) NOT NULL CHECK (comision_pct BETWEEN 0 AND 100),
  impuesto_pct          numeric(5,2) NOT NULL CHECK (impuesto_pct BETWEEN 0 AND 100),
  costo_proveedor       numeric(12,2) NOT NULL DEFAULT 0,
  comision              numeric(12,2) NOT NULL DEFAULT 0,
  impuestos             numeric(12,2) NOT NULL DEFAULT 0,
  total                 numeric(12,2) NOT NULL DEFAULT 0,
  reserva_solicitada_en timestamptz,
  observaciones         text,
  creado_en             timestamptz NOT NULL DEFAULT now(),
  CHECK (vigencia_hasta >= fecha_emision),
  CHECK (total = costo_proveedor + comision + impuestos)
);
CREATE INDEX ix_cotizacion_cliente_estado ON cotizacion (cliente_id, estado);
CREATE INDEX ix_cotizacion_vigencia ON cotizacion (vigencia_hasta) WHERE estado = 'ENVIADA';
CREATE TABLE cotizacion_detalle (
  id              integer GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  cotizacion_id   integer NOT NULL REFERENCES cotizacion(id) ON DELETE CASCADE,
  servicio_id     integer NOT NULL REFERENCES servicio(id),
  cantidad        integer NOT NULL CHECK (cantidad > 0),
  tarifa_unitaria numeric(12,2) NOT NULL CHECK (tarifa_unitaria >= 0),
  subtotal        numeric(12,2) GENERATED ALWAYS AS (cantidad * tarifa_unitaria) STORED,
  UNIQUE (cotizacion_id, servicio_id)
);
CREATE TABLE reserva (
  id                 integer GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  codigo             varchar(20) NOT NULL UNIQUE,
  cotizacion_id      integer NOT NULL UNIQUE REFERENCES cotizacion(id),
  cliente_id         integer NOT NULL REFERENCES cliente(id),
  agente_id          integer NOT NULL REFERENCES usuario(id),
  fecha_inicio       date NOT NULL,
  fecha_fin          date NOT NULL,
  nro_pasajeros      smallint NOT NULL CHECK (nro_pasajeros > 0),
  estado             estado_reserva NOT NULL DEFAULT 'PENDIENTE',
  total              numeric(12,2) NOT NULL CHECK (total >= 0),
  motivo_cancelacion varchar(250),
  cancelada_en       timestamptz,
  creado_en          timestamptz NOT NULL DEFAULT now(),
  CHECK (fecha_fin >= fecha_inicio),
  CHECK (estado <> 'CANCELADA' OR motivo_cancelacion IS NOT NULL)
);
CREATE INDEX ix_reserva_cliente ON reserva (cliente_id);
CREATE INDEX ix_reserva_estado_fecha ON reserva (estado, creado_en);
CREATE TABLE reserva_detalle (
  id              integer GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  reserva_id      integer NOT NULL REFERENCES reserva(id) ON DELETE CASCADE,
  servicio_id     integer NOT NULL REFERENCES servicio(id),
  cantidad        integer NOT NULL CHECK (cantidad > 0),
  tarifa_unitaria numeric(12,2) NOT NULL CHECK (tarifa_unitaria >= 0),
  fecha_servicio  date,
  subtotal        numeric(12,2) GENERATED ALWAYS AS (cantidad * tarifa_unitaria) STORED,
  UNIQUE (reserva_id, servicio_id)
);
CREATE INDEX ix_reserva_detalle_servicio ON reserva_detalle (servicio_id);
CREATE TABLE pasajero (
  id               integer GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  reserva_id       integer NOT NULL REFERENCES reserva(id) ON DELETE CASCADE,
  tipo             tipo_pasajero  NOT NULL DEFAULT 'ADULTO',
  nombres          varchar(80)    NOT NULL,
  apellidos        varchar(80)    NOT NULL,
  tipo_documento   tipo_documento NOT NULL,
  nro_documento    varchar(20)    NOT NULL,
  nacionalidad     varchar(50)    NOT NULL,
  fecha_nacimiento date           NOT NULL,
  UNIQUE (reserva_id, tipo_documento, nro_documento)
);
CREATE TABLE historial_estado_reserva (
  id              bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  reserva_id      integer NOT NULL REFERENCES reserva(id) ON DELETE CASCADE,
  estado_anterior estado_reserva,
  estado_nuevo    estado_reserva NOT NULL,
  usuario_id      integer REFERENCES usuario(id) ON DELETE SET NULL,
  fecha           timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE pago (
  id                  integer GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  reserva_id          integer NOT NULL REFERENCES reserva(id),
  registrado_por      integer NOT NULL REFERENCES usuario(id),
  verificado_por      integer REFERENCES usuario(id),
  monto               numeric(12,2) NOT NULL CHECK (monto > 0),
  metodo              metodo_pago NOT NULL,
  nro_comprobante     varchar(40),
  comprobante_archivo varchar(255),
  fecha_pago          date NOT NULL DEFAULT CURRENT_DATE,
  estado              estado_pago NOT NULL DEFAULT 'PENDIENTE_VERIFICACION',
  observacion         varchar(250),
  fecha_verificacion  timestamptz,
  creado_en           timestamptz NOT NULL DEFAULT now(),
  CHECK (metodo = 'EFECTIVO' OR nro_comprobante IS NOT NULL),
  CHECK (estado = 'PENDIENTE_VERIFICACION' OR verificado_por IS NOT NULL),
  CHECK (estado <> 'RECHAZADO' OR observacion IS NOT NULL)
);
CREATE UNIQUE INDEX ux_pago_comprobante ON pago (nro_comprobante) WHERE metodo <> 'EFECTIVO' AND estado <> 'RECHAZADO';
CREATE INDEX ix_pago_reserva ON pago (reserva_id);
CREATE INDEX ix_pago_estado  ON pago (estado);
CREATE TABLE notificacion (
  id               bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  usuario_id       integer NOT NULL REFERENCES usuario(id) ON DELETE CASCADE,
  tipo             tipo_notificacion NOT NULL,
  mensaje          varchar(250) NOT NULL,
  referencia_tabla varchar(30),
  referencia_id    integer,
  leida            boolean NOT NULL DEFAULT false,
  creado_en        timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX ix_notificacion_usuario ON notificacion (usuario_id, leida);
-- ======================= FUNCIONES AUXILIARES =======================
CREATE FUNCTION fn_param(p_clave varchar) RETURNS varchar LANGUAGE sql STABLE AS
$$ SELECT valor FROM parametro_sistema WHERE clave = p_clave $$;

CREATE FUNCTION fn_usuario_app() RETURNS integer LANGUAGE sql STABLE AS
$$ SELECT NULLIF(current_setting('app.usuario_id', true), '')::integer $$;

CREATE FUNCTION fn_siguiente_codigo(p_prefijo varchar) RETURNS varchar LANGUAGE plpgsql AS $$
DECLARE v_anio smallint := EXTRACT(YEAR FROM CURRENT_DATE)::smallint; v_n integer;
BEGIN
  INSERT INTO contador_codigo(prefijo, anio, ultimo) VALUES (p_prefijo, v_anio, 1)
  ON CONFLICT (prefijo, anio) DO UPDATE SET ultimo = contador_codigo.ultimo + 1
  RETURNING ultimo INTO v_n;
  RETURN p_prefijo || '-' || v_anio || '-' || lpad(v_n::text, 5, '0');
END $$;

CREATE FUNCTION fn_tiene_permiso(p_usuario_id integer, p_codigo varchar) RETURNS boolean LANGUAGE sql STABLE AS
$$ SELECT EXISTS (SELECT 1 FROM usuario u JOIN rol_permiso rp ON rp.rol_id = u.rol_id JOIN permiso p ON p.id = rp.permiso_id
                  WHERE u.id = p_usuario_id AND u.activo AND p.codigo = p_codigo) $$;

CREATE FUNCTION fn_notificar_permiso(p_permiso varchar, p_tipo tipo_notificacion, p_msg varchar, p_tabla varchar, p_ref integer)
RETURNS void LANGUAGE sql AS
$$ INSERT INTO notificacion(usuario_id, tipo, mensaje, referencia_tabla, referencia_id)
   SELECT u.id, p_tipo, p_msg, p_tabla, p_ref FROM usuario u WHERE u.activo AND fn_tiene_permiso(u.id, p_permiso) $$;

CREATE FUNCTION fn_notificar_cliente(p_cliente integer, p_tipo tipo_notificacion, p_msg varchar, p_tabla varchar, p_ref integer)
RETURNS void LANGUAGE sql AS
$$ INSERT INTO notificacion(usuario_id, tipo, mensaje, referencia_tabla, referencia_id)
   SELECT c.usuario_id, p_tipo, p_msg, p_tabla, p_ref FROM cliente c WHERE c.id = p_cliente AND c.usuario_id IS NOT NULL $$;

-- ======================= CONTROL DE ACCESO =======================
CREATE FUNCTION fn_registrar_intento_acceso(p_username varchar, p_exito boolean, p_ip inet) RETURNS varchar LANGUAGE plpgsql AS $$
DECLARE u usuario%ROWTYPE; v_n smallint;
BEGIN
  SELECT * INTO u FROM usuario WHERE username = p_username FOR UPDATE;
  IF NOT FOUND THEN
    INSERT INTO bitacora_acceso(username_intentado, evento, exito, ip, detalle) VALUES (p_username,'LOGIN_FALLIDO',false,p_ip,'Usuario inexistente');
    RETURN 'FALLIDO';
  END IF;
  IF NOT u.activo THEN
    INSERT INTO bitacora_acceso(usuario_id, username_intentado, evento, exito, ip, detalle) VALUES (u.id,p_username,'LOGIN_FALLIDO',false,p_ip,'Cuenta inactiva');
    RETURN 'INACTIVO';
  END IF;
  IF u.bloqueado_hasta IS NOT NULL AND u.bloqueado_hasta > now() THEN
    INSERT INTO bitacora_acceso(usuario_id, username_intentado, evento, exito, ip, detalle) VALUES (u.id,p_username,'LOGIN_FALLIDO',false,p_ip,'Cuenta bloqueada temporalmente');
    RETURN 'BLOQUEADO';
  END IF;
  IF p_exito THEN
    UPDATE usuario SET intentos_fallidos = 0, bloqueado_hasta = NULL, ultimo_acceso = now() WHERE id = u.id;
    INSERT INTO bitacora_acceso(usuario_id, username_intentado, evento, exito, ip) VALUES (u.id,p_username,'LOGIN_OK',true,p_ip);
    RETURN 'OK';
  END IF;
  UPDATE usuario SET intentos_fallidos = intentos_fallidos + 1 WHERE id = u.id RETURNING intentos_fallidos INTO v_n;
  IF v_n >= fn_param('max_intentos_fallidos')::int THEN
    UPDATE usuario SET intentos_fallidos = 0, bloqueado_hasta = now() + make_interval(mins => fn_param('minutos_bloqueo')::int) WHERE id = u.id;
    INSERT INTO bitacora_acceso(usuario_id, username_intentado, evento, exito, ip, detalle) VALUES (u.id,p_username,'BLOQUEO',false,p_ip,'Cuenta bloqueada por intentos fallidos');
    RETURN 'BLOQUEADO';
  END IF;
  INSERT INTO bitacora_acceso(usuario_id, username_intentado, evento, exito, ip, detalle) VALUES (u.id,p_username,'LOGIN_FALLIDO',false,p_ip,'Credenciales inválidas');
  RETURN 'FALLIDO';
END $$;

CREATE FUNCTION trg_usuario_guardia() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE v_admin smallint;
BEGIN
  SELECT id INTO v_admin FROM rol WHERE codigo = 'ADMIN';
  IF OLD.activo AND OLD.rol_id = v_admin AND (NEW.activo = false OR NEW.rol_id <> OLD.rol_id) THEN
    IF NOT EXISTS (SELECT 1 FROM usuario WHERE rol_id = v_admin AND activo AND id <> OLD.id) THEN
      RAISE EXCEPTION 'No se puede desactivar ni cambiar el rol del único administrador';
    END IF;
  END IF;
  RETURN NEW;
END $$;
CREATE TRIGGER trg_usuario_guardia BEFORE UPDATE OF activo, rol_id ON usuario FOR EACH ROW EXECUTE FUNCTION trg_usuario_guardia();

CREATE FUNCTION trg_usuario_auditoria() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  IF NEW.rol_id <> OLD.rol_id THEN
    INSERT INTO bitacora_acceso(usuario_id, username_intentado, evento, exito, detalle)
    VALUES (NEW.id, NEW.username, 'CAMBIO_ROL', true, 'Rol ' || OLD.rol_id || ' -> ' || NEW.rol_id || ' por usuario ' || COALESCE(fn_usuario_app()::text,'sistema'));
  END IF;
  IF OLD.activo AND NOT NEW.activo THEN
    INSERT INTO bitacora_acceso(usuario_id, username_intentado, evento, exito, detalle) VALUES (NEW.id, NEW.username, 'USUARIO_DESACTIVADO', true, 'Cuenta desactivada');
  END IF;
  IF OLD.password_hash <> NEW.password_hash THEN
    INSERT INTO bitacora_acceso(usuario_id, username_intentado, evento, exito) VALUES (NEW.id, NEW.username, 'CAMBIO_PASSWORD', true);
  END IF;
  RETURN NEW;
END $$;
CREATE TRIGGER trg_usuario_auditoria AFTER UPDATE ON usuario FOR EACH ROW EXECUTE FUNCTION trg_usuario_auditoria();

-- ======================= CATÁLOGO =======================
CREATE FUNCTION trg_servicio_tarifa() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  IF NEW.tarifa_base <> OLD.tarifa_base THEN
    INSERT INTO historial_tarifa(servicio_id, tarifa_anterior, tarifa_nueva, usuario_id) VALUES (NEW.id, OLD.tarifa_base, NEW.tarifa_base, fn_usuario_app());
  END IF;
  RETURN NEW;
END $$;
CREATE TRIGGER trg_servicio_tarifa AFTER UPDATE OF tarifa_base ON servicio FOR EACH ROW EXECUTE FUNCTION trg_servicio_tarifa();

CREATE FUNCTION trg_proveedor_baja_logica() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  IF EXISTS (SELECT 1 FROM servicio WHERE proveedor_id = OLD.id) THEN
    UPDATE proveedor SET activo = false WHERE id = OLD.id;
    UPDATE servicio SET activo = false WHERE proveedor_id = OLD.id;
    RETURN NULL;   -- cancela el DELETE físico: se conserva el historial
  END IF;
  RETURN OLD;
END $$;
CREATE TRIGGER trg_proveedor_baja_logica BEFORE DELETE ON proveedor FOR EACH ROW EXECUTE FUNCTION trg_proveedor_baja_logica();

-- ======================= SOLICITUDES Y COTIZACIONES =======================
CREATE FUNCTION trg_solicitud_antes_insert() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  IF NEW.codigo IS NULL THEN NEW.codigo := fn_siguiente_codigo('SOL'); END IF;
  RETURN NEW;
END $$;
CREATE TRIGGER trg_solicitud_antes_insert BEFORE INSERT ON solicitud_cotizacion FOR EACH ROW EXECUTE FUNCTION trg_solicitud_antes_insert();

CREATE FUNCTION trg_solicitud_despues_insert() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  PERFORM fn_notificar_permiso('COT_GESTIONAR','NUEVA_SOLICITUD','Nueva solicitud de cotización ' || NEW.codigo,'solicitud_cotizacion',NEW.id);
  RETURN NEW;
END $$;
CREATE TRIGGER trg_solicitud_despues_insert AFTER INSERT ON solicitud_cotizacion FOR EACH ROW EXECUTE FUNCTION trg_solicitud_despues_insert();

CREATE FUNCTION trg_cotizacion_antes_insert() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE p paquete%ROWTYPE;
BEGIN
  IF NEW.codigo IS NULL THEN NEW.codigo := fn_siguiente_codigo('COT'); END IF;
  IF NEW.paquete_id IS NOT NULL THEN
    SELECT * INTO p FROM paquete WHERE id = NEW.paquete_id;
    IF NEW.comision_pct  IS NULL THEN NEW.comision_pct  := p.comision_pct;  END IF;
    IF NEW.impuesto_pct  IS NULL THEN NEW.impuesto_pct  := p.impuesto_pct;  END IF;
  END IF;
  IF NEW.comision_pct IS NULL THEN NEW.comision_pct := fn_param('comision_defecto')::numeric; END IF;
  IF NEW.impuesto_pct IS NULL THEN NEW.impuesto_pct := fn_param('impuesto_defecto')::numeric; END IF;
  IF NEW.vigencia_hasta IS NULL THEN NEW.vigencia_hasta := NEW.fecha_emision + fn_param('vigencia_cotizacion_dias')::int; END IF;
  RETURN NEW;
END $$;
CREATE TRIGGER trg_cotizacion_antes_insert BEFORE INSERT ON cotizacion FOR EACH ROW EXECUTE FUNCTION trg_cotizacion_antes_insert();

CREATE FUNCTION trg_cotizacion_transicion() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  IF NEW.estado <> OLD.estado THEN
    IF NOT ((OLD.estado = 'BORRADOR' AND NEW.estado = 'ENVIADA')
         OR (OLD.estado = 'ENVIADA'  AND NEW.estado IN ('ACEPTADA','RECHAZADA','VENCIDA'))) THEN
      RAISE EXCEPTION 'Transición inválida de la cotización: % -> %', OLD.estado, NEW.estado;
    END IF;
    IF NEW.estado = 'ENVIADA' AND NOT EXISTS (SELECT 1 FROM cotizacion_detalle WHERE cotizacion_id = NEW.id) THEN
      RAISE EXCEPTION 'No se puede enviar una cotización sin servicios';
    END IF;
  END IF;
  RETURN NEW;
END $$;
CREATE TRIGGER trg_cotizacion_transicion BEFORE UPDATE OF estado ON cotizacion FOR EACH ROW EXECUTE FUNCTION trg_cotizacion_transicion();

CREATE FUNCTION trg_cotizacion_despues_update() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  IF NEW.estado = 'ENVIADA' AND OLD.estado = 'BORRADOR' THEN
    PERFORM fn_notificar_cliente(NEW.cliente_id,'COTIZACION_ENVIADA','Su cotización ' || NEW.codigo || ' está disponible hasta el ' || to_char(NEW.vigencia_hasta,'DD/MM/YYYY'),'cotizacion',NEW.id);
    IF NEW.solicitud_id IS NOT NULL THEN UPDATE solicitud_cotizacion SET estado = 'COTIZADA', atendida_por = NEW.agente_id WHERE id = NEW.solicitud_id; END IF;
  END IF;
  IF NEW.reserva_solicitada_en IS NOT NULL AND OLD.reserva_solicitada_en IS NULL THEN
    INSERT INTO notificacion(usuario_id, tipo, mensaje, referencia_tabla, referencia_id)
    VALUES (NEW.agente_id,'SOLICITUD_RESERVA','El cliente solicita reservar la cotización ' || NEW.codigo,'cotizacion',NEW.id);
  END IF;
  RETURN NEW;
END $$;
CREATE TRIGGER trg_cotizacion_despues_update AFTER UPDATE ON cotizacion FOR EACH ROW EXECUTE FUNCTION trg_cotizacion_despues_update();

CREATE FUNCTION fn_recalcular_cotizacion(p_id integer) RETURNS void LANGUAGE plpgsql AS $$
DECLARE c cotizacion%ROWTYPE; v_costo numeric(12,2); v_com numeric(12,2); v_imp numeric(12,2);
BEGIN
  SELECT * INTO c FROM cotizacion WHERE id = p_id;
  SELECT COALESCE(SUM(cantidad * tarifa_unitaria), 0) INTO v_costo FROM cotizacion_detalle WHERE cotizacion_id = p_id;
  v_com := ROUND(v_costo * c.comision_pct / 100, 2);
  v_imp := ROUND((v_costo + v_com) * c.impuesto_pct / 100, 2);
  UPDATE cotizacion SET costo_proveedor = v_costo, comision = v_com, impuestos = v_imp, total = v_costo + v_com + v_imp WHERE id = p_id;
END $$;

CREATE FUNCTION trg_cotizacion_detalle_antes() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE v_estado estado_cotizacion; s servicio%ROWTYPE;
BEGIN
  SELECT estado INTO v_estado FROM cotizacion WHERE id = COALESCE(NEW.cotizacion_id, OLD.cotizacion_id);
  IF v_estado <> 'BORRADOR' THEN RAISE EXCEPTION 'Solo se pueden modificar los servicios de una cotización en BORRADOR'; END IF;
  IF TG_OP <> 'DELETE' THEN
    SELECT * INTO s FROM servicio WHERE id = NEW.servicio_id;
    IF NOT s.activo THEN RAISE EXCEPTION 'El servicio % está inactivo', s.nombre; END IF;
    IF s.tarifa_base <= 0 THEN RAISE EXCEPTION 'El servicio % no tiene tarifa registrada', s.nombre; END IF;
    IF NEW.tarifa_unitaria IS NULL THEN NEW.tarifa_unitaria := s.tarifa_base; END IF;
    RETURN NEW;
  END IF;
  RETURN OLD;
END $$;
CREATE TRIGGER trg_cotizacion_detalle_antes BEFORE INSERT OR UPDATE OR DELETE ON cotizacion_detalle FOR EACH ROW EXECUTE FUNCTION trg_cotizacion_detalle_antes();

CREATE FUNCTION trg_cotizacion_detalle_despues() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  PERFORM fn_recalcular_cotizacion(COALESCE(NEW.cotizacion_id, OLD.cotizacion_id));
  RETURN NULL;
END $$;
CREATE TRIGGER trg_cotizacion_detalle_despues AFTER INSERT OR UPDATE OR DELETE ON cotizacion_detalle FOR EACH ROW EXECUTE FUNCTION trg_cotizacion_detalle_despues();

CREATE FUNCTION fn_generar_detalle_desde_paquete(p_cotizacion integer) RETURNS integer LANGUAGE plpgsql AS $$
DECLARE v_n integer;
BEGIN
  INSERT INTO cotizacion_detalle(cotizacion_id, servicio_id, cantidad)
  SELECT c.id, ps.servicio_id, ps.cantidad * c.nro_pasajeros FROM cotizacion c JOIN paquete_servicio ps ON ps.paquete_id = c.paquete_id WHERE c.id = p_cotizacion;
  GET DIAGNOSTICS v_n = ROW_COUNT;
  RETURN v_n;
END $$;

CREATE FUNCTION fn_vencer_cotizaciones() RETURNS integer LANGUAGE plpgsql AS $$
DECLARE v_n integer;
BEGIN
  UPDATE cotizacion SET estado = 'VENCIDA' WHERE estado = 'ENVIADA' AND vigencia_hasta < CURRENT_DATE;
  GET DIAGNOSTICS v_n = ROW_COUNT;
  RETURN v_n;
END $$;

-- ======================= RESERVAS =======================
CREATE FUNCTION fn_convertir_cotizacion_en_reserva(p_cotizacion integer, p_inicio date, p_fin date, p_agente integer) RETURNS integer LANGUAGE plpgsql AS $$
DECLARE c cotizacion%ROWTYPE; v_id integer;
BEGIN
  SELECT * INTO c FROM cotizacion WHERE id = p_cotizacion FOR UPDATE;       -- bloquea la fila: evita doble reserva
  IF NOT FOUND THEN RAISE EXCEPTION 'La cotización no existe'; END IF;
  IF EXISTS (SELECT 1 FROM reserva WHERE cotizacion_id = p_cotizacion) THEN RAISE EXCEPTION 'La cotización % ya tiene una reserva', c.codigo; END IF;
  IF c.estado <> 'ENVIADA' THEN RAISE EXCEPTION 'La cotización % está en estado % y no puede reservarse', c.codigo, c.estado; END IF;
  IF c.vigencia_hasta < CURRENT_DATE THEN RAISE EXCEPTION 'La cotización % venció el %', c.codigo, to_char(c.vigencia_hasta,'DD/MM/YYYY'); END IF;
  IF NOT fn_tiene_permiso(p_agente, 'RES_GESTIONAR') THEN RAISE EXCEPTION 'El usuario no tiene permiso para administrar reservas'; END IF;
  INSERT INTO reserva(cotizacion_id, cliente_id, agente_id, fecha_inicio, fecha_fin, nro_pasajeros, total)
  VALUES (c.id, c.cliente_id, p_agente, p_inicio, p_fin, c.nro_pasajeros, c.total) RETURNING id INTO v_id;
  INSERT INTO reserva_detalle(reserva_id, servicio_id, cantidad, tarifa_unitaria)
  SELECT v_id, servicio_id, cantidad, tarifa_unitaria FROM cotizacion_detalle WHERE cotizacion_id = c.id;
  UPDATE cotizacion SET estado = 'ACEPTADA' WHERE id = c.id;
  RETURN v_id;                                                              -- todo ocurre en una sola transacción
END $$;

CREATE FUNCTION trg_reserva_antes_insert() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  IF NEW.codigo IS NULL THEN NEW.codigo := fn_siguiente_codigo('RES'); END IF;
  RETURN NEW;
END $$;
CREATE TRIGGER trg_reserva_antes_insert BEFORE INSERT ON reserva FOR EACH ROW EXECUTE FUNCTION trg_reserva_antes_insert();

CREATE FUNCTION trg_reserva_transicion() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  IF NEW.estado <> OLD.estado THEN
    IF NOT ((OLD.estado = 'PENDIENTE'  AND NEW.estado IN ('CONFIRMADA','PAGADA','CANCELADA'))
         OR (OLD.estado = 'CONFIRMADA' AND NEW.estado IN ('PAGADA','CANCELADA'))
         OR (OLD.estado = 'PAGADA'     AND NEW.estado IN ('FINALIZADA','CANCELADA'))) THEN
      RAISE EXCEPTION 'Transición inválida de la reserva: % -> %', OLD.estado, NEW.estado;
    END IF;
    IF NEW.estado = 'CANCELADA' THEN NEW.cancelada_en := now(); END IF;
  END IF;
  RETURN NEW;
END $$;
CREATE TRIGGER trg_reserva_transicion BEFORE UPDATE OF estado ON reserva FOR EACH ROW EXECUTE FUNCTION trg_reserva_transicion();

CREATE FUNCTION trg_reserva_historial() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  IF TG_OP = 'INSERT' THEN
    INSERT INTO historial_estado_reserva(reserva_id, estado_anterior, estado_nuevo, usuario_id) VALUES (NEW.id, NULL, NEW.estado, COALESCE(fn_usuario_app(), NEW.agente_id));
  ELSIF NEW.estado <> OLD.estado THEN
    INSERT INTO historial_estado_reserva(reserva_id, estado_anterior, estado_nuevo, usuario_id) VALUES (NEW.id, OLD.estado, NEW.estado, fn_usuario_app());
    IF NEW.estado = 'CANCELADA' THEN
      PERFORM fn_notificar_cliente(NEW.cliente_id,'RESERVA_CANCELADA','La reserva ' || NEW.codigo || ' fue cancelada','reserva',NEW.id);
    END IF;
  END IF;
  RETURN NULL;
END $$;
CREATE TRIGGER trg_reserva_historial AFTER INSERT OR UPDATE OF estado ON reserva FOR EACH ROW EXECUTE FUNCTION trg_reserva_historial();

CREATE FUNCTION trg_pasajero_limite() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE v_max smallint; v_actual integer;
BEGIN
  SELECT nro_pasajeros INTO v_max FROM reserva WHERE id = NEW.reserva_id;
  SELECT COUNT(*) INTO v_actual FROM pasajero WHERE reserva_id = NEW.reserva_id;
  IF v_actual >= v_max THEN RAISE EXCEPTION 'La reserva solo admite % pasajeros', v_max; END IF;
  RETURN NEW;
END $$;
CREATE TRIGGER trg_pasajero_limite BEFORE INSERT ON pasajero FOR EACH ROW EXECUTE FUNCTION trg_pasajero_limite();

CREATE FUNCTION fn_finalizar_reservas() RETURNS integer LANGUAGE plpgsql AS $$
DECLARE v_n integer;
BEGIN
  UPDATE reserva SET estado = 'FINALIZADA' WHERE estado = 'PAGADA' AND fecha_fin < CURRENT_DATE;
  GET DIAGNOSTICS v_n = ROW_COUNT;
  RETURN v_n;
END $$;

-- ======================= PAGOS =======================
CREATE FUNCTION fn_actualizar_estado_reserva(p_reserva integer) RETURNS void LANGUAGE plpgsql AS $$
DECLARE r reserva%ROWTYPE; v_verificado numeric(12,2);
BEGIN
  SELECT * INTO r FROM reserva WHERE id = p_reserva FOR UPDATE;
  SELECT COALESCE(SUM(monto),0) INTO v_verificado FROM pago WHERE reserva_id = p_reserva AND estado = 'VERIFICADO';
  IF r.estado IN ('PENDIENTE','CONFIRMADA') THEN
    IF v_verificado >= r.total THEN UPDATE reserva SET estado = 'PAGADA' WHERE id = p_reserva;
    ELSIF v_verificado > 0 AND r.estado = 'PENDIENTE' THEN UPDATE reserva SET estado = 'CONFIRMADA' WHERE id = p_reserva;
    END IF;
  END IF;
END $$;

CREATE FUNCTION trg_pago_antes_insert() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE r reserva%ROWTYPE; v_comprometido numeric(12,2);
BEGIN
  SELECT * INTO r FROM reserva WHERE id = NEW.reserva_id FOR UPDATE;
  IF r.estado IN ('CANCELADA','FINALIZADA') THEN RAISE EXCEPTION 'No se aceptan pagos sobre una reserva %', lower(r.estado::text); END IF;
  SELECT COALESCE(SUM(monto),0) INTO v_comprometido FROM pago WHERE reserva_id = NEW.reserva_id AND estado <> 'RECHAZADO';
  IF v_comprometido + NEW.monto > r.total THEN
    RAISE EXCEPTION 'El pago excede el saldo: total %, comprometido %', r.total, v_comprometido;
  END IF;
  NEW.estado := 'PENDIENTE_VERIFICACION'; NEW.verificado_por := NULL; NEW.fecha_verificacion := NULL;
  RETURN NEW;
END $$;
CREATE TRIGGER trg_pago_antes_insert BEFORE INSERT ON pago FOR EACH ROW EXECUTE FUNCTION trg_pago_antes_insert();

CREATE FUNCTION trg_pago_despues_insert() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  PERFORM fn_notificar_permiso('PAGO_VERIFICAR','PAGO_REGISTRADO','Pago de ' || NEW.monto || ' Bs por verificar','pago',NEW.id);
  RETURN NEW;
END $$;
CREATE TRIGGER trg_pago_despues_insert AFTER INSERT ON pago FOR EACH ROW EXECUTE FUNCTION trg_pago_despues_insert();

CREATE FUNCTION trg_pago_antes_update() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  IF NEW.estado <> OLD.estado THEN
    IF OLD.estado <> 'PENDIENTE_VERIFICACION' THEN RAISE EXCEPTION 'El pago ya fue resuelto (%)', OLD.estado; END IF;
    IF NEW.verificado_por IS NULL THEN NEW.verificado_por := fn_usuario_app(); END IF;
    IF NEW.verificado_por IS NULL THEN RAISE EXCEPTION 'Verificar o rechazar un pago exige un responsable'; END IF;
    IF NOT fn_tiene_permiso(NEW.verificado_por, 'PAGO_VERIFICAR') THEN RAISE EXCEPTION 'El usuario no tiene permiso para verificar pagos'; END IF;
    NEW.fecha_verificacion := now();
  END IF;
  RETURN NEW;
END $$;
CREATE TRIGGER trg_pago_antes_update BEFORE UPDATE ON pago FOR EACH ROW EXECUTE FUNCTION trg_pago_antes_update();

CREATE FUNCTION trg_pago_despues_update() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE v_cli integer; v_cod varchar;
BEGIN
  IF NEW.estado <> OLD.estado THEN
    PERFORM fn_actualizar_estado_reserva(NEW.reserva_id);
    SELECT cliente_id, codigo INTO v_cli, v_cod FROM reserva WHERE id = NEW.reserva_id;
    PERFORM fn_notificar_cliente(v_cli, CASE WHEN NEW.estado = 'VERIFICADO' THEN 'PAGO_VERIFICADO'::tipo_notificacion ELSE 'PAGO_RECHAZADO'::tipo_notificacion END,
            'Su pago de ' || NEW.monto || ' Bs sobre la reserva ' || v_cod || ' fue ' || lower(NEW.estado::text), 'pago', NEW.id);
  END IF;
  RETURN NULL;
END $$;
CREATE TRIGGER trg_pago_despues_update AFTER UPDATE OF estado ON pago FOR EACH ROW EXECUTE FUNCTION trg_pago_despues_update();
CREATE VIEW v_paquete_precio AS      -- precio de 1 pasajero con la regla única de cálculo
SELECT p.id AS paquete_id, p.nombre, p.duracion_dias, p.comision_pct, p.impuesto_pct,
       t.costo_proveedor,
       ROUND(t.costo_proveedor * p.comision_pct / 100, 2) AS comision,
       ROUND((t.costo_proveedor + ROUND(t.costo_proveedor * p.comision_pct / 100, 2)) * p.impuesto_pct / 100, 2) AS impuestos,
       t.costo_proveedor + ROUND(t.costo_proveedor * p.comision_pct / 100, 2)
         + ROUND((t.costo_proveedor + ROUND(t.costo_proveedor * p.comision_pct / 100, 2)) * p.impuesto_pct / 100, 2) AS precio_final
FROM paquete p
JOIN LATERAL (SELECT COALESCE(SUM(ps.cantidad * s.tarifa_base),0)::numeric(12,2) AS costo_proveedor
              FROM paquete_servicio ps JOIN servicio s ON s.id = ps.servicio_id WHERE ps.paquete_id = p.id) t ON true;

CREATE VIEW v_reserva_saldo AS
SELECT r.id AS reserva_id, r.codigo, r.cliente_id, r.estado, r.total,
       COALESCE(SUM(p.monto) FILTER (WHERE p.estado = 'VERIFICADO'), 0) AS pagado_verificado,
       COALESCE(SUM(p.monto) FILTER (WHERE p.estado = 'PENDIENTE_VERIFICACION'), 0) AS pendiente_verificacion,
       r.total - COALESCE(SUM(p.monto) FILTER (WHERE p.estado = 'VERIFICADO'), 0) AS saldo
FROM reserva r LEFT JOIN pago p ON p.reserva_id = r.id
GROUP BY r.id;

CREATE VIEW v_ventas_mensuales AS
SELECT date_trunc('month', r.creado_en)::date AS mes, COUNT(*) AS reservas,
       SUM(c.costo_proveedor) AS costo_proveedor, SUM(c.comision) AS comision, SUM(c.impuestos) AS impuestos, SUM(r.total) AS ventas
FROM reserva r JOIN cotizacion c ON c.id = r.cotizacion_id
WHERE r.estado <> 'CANCELADA' GROUP BY 1 ORDER BY 1;

CREATE VIEW v_cobros_mensuales AS
SELECT date_trunc('month', fecha_verificacion)::date AS mes, COUNT(*) AS pagos, SUM(monto) AS cobrado
FROM pago WHERE estado = 'VERIFICADO' GROUP BY 1 ORDER BY 1;

CREATE VIEW v_servicios_mas_solicitados AS
SELECT s.id AS servicio_id, s.nombre, s.tipo, COUNT(DISTINCT rd.reserva_id) AS reservas, SUM(rd.cantidad) AS unidades
FROM reserva_detalle rd JOIN reserva r ON r.id = rd.reserva_id AND r.estado <> 'CANCELADA' JOIN servicio s ON s.id = rd.servicio_id
GROUP BY s.id ORDER BY reservas DESC, unidades DESC, s.nombre;

CREATE VIEW v_clientes_frecuentes AS
SELECT c.id AS cliente_id, c.nombres || ' ' || c.apellidos AS cliente, COUNT(*) AS reservas, SUM(r.total) AS total_gastado, MAX(r.creado_en)::date AS ultima_reserva
FROM cliente c JOIN reserva r ON r.cliente_id = c.id AND r.estado <> 'CANCELADA'
GROUP BY c.id ORDER BY reservas DESC, total_gastado DESC;

CREATE VIEW v_historial_viajes AS
SELECT r.cliente_id, r.codigo, r.fecha_inicio, r.fecha_fin, r.total, r.estado
FROM reserva r WHERE r.estado = 'FINALIZADA' OR (r.estado = 'PAGADA' AND r.fecha_fin < CURRENT_DATE);

CREATE VIEW v_pagos_por_verificar AS
SELECT p.id AS pago_id, r.codigo AS reserva, cl.nombres || ' ' || cl.apellidos AS cliente, p.monto, p.metodo, p.nro_comprobante, p.fecha_pago
FROM pago p JOIN reserva r ON r.id = p.reserva_id JOIN cliente cl ON cl.id = r.cliente_id
WHERE p.estado = 'PENDIENTE_VERIFICACION' ORDER BY p.fecha_pago;

CREATE VIEW v_cotizaciones_por_vencer AS
SELECT c.codigo, cl.nombres || ' ' || cl.apellidos AS cliente, c.total, c.vigencia_hasta, (c.vigencia_hasta - CURRENT_DATE) AS dias_restantes
FROM cotizacion c JOIN cliente cl ON cl.id = c.cliente_id
WHERE c.estado = 'ENVIADA' AND c.vigencia_hasta <= CURRENT_DATE + 2 ORDER BY c.vigencia_hasta;
-- ======================= DATOS INICIALES Y DE EJEMPLO =======================
INSERT INTO parametro_sistema(clave, valor, descripcion) VALUES
 ('impuesto_defecto','13','Porcentaje de impuesto por defecto'),
 ('comision_defecto','10','Porcentaje de comisión por defecto'),
 ('vigencia_cotizacion_dias','7','Días de vigencia de una cotización'),
 ('max_intentos_fallidos','5','Intentos fallidos antes del bloqueo'),
 ('minutos_bloqueo','15','Minutos de bloqueo de la cuenta'),
 ('moneda','BOB','Moneda única de referencia (bolivianos)');

INSERT INTO rol(codigo, nombre, descripcion) VALUES
 ('CLIENTE','Cliente','Usa el portal del cliente'),
 ('AGENTE','Agente de viajes','Opera el sistema'),
 ('ADMIN','Administrador','Hereda las funciones del agente y gestiona usuarios y reportes');
INSERT INTO permiso(codigo, descripcion) VALUES
 ('CAT_CONSULTAR','Consultar servicios y paquetes'),('COT_SOLICITAR','Solicitar cotizaciones'),('RES_SOLICITAR','Solicitar reservas'),
 ('RES_CONSULTAR','Consultar reservas propias'),('PAGO_REGISTRAR','Registrar pagos con comprobante'),('PROV_GESTIONAR','Gestionar proveedores y servicios'),
 ('PAQ_GESTIONAR','Gestionar paquetes'),('CLI_GESTIONAR','Gestionar clientes'),('COT_GESTIONAR','Elaborar cotizaciones'),
 ('RES_GESTIONAR','Administrar reservas'),('PAGO_VERIFICAR','Verificar pagos'),('USR_GESTIONAR','Gestionar usuarios y roles'),('REP_VER','Ver reportes gerenciales');
INSERT INTO rol_permiso(rol_id, permiso_id)
SELECT r.id, p.id FROM rol r JOIN permiso p ON
  (r.codigo = 'CLIENTE' AND p.codigo IN ('CAT_CONSULTAR','COT_SOLICITAR','RES_SOLICITAR','RES_CONSULTAR','PAGO_REGISTRAR'))
  OR (r.codigo = 'AGENTE' AND p.codigo NOT IN ('USR_GESTIONAR','REP_VER'))
  OR (r.codigo = 'ADMIN');

INSERT INTO usuario(rol_id, username, email, password_hash, nombres, apellidos)
SELECT r.id, v.u, v.e, 'pbkdf2_sha256$720000$sal$hash-ejemplo', v.n, v.a
FROM (VALUES ('ADMIN','admin.agencia','admin@definitively.bo','Rosa','Condori'),
             ('AGENTE','agente.uno','agente1@definitively.bo','Jorge','Salazar'),
             ('AGENTE','agente.dos','agente2@definitively.bo','Paola','Limachi'),
             ('CLIENTE','mquispe','maria.quispe@correo.bo','María','Quispe'),
             ('CLIENTE','cmamani','carlos.mamani@correo.bo','Carlos','Mamani'),
             ('CLIENTE','arojas','ana.rojas@correo.bo','Ana','Rojas'),
             ('CLIENTE','pvargas','pedro.vargas@correo.bo','Pedro','Vargas')) AS v(rol,u,e,n,a)
JOIN rol r ON r.codigo = v.rol;

INSERT INTO cliente(usuario_id, tipo_documento, nro_documento, nombres, apellidos, nacionalidad, telefono, correo, preferencias)
SELECT u.id, 'CI', v.doc, u.nombres, u.apellidos, 'Boliviana', v.tel, u.email, v.pref
FROM usuario u JOIN (VALUES ('mquispe','4587123','70011223','Prefiere hoteles céntricos'),('cmamani','5123456','70022334','Viaja en familia'),
                            ('arojas','6234567','70033445','Interés en turismo de aventura'),('pvargas','7345678','70044556','Prefiere paquetes cortos')) AS v(un,doc,tel,pref) ON v.un = u.username;

INSERT INTO destino(nombre, pais, ambito) VALUES ('Uyuni','Bolivia','NACIONAL'),('Copacabana','Bolivia','NACIONAL'),('Cancún','México','INTERNACIONAL');
INSERT INTO proveedor(nombre, tipo, nit, contacto_nombre, contacto_telefono, contacto_correo, politicas) VALUES
 ('Aerolínea Altiplano','AEROLINEA','1020304011','Mesa de agencias','22111111','agencias@altiplano.bo','Cambios con 48 h de anticipación'),
 ('Hotel Salar Real','HOTEL','1020304022','Recepción','26222222','reservas@salarreal.bo','Cancelación gratuita hasta 72 h antes'),
 ('Salar Expediciones','OPERADOR_TOUR','1020304033','Operaciones','26333333','ventas@salarexp.bo','Tour con mínimo 2 pasajeros'),
 ('Transturismo Titicaca','TRANSPORTE','1020304044','Despacho','22444444','despacho@transtiticaca.bo','Equipaje máximo 20 kg'),
 ('Hotel Lago Azul','HOTEL','1020304055','Recepción','28555555','reservas@lagoazul.bo','Check-in 14:00'),
 ('Aerovías Continentales','AEROLINEA','1020304066','Mesa de agencias','22666666','agencias@aerovias.bo','Boletos no reembolsables'),
 ('Caribe Resorts','HOTEL','1020304077','Reservas grupos','+52-998-0000','grupos@caribe.example','Todo incluido'),
 ('Traslados Caribe','TRANSPORTE','1020304088','Despacho','+52-998-1111','info@trasladoscaribe.example','Servicio compartido');
INSERT INTO servicio(proveedor_id, destino_id, nombre, tipo, categoria, tarifa_base, cupo_referencial)
SELECT p.id, d.id, v.n, v.t::tipo_servicio, v.c::categoria_tarifaria, v.tar, v.cupo
FROM (VALUES ('Aerolínea Altiplano','Uyuni','Vuelo La Paz - Uyuni (ida y vuelta)','AEREO','ESTANDAR',850,40),
 ('Hotel Salar Real','Uyuni','Habitación doble 1 noche','HOSPEDAJE','ESTANDAR',320,12),
 ('Salar Expediciones','Uyuni','Tour Salar de Uyuni 3 días','TOUR','ESTANDAR',980,16),
 ('Transturismo Titicaca','Copacabana','Traslado La Paz - Copacabana','TRASLADO','ECONOMICA',100,30),
 ('Hotel Lago Azul','Copacabana','Habitación doble 1 noche Copacabana','HOSPEDAJE','ESTANDAR',240,10),
 ('Transturismo Titicaca','Copacabana','Excursión Isla del Sol','TOUR','ESTANDAR',140,25),
 ('Aerovías Continentales','Cancún','Vuelo La Paz - Cancún (ida y vuelta)','AEREO','PREMIUM',2800,20),
 ('Caribe Resorts','Cancún','Hotel todo incluido Cancún 1 noche','HOSPEDAJE','PREMIUM',180,40),
 ('Traslados Caribe','Cancún','Traslado aeropuerto - hotel Cancún','TRASLADO','ESTANDAR',200,40)) AS v(prov,dest,n,t,c,tar,cupo)
JOIN proveedor p ON p.nombre = v.prov JOIN destino d ON d.nombre = v.dest;

INSERT INTO paquete(nombre, destino_id, duracion_dias, comision_pct, impuesto_pct, vigente_desde, vigente_hasta)
SELECT v.n, d.id, v.dias, v.com, 13, DATE '2026-08-01', DATE '2027-12-31'
FROM (VALUES ('Salar de Uyuni 3D/2N','Uyuni',3,15),('Lago Titicaca y Copacabana','Copacabana',2,12),('Cancún todo incluido','Cancún',7,10)) AS v(n,dest,dias,com)
JOIN destino d ON d.nombre = v.dest;
INSERT INTO paquete_servicio(paquete_id, servicio_id, cantidad)
SELECT p.id, s.id, v.q FROM (VALUES
 ('Salar de Uyuni 3D/2N','Vuelo La Paz - Uyuni (ida y vuelta)',1),('Salar de Uyuni 3D/2N','Habitación doble 1 noche',2),('Salar de Uyuni 3D/2N','Tour Salar de Uyuni 3 días',1),
 ('Lago Titicaca y Copacabana','Traslado La Paz - Copacabana',2),('Lago Titicaca y Copacabana','Habitación doble 1 noche Copacabana',1),('Lago Titicaca y Copacabana','Excursión Isla del Sol',1),
 ('Cancún todo incluido','Vuelo La Paz - Cancún (ida y vuelta)',1),('Cancún todo incluido','Hotel todo incluido Cancún 1 noche',7),('Cancún todo incluido','Traslado aeropuerto - hotel Cancún',2)) AS v(pq,sv,q)
JOIN paquete p ON p.nombre = v.pq JOIN servicio s ON s.nombre = v.sv;

-- Cotizaciones y reservas de ejemplo (6 reservas: 3 en septiembre y 3 en octubre de 2026)
CREATE TEMP TABLE ej(n int, cli text, pq text, pax int, f_res timestamptz, ini date, fin date);
INSERT INTO ej VALUES
 (1,'mquispe','Salar de Uyuni 3D/2N',2,'2026-09-16 10:00-04','2026-11-20','2026-11-22'),
 (2,'cmamani','Lago Titicaca y Copacabana',2,'2026-09-22 11:30-04','2026-12-05','2026-12-06'),
 (3,'mquispe','Cancún todo incluido',2,'2026-09-28 16:00-04','2027-01-10','2027-01-17'),
 (4,'arojas','Salar de Uyuni 3D/2N',4,'2026-10-06 09:15-04','2027-02-12','2027-02-14'),
 (5,'pvargas','Lago Titicaca y Copacabana',3,'2026-10-08 15:40-04','2027-01-23','2027-01-24'),
 (6,'cmamani','Salar de Uyuni 3D/2N',2,'2026-10-12 12:10-04','2027-03-06','2027-03-08');
DO $$
DECLARE e record; v_cot integer; v_res integer; v_ag integer := (SELECT id FROM usuario WHERE username='agente.uno');
BEGIN
  FOR e IN SELECT * FROM ej ORDER BY n LOOP
    INSERT INTO cotizacion(cliente_id, agente_id, paquete_id, nro_pasajeros, fecha_emision, vigencia_hasta)
    SELECT c.id, v_ag, p.id, e.pax, e.f_res::date, CURRENT_DATE + 7 FROM cliente c JOIN usuario u ON u.id = c.usuario_id, paquete p WHERE u.username = e.cli AND p.nombre = e.pq
    RETURNING id INTO v_cot;
    PERFORM fn_generar_detalle_desde_paquete(v_cot);
    UPDATE cotizacion SET estado = 'ENVIADA' WHERE id = v_cot;
    v_res := fn_convertir_cotizacion_en_reserva(v_cot, e.ini, e.fin, v_ag);
    UPDATE reserva SET creado_en = e.f_res WHERE id = v_res;
  END LOOP;
END $$;
-- Pagos de ejemplo
INSERT INTO pago(reserva_id, registrado_por, monto, metodo, nro_comprobante, fecha_pago)
SELECT r.id, (SELECT cl.usuario_id FROM cliente cl WHERE cl.id = r.cliente_id), v.m, v.mt::metodo_pago, v.nc, v.f::date
FROM (VALUES ('RES-2026-00001',3000.00,'TRANSFERENCIA','TR-100001','2026-09-18'),('RES-2026-00002',1468.10,'TRANSFERENCIA','TR-100002','2026-09-24'),
             ('RES-2026-00003',5000.00,'DEPOSITO','DEP-200003','2026-09-30'),('RES-2026-00004',1000.00,'TRANSFERENCIA','TR-100004','2026-10-14'),
             ('RES-2026-00005',500.00,'EFECTIVO',NULL,'2026-10-15')) AS v(cod,m,mt,nc,f) JOIN reserva r ON r.codigo = v.cod;
UPDATE pago SET estado = 'VERIFICADO', verificado_por = (SELECT id FROM usuario WHERE username='agente.uno') WHERE reserva_id IN (SELECT id FROM reserva WHERE codigo IN ('RES-2026-00001','RES-2026-00002','RES-2026-00003'));
UPDATE pago SET fecha_verificacion = (SELECT creado_en FROM reserva r WHERE r.id = pago.reserva_id) + interval '2 days' WHERE estado = 'VERIFICADO';
INSERT INTO pasajero(reserva_id, tipo, nombres, apellidos, tipo_documento, nro_documento, nacionalidad, fecha_nacimiento)
SELECT r.id, 'ADULTO', v.n, v.a, 'CI', v.d, 'Boliviana', v.f::date FROM (VALUES ('María','Quispe','4587123','1988-03-14'),('Luis','Quispe','4587999','1986-07-02')) AS v(n,a,d,f), reserva r WHERE r.codigo = 'RES-2026-00001';
