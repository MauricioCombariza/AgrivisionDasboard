-- =====================================================
-- DATOS DE EJEMPLO: Ciudades Principales de Colombia
-- =====================================================

USE logistica;

-- Insertar ciudades principales con costos de flete sugeridos
INSERT INTO ciudades (nombre, departamento, codigo, es_bogota, costo_flete_sugerido) VALUES
('Medellín', 'Antioquia', 'MDE', FALSE, 40000),
('Cali', 'Valle del Cauca', 'CLI', FALSE, 45000),
('Barranquilla', 'Atlántico', 'BAQ', FALSE, 50000),
('Cartagena', 'Bolívar', 'CTG', FALSE, 55000),
('Bucaramanga', 'Santander', 'BGA', FALSE, 35000),
('Pereira', 'Risaralda', 'PEI', FALSE, 38000),
('Manizales', 'Caldas', 'MZL', FALSE, 38000),
('Ibagué', 'Tolima', 'IBE', FALSE, 30000),
('Cúcuta', 'Norte de Santander', 'CUC', FALSE, 42000),
('Villavicencio', 'Meta', 'VVC', FALSE, 28000),
('Soacha', 'Cundinamarca', 'SOA', FALSE, 0),
('Chía', 'Cundinamarca', 'CHI', FALSE, 0),
('Zipaquirá', 'Cundinamarca', 'ZPA', FALSE, 0),
('Facatativá', 'Cundinamarca', 'FAC', FALSE, 0)
ON DUPLICATE KEY UPDATE nombre=nombre;

SELECT '✅ Ciudades de ejemplo agregadas' AS resultado;
