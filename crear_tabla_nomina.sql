-- =====================================================
-- MIGRACIÓN: Crear tablas de NÓMINA
-- Fecha: 2026-01-16
-- Descripción: Tablas para gestión de nómina administrativa
-- =====================================================

USE logistica;

-- Tabla de empleados de nómina (diferente de personal operativo)
CREATE TABLE IF NOT EXISTS nomina_empleados (
    id INT AUTO_INCREMENT PRIMARY KEY,
    nombre_completo VARCHAR(150) NOT NULL,
    identificacion VARCHAR(20) UNIQUE NOT NULL,
    cargo VARCHAR(100) NOT NULL,
    salario_mensual DECIMAL(12, 2) NOT NULL DEFAULT 0,
    tiene_auxilio_transporte BOOLEAN DEFAULT TRUE COMMENT 'Si gana menos de 2 SMMLV',
    fecha_ingreso DATE NOT NULL,
    fecha_retiro DATE NULL,
    activo BOOLEAN DEFAULT TRUE,
    banco VARCHAR(100),
    numero_cuenta VARCHAR(50),
    tipo_cuenta ENUM('ahorros', 'corriente'),
    observaciones TEXT,
    fecha_creacion TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    fecha_modificacion TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,

    INDEX idx_activo (activo),
    INDEX idx_cargo (cargo)
) ENGINE=InnoDB COMMENT='Empleados de nómina administrativa';

-- Tabla de configuración de parámetros de nómina
CREATE TABLE IF NOT EXISTS nomina_parametros (
    id INT AUTO_INCREMENT PRIMARY KEY,
    parametro VARCHAR(50) NOT NULL UNIQUE,
    valor DECIMAL(12, 4) NOT NULL,
    descripcion VARCHAR(200),
    vigencia_desde DATE NOT NULL,
    vigencia_hasta DATE,
    activo BOOLEAN DEFAULT TRUE,
    fecha_creacion TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    INDEX idx_parametro (parametro),
    INDEX idx_vigencia (vigencia_desde)
) ENGINE=InnoDB COMMENT='Parámetros de cálculo de nómina';

-- Insertar parámetros de nómina 2026 (Decretos 1469 y 1470 del 29/12/2025)
INSERT INTO nomina_parametros (parametro, valor, descripcion, vigencia_desde) VALUES
-- Valores fijos
('smmlv', 1750905.00, 'Salario Mínimo Mensual Legal Vigente 2026', '2026-01-01'),
('auxilio_transporte', 249095.00, 'Auxilio de Transporte mensual 2026', '2026-01-01'),
-- Porcentajes empleador
('arl_porcentaje', 0.522, 'ARL Riesgo I - % sobre salario', '2025-01-01'),
('eps_porcentaje', 8.5, 'EPS Empleador - % sobre salario', '2025-01-01'),
('afp_porcentaje', 12.0, 'AFP Empleador - % sobre salario', '2025-01-01'),
('caja_porcentaje', 4.0, 'Caja de Compensación - % sobre salario', '2025-01-01'),
-- Provisiones
('prima_porcentaje', 8.33, 'Prima de servicios - % sobre salario+aux', '2025-01-01'),
('cesantias_porcentaje', 8.33, 'Cesantías - % sobre salario+aux', '2025-01-01'),
('int_cesantias_porcentaje', 12.0, 'Intereses a cesantías - % anual sobre cesantías', '2025-01-01'),
('vacaciones_porcentaje', 4.17, 'Vacaciones - % sobre salario (sin aux)', '2025-01-01')
ON DUPLICATE KEY UPDATE valor = VALUES(valor), vigencia_desde = VALUES(vigencia_desde);

-- Tabla de provisiones mensuales de nómina
CREATE TABLE IF NOT EXISTS nomina_provisiones (
    id INT AUTO_INCREMENT PRIMARY KEY,
    empleado_id INT NOT NULL,
    periodo_mes INT NOT NULL COMMENT '1-12',
    periodo_anio INT NOT NULL,

    -- Salario base
    salario_base DECIMAL(12, 2) NOT NULL DEFAULT 0,
    auxilio_transporte DECIMAL(12, 2) NOT NULL DEFAULT 0,

    -- Aportes seguridad social (gasto mensual)
    arl DECIMAL(12, 2) NOT NULL DEFAULT 0,
    eps DECIMAL(12, 2) NOT NULL DEFAULT 0,
    afp DECIMAL(12, 2) NOT NULL DEFAULT 0,
    caja_compensacion DECIMAL(12, 2) NOT NULL DEFAULT 0,

    -- Provisiones (se acumulan para pago futuro)
    prima DECIMAL(12, 2) NOT NULL DEFAULT 0,
    cesantias DECIMAL(12, 2) NOT NULL DEFAULT 0,
    int_cesantias DECIMAL(12, 2) NOT NULL DEFAULT 0,
    vacaciones DECIMAL(12, 2) NOT NULL DEFAULT 0,

    -- Totales calculados
    total_seguridad_social DECIMAL(12, 2) GENERATED ALWAYS AS (arl + eps + afp + caja_compensacion) STORED,
    total_provisiones DECIMAL(12, 2) GENERATED ALWAYS AS (prima + cesantias + int_cesantias + vacaciones) STORED,
    costo_total_empleado DECIMAL(12, 2) GENERATED ALWAYS AS (
        salario_base + auxilio_transporte + arl + eps + afp + caja_compensacion +
        prima + cesantias + int_cesantias + vacaciones
    ) STORED,

    estado ENUM('provisionado', 'pagado') DEFAULT 'provisionado',
    fecha_pago DATE NULL,
    observaciones TEXT,
    fecha_creacion TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY (empleado_id) REFERENCES nomina_empleados(id) ON DELETE CASCADE,
    UNIQUE KEY uk_empleado_periodo (empleado_id, periodo_mes, periodo_anio),
    INDEX idx_periodo (periodo_anio, periodo_mes),
    INDEX idx_estado (estado)
) ENGINE=InnoDB COMMENT='Provisiones mensuales de nómina por empleado';

-- Insertar empleados iniciales basados en los datos proporcionados
INSERT INTO nomina_empleados (nombre_completo, identificacion, cargo, salario_mensual, tiene_auxilio_transporte, fecha_ingreso) VALUES
('Asistente Operativo', '0000000001', 'Asistente operativo', 1746882.00, TRUE, '2025-01-01'),
('Gerente Tecnología', '0000000002', 'Gerente Tecnología', 6987528.00, FALSE, '2025-01-01'),
('Pasante', '0000000003', 'Pasante', 0.00, FALSE, '2025-01-01')
ON DUPLICATE KEY UPDATE salario_mensual = VALUES(salario_mensual);

-- Verificar creación
SELECT 'Tablas de nómina creadas exitosamente' as resultado;
SELECT * FROM nomina_empleados;
SELECT * FROM nomina_parametros WHERE activo = TRUE;
