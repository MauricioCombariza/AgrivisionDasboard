-- =====================================================
-- MIGRACIÓN PASO A PASO - Sistema de Tarifas Logísticas
-- Ejecutar línea por línea o sección por sección
-- =====================================================

USE logistica;

-- =====================================================
-- PASO 1: Modificar tabla precios_cliente
-- =====================================================

-- Verificar columnas actuales
SELECT 'PASO 1: Verificando estructura de precios_cliente' AS info;
SHOW COLUMNS FROM precios_cliente LIKE '%mensajero%';

-- Eliminar columna antigua si existe (solo una tarifa)
SELECT 'Eliminando tarifa_mensajero antigua (si existe)' AS info;
ALTER TABLE precios_cliente DROP COLUMN IF EXISTS tarifa_mensajero;

-- Agregar las dos columnas nuevas (entrega y devolución)
SELECT 'Agregando costo_mensajero_entrega' AS info;
ALTER TABLE precios_cliente
ADD COLUMN IF NOT EXISTS costo_mensajero_entrega DECIMAL(10, 2) DEFAULT NULL
    COMMENT 'Lo que se le paga al mensajero por entrega (solo ámbito Bogotá)'
    AFTER precio_unitario;

SELECT 'Agregando costo_mensajero_devolucion' AS info;
ALTER TABLE precios_cliente
ADD COLUMN IF NOT EXISTS costo_mensajero_devolucion DECIMAL(10, 2) DEFAULT NULL
    COMMENT 'Lo que se le paga al mensajero por devolución (solo ámbito Bogotá)'
    AFTER costo_mensajero_entrega;

SELECT 'PASO 1 COMPLETADO' AS resultado;
SELECT '---' AS separador;

-- =====================================================
-- PASO 2: Modificar tabla personal_ciudades
-- =====================================================

SELECT 'PASO 2: Modificando personal_ciudades para agregar tipo_servicio' AS info;

-- Verificar si existe constraint único anterior
SELECT 'Eliminando constraint antiguo uk_personal_ciudad (si existe)' AS info;
ALTER TABLE personal_ciudades DROP KEY IF EXISTS uk_personal_ciudad;

-- Agregar campo tipo_servicio
SELECT 'Agregando campo tipo_servicio' AS info;
ALTER TABLE personal_ciudades
ADD COLUMN IF NOT EXISTS tipo_servicio ENUM('sobre', 'paquete') DEFAULT 'sobre'
    COMMENT 'Tipo de servicio (para couriers nacionales)'
    AFTER ciudad_id;

-- Crear nuevo constraint UNIQUE que incluye tipo_servicio
SELECT 'Creando constraint uk_personal_ciudad_servicio' AS info;
ALTER TABLE personal_ciudades
ADD UNIQUE KEY IF NOT EXISTS uk_personal_ciudad_servicio (personal_id, ciudad_id, tipo_servicio);

SELECT 'PASO 2 COMPLETADO' AS resultado;
SELECT '---' AS separador;

-- =====================================================
-- PASO 3: Modificar tabla orden_personal
-- =====================================================

SELECT 'PASO 3: Modificando orden_personal' AS info;

-- Agregar las dos columnas nuevas
SELECT 'Agregando tarifa_entrega' AS info;
ALTER TABLE orden_personal
ADD COLUMN IF NOT EXISTS tarifa_entrega DECIMAL(10, 2) DEFAULT 0
    COMMENT 'Tarifa por entrega'
    AFTER cantidad_devolucion;

SELECT 'Agregando tarifa_devolucion' AS info;
ALTER TABLE orden_personal
ADD COLUMN IF NOT EXISTS tarifa_devolucion DECIMAL(10, 2) DEFAULT 0
    COMMENT 'Tarifa por devolución'
    AFTER tarifa_entrega;

-- Migrar datos existentes de tarifa_unitaria a las nuevas columnas
SELECT 'Migrando datos de tarifa_unitaria a tarifa_entrega y tarifa_devolucion' AS info;
UPDATE orden_personal
SET tarifa_entrega = COALESCE(tarifa_unitaria, 0),
    tarifa_devolucion = COALESCE(tarifa_unitaria, 0)
WHERE tarifa_unitaria IS NOT NULL
  AND (tarifa_entrega IS NULL OR tarifa_entrega = 0);

-- Eliminar columna calculada total_pagar (necesario antes de cambiar definición)
SELECT 'Eliminando columna calculada total_pagar antigua' AS info;
ALTER TABLE orden_personal DROP COLUMN IF EXISTS total_pagar;

-- Eliminar columna antigua tarifa_unitaria
SELECT 'Eliminando tarifa_unitaria antigua' AS info;
ALTER TABLE orden_personal DROP COLUMN IF EXISTS tarifa_unitaria;

-- Recrear columna total_pagar con nueva fórmula
SELECT 'Recreando total_pagar con nueva fórmula' AS info;
ALTER TABLE orden_personal
ADD COLUMN total_pagar DECIMAL(10, 2) GENERATED ALWAYS AS (
    (COALESCE(cantidad_entregada, 0) * COALESCE(tarifa_entrega, 0)) +
    (COALESCE(cantidad_devolucion, 0) * COALESCE(tarifa_devolucion, 0))
) STORED COMMENT 'Total: (entregadas * tarifa_entrega) + (devoluciones * tarifa_devolucion)';

SELECT 'PASO 3 COMPLETADO' AS resultado;
SELECT '---' AS separador;

-- =====================================================
-- VERIFICACIÓN FINAL
-- =====================================================

SELECT '=====================================' AS info;
SELECT 'VERIFICACIÓN FINAL' AS info;
SELECT '=====================================' AS info;

SELECT 'Estructura de precios_cliente:' AS info;
SHOW COLUMNS FROM precios_cliente LIKE '%mensajero%';

SELECT 'Estructura de personal_ciudades:' AS info;
SHOW COLUMNS FROM personal_ciudades LIKE '%servicio%';

SELECT 'Estructura de orden_personal:' AS info;
SHOW COLUMNS FROM orden_personal LIKE '%tarifa%';

-- Muestra de datos
SELECT 'Muestra de orden_personal (primeros 5 registros):' AS info;
SELECT
    id, orden_id, personal_id, cantidad_asignada,
    cantidad_entregada, cantidad_devolucion,
    tarifa_entrega, tarifa_devolucion, total_pagar
FROM orden_personal
LIMIT 5;

SELECT '=====================================' AS info;
SELECT '✅ MIGRACIÓN COMPLETADA EXITOSAMENTE' AS resultado;
SELECT '=====================================' AS info;
