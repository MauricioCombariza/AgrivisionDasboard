-- ============================================================================
-- Migración: Separar cantidades en local y nacional
-- Fecha: 2026-01-08
-- ============================================================================
--
-- Objetivo: Permitir que una orden tenga cantidades tanto locales como nacionales
-- sin necesidad de duplicar el número de orden
--
-- Cambios:
-- - Agregar: cantidad_local, cantidad_nacional
-- - Agregar versiones local/nacional para todas las cantidades de seguimiento
-- - Mantener: numero_orden UNIQUE
-- - Eliminar: cantidad_total (o convertir en columna calculada)
-- ============================================================================

USE logistica;

-- Paso 1: Agregar columnas de cantidades locales y nacionales
ALTER TABLE ordenes
ADD COLUMN cantidad_local INT NOT NULL DEFAULT 0
    COMMENT 'Cantidad de items para entrega local (Bogotá)'
    AFTER tipo_servicio,
ADD COLUMN cantidad_nacional INT NOT NULL DEFAULT 0
    COMMENT 'Cantidad de items para entrega nacional'
    AFTER cantidad_local;

-- Paso 2: Migrar datos existentes
-- Si existe ciudad_destino_id y es Bogotá → cantidad_local
-- Si existe ciudad_destino_id y NO es Bogotá → cantidad_nacional
-- Si NO existe ciudad_destino_id → asumir nacional
UPDATE ordenes o
LEFT JOIN ciudades c ON o.ciudad_destino_id = c.id
SET
    o.cantidad_local = CASE
        WHEN c.nombre LIKE '%ogot%' THEN o.cantidad_total
        ELSE 0
    END,
    o.cantidad_nacional = CASE
        WHEN c.nombre LIKE '%ogot%' OR c.nombre IS NULL THEN 0
        WHEN c.nombre IS NULL THEN o.cantidad_total
        ELSE o.cantidad_total
    END
WHERE o.cantidad_total > 0;

-- Paso 3: Agregar versiones local/nacional para seguimiento
ALTER TABLE ordenes
ADD COLUMN cantidad_recibido_local INT NOT NULL DEFAULT 0
    COMMENT 'Cantidad recibida de items locales'
    AFTER cantidad_nacional,
ADD COLUMN cantidad_recibido_nacional INT NOT NULL DEFAULT 0
    COMMENT 'Cantidad recibida de items nacionales'
    AFTER cantidad_recibido_local,

ADD COLUMN cantidad_cajoneras_local INT NOT NULL DEFAULT 0
    COMMENT 'Cantidad en cajoneras (local)'
    AFTER cantidad_recibido_nacional,
ADD COLUMN cantidad_cajoneras_nacional INT NOT NULL DEFAULT 0
    COMMENT 'Cantidad en cajoneras (nacional)'
    AFTER cantidad_cajoneras_local,

ADD COLUMN cantidad_lleva_local INT NOT NULL DEFAULT 0
    COMMENT 'Cantidad en ruta (local)'
    AFTER cantidad_cajoneras_nacional,
ADD COLUMN cantidad_lleva_nacional INT NOT NULL DEFAULT 0
    COMMENT 'Cantidad en ruta (nacional)'
    AFTER cantidad_lleva_local,

ADD COLUMN cantidad_entregados_local INT NOT NULL DEFAULT 0
    COMMENT 'Cantidad entregada (local)'
    AFTER cantidad_lleva_nacional,
ADD COLUMN cantidad_entregados_nacional INT NOT NULL DEFAULT 0
    COMMENT 'Cantidad entregada (nacional)'
    AFTER cantidad_entregados_local,

ADD COLUMN cantidad_devolucion_local INT NOT NULL DEFAULT 0
    COMMENT 'Cantidad devuelta (local)'
    AFTER cantidad_entregados_nacional,
ADD COLUMN cantidad_devolucion_nacional INT NOT NULL DEFAULT 0
    COMMENT 'Cantidad devuelta (nacional)'
    AFTER cantidad_devolucion_local;

-- Paso 4: Migrar datos de seguimiento existentes
UPDATE ordenes o
LEFT JOIN ciudades c ON o.ciudad_destino_id = c.id
SET
    o.cantidad_recibido_local = CASE WHEN c.nombre LIKE '%ogot%' THEN o.cantidad_recibido ELSE 0 END,
    o.cantidad_recibido_nacional = CASE WHEN c.nombre LIKE '%ogot%' OR c.nombre IS NULL THEN 0 ELSE o.cantidad_recibido END,

    o.cantidad_cajoneras_local = CASE WHEN c.nombre LIKE '%ogot%' THEN o.cantidad_en_cajoneras ELSE 0 END,
    o.cantidad_cajoneras_nacional = CASE WHEN c.nombre LIKE '%ogot%' OR c.nombre IS NULL THEN 0 ELSE o.cantidad_en_cajoneras END,

    o.cantidad_lleva_local = CASE WHEN c.nombre LIKE '%ogot%' THEN o.cantidad_en_lleva ELSE 0 END,
    o.cantidad_lleva_nacional = CASE WHEN c.nombre LIKE '%ogot%' OR c.nombre IS NULL THEN 0 ELSE o.cantidad_en_lleva END,

    o.cantidad_entregados_local = CASE WHEN c.nombre LIKE '%ogot%' THEN o.cantidad_entregados ELSE 0 END,
    o.cantidad_entregados_nacional = CASE WHEN c.nombre LIKE '%ogot%' OR c.nombre IS NULL THEN 0 ELSE o.cantidad_entregados END,

    o.cantidad_devolucion_local = CASE WHEN c.nombre LIKE '%ogot%' THEN o.cantidad_devolucion ELSE 0 END,
    o.cantidad_devolucion_nacional = CASE WHEN c.nombre LIKE '%ogot%' OR c.nombre IS NULL THEN 0 ELSE o.cantidad_devolucion END;

-- Paso 5: Modificar cantidad_total para que sea columna calculada
-- Primero eliminar la columna actual
ALTER TABLE ordenes
DROP COLUMN cantidad_total;

-- Luego recrearla como GENERATED
ALTER TABLE ordenes
ADD COLUMN cantidad_total INT AS (cantidad_local + cantidad_nacional) STORED
    COMMENT 'Total de items (local + nacional) - Calculado'
    AFTER cantidad_devolucion_nacional;

-- Paso 6: Hacer lo mismo con cantidad_recibido
ALTER TABLE ordenes
DROP COLUMN cantidad_recibido;

ALTER TABLE ordenes
ADD COLUMN cantidad_recibido INT AS (cantidad_recibido_local + cantidad_recibido_nacional) STORED
    COMMENT 'Total recibido (local + nacional) - Calculado'
    AFTER cantidad_total;

-- Paso 7: Eliminar columnas antiguas de seguimiento (ya tenemos las nuevas)
ALTER TABLE ordenes
DROP COLUMN cantidad_en_cajoneras,
DROP COLUMN cantidad_en_lleva,
DROP COLUMN cantidad_entregados,
DROP COLUMN cantidad_devolucion;

-- Paso 8: Verificar estructura final
DESCRIBE ordenes;

-- Paso 9: Mostrar ejemplo de datos migrados
SELECT
    numero_orden,
    cantidad_local,
    cantidad_nacional,
    cantidad_total,
    tipo_servicio,
    estado
FROM ordenes
ORDER BY fecha_recepcion DESC
LIMIT 10;

-- ============================================================================
-- RESUMEN DE LA MIGRACIÓN:
--
-- ANTES:
-- - numero_orden (UNIQUE)
-- - cantidad_total
-- - cantidad_recibido, cantidad_en_cajoneras, etc.
-- - Para orden 123277 local Y nacional → ERROR (duplicate entry)
--
-- DESPUÉS:
-- - numero_orden (UNIQUE)
-- - cantidad_local, cantidad_nacional
-- - cantidad_total (CALCULADA = local + nacional)
-- - cantidad_recibido_local, cantidad_recibido_nacional, etc.
-- - cantidad_recibido (CALCULADA = local + nacional)
-- - Para orden 123277 → un solo registro con cantidad_local Y cantidad_nacional
--
-- FORMATO CSV NUEVO:
-- orden,fecha_recepcion,nombre_cliente,tipo_servicio,cantidad_local,cantidad_nacional
-- 123277,2026-01-06,Banco Caja Social,sobre,4229,7674
-- ============================================================================
