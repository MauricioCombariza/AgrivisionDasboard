import mysql.connector
import os
from dotenv import load_dotenv

load_dotenv()

conn = mysql.connector.connect(
    host=os.environ.get("DB_HOST", "localhost"),
    user=os.environ.get("DB_USER", "root"),
    password=os.environ.get("DB_PASSWORD", ""),
    database=os.environ.get("DB_NAME_LOGISTICA", "logistica")
)
cursor = conn.cursor()

# Verificar si la columna existe en nomina_empleados
cursor.execute("""
    SELECT COUNT(*) FROM INFORMATION_SCHEMA.COLUMNS
    WHERE TABLE_SCHEMA = 'logistica'
    AND TABLE_NAME = 'nomina_empleados'
    AND COLUMN_NAME = 'auxilio_no_salarial'
""")
existe = cursor.fetchone()[0]

if existe == 0:
    print("Agregando columna auxilio_no_salarial a nomina_empleados...")
    cursor.execute("""
        ALTER TABLE nomina_empleados
        ADD COLUMN auxilio_no_salarial DECIMAL(12, 2) NOT NULL DEFAULT 0
        AFTER tiene_auxilio_transporte
    """)
    conn.commit()
    print("Columna agregada exitosamente")
else:
    print("Columna auxilio_no_salarial ya existe en nomina_empleados")

# Verificar si existe en provisiones
cursor.execute("""
    SELECT COUNT(*) FROM INFORMATION_SCHEMA.COLUMNS
    WHERE TABLE_SCHEMA = 'logistica'
    AND TABLE_NAME = 'nomina_provisiones'
    AND COLUMN_NAME = 'auxilio_no_salarial'
""")
existe_prov = cursor.fetchone()[0]

if existe_prov == 0:
    print("Agregando columna auxilio_no_salarial a nomina_provisiones...")
    cursor.execute("""
        ALTER TABLE nomina_provisiones
        ADD COLUMN auxilio_no_salarial DECIMAL(12, 2) NOT NULL DEFAULT 0
        AFTER auxilio_transporte
    """)
    conn.commit()
    print("Columna agregada exitosamente")
else:
    print("Columna auxilio_no_salarial ya existe en provisiones")

# Actualizar Gerente de Tecnología
print("\nActualizando Gerente de Tecnologia...")
cursor.execute("""
    UPDATE nomina_empleados
    SET salario_mensual = 5500000.00,
        auxilio_no_salarial = 3500000.00,
        tiene_auxilio_transporte = FALSE
    WHERE cargo = 'Gerente Tecnología'
""")
conn.commit()
print(f"Filas actualizadas: {cursor.rowcount}")

# Mostrar empleados actualizados
print("\n" + "=" * 80)
print("EMPLEADOS DE NOMINA ACTUALIZADOS")
print("=" * 80)

cursor.execute("""
    SELECT nombre_completo, cargo, salario_mensual, auxilio_no_salarial,
           tiene_auxilio_transporte
    FROM nomina_empleados WHERE activo = TRUE
""")

for row in cursor.fetchall():
    nombre, cargo, salario, aux_no_sal, tiene_aux = row
    total = float(salario) + float(aux_no_sal)
    pct = (float(aux_no_sal) / total * 100) if total > 0 else 0

    print(f"\n{nombre} ({cargo}):")
    print(f"  Salario nominal: ${float(salario):,.0f}")
    print(f"  Auxilio no salarial: ${float(aux_no_sal):,.0f}")
    print(f"  Remuneracion total: ${total:,.0f}")
    print(f"  % No salarial: {pct:.2f}% {'OK LEGAL' if pct <= 40 else 'EXCEDE 40%'}")
    print(f"  Auxilio transporte: {'Si' if tiene_aux else 'No'}")

cursor.close()
conn.close()
print("\nActualizacion completada")
