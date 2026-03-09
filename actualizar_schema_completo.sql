-- =====================================================
-- SCRIPT PARA ACTUALIZAR EL SCHEMA PRINCIPAL
-- Ejecutar DESPUÉS de la migración de datos
-- =====================================================

USE logistica;

-- Este script solo documenta los cambios para futuras instalaciones
-- Los ajustes reales a la base de datos están en migracion_tarifas_logistica.sql

SELECT '===================================================' AS info;
SELECT 'CAMBIOS EN EL SCHEMA PARA NUEVAS INSTALACIONES' AS info;
SELECT '===================================================' AS info;

SELECT '' AS separador;
SELECT 'TABLA: precios_cliente' AS tabla;
SELECT '- Agregar: costo_mensajero_entrega DECIMAL(10, 2)' AS cambio_1;
SELECT '- Agregar: costo_mensajero_devolucion DECIMAL(10, 2)' AS cambio_2;
SELECT '- Comentario: Solo aplica para ámbito Bogotá' AS nota;

SELECT '' AS separador;
SELECT 'TABLA: personal_ciudades' AS tabla;
SELECT '- Agregar: tipo_servicio ENUM(''sobre'', ''paquete'') DEFAULT ''sobre''' AS cambio_1;
SELECT '- Modificar UNIQUE KEY: uk_personal_ciudad_servicio (personal_id, ciudad_id, tipo_servicio)' AS cambio_2;
SELECT '- Comentario: Permite diferentes tarifas por tipo de servicio' AS nota;

SELECT '' AS separador;
SELECT 'TABLA: orden_personal' AS tabla;
SELECT '- Eliminar: tarifa_unitaria' AS cambio_1;
SELECT '- Agregar: tarifa_entrega DECIMAL(10, 2)' AS cambio_2;
SELECT '- Agregar: tarifa_devolucion DECIMAL(10, 2)' AS cambio_3;
SELECT '- Modificar GENERATED: total_pagar = (cantidad_entregada * tarifa_entrega) + (cantidad_devolucion * tarifa_devolucion)' AS cambio_4;

SELECT '' AS separador;
SELECT 'Para aplicar estos cambios a la base de datos actual, ejecutar:' AS instruccion;
SELECT 'mysql -u root -p logistica < migracion_tarifas_logistica.sql' AS comando;
