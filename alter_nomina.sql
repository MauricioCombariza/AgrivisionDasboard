-- Agregar campo auxilio_no_salarial a nomina_empleados
ALTER TABLE nomina_empleados
ADD COLUMN auxilio_no_salarial DECIMAL(12, 2) NOT NULL DEFAULT 0
AFTER tiene_auxilio_transporte;

-- Agregar campo a nomina_provisiones
ALTER TABLE nomina_provisiones
ADD COLUMN auxilio_no_salarial DECIMAL(12, 2) NOT NULL DEFAULT 0
AFTER auxilio_transporte;

-- Actualizar Gerente de Tecnología
UPDATE nomina_empleados
SET salario_mensual = 5500000.00,
    auxilio_no_salarial = 3500000.00,
    tiene_auxilio_transporte = FALSE
WHERE cargo = 'Gerente Tecnología';

-- Verificar
SELECT nombre_completo, cargo, salario_mensual, auxilio_no_salarial,
       salario_mensual + auxilio_no_salarial as total_remuneracion
FROM nomina_empleados WHERE activo = TRUE;
