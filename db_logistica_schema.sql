-- =====================================================
-- SISTEMA DE GESTIÓN LOGÍSTICA - SCHEMA DATABASE
-- Versión: 1.0 - Enero 2025
-- Modelo simplificado con contadores por estado
-- =====================================================

CREATE DATABASE IF NOT EXISTS logistica CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
USE logistica;

-- =====================================================
-- 1. TABLA DE USUARIOS Y PERMISOS
-- =====================================================

CREATE TABLE usuarios (
    id INT AUTO_INCREMENT PRIMARY KEY,
    username VARCHAR(50) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    nombre_completo VARCHAR(100) NOT NULL,
    email VARCHAR(100),
    rol ENUM('administrador', 'contabilidad', 'operaciones', 'ventas') NOT NULL,
    activo BOOLEAN DEFAULT TRUE,
    fecha_creacion TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    ultimo_acceso TIMESTAMP NULL,
    INDEX idx_username (username),
    INDEX idx_rol (rol)
) ENGINE=InnoDB;

-- =====================================================
-- 2. TABLA DE CLIENTES
-- =====================================================

CREATE TABLE clientes (
    id INT AUTO_INCREMENT PRIMARY KEY,
    nombre_empresa VARCHAR(150) NOT NULL,
    nit VARCHAR(20) UNIQUE NOT NULL,
    contacto_nombre VARCHAR(100),
    contacto_telefono VARCHAR(20),
    contacto_email VARCHAR(100),
    direccion TEXT,
    ciudad VARCHAR(50),
    plazo_pago_dias INT DEFAULT 30 COMMENT 'Días para pago después de factura',
    activo BOOLEAN DEFAULT TRUE,
    notas TEXT,
    fecha_creacion TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    fecha_modificacion TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    INDEX idx_nit (nit),
    INDEX idx_activo (activo)
) ENGINE=InnoDB;

-- =====================================================
-- 3. TABLA DE PRECIOS POR CLIENTE
-- =====================================================

CREATE TABLE precios_cliente (
    id INT AUTO_INCREMENT PRIMARY KEY,
    cliente_id INT NOT NULL,
    tipo_servicio ENUM('sobre', 'paquete') NOT NULL,
    tipo_operacion ENUM('entrega', 'devolucion') NOT NULL,
    ambito ENUM('bogota', 'nacional') NOT NULL,
    precio_unitario DECIMAL(10, 2) NOT NULL COMMENT 'Precio que cobra el cliente',
    -- Costos de mensajero (solo para ámbito Bogotá)
    costo_mensajero_entrega DECIMAL(10, 2) DEFAULT NULL COMMENT 'Lo que se le paga al mensajero por entrega (solo ámbito Bogotá)',
    costo_mensajero_devolucion DECIMAL(10, 2) DEFAULT NULL COMMENT 'Lo que se le paga al mensajero por devolución (solo ámbito Bogotá)',
    vigencia_desde DATE NOT NULL,
    vigencia_hasta DATE NOT NULL,
    activo BOOLEAN DEFAULT TRUE,
    notas TEXT,
    fecha_creacion TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (cliente_id) REFERENCES clientes(id) ON DELETE CASCADE,
    INDEX idx_cliente_tipo (cliente_id, tipo_servicio, tipo_operacion),
    INDEX idx_vigencia (vigencia_desde, vigencia_hasta)
) ENGINE=InnoDB;

-- =====================================================
-- 4. TABLA DE CIUDADES
-- =====================================================

CREATE TABLE ciudades (
    id INT AUTO_INCREMENT PRIMARY KEY,
    nombre VARCHAR(100) NOT NULL,
    departamento VARCHAR(100),
    codigo VARCHAR(10),
    es_bogota BOOLEAN DEFAULT FALSE,
    activa BOOLEAN DEFAULT TRUE,
    INDEX idx_nombre (nombre),
    INDEX idx_bogota (es_bogota)
) ENGINE=InnoDB;

-- =====================================================
-- 5. TABLA DE PERSONAL (CÓDIGO ÚNICO DE 4 DÍGITOS)
-- =====================================================

CREATE TABLE personal (
    id INT AUTO_INCREMENT PRIMARY KEY,
    codigo CHAR(4) UNIQUE NOT NULL COMMENT 'Código único de 4 dígitos (puede empezar con 0)',
    nombre_completo VARCHAR(150) NOT NULL,
    identificacion VARCHAR(20) UNIQUE NOT NULL,
    telefono VARCHAR(20),
    email VARCHAR(100),
    tipo_personal ENUM('mensajero', 'alistamiento', 'conductor', 'courier_externo', 'transportadora') NOT NULL,
    -- Datos bancarios
    banco VARCHAR(100),
    numero_cuenta VARCHAR(50),
    tipo_cuenta ENUM('ahorros', 'corriente'),
    -- Condiciones de pago
    dia_pago INT DEFAULT 8 COMMENT 'Día del mes para pago',
    activo BOOLEAN DEFAULT TRUE,
    observaciones TEXT,
    fecha_ingreso DATE,
    fecha_creacion TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    fecha_modificacion TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    INDEX idx_codigo (codigo),
    INDEX idx_tipo (tipo_personal),
    INDEX idx_activo (activo)
) ENGINE=InnoDB;

-- =====================================================
-- 6. TABLA DE TARIFAS PERSONAL-CIUDAD
-- =====================================================

CREATE TABLE personal_ciudades (
    id INT AUTO_INCREMENT PRIMARY KEY,
    personal_id INT NOT NULL,
    ciudad_id INT NOT NULL,
    tarifa_entrega DECIMAL(10, 2) COMMENT 'Tarifa por entrega',
    tarifa_devolucion DECIMAL(10, 2) COMMENT 'Tarifa por devolución',
    vigencia_desde DATE NOT NULL,
    vigencia_hasta DATE,
    activo BOOLEAN DEFAULT TRUE,
    FOREIGN KEY (personal_id) REFERENCES personal(id) ON DELETE CASCADE,
    FOREIGN KEY (ciudad_id) REFERENCES ciudades(id) ON DELETE CASCADE,
    UNIQUE KEY uk_personal_ciudad (personal_id, ciudad_id),
    INDEX idx_ciudad (ciudad_id)
) ENGINE=InnoDB;

-- =====================================================
-- 7. TABLA DE TARIFAS DE SERVICIOS INTERNOS
-- =====================================================

CREATE TABLE tarifas_servicios (
    id INT AUTO_INCREMENT PRIMARY KEY,
    tipo_servicio ENUM('alistamiento_hora', 'transporte_completo', 'medio_transporte', 'pegado_guia') NOT NULL,
    descripcion VARCHAR(200),
    tarifa DECIMAL(10, 2) NOT NULL,
    vigencia_desde DATE NOT NULL,
    vigencia_hasta DATE,
    activo BOOLEAN DEFAULT TRUE,
    fecha_creacion TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_tipo (tipo_servicio),
    INDEX idx_vigencia (vigencia_desde, vigencia_hasta)
) ENGINE=InnoDB;

-- =====================================================
-- 8. TABLA DE ÓRDENES (CON CONTADORES POR ESTADO)
-- =====================================================

CREATE TABLE ordenes (
    id INT AUTO_INCREMENT PRIMARY KEY,
    numero_orden VARCHAR(50) UNIQUE NOT NULL COMMENT 'Número de orden único',
    cliente_id INT NOT NULL,
    ciudad_destino_id INT COMMENT 'Ciudad destino principal',
    fecha_recepcion DATE NOT NULL,
    tipo_servicio ENUM('sobre', 'paquete') NOT NULL,

    -- CONTADORES POR ESTADO (flujo: recibido → cajoneras → lleva → finalizado)
    cantidad_total INT NOT NULL DEFAULT 0 COMMENT 'Total de sobres/paquetes',
    cantidad_recibido INT NOT NULL DEFAULT 0 COMMENT 'En estado: recibido',
    cantidad_en_cajoneras INT NOT NULL DEFAULT 0 COMMENT 'En estado: cajoneras',
    cantidad_en_lleva INT NOT NULL DEFAULT 0 COMMENT 'En estado: en lleva',
    cantidad_entregados INT NOT NULL DEFAULT 0 COMMENT 'Finalizados: entregados',
    cantidad_devolucion INT NOT NULL DEFAULT 0 COMMENT 'Finalizados: devolución',

    -- Valores financieros
    precio_unitario DECIMAL(10, 2) COMMENT 'Precio por unidad según contrato',
    valor_total DECIMAL(12, 2) DEFAULT 0 COMMENT 'Valor total a cobrar al cliente',

    -- Costos
    costo_mensajero_total DECIMAL(12, 2) DEFAULT 0,
    costo_alistamiento_total DECIMAL(12, 2) DEFAULT 0,
    costo_pegado_total DECIMAL(12, 2) DEFAULT 0,
    costo_transporte_total DECIMAL(12, 2) DEFAULT 0,
    costo_flete_total DECIMAL(12, 2) DEFAULT 0,
    costo_total DECIMAL(12, 2) GENERATED ALWAYS AS (
        COALESCE(costo_mensajero_total, 0) +
        COALESCE(costo_alistamiento_total, 0) +
        COALESCE(costo_pegado_total, 0) +
        COALESCE(costo_transporte_total, 0) +
        COALESCE(costo_flete_total, 0)
    ) STORED,

    utilidad_total DECIMAL(12, 2) GENERATED ALWAYS AS (
        COALESCE(valor_total, 0) - (
            COALESCE(costo_mensajero_total, 0) +
            COALESCE(costo_alistamiento_total, 0) +
            COALESCE(costo_pegado_total, 0) +
            COALESCE(costo_transporte_total, 0) +
            COALESCE(costo_flete_total, 0)
        )
    ) STORED,

    -- Control
    estado ENUM('activa', 'finalizada', 'anulada') DEFAULT 'activa',
    facturado BOOLEAN DEFAULT FALSE,
    fecha_finalizacion DATE COMMENT 'Cuando entregados + devoluciones = total',
    observaciones TEXT,
    fecha_creacion TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    fecha_modificacion TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,

    FOREIGN KEY (cliente_id) REFERENCES clientes(id),
    FOREIGN KEY (ciudad_destino_id) REFERENCES ciudades(id) ON DELETE SET NULL,
    INDEX idx_cliente (cliente_id),
    INDEX idx_fecha (fecha_recepcion),
    INDEX idx_estado (estado),
    INDEX idx_facturado (facturado),
    INDEX idx_numero (numero_orden),
    INDEX idx_ciudad (ciudad_destino_id)
) ENGINE=InnoDB;

-- =====================================================
-- 9. TABLA DE ASIGNACIONES DE PERSONAL A ÓRDENES
-- =====================================================

CREATE TABLE orden_personal (
    id INT AUTO_INCREMENT PRIMARY KEY,
    orden_id INT NOT NULL,
    personal_id INT NOT NULL,
    cantidad_asignada INT NOT NULL COMMENT 'Cuántos ítems se asignaron a este personal',
    cantidad_entregada INT DEFAULT 0,
    cantidad_devolucion INT DEFAULT 0,
    tarifa_unitaria DECIMAL(10, 2),
    total_pagar DECIMAL(10, 2) GENERATED ALWAYS AS (
        (COALESCE(cantidad_entregada, 0) + COALESCE(cantidad_devolucion, 0)) * COALESCE(tarifa_unitaria, 0)
    ) STORED,
    fecha_asignacion DATE,
    observaciones TEXT,
    FOREIGN KEY (orden_id) REFERENCES ordenes(id) ON DELETE CASCADE,
    FOREIGN KEY (personal_id) REFERENCES personal(id) ON DELETE CASCADE,
    INDEX idx_orden (orden_id),
    INDEX idx_personal (personal_id)
) ENGINE=InnoDB;

-- =====================================================
-- 10. TABLA DE REGISTRO DE HORAS (ALISTAMIENTO)
-- =====================================================

CREATE TABLE registro_horas (
    id INT AUTO_INCREMENT PRIMARY KEY,
    personal_id INT NOT NULL,
    orden_id INT COMMENT 'Orden en la que trabajó (opcional)',
    fecha DATE NOT NULL,
    horas_trabajadas DECIMAL(5, 2) NOT NULL,
    tarifa_hora DECIMAL(10, 2) NOT NULL,
    total DECIMAL(10, 2) GENERATED ALWAYS AS (horas_trabajadas * tarifa_hora) STORED,
    tipo_trabajo ENUM('alistamiento_sobres', 'alistamiento_paquetes') NOT NULL,
    aprobado BOOLEAN DEFAULT FALSE,
    aprobado_por INT COMMENT 'Usuario que aprobó',
    fecha_aprobacion TIMESTAMP NULL,
    liquidado BOOLEAN DEFAULT FALSE,
    liquidacion_id INT,
    observaciones TEXT,
    fecha_creacion TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (personal_id) REFERENCES personal(id) ON DELETE CASCADE,
    FOREIGN KEY (orden_id) REFERENCES ordenes(id) ON DELETE SET NULL,
    FOREIGN KEY (aprobado_por) REFERENCES usuarios(id) ON DELETE SET NULL,
    INDEX idx_personal (personal_id),
    INDEX idx_fecha (fecha),
    INDEX idx_aprobado (aprobado),
    INDEX idx_liquidado (liquidado)
) ENGINE=InnoDB;

-- =====================================================
-- 11. TABLA DE REGISTRO DE LABORES
-- =====================================================

CREATE TABLE registro_labores (
    id INT AUTO_INCREMENT PRIMARY KEY,
    personal_id INT NOT NULL,
    orden_id INT COMMENT 'Orden relacionada',
    fecha DATE NOT NULL,
    tipo_labor ENUM('pegado_guia', 'transporte_completo', 'medio_transporte') NOT NULL,
    cantidad INT NOT NULL COMMENT 'Guías pegadas o viajes',
    tarifa_unitaria DECIMAL(10, 2) NOT NULL,
    total DECIMAL(10, 2) GENERATED ALWAYS AS (cantidad * tarifa_unitaria) STORED,
    aprobado BOOLEAN DEFAULT FALSE,
    aprobado_por INT,
    fecha_aprobacion TIMESTAMP NULL,
    liquidado BOOLEAN DEFAULT FALSE,
    liquidacion_id INT,
    observaciones TEXT,
    fecha_creacion TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (personal_id) REFERENCES personal(id) ON DELETE CASCADE,
    FOREIGN KEY (orden_id) REFERENCES ordenes(id) ON DELETE SET NULL,
    FOREIGN KEY (aprobado_por) REFERENCES usuarios(id) ON DELETE SET NULL,
    INDEX idx_personal (personal_id),
    INDEX idx_fecha (fecha),
    INDEX idx_tipo (tipo_labor),
    INDEX idx_aprobado (aprobado),
    INDEX idx_liquidado (liquidado)
) ENGINE=InnoDB;

-- =====================================================
-- 11B. SUBSIDIO DE TRANSPORTE
-- =====================================================
-- Calcula automáticamente el subsidio de transporte basado en horas trabajadas
-- Regla: >= 5 horas = transporte_completo, < 5 horas = medio_transporte
-- Máximo 1 subsidio por persona por día

CREATE TABLE subsidio_transporte (
    id INT AUTO_INCREMENT PRIMARY KEY,
    personal_id INT NOT NULL,
    fecha DATE NOT NULL,

    -- Datos del cálculo
    horas_totales DECIMAL(5, 2) NOT NULL DEFAULT 0.00
        COMMENT 'Total de horas trabajadas ese día (alistamiento + admin)',
    tipo_subsidio ENUM('transporte_completo', 'medio_transporte') NOT NULL
        COMMENT 'transporte_completo si >= 5 horas, medio_transporte si < 5 horas',
    tarifa DECIMAL(10, 2) NOT NULL
        COMMENT 'Tarifa aplicada al momento del cálculo',
    total DECIMAL(10, 2) GENERATED ALWAYS AS (tarifa) STORED
        COMMENT 'Igual a tarifa (1 subsidio por día)',

    -- Origen del registro
    origen ENUM('automatico', 'manual', 'recalculado') DEFAULT 'automatico'
        COMMENT 'Cómo se generó el registro',

    -- Control de aprobación y liquidación
    aprobado BOOLEAN DEFAULT FALSE,
    aprobado_por INT COMMENT 'Usuario que aprobó',
    fecha_aprobacion TIMESTAMP NULL,
    liquidado BOOLEAN DEFAULT FALSE,
    liquidacion_id INT,

    observaciones TEXT,
    fecha_creacion TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    fecha_modificacion TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,

    FOREIGN KEY (personal_id) REFERENCES personal(id) ON DELETE CASCADE,
    UNIQUE KEY uk_personal_fecha (personal_id, fecha),
    INDEX idx_fecha (fecha),
    INDEX idx_personal (personal_id),
    INDEX idx_aprobado (aprobado),
    INDEX idx_liquidado (liquidado),
    INDEX idx_tipo (tipo_subsidio)
) ENGINE=InnoDB COMMENT='Subsidios de transporte calculados por horas trabajadas';

-- =====================================================
-- 12. LIQUIDACIONES DE PAGO A PERSONAL
-- =====================================================

CREATE TABLE liquidaciones (
    id INT AUTO_INCREMENT PRIMARY KEY,
    numero_liquidacion VARCHAR(50) UNIQUE NOT NULL,
    personal_id INT NOT NULL,
    periodo_mes INT NOT NULL COMMENT '1-12',
    periodo_anio INT NOT NULL,
    fecha_generacion DATE NOT NULL,
    fecha_pago_programada DATE NOT NULL COMMENT 'Día 8 generalmente',

    -- Desglose
    total_entregas DECIMAL(12, 2) DEFAULT 0,
    cantidad_entregas INT DEFAULT 0,
    total_horas DECIMAL(12, 2) DEFAULT 0,
    cantidad_horas DECIMAL(5, 2) DEFAULT 0,
    total_labores DECIMAL(12, 2) DEFAULT 0,
    cantidad_labores INT DEFAULT 0,
    bonificaciones DECIMAL(12, 2) DEFAULT 0,
    descuentos DECIMAL(12, 2) DEFAULT 0,
    total_a_pagar DECIMAL(12, 2) NOT NULL,

    estado ENUM('generada', 'aprobada', 'pagada') DEFAULT 'generada',
    fecha_pago_real DATE,
    metodo_pago ENUM('efectivo', 'transferencia', 'cheque') DEFAULT 'transferencia',
    referencia_pago VARCHAR(100),
    observaciones TEXT,
    generado_por INT,
    aprobado_por INT,
    fecha_creacion TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY (personal_id) REFERENCES personal(id) ON DELETE CASCADE,
    FOREIGN KEY (generado_por) REFERENCES usuarios(id) ON DELETE SET NULL,
    FOREIGN KEY (aprobado_por) REFERENCES usuarios(id) ON DELETE SET NULL,
    INDEX idx_personal (personal_id),
    INDEX idx_periodo (periodo_anio, periodo_mes),
    INDEX idx_fecha_pago (fecha_pago_programada),
    INDEX idx_estado (estado)
) ENGINE=InnoDB;

-- =====================================================
-- 13. FACTURAS EMITIDAS (A CLIENTES)
-- =====================================================

CREATE TABLE facturas_emitidas (
    id INT AUTO_INCREMENT PRIMARY KEY,
    numero_factura VARCHAR(50) UNIQUE NOT NULL,
    cliente_id INT NOT NULL,
    fecha_emision DATE NOT NULL,
    fecha_vencimiento DATE NOT NULL,
    periodo_mes INT NOT NULL,
    periodo_anio INT NOT NULL,

    cantidad_items INT DEFAULT 0,
    subtotal DECIMAL(12, 2) NOT NULL,
    descuento DECIMAL(12, 2) DEFAULT 0,
    total DECIMAL(12, 2) NOT NULL,
    saldo_pendiente DECIMAL(12, 2) NOT NULL,

    estado ENUM('pendiente', 'parcial', 'pagada', 'vencida', 'anulada') DEFAULT 'pendiente',
    observaciones TEXT,
    fecha_creacion TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    fecha_modificacion TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,

    FOREIGN KEY (cliente_id) REFERENCES clientes(id),
    INDEX idx_numero (numero_factura),
    INDEX idx_cliente (cliente_id),
    INDEX idx_fecha_emision (fecha_emision),
    INDEX idx_fecha_vencimiento (fecha_vencimiento),
    INDEX idx_estado (estado),
    INDEX idx_periodo (periodo_anio, periodo_mes)
) ENGINE=InnoDB;

-- =====================================================
-- 14. DETALLE DE FACTURAS EMITIDAS
-- =====================================================

CREATE TABLE detalle_facturas_emitidas (
    id INT AUTO_INCREMENT PRIMARY KEY,
    factura_id INT NOT NULL,
    orden_id INT COMMENT 'Orden facturada',
    descripcion TEXT NOT NULL,
    cantidad INT NOT NULL DEFAULT 1,
    precio_unitario DECIMAL(10, 2) NOT NULL,
    subtotal DECIMAL(10, 2) NOT NULL,
    FOREIGN KEY (factura_id) REFERENCES facturas_emitidas(id) ON DELETE CASCADE,
    FOREIGN KEY (orden_id) REFERENCES ordenes(id) ON DELETE SET NULL,
    INDEX idx_factura (factura_id),
    INDEX idx_orden (orden_id)
) ENGINE=InnoDB;

-- =====================================================
-- 15. FACTURAS RECIBIDAS (COURIERS/TRANSPORTADORAS)
-- =====================================================

CREATE TABLE facturas_recibidas (
    id INT AUTO_INCREMENT PRIMARY KEY,
    numero_factura VARCHAR(50) NOT NULL,
    personal_id INT NOT NULL,
    tipo ENUM('courier', 'transportadora', 'materiales', 'otros') NOT NULL,
    fecha_recepcion DATE NOT NULL,
    fecha_vencimiento DATE NOT NULL,
    periodo_mes INT,
    periodo_anio INT,

    cantidad_items INT DEFAULT 0,
    subtotal DECIMAL(12, 2) NOT NULL,
    descuento DECIMAL(12, 2) DEFAULT 0,
    total DECIMAL(12, 2) NOT NULL,
    saldo_pendiente DECIMAL(12, 2) NOT NULL,

    estado ENUM('pendiente', 'parcial', 'pagada', 'anulada') DEFAULT 'pendiente',
    observaciones TEXT,
    archivo_adjunto VARCHAR(255),
    fecha_creacion TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    fecha_modificacion TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,

    FOREIGN KEY (personal_id) REFERENCES personal(id),
    INDEX idx_numero (numero_factura, personal_id),
    INDEX idx_personal (personal_id),
    INDEX idx_fecha_recepcion (fecha_recepcion),
    INDEX idx_fecha_vencimiento (fecha_vencimiento),
    INDEX idx_estado (estado),
    INDEX idx_tipo (tipo)
) ENGINE=InnoDB;

-- =====================================================
-- 16. DETALLE DE FACTURAS RECIBIDAS
-- =====================================================

CREATE TABLE detalle_facturas_recibidas (
    id INT AUTO_INCREMENT PRIMARY KEY,
    factura_id INT NOT NULL,
    descripcion TEXT NOT NULL,
    cantidad INT NOT NULL DEFAULT 1,
    precio_unitario DECIMAL(10, 2) NOT NULL,
    subtotal DECIMAL(10, 2) NOT NULL,
    FOREIGN KEY (factura_id) REFERENCES facturas_recibidas(id) ON DELETE CASCADE,
    INDEX idx_factura (factura_id)
) ENGINE=InnoDB;

-- =====================================================
-- 17. PAGOS RECIBIDOS (DE CLIENTES)
-- =====================================================

CREATE TABLE pagos_recibidos (
    id INT AUTO_INCREMENT PRIMARY KEY,
    factura_id INT NOT NULL,
    fecha_pago DATE NOT NULL,
    monto DECIMAL(12, 2) NOT NULL,
    metodo_pago ENUM('efectivo', 'transferencia', 'cheque', 'tarjeta', 'otros') NOT NULL,
    referencia VARCHAR(100),
    observaciones TEXT,
    usuario_registro_id INT,
    fecha_creacion TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (factura_id) REFERENCES facturas_emitidas(id) ON DELETE CASCADE,
    FOREIGN KEY (usuario_registro_id) REFERENCES usuarios(id) ON DELETE SET NULL,
    INDEX idx_factura (factura_id),
    INDEX idx_fecha (fecha_pago)
) ENGINE=InnoDB;

-- =====================================================
-- 18. PAGOS REALIZADOS (A PERSONAL/COURIERS)
-- =====================================================

CREATE TABLE pagos_realizados (
    id INT AUTO_INCREMENT PRIMARY KEY,
    factura_id INT NULL,
    liquidacion_id INT NULL,
    fecha_pago DATE NOT NULL,
    monto DECIMAL(12, 2) NOT NULL,
    metodo_pago ENUM('efectivo', 'transferencia', 'cheque', 'tarjeta', 'otros') NOT NULL,
    referencia VARCHAR(100),
    observaciones TEXT,
    usuario_registro_id INT,
    fecha_creacion TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (factura_id) REFERENCES facturas_recibidas(id) ON DELETE CASCADE,
    FOREIGN KEY (liquidacion_id) REFERENCES liquidaciones(id) ON DELETE CASCADE,
    FOREIGN KEY (usuario_registro_id) REFERENCES usuarios(id) ON DELETE SET NULL,
    INDEX idx_factura (factura_id),
    INDEX idx_liquidacion (liquidacion_id),
    INDEX idx_fecha (fecha_pago)
) ENGINE=InnoDB;

-- =====================================================
-- 19. COSTOS ADICIONALES
-- =====================================================

CREATE TABLE costos_adicionales (
    id INT AUTO_INCREMENT PRIMARY KEY,
    tipo ENUM('flete', 'materiales', 'otros') NOT NULL,
    descripcion TEXT NOT NULL,
    ciudad_id INT,
    fecha DATE NOT NULL,
    monto DECIMAL(10, 2) NOT NULL,
    proveedor VARCHAR(150),
    factura_referencia VARCHAR(50),
    orden_id INT,
    pagado BOOLEAN DEFAULT FALSE,
    fecha_pago DATE,
    observaciones TEXT,
    fecha_creacion TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (ciudad_id) REFERENCES ciudades(id) ON DELETE SET NULL,
    FOREIGN KEY (orden_id) REFERENCES ordenes(id) ON DELETE SET NULL,
    INDEX idx_tipo (tipo),
    INDEX idx_fecha (fecha),
    INDEX idx_ciudad (ciudad_id),
    INDEX idx_pagado (pagado)
) ENGINE=InnoDB;

-- =====================================================
-- 20. AUDITORÍA
-- =====================================================

CREATE TABLE auditoria (
    id INT AUTO_INCREMENT PRIMARY KEY,
    usuario_id INT,
    tabla VARCHAR(50) NOT NULL,
    registro_id INT,
    accion ENUM('INSERT', 'UPDATE', 'DELETE') NOT NULL,
    datos_anteriores JSON,
    datos_nuevos JSON,
    fecha_accion TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    ip_address VARCHAR(45),
    FOREIGN KEY (usuario_id) REFERENCES usuarios(id) ON DELETE SET NULL,
    INDEX idx_tabla_registro (tabla, registro_id),
    INDEX idx_usuario (usuario_id),
    INDEX idx_fecha (fecha_accion)
) ENGINE=InnoDB;

-- =====================================================
-- DATOS INICIALES
-- =====================================================

-- Usuario admin (password: admin123)
INSERT INTO usuarios (username, password_hash, nombre_completo, email, rol) VALUES
('admin', '$2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMQJqhN8/LewY5NU7RXVdgxEgi', 'Administrador', 'admin@carvajal.com', 'administrador');

-- Bogotá
INSERT INTO ciudades (nombre, departamento, codigo, es_bogota) VALUES
('Bogotá D.C.', 'Cundinamarca', 'BOG', TRUE);

-- Tarifas 2025
INSERT INTO tarifas_servicios (tipo_servicio, descripcion, tarifa, vigencia_desde, vigencia_hasta) VALUES
('alistamiento_hora', 'Hora de alistamiento', 7960.90, '2025-01-01', '2025-12-31'),
('transporte_completo', 'Transporte completo', 8333.33, '2025-01-01', '2025-12-31'),
('medio_transporte', 'Medio transporte', 4166.67, '2025-01-01', '2025-12-31'),
('pegado_guia', 'Pegado de guía', 11.54, '2025-01-01', '2025-12-31');

-- =====================================================
-- VISTAS PARA REPORTES
-- =====================================================

-- Vista: Estado de órdenes
CREATE VIEW vista_estado_ordenes AS
SELECT
    o.id,
    o.numero_orden,
    c.nombre_empresa AS cliente,
    ci.nombre AS ciudad_destino,
    o.tipo_servicio,
    o.fecha_recepcion,
    o.cantidad_total,
    o.cantidad_recibido,
    o.cantidad_en_cajoneras,
    o.cantidad_en_lleva,
    o.cantidad_entregados,
    o.cantidad_devolucion,
    (o.cantidad_entregados + o.cantidad_devolucion) AS finalizados,
    CASE
        WHEN o.cantidad_total > 0
        THEN ROUND((o.cantidad_entregados + o.cantidad_devolucion) / o.cantidad_total * 100, 2)
        ELSE 0
    END AS porcentaje_completado,
    o.valor_total,
    o.costo_total,
    o.utilidad_total,
    CASE
        WHEN o.valor_total > 0
        THEN ROUND(o.utilidad_total / o.valor_total * 100, 2)
        ELSE 0
    END AS margen_porcentaje,
    o.estado,
    o.facturado
FROM ordenes o
JOIN clientes c ON o.cliente_id = c.id
LEFT JOIN ciudades ci ON o.ciudad_destino_id = ci.id;

-- Vista: Rentabilidad por cliente
CREATE VIEW vista_rentabilidad_cliente AS
SELECT
    c.id,
    c.nombre_empresa,
    COUNT(DISTINCT o.id) AS total_ordenes,
    SUM(o.cantidad_total) AS total_items,
    SUM(o.cantidad_entregados) AS total_entregados,
    SUM(o.cantidad_devolucion) AS total_devoluciones,
    SUM(o.valor_total) AS ingresos_totales,
    SUM(o.costo_total) AS costos_totales,
    SUM(o.utilidad_total) AS utilidad_total,
    CASE
        WHEN SUM(o.valor_total) > 0
        THEN ROUND(SUM(o.utilidad_total) / SUM(o.valor_total) * 100, 2)
        ELSE 0
    END AS margen_porcentaje
FROM clientes c
LEFT JOIN ordenes o ON c.id = o.cliente_id AND o.estado = 'finalizada'
GROUP BY c.id, c.nombre_empresa;

-- Vista: Cuentas por cobrar
CREATE VIEW vista_cuentas_por_cobrar AS
SELECT
    fe.id,
    fe.numero_factura,
    c.nombre_empresa AS cliente,
    fe.fecha_emision,
    fe.fecha_vencimiento,
    fe.total,
    fe.saldo_pendiente,
    fe.estado,
    DATEDIFF(CURRENT_DATE, fe.fecha_vencimiento) AS dias_vencidos,
    CASE
        WHEN DATEDIFF(CURRENT_DATE, fe.fecha_vencimiento) > 0 THEN 'VENCIDA'
        WHEN DATEDIFF(fe.fecha_vencimiento, CURRENT_DATE) <= 7 THEN 'POR VENCER'
        ELSE 'VIGENTE'
    END AS clasificacion
FROM facturas_emitidas fe
JOIN clientes c ON fe.cliente_id = c.id
WHERE fe.estado IN ('pendiente', 'parcial', 'vencida')
ORDER BY fe.fecha_vencimiento;

-- Vista: Cuentas por pagar
CREATE VIEW vista_cuentas_por_pagar AS
SELECT
    'factura' AS tipo,
    fr.id,
    fr.numero_factura AS referencia,
    p.codigo,
    p.nombre_completo AS acreedor,
    fr.fecha_vencimiento,
    fr.saldo_pendiente AS monto,
    fr.estado,
    DATEDIFF(fr.fecha_vencimiento, CURRENT_DATE) AS dias_hasta_vencimiento,
    CASE
        WHEN DATEDIFF(CURRENT_DATE, fr.fecha_vencimiento) > 0 THEN 'VENCIDA'
        WHEN DATEDIFF(fr.fecha_vencimiento, CURRENT_DATE) <= 7 THEN 'POR VENCER'
        ELSE 'VIGENTE'
    END AS clasificacion
FROM facturas_recibidas fr
JOIN personal p ON fr.personal_id = p.id
WHERE fr.estado IN ('pendiente', 'parcial')

UNION ALL

SELECT
    'liquidacion' AS tipo,
    l.id,
    l.numero_liquidacion AS referencia,
    p.codigo,
    p.nombre_completo AS acreedor,
    l.fecha_pago_programada AS fecha_vencimiento,
    l.total_a_pagar AS monto,
    l.estado,
    DATEDIFF(l.fecha_pago_programada, CURRENT_DATE) AS dias_hasta_vencimiento,
    CASE
        WHEN DATEDIFF(CURRENT_DATE, l.fecha_pago_programada) > 0 THEN 'VENCIDA'
        WHEN DATEDIFF(l.fecha_pago_programada, CURRENT_DATE) <= 7 THEN 'POR VENCER'
        ELSE 'VIGENTE'
    END AS clasificacion
FROM liquidaciones l
JOIN personal p ON l.personal_id = p.id
WHERE l.estado IN ('generada', 'aprobada')

ORDER BY fecha_vencimiento;

-- Vista: Flujo de caja (60 días)
CREATE VIEW vista_flujo_caja_60dias AS
SELECT
    fecha,
    tipo,
    descripcion,
    monto,
    categoria,
    dias_hasta_fecha,
    CASE
        WHEN dias_hasta_fecha < 0 THEN 'VENCIDO'
        WHEN dias_hasta_fecha <= 7 THEN 'ESTA SEMANA'
        WHEN dias_hasta_fecha <= 30 THEN 'ESTE MES'
        ELSE 'PROXIMO MES'
    END AS periodo
FROM (
    SELECT
        fe.fecha_vencimiento AS fecha,
        'ingreso' AS tipo,
        CONCAT('Cobro: ', c.nombre_empresa, ' - ', fe.numero_factura) AS descripcion,
        fe.saldo_pendiente AS monto,
        'cliente' AS categoria,
        DATEDIFF(fe.fecha_vencimiento, CURRENT_DATE) AS dias_hasta_fecha
    FROM facturas_emitidas fe
    JOIN clientes c ON fe.cliente_id = c.id
    WHERE fe.estado IN ('pendiente', 'parcial', 'vencida')
    AND fe.fecha_vencimiento <= DATE_ADD(CURRENT_DATE, INTERVAL 60 DAY)

    UNION ALL

    SELECT
        fr.fecha_vencimiento AS fecha,
        'egreso' AS tipo,
        CONCAT('Pago: ', p.nombre_completo, ' - ', fr.numero_factura) AS descripcion,
        fr.saldo_pendiente AS monto,
        fr.tipo AS categoria,
        DATEDIFF(fr.fecha_vencimiento, CURRENT_DATE) AS dias_hasta_fecha
    FROM facturas_recibidas fr
    JOIN personal p ON fr.personal_id = p.id
    WHERE fr.estado IN ('pendiente', 'parcial')
    AND fr.fecha_vencimiento <= DATE_ADD(CURRENT_DATE, INTERVAL 60 DAY)

    UNION ALL

    SELECT
        l.fecha_pago_programada AS fecha,
        'egreso' AS tipo,
        CONCAT('Pago: ', p.nombre_completo, ' - ', l.numero_liquidacion) AS descripcion,
        l.total_a_pagar AS monto,
        p.tipo_personal AS categoria,
        DATEDIFF(l.fecha_pago_programada, CURRENT_DATE) AS dias_hasta_fecha
    FROM liquidaciones l
    JOIN personal p ON l.personal_id = p.id
    WHERE l.estado IN ('generada', 'aprobada')
    AND l.fecha_pago_programada <= DATE_ADD(CURRENT_DATE, INTERVAL 60 DAY)
) AS flujo
ORDER BY fecha, tipo DESC;
