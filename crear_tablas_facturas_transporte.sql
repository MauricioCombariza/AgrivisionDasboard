-- =====================================================
-- TABLAS PARA FACTURAS DE TRANSPORTE (COURRIERS)
-- Fecha: 2026-01-15
-- =====================================================

USE logistica;

-- =====================================================
-- 1. TABLA DE FACTURAS DE TRANSPORTE (CABECERA)
-- =====================================================

CREATE TABLE IF NOT EXISTS facturas_transporte (
    id INT AUTO_INCREMENT PRIMARY KEY,
    numero_factura VARCHAR(50) NOT NULL COMMENT 'Numero alfanumerico de la factura',
    fecha_factura DATE NOT NULL,
    courrier_id INT NOT NULL COMMENT 'ID del courrier/transportadora en tabla personal',
    monto_total DECIMAL(12, 2) NOT NULL COMMENT 'Monto total de la factura',
    total_sobres INT DEFAULT 0 COMMENT 'Total de sobres en la factura (calculado)',
    estado ENUM('pendiente', 'pagada', 'anulada') DEFAULT 'pendiente',
    observaciones TEXT,
    fecha_creacion TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    fecha_modificacion TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,

    FOREIGN KEY (courrier_id) REFERENCES personal(id),
    UNIQUE KEY uk_factura_courrier (numero_factura, courrier_id),
    INDEX idx_fecha (fecha_factura),
    INDEX idx_courrier (courrier_id),
    INDEX idx_estado (estado)
) ENGINE=InnoDB;

-- =====================================================
-- 2. TABLA DE DETALLE DE FACTURAS DE TRANSPORTE
-- =====================================================

CREATE TABLE IF NOT EXISTS detalle_facturas_transporte (
    id INT AUTO_INCREMENT PRIMARY KEY,
    factura_id INT NOT NULL,
    orden_id INT NOT NULL COMMENT 'Orden asociada',
    cantidad_sobres INT NOT NULL COMMENT 'Cantidad de sobres de esta orden',
    porcentaje DECIMAL(5, 2) GENERATED ALWAYS AS (
        cantidad_sobres * 100.0 / NULLIF((
            SELECT total_sobres FROM facturas_transporte WHERE id = factura_id
        ), 0)
    ) VIRTUAL COMMENT 'Porcentaje del total de sobres',
    costo_asignado DECIMAL(12, 2) NOT NULL COMMENT 'Costo proporcional asignado',
    fecha_creacion TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY (factura_id) REFERENCES facturas_transporte(id) ON DELETE CASCADE,
    FOREIGN KEY (orden_id) REFERENCES ordenes(id),
    UNIQUE KEY uk_factura_orden (factura_id, orden_id),
    INDEX idx_orden (orden_id)
) ENGINE=InnoDB;

-- =====================================================
-- NOTA: El campo porcentaje es virtual y se calcula automaticamente.
-- El costo_asignado se calcula en Python antes de insertar.
-- =====================================================
