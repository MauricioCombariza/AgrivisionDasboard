-- =====================================================
-- Actualización: Sistema de Tarifas Simplificado
-- =====================================================
-- Este script agrega campos de tarifas directamente
-- a la tabla personal para simplificar el sistema
-- =====================================================

USE logistica;

-- Agregar campos de tarifas a la tabla personal
ALTER TABLE personal
ADD COLUMN tarifa_entrega DECIMAL(10, 2) DEFAULT 0 COMMENT 'Tarifa fija por entrega para couriers externos',
ADD COLUMN tarifa_devolucion DECIMAL(10, 2) DEFAULT 0 COMMENT 'Tarifa fija por devolución (70% de entrega por default)',
ADD COLUMN costo_flete_sobre DECIMAL(10, 2) DEFAULT 0 COMMENT 'Costo aproximado de flete terrestre por sobre';

-- Actualizar comentario de la tabla
ALTER TABLE personal COMMENT = 'Personal: mensajeros, couriers, alistamiento. Tarifas fijas por courier (no por ciudad)';

SELECT 'Campos agregados exitosamente a tabla personal' as mensaje;
SELECT 'Ahora los couriers tienen tarifas fijas independientes de la ciudad' as info;
