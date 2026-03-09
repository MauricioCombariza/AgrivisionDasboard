#!/usr/bin/env python3
"""
Script para inicializar la base de datos de gestión logística
Ejecuta el schema SQL y crea las tablas necesarias
"""

import mysql.connector
from mysql.connector import Error
import os
from dotenv import load_dotenv

load_dotenv()
import sys

def conectar_mysql(host=None, user=None, password=None):
    host = host or os.environ.get('DB_HOST', 'localhost')
    user = user or os.environ.get('DB_USER', 'root')
    password = password if password is not None else os.environ.get('DB_PASSWORD', '')
    """Conecta a MySQL sin especificar base de datos"""
    try:
        connection = mysql.connector.connect(
            host=host,
            user=user,
            password=password
        )
        if connection.is_connected():
            return connection
    except Error as e:
        print(f"❌ Error al conectar a MySQL: {e}")
        return None

def ejecutar_schema(connection, schema_file):
    """Ejecuta el archivo SQL para crear la base de datos"""
    try:
        cursor = connection.cursor()

        # Leer el archivo SQL
        with open(schema_file, 'r', encoding='utf-8') as f:
            sql_script = f.read()

        # Dividir por comandos (separados por ;)
        # Eliminar comentarios y líneas vacías
        commands = []
        current_command = []

        for line in sql_script.split('\n'):
            # Ignorar comentarios
            if line.strip().startswith('--') or line.strip() == '':
                continue

            current_command.append(line)

            # Si termina con ;, es el final del comando
            if line.strip().endswith(';'):
                command = '\n'.join(current_command)
                commands.append(command)
                current_command = []

        # Ejecutar cada comando
        print(f"\n🔄 Ejecutando {len(commands)} comandos SQL...\n")

        for i, command in enumerate(commands, 1):
            try:
                # Limpiar comando
                cmd = command.strip()
                if not cmd or cmd == ';':
                    continue

                cursor.execute(cmd)

                # Mostrar progreso
                if 'CREATE DATABASE' in cmd:
                    print("✅ Base de datos 'logistica' creada")
                elif 'CREATE TABLE' in cmd:
                    table_name = cmd.split('CREATE TABLE')[1].split('(')[0].strip()
                    print(f"✅ Tabla '{table_name}' creada")
                elif 'INSERT INTO' in cmd:
                    table_name = cmd.split('INSERT INTO')[1].split('(')[0].strip()
                    print(f"✅ Datos iniciales en '{table_name}' insertados")
                elif 'CREATE VIEW' in cmd:
                    view_name = cmd.split('CREATE VIEW')[1].split('AS')[0].strip()
                    print(f"✅ Vista '{view_name}' creada")

            except Error as e:
                # Ignorar si la base de datos ya existe
                if 'already exists' in str(e).lower() or 'duplicate' in str(e).lower():
                    continue
                print(f"⚠️ Error en comando {i}: {e}")
                print(f"   Comando: {cmd[:100]}...")

        connection.commit()
        cursor.close()
        return True

    except Error as e:
        print(f"❌ Error ejecutando schema: {e}")
        return False
    except FileNotFoundError:
        print(f"❌ No se encontró el archivo: {schema_file}")
        return False

def verificar_tablas(connection):
    """Verifica que las tablas se hayan creado correctamente"""
    try:
        cursor = connection.cursor()
        cursor.execute("USE logistica")

        cursor.execute("SHOW TABLES")
        tables = cursor.fetchall()

        print(f"\n📊 Tablas creadas ({len(tables)}):")
        for table in tables:
            cursor.execute(f"SELECT COUNT(*) FROM {table[0]}")
            count = cursor.fetchone()[0]
            print(f"   • {table[0]}: {count} registros")

        cursor.close()
        return True

    except Error as e:
        print(f"❌ Error verificando tablas: {e}")
        return False

def main():
    print("=" * 60)
    print("INICIALIZACIÓN DE BASE DE DATOS - SISTEMA LOGÍSTICA")
    print("=" * 60)

    # Ruta al archivo schema
    script_dir = os.path.dirname(os.path.abspath(__file__))
    schema_file = os.path.join(script_dir, 'db_logistica_schema.sql')

    if not os.path.exists(schema_file):
        print(f"\n❌ No se encuentra el archivo: {schema_file}")
        print("   Asegúrate de que db_logistica_schema.sql esté en el mismo directorio")
        sys.exit(1)

    # Conectar a MySQL
    print("\n🔌 Conectando a MySQL...")
    connection = conectar_mysql()

    if not connection:
        print("\n❌ No se pudo conectar a MySQL")
        print("   Verifica:")
        print("   1. MySQL está corriendo")
        print("   2. Usuario: root")
        print("   3. Password: (ver .env -> DB_PASSWORD)")
        sys.exit(1)

    print("✅ Conectado a MySQL exitosamente")

    # Ejecutar schema
    print(f"\n📄 Leyendo archivo: {os.path.basename(schema_file)}")

    if ejecutar_schema(connection, schema_file):
        print("\n✅ Schema ejecutado exitosamente")

        # Verificar tablas
        if verificar_tablas(connection):
            print("\n" + "=" * 60)
            print("✅ BASE DE DATOS INICIALIZADA CORRECTAMENTE")
            print("=" * 60)
            print("\n📝 Credenciales por defecto:")
            print("   Usuario: admin")
            print("   Password: admin123")
            print("\n💡 Accede al sistema Streamlit para comenzar a usar")
            print("=" * 60)
        else:
            print("\n⚠️ Hubo problemas al verificar las tablas")

    else:
        print("\n❌ Error al ejecutar el schema")
        sys.exit(1)

    # Cerrar conexión
    if connection.is_connected():
        connection.close()
        print("\n🔌 Conexión cerrada")

if __name__ == "__main__":
    main()
