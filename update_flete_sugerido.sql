-- =====================================================
-- ACTUALIZACIÓN: Agregar costo de flete sugerido
-- Opción 1 + Opción 3 combinadas
-- =====================================================

USE logistica;

-- Agregar campo de costo flete sugerido a ciudades
ALTER TABLE ciudades
ADD COLUMN costo_flete_sugerido DECIMAL(10, 2) DEFAULT 0 COMMENT 'Costo sugerido de flete terrestre a esta ciudad';

-- Crear tabla de historial de fletes para mostrar últimos valores
CREATE TABLE IF NOT EXISTS historial_fletes (
    id INT AUTO_INCREMENT PRIMARY KEY,
    ciudad_id INT NOT NULL,
    orden_id INT,
    costo DECIMAL(10, 2) NOT NULL,
    fecha DATE NOT NULL,
    FOREIGN KEY (ciudad_id) REFERENCES ciudades(id) ON DELETE CASCADE,
    FOREIGN KEY (orden_id) REFERENCES ordenes(id) ON DELETE SET NULL,
    INDEX idx_ciudad_fecha (ciudad_id, fecha DESC)
) ENGINE=InnoDB;

-- Actualizar Bogotá con costo 0 (no tiene flete)
UPDATE ciudades SET costo_flete_sugerido = 0 WHERE es_bogota = TRUE;

SELECT '✅ Campos de flete agregados exitosamente' AS resultado;
