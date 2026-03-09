-- =====================================================
-- MIGRACIÓN COMPATIBLE - Sistema de Tarifas Logísticas
-- Compatible con MySQL 5.7+
-- =====================================================

USE logistica;

-- =====================================================
-- PASO 1: Modificar tabla precios_cliente
-- =====================================================

-- Agregar las dos columnas nuevas (entrega y devolución)
ALTER TABLE precios_cliente
ADD COLUMN costo_mensajero_entrega DECIMAL(10, 2) DEFAULT NULL
    COMMENT 'Lo que se le paga al mensajero por entrega (solo ámbito Bogotá)'
    AFTER precio_unitario;

ALTER TABLE precios_cliente
ADD COLUMN costo_mensajero_devolucion DECIMAL(10, 2) DEFAULT NULL
    COMMENT 'Lo que se le paga al mensajero por devolución (solo ámbito Bogotá)'
    AFTER costo_mensajero_entrega;

-- Migrar datos de tarifa_mensajero (si existen) a las nuevas columnas
-- Asumir que tarifa_mensajero era para entregas
UPDATE precios_cliente
SET costo_mensajero_entrega = tarifa_mensajero
WHERE tarifa_mensajero IS NOT NULL AND tarifa_mensajero > 0;

-- Eliminar columna antigua
ALTER TABLE precios_cliente DROP COLUMN tarifa_mensajero;

SELECT 'PASO 1: precios_cliente actualizada' AS resultado;

-- =====================================================
-- PASO 2: Modificar tabla personal_ciudades
-- =====================================================

-- Eliminar constraint único anterior
ALTER TABLE personal_ciudades DROP KEY uk_personal_ciudad;

-- Agregar campo tipo_servicio
ALTER TABLE personal_ciudades
ADD COLUMN tipo_servicio ENUM('sobre', 'paquete') DEFAULT 'sobre'
    COMMENT 'Tipo de servicio (para couriers nacionales)'
    AFTER ciudad_id;

-- Crear nuevo constraint UNIQUE
ALTER TABLE personal_ciudades
ADD UNIQUE KEY uk_personal_ciudad_servicio (personal_id, ciudad_id, tipo_servicio);

SELECT 'PASO 2: personal_ciudades actualizada' AS resultado;

-- =====================================================
-- PASO 3: Modificar tabla orden_personal
-- =====================================================

-- Agregar las dos columnas nuevas
ALTER TABLE orden_personal
ADD COLUMN tarifa_entrega DECIMAL(10, 2) DEFAULT 0
    COMMENT 'Tarifa por entrega'
    AFTER cantidad_devolucion;

ALTER TABLE orden_personal
ADD COLUMN tarifa_devolucion DECIMAL(10, 2) DEFAULT 0
    COMMENT 'Tarifa por devolución'
    AFTER tarifa_entrega;

-- Migrar datos existentes
UPDATE orden_personal
SET tarifa_entrega = COALESCE(tarifa_unitaria, 0),
    tarifa_devolucion = COALESCE(tarifa_unitaria, 0)
WHERE tarifa_unitaria IS NOT NULL;

-- Eliminar columna calculada
ALTER TABLE orden_personal DROP COLUMN total_pagar;

-- Eliminar columna antigua
ALTER TABLE orden_personal DROP COLUMN tarifa_unitaria;

-- Recrear columna total_pagar con nueva fórmula
ALTER TABLE orden_personal
ADD COLUMN total_pagar DECIMAL(10, 2) GENERATED ALWAYS AS (
    (COALESCE(cantidad_entregada, 0) * COALESCE(tarifa_entrega, 0)) +
    (COALESCE(cantidad_devolucion, 0) * COALESCE(tarifa_devolucion, 0))
) STORED COMMENT 'Total: (entregadas * tarifa_entrega) + (devoluciones * tarifa_devolucion)';

SELECT 'PASO 3: orden_personal actualizada' AS resultado;

-- =====================================================
-- VERIFICACIÓN FINAL
-- =====================================================

SELECT '✅ MIGRACIÓN COMPLETADA EXITOSAMENTE' AS resultado;

-- Mostrar estructura final
SELECT 'Columnas de precios_cliente con mensajero:' AS info;
SELECT COLUMN_NAME, COLUMN_TYPE, COLUMN_COMMENT
FROM INFORMATION_SCHEMA.COLUMNS
WHERE TABLE_SCHEMA = 'logistica'
  AND TABLE_NAME = 'precios_cliente'
  AND COLUMN_NAME LIKE '%mensajero%';

SELECT 'Columnas de personal_ciudades:' AS info;
SELECT COLUMN_NAME, COLUMN_TYPE
FROM INFORMATION_SCHEMA.COLUMNS
WHERE TABLE_SCHEMA = 'logistica'
  AND TABLE_NAME = 'personal_ciudades'
  AND COLUMN_NAME = 'tipo_servicio';

SELECT 'Columnas de orden_personal con tarifa:' AS info;
SELECT COLUMN_NAME, COLUMN_TYPE, COLUMN_COMMENT
FROM INFORMATION_SCHEMA.COLUMNS
WHERE TABLE_SCHEMA = 'logistica'
  AND TABLE_NAME = 'orden_personal'
  AND COLUMN_NAME LIKE '%tarifa%';
