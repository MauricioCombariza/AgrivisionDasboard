-- =====================================================
-- MIGRACIÓN: Crear tabla SUBSIDIO_TRANSPORTE
-- Fecha: 2026-01-16
-- Descripción: Tabla para almacenar subsidios de transporte
--              calculados automáticamente basados en horas trabajadas
-- =====================================================

-- Regla de negocio:
-- Si horas_alistamiento + horas_administrativas >= 5h/día/persona → transporte_completo
-- Si < 5h → medio_transporte

USE logistica;

-- Crear tabla subsidio_transporte
CREATE TABLE IF NOT EXISTS subsidio_transporte (
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

    -- Restricciones
    FOREIGN KEY (personal_id) REFERENCES personal(id) ON DELETE CASCADE,

    -- IMPORTANTE: Máximo 1 subsidio por persona por día
    UNIQUE KEY uk_personal_fecha (personal_id, fecha),

    -- Índices para consultas frecuentes
    INDEX idx_fecha (fecha),
    INDEX idx_personal (personal_id),
    INDEX idx_aprobado (aprobado),
    INDEX idx_liquidado (liquidado),
    INDEX idx_tipo (tipo_subsidio)
) ENGINE=InnoDB COMMENT='Subsidios de transporte calculados por horas trabajadas';

-- Verificar creación
SELECT 'Tabla subsidio_transporte creada exitosamente' as resultado;
DESCRIBE subsidio_transporte;
