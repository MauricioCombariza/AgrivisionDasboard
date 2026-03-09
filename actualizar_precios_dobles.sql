-- =====================================================
-- Actualización: Sistema de Precios Duales
-- =====================================================
-- Agrega campo para manejar dos precios por cliente:
-- 1. precio_unitario: Lo que el cliente PAGA a Agrivision
-- 2. tarifa_mensajero: Lo que Agrivision PAGA al mensajero
-- =====================================================

USE logistica;

-- Agregar campo de tarifa al mensajero
ALTER TABLE precios_cliente
ADD COLUMN tarifa_mensajero DECIMAL(10, 2) DEFAULT 0 COMMENT 'Tarifa que se paga al mensajero por este servicio'
AFTER precio_unitario;

-- Actualizar comentario de precio_unitario para claridad
ALTER TABLE precios_cliente
MODIFY COLUMN precio_unitario DECIMAL(10, 2) NOT NULL COMMENT 'Precio que el cliente paga a Agrivision';

-- Actualizar comentario de la tabla
ALTER TABLE precios_cliente COMMENT = 'Precios por cliente: precio de venta y tarifa al mensajero';

SELECT 'Campo tarifa_mensajero agregado exitosamente' as mensaje;
SELECT 'Ahora puedes configurar el precio de venta y la tarifa al mensajero' as info;
