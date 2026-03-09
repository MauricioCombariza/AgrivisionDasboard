-- =====================================================
-- MIGRACIÓN: Ajustar sistema de tarifas logísticas
--
-- LÓGICA DE NEGOCIO:
-- - Local (Bogotá): La tarifa del mensajero depende del CLIENTE
-- - Nacional: La tarifa del courier depende del COURIER + Ciudad + Tipo Servicio
--
-- Fecha: 2026-01-07
-- =====================================================

USE logistica;

-- =====================================================
-- PARTE 1: AJUSTAR TABLA precios_cliente
-- Agregar campos para tarifa de mensajero (ámbito local)
-- =====================================================

SELECT '=== PARTE 1: Agregando campos de costo mensajero a precios_cliente ===' AS paso;

ALTER TABLE precios_cliente
ADD COLUMN costo_mensajero_entrega DECIMAL(10, 2) DEFAULT NULL
    COMMENT 'Lo que se le paga al mensajero por entrega (solo ámbito Bogotá)'
    AFTER precio_unitario,
ADD COLUMN costo_mensajero_devolucion DECIMAL(10, 2) DEFAULT NULL
    COMMENT 'Lo que se le paga al mensajero por devolución (solo ámbito Bogotá)'
    AFTER costo_mensajero_entrega;

SELECT 'Campos agregados a precios_cliente' AS resultado;
DESCRIBE precios_cliente;

-- =====================================================
-- PARTE 2: AJUSTAR TABLA personal_ciudades
-- Agregar tipo_servicio para couriers nacionales
-- =====================================================

SELECT '=== PARTE 2: Ajustando personal_ciudades para incluir tipo_servicio ===' AS paso;

-- Eliminar el constraint UNIQUE anterior
ALTER TABLE personal_ciudades DROP KEY uk_personal_ciudad;

-- Agregar campo tipo_servicio
ALTER TABLE personal_ciudades
ADD COLUMN tipo_servicio ENUM('sobre', 'paquete') DEFAULT 'sobre'
    COMMENT 'Tipo de servicio (para couriers nacionales)'
    AFTER ciudad_id;

-- Crear nuevo constraint UNIQUE que incluye tipo_servicio
ALTER TABLE personal_ciudades
ADD UNIQUE KEY uk_personal_ciudad_servicio (personal_id, ciudad_id, tipo_servicio);

SELECT 'Campos agregados a personal_ciudades' AS resultado;
DESCRIBE personal_ciudades;

-- =====================================================
-- PARTE 3: AJUSTAR TABLA orden_personal
-- Separar tarifa_unitaria en tarifa_entrega y tarifa_devolucion
-- =====================================================

SELECT '=== PARTE 3: Ajustando orden_personal para tarifas diferenciadas ===' AS paso;

-- Crear columnas nuevas
ALTER TABLE orden_personal
ADD COLUMN tarifa_entrega DECIMAL(10, 2) DEFAULT 0
    COMMENT 'Tarifa por entrega'
    AFTER cantidad_devolucion,
ADD COLUMN tarifa_devolucion DECIMAL(10, 2) DEFAULT 0
    COMMENT 'Tarifa por devolución'
    AFTER tarifa_entrega;

-- Migrar datos existentes (copiar tarifa_unitaria a ambas tarifas)
UPDATE orden_personal
SET tarifa_entrega = COALESCE(tarifa_unitaria, 0),
    tarifa_devolucion = COALESCE(tarifa_unitaria, 0)
WHERE tarifa_unitaria IS NOT NULL;

-- Eliminar la columna calculada total_pagar
ALTER TABLE orden_personal DROP COLUMN total_pagar;

-- Eliminar la columna antigua tarifa_unitaria
ALTER TABLE orden_personal DROP COLUMN tarifa_unitaria;

-- Recrear la columna total_pagar con la nueva fórmula
ALTER TABLE orden_personal
ADD COLUMN total_pagar DECIMAL(10, 2) GENERATED ALWAYS AS (
    (COALESCE(cantidad_entregada, 0) * COALESCE(tarifa_entrega, 0)) +
    (COALESCE(cantidad_devolucion, 0) * COALESCE(tarifa_devolucion, 0))
) STORED COMMENT 'Total: (entregadas * tarifa_entrega) + (devoluciones * tarifa_devolucion)';

SELECT 'Tabla orden_personal actualizada' AS resultado;
DESCRIBE orden_personal;

-- =====================================================
-- VERIFICACIÓN FINAL
-- =====================================================

SELECT '=== VERIFICACIÓN FINAL ===' AS paso;

SELECT 'Estructura de precios_cliente:' AS info;
SELECT
    COLUMN_NAME,
    COLUMN_TYPE,
    COLUMN_COMMENT
FROM INFORMATION_SCHEMA.COLUMNS
WHERE TABLE_SCHEMA = 'logistica'
  AND TABLE_NAME = 'precios_cliente'
  AND COLUMN_NAME LIKE '%costo%';

SELECT 'Estructura de personal_ciudades:' AS info;
SELECT
    COLUMN_NAME,
    COLUMN_TYPE,
    COLUMN_COMMENT
FROM INFORMATION_SCHEMA.COLUMNS
WHERE TABLE_SCHEMA = 'logistica'
  AND TABLE_NAME = 'personal_ciudades';

SELECT 'Estructura de orden_personal:' AS info;
SELECT
    COLUMN_NAME,
    COLUMN_TYPE,
    COLUMN_COMMENT
FROM INFORMATION_SCHEMA.COLUMNS
WHERE TABLE_SCHEMA = 'logistica'
  AND TABLE_NAME = 'orden_personal'
  AND COLUMN_NAME LIKE '%tarifa%';

-- Verificar datos migrados
SELECT 'Muestra de datos migrados en orden_personal:' AS info;
SELECT
    id,
    orden_id,
    personal_id,
    cantidad_asignada,
    cantidad_entregada,
    cantidad_devolucion,
    tarifa_entrega,
    tarifa_devolucion,
    total_pagar
FROM orden_personal
LIMIT 5;

SELECT '✅ MIGRACIÓN COMPLETADA EXITOSAMENTE' AS resultado;
SELECT 'Ahora se pueden configurar:' AS siguiente_paso;
SELECT '- Tarifas de mensajero por cliente en precios_cliente (ámbito Bogotá)' AS paso_1;
SELECT '- Tarifas de courier por ciudad y tipo_servicio en personal_ciudades (ámbito Nacional)' AS paso_2;
