#!/usr/bin/env python3
"""
Script para ejecutar la migración de base de datos
con manejo de errores
"""

import mysql.connector
import sys
import os
from dotenv import load_dotenv

load_dotenv()

def conectar():
    """Conectar a la base de datos"""
    try:
        conn = mysql.connector.connect(
            host=os.environ.get("DB_HOST", "localhost"),
            user=os.environ.get("DB_USER", "root"),
            password=os.environ.get("DB_PASSWORD", ""),
            database=os.environ.get("DB_NAME_LOGISTICA", "logistica")
        )
        return conn
    except Exception as e:
        print(f"❌ Error conectando a BD: {e}")
        sys.exit(1)

def ejecutar_sql(cursor, sql, descripcion):
    """Ejecutar un comando SQL con manejo de errores"""
    try:
        print(f"⏳ {descripcion}...")
        cursor.execute(sql)
        print(f"✅ {descripcion} - OK")
        return True
    except mysql.connector.errors.DatabaseError as e:
        if "Duplicate column name" in str(e):
            print(f"⚠️  {descripcion} - Ya existe (omitiendo)")
            return True
        elif "Can't DROP" in str(e):
            print(f"⚠️  {descripcion} - No existe (omitiendo)")
            return True
        else:
            print(f"❌ {descripcion} - ERROR: {e}")
            return False

def main():
    print("=" * 60)
    print("MIGRACIÓN DE BASE DE DATOS - Sistema de Tarifas")
    print("=" * 60)
    print()

    conn = conectar()
    cursor = conn.cursor()

    # =====================================================
    # PASO 1: Modificar precios_cliente
    # =====================================================
    print("PASO 1: Modificar tabla precios_cliente")
    print("-" * 60)

    ejecutar_sql(cursor, """
        ALTER TABLE precios_cliente
        ADD COLUMN costo_mensajero_entrega DECIMAL(10, 2) DEFAULT NULL
        COMMENT 'Costo mensajero por entrega (ámbito Bogotá)'
        AFTER precio_unitario
    """, "Agregar costo_mensajero_entrega")

    ejecutar_sql(cursor, """
        ALTER TABLE precios_cliente
        ADD COLUMN costo_mensajero_devolucion DECIMAL(10, 2) DEFAULT NULL
        COMMENT 'Costo mensajero por devolución (ámbito Bogotá)'
        AFTER costo_mensajero_entrega
    """, "Agregar costo_mensajero_devolucion")

    # Migrar datos existentes
    ejecutar_sql(cursor, """
        UPDATE precios_cliente
        SET costo_mensajero_entrega = tarifa_mensajero
        WHERE tarifa_mensajero IS NOT NULL AND tarifa_mensajero > 0
          AND costo_mensajero_entrega IS NULL
    """, "Migrar datos de tarifa_mensajero")

    # Eliminar columna antigua
    if ejecutar_sql(cursor, """
        ALTER TABLE precios_cliente DROP COLUMN tarifa_mensajero
    """, "Eliminar columna tarifa_mensajero"):
        conn.commit()

    print()

    # =====================================================
    # PASO 2: Modificar personal_ciudades
    # =====================================================
    print("PASO 2: Modificar tabla personal_ciudades")
    print("-" * 60)

    # Eliminar constraint anterior
    ejecutar_sql(cursor, """
        ALTER TABLE personal_ciudades DROP KEY uk_personal_ciudad
    """, "Eliminar constraint uk_personal_ciudad")

    # Agregar tipo_servicio
    ejecutar_sql(cursor, """
        ALTER TABLE personal_ciudades
        ADD COLUMN tipo_servicio ENUM('sobre', 'paquete') DEFAULT 'sobre'
        COMMENT 'Tipo de servicio'
        AFTER ciudad_id
    """, "Agregar campo tipo_servicio")

    # Crear nuevo constraint
    ejecutar_sql(cursor, """
        ALTER TABLE personal_ciudades
        ADD UNIQUE KEY uk_personal_ciudad_servicio (personal_id, ciudad_id, tipo_servicio)
    """, "Crear constraint uk_personal_ciudad_servicio")

    conn.commit()
    print()

    # =====================================================
    # PASO 3: Modificar orden_personal
    # =====================================================
    print("PASO 3: Modificar tabla orden_personal")
    print("-" * 60)

    # Agregar nuevas columnas
    ejecutar_sql(cursor, """
        ALTER TABLE orden_personal
        ADD COLUMN tarifa_entrega DECIMAL(10, 2) DEFAULT 0
        COMMENT 'Tarifa por entrega'
        AFTER cantidad_devolucion
    """, "Agregar tarifa_entrega")

    ejecutar_sql(cursor, """
        ALTER TABLE orden_personal
        ADD COLUMN tarifa_devolucion DECIMAL(10, 2) DEFAULT 0
        COMMENT 'Tarifa por devolución'
        AFTER tarifa_entrega
    """, "Agregar tarifa_devolucion")

    # Migrar datos
    ejecutar_sql(cursor, """
        UPDATE orden_personal
        SET tarifa_entrega = COALESCE(tarifa_unitaria, 0),
            tarifa_devolucion = COALESCE(tarifa_unitaria, 0)
        WHERE tarifa_unitaria IS NOT NULL
          AND tarifa_entrega = 0
    """, "Migrar datos de tarifa_unitaria")

    # Eliminar columna calculada
    ejecutar_sql(cursor, """
        ALTER TABLE orden_personal DROP COLUMN total_pagar
    """, "Eliminar columna total_pagar")

    # Eliminar columna antigua
    ejecutar_sql(cursor, """
        ALTER TABLE orden_personal DROP COLUMN tarifa_unitaria
    """, "Eliminar columna tarifa_unitaria")

    # Recrear columna calculada
    ejecutar_sql(cursor, """
        ALTER TABLE orden_personal
        ADD COLUMN total_pagar DECIMAL(10, 2) GENERATED ALWAYS AS (
            (COALESCE(cantidad_entregada, 0) * COALESCE(tarifa_entrega, 0)) +
            (COALESCE(cantidad_devolucion, 0) * COALESCE(tarifa_devolucion, 0))
        ) STORED COMMENT 'Total calculado automáticamente'
    """, "Recrear total_pagar con nueva fórmula")

    conn.commit()
    print()

    # =====================================================
    # VERIFICACIÓN
    # =====================================================
    print("=" * 60)
    print("VERIFICACIÓN FINAL")
    print("=" * 60)

    cursor.execute("""
        SELECT COLUMN_NAME, COLUMN_TYPE
        FROM INFORMATION_SCHEMA.COLUMNS
        WHERE TABLE_SCHEMA = 'logistica'
          AND TABLE_NAME = 'precios_cliente'
          AND COLUMN_NAME LIKE '%mensajero%'
    """)
    print("\nColumnas de precios_cliente:")
    for row in cursor.fetchall():
        print(f"  ✓ {row[0]}: {row[1]}")

    cursor.execute("""
        SELECT COLUMN_NAME, COLUMN_TYPE
        FROM INFORMATION_SCHEMA.COLUMNS
        WHERE TABLE_SCHEMA = 'logistica'
          AND TABLE_NAME = 'personal_ciudades'
          AND COLUMN_NAME = 'tipo_servicio'
    """)
    print("\nColumnas de personal_ciudades:")
    for row in cursor.fetchall():
        print(f"  ✓ {row[0]}: {row[1]}")

    cursor.execute("""
        SELECT COLUMN_NAME, COLUMN_TYPE
        FROM INFORMATION_SCHEMA.COLUMNS
        WHERE TABLE_SCHEMA = 'logistica'
          AND TABLE_NAME = 'orden_personal'
          AND COLUMN_NAME LIKE '%tarifa%'
    """)
    print("\nColumnas de orden_personal:")
    for row in cursor.fetchall():
        print(f"  ✓ {row[0]}: {row[1]}")

    cursor.close()
    conn.close()

    print()
    print("=" * 60)
    print("✅ MIGRACIÓN COMPLETADA EXITOSAMENTE")
    print("=" * 60)
    print()
    print("Ahora puedes ejecutar la aplicación Streamlit:")
    print("  streamlit run home_logistica.py")

if __name__ == "__main__":
    main()
