import mysql.connector
from mysql.connector import pooling
import streamlit as st
import pandas as pd
from datetime import date
import os
from dotenv import load_dotenv

load_dotenv()

# Configuración de bases de datos
DB_CONFIG_IMILE = {
    "host": os.environ.get("DB_HOST", "localhost"),
    "user": os.environ.get("DB_USER", "root"),
    "password": os.environ.get("DB_PASSWORD", ""),
    "database": os.environ.get("DB_NAME_IMILE", "imile")
}

DB_CONFIG_LOGISTICA = {
    "host": os.environ.get("DB_HOST", "localhost"),
    "user": os.environ.get("DB_USER", "root"),
    "password": os.environ.get("DB_PASSWORD", ""),
    "database": os.environ.get("DB_NAME_LOGISTICA", "logistica")
}

def get_connection(database="imile"):
    """
    Obtiene una conexión fresca a la base de datos MySQL.
    NO usar con @st.cache_resource ya que las conexiones MySQL expiran.

    Args:
        database: "imile" o "logistica"

    Returns:
        mysql.connector.connection: Objeto de conexión a la base de datos o None si hay error.
    """
    config = DB_CONFIG_LOGISTICA if database == "logistica" else DB_CONFIG_IMILE
    try:
        conn = mysql.connector.connect(**config)
        return conn
    except mysql.connector.Error as err:
        st.error(f"Error al conectar a la base de datos {database}: {err}")
        return None

def conectar_bd():
    """
    Establece una conexión con la base de datos MySQL (imile).
    Mantiene compatibilidad con código existente.

    Returns:
        mysql.connector.connection: Objeto de conexión a la base de datos o None si hay error.
    """
    return get_connection("imile")

def conectar_logistica():
    """
    Establece una conexión con la base de datos logistica.

    Returns:
        mysql.connector.connection: Objeto de conexión a la base de datos o None si hay error.
    """
    return get_connection("logistica")

def obtener_paquetes():
    """
    Recupera todos los paquetes de la base de datos.
    
    Returns:
        pandas.DataFrame: DataFrame con los paquetes o DataFrame vacío si hay error.
    """
    mydb = conectar_bd()
    if mydb is None:
        return pd.DataFrame()
    
    try:
        query = "SELECT * FROM paquetes"
        df_paquetes = pd.read_sql_query(query, mydb)
        return df_paquetes
    except mysql.connector.Error as err:
        st.error(f"Error al obtener paquetes: {err}")
        return pd.DataFrame()
    finally:
        if mydb.is_connected():
            mydb.close()

def actualizar_sector_ruta(serial, sector, ruta):
    """
    Actualiza el sector y ruta de un paquete en la base de datos.
    
    Args:
        serial (str): Número de serie del paquete.
        sector (str): Sector asignado.
        ruta (str): Ruta asignada.
    
    Returns:
        bool: True si se actualizó correctamente, False en caso contrario.
    """
    mydb = conectar_bd()
    if mydb is None:
        return False
    
    try:
        mycursor = mydb.cursor()
        sql = "UPDATE paquetes SET sector = %s, ruta = %s WHERE serial = %s"
        val = (sector, ruta, serial)
        mycursor.execute(sql, val)
        mydb.commit()
        return True
    except mysql.connector.Error as err:
        st.error(f"Error al actualizar el registro con serial {serial}: {err}")
        return False
    finally:
        if mydb and mydb.is_connected():
            mycursor.close()
            mydb.close()

def insertar_paquetes(df, fecha_entrega):
    """
    Inserta nuevos paquetes o actualiza existentes en la base de datos.
    
    Args:
        df (pandas.DataFrame): DataFrame con los paquetes a insertar/actualizar.
        fecha_entrega (datetime.date): Fecha de entrega.
    
    Returns:
        tuple: (registros_procesados, registros_fallidos)
    """
    mydb = conectar_bd()
    if mydb is None:
        return (0, 0)
    
    registros_procesados = 0
    registros_fallidos = 0
    
    try:
        mycursor = mydb.cursor()
        
        # ⚠️ Clave del cambio: Uso de REPLACE INTO en lugar de INSERT INTO
        sql = """
        REPLACE INTO paquetes (serial, f_emi, nombre, telefono, direccion)
        VALUES (%s, %s, %s, %s, %s)
        """
        
        for index, row in df.iterrows():
            try:
                # Asegúrate de que los nombres de las columnas en tu Excel sean los correctos
                serial = row.get('Waybill number')
                nombre = row.get("Recipient's name")
                telefono = row.get('Customer phone')
                direccion = row.get('Address2')
                
                # Manejar el caso donde las columnas no existen o los datos son nulos
                if not serial or pd.isna(serial):
                    st.warning(f"Fila {index}: 'Waybill number' (serial) no válido. Omitiendo.")
                    registros_fallidos += 1
                    continue

                f_emi = fecha_entrega.strftime('%Y-%m-%d')
                
                val = (str(serial), f_emi, str(nombre), str(telefono), str(direccion))
                
                mycursor.execute(sql, val)
                mydb.commit()
                registros_procesados += 1
            except Exception as e:
                st.error(f"Error al procesar la fila {index} (serial: {serial}): {e}")
                registros_fallidos += 1
        
        return (registros_procesados, registros_fallidos)
    finally:
        if mydb.is_connected():
            mycursor.close()
            mydb.close()