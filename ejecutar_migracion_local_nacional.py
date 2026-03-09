#!/usr/bin/env python3
"""
Script para ejecutar migración de ordenes a formato local/nacional
"""

import mysql.connector
import os
from dotenv import load_dotenv

load_dotenv()
import sys

# Colores para output
class Color:
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    BLUE = '\033[94m'
    END = '\033[0m'

def print_color(color, message):
    print(f"{color}{message}{Color.END}")

def ejecutar_migracion():
    try:
        # Conectar a la base de datos
        print_color(Color.BLUE, "=" * 70)
        print_color(Color.BLUE, " Migración: Ordenes Local/Nacional")
        print_color(Color.BLUE, "=" * 70)
        print()

        conn = mysql.connector.connect(
            host=os.environ.get("DB_HOST", "localhost"),
            user=os.environ.get("DB_USER", "root"),
            password=os.environ.get("DB_PASSWORD", ""),
            database="logistica"
        )
        cursor = conn.cursor()

        print_color(Color.GREEN, "✓ Conexión establecida")
        print()

        # Leer archivo SQL
        with open('migracion_ordenes_local_nacional.sql', 'r', encoding='utf-8') as f:
            sql_content = f.read()

        # Separar en statements individuales
        statements = []
        current_statement = ""

        for line in sql_content.split('\n'):
            # Ignorar comentarios
            if line.strip().startswith('--') or not line.strip():
                continue

            current_statement += line + "\n"

            # Si termina en ;, es un statement completo
            if line.strip().endswith(';'):
                statements.append(current_statement)
                current_statement = ""

        print_color(Color.YELLOW, f"Se encontraron {len(statements)} operaciones SQL")
        print()

        # Ejecutar cada statement
        for i, statement in enumerate(statements, 1):
            statement = statement.strip()
            if not statement:
                continue

            # Extraer tipo de operación
            operation_type = statement.split()[0].upper()

            try:
                print(f"[{i}/{len(statements)}] Ejecutando: {operation_type}...", end=" ")

                cursor.execute(statement)

                if operation_type in ('SELECT', 'DESCRIBE'):
                    results = cursor.fetchall()
                    print_color(Color.GREEN, "✓")
                    if results:
                        for row in results:
                            print(f"    {row}")
                else:
                    conn.commit()
                    print_color(Color.GREEN, "✓")

            except mysql.connector.Error as e:
                # Algunos errores son esperados (ej: columna ya existe)
                if "Duplicate column name" in str(e):
                    print_color(Color.YELLOW, f"⚠ (columna ya existe - OK)")
                elif "Can't DROP" in str(e):
                    print_color(Color.YELLOW, f"⚠ (índice no existe - OK)")
                else:
                    print_color(Color.RED, f"✗")
                    print_color(Color.RED, f"    Error: {e}")
                    raise

        print()
        print_color(Color.GREEN, "=" * 70)
        print_color(Color.GREEN, " Migración completada exitosamente")
        print_color(Color.GREEN, "=" * 70)
        print()

        # Verificar estructura final
        print_color(Color.BLUE, "Verificando estructura final de tabla ordenes:")
        print()

        cursor.execute("DESCRIBE ordenes")
        columns = cursor.fetchall()

        print_color(Color.YELLOW, "Nuevas columnas agregadas:")
        for col in columns:
            if 'local' in col[0] or 'nacional' in col[0]:
                print(f"  ✓ {col[0]:30s} {col[1]:20s}")

        print()
        print_color(Color.GREEN, "✓ Migración finalizada correctamente")
        print()
        print_color(Color.BLUE, "IMPORTANTE:")
        print("  - Actualizar Procesador_Ordenes.py para generar nuevo formato CSV")
        print("  - Actualizar 3_Ordenes.py para leer nuevo formato CSV")
        print("  - Formato nuevo: orden,fecha_recepcion,nombre_cliente,tipo_servicio,cantidad_local,cantidad_nacional")

        cursor.close()
        conn.close()

    except FileNotFoundError:
        print_color(Color.RED, "✗ Error: No se encontró el archivo migracion_ordenes_local_nacional.sql")
        print_color(Color.YELLOW, "  Asegúrate de ejecutar este script desde el directorio dashboard/")
        sys.exit(1)

    except mysql.connector.Error as e:
        print_color(Color.RED, f"\n✗ Error de MySQL: {e}")
        sys.exit(1)

    except Exception as e:
        print_color(Color.RED, f"\n✗ Error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    ejecutar_migracion()
