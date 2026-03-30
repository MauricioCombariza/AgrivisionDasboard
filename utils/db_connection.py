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
    "host": os.environ.get("DB_HOST_IMILE", "localhost"),
    "user": os.environ.get("DB_USER_IMILE", "root"),
    "password": os.environ.get("DB_PASSWORD_IMILE", ""),
    "database": os.environ.get("DB_NAME_IMILE", "imile")
}

DB_CONFIG_LOGISTICA = {
    "host": os.environ.get("DB_HOST", "localhost"),
    "user": os.environ.get("DB_USER", "root"),
    "password": os.environ.get("DB_PASSWORD", ""),
    "database": os.environ.get("DB_NAME_LOGISTICA", "logistica"),
    "connect_timeout": 10,
}

def get_connection(database="imile"):
    """
    Obtiene una conexión fresca a la base de datos MySQL.
    Usar para escrituras (INSERT/UPDATE/DELETE).
    Para lecturas repetidas, usar las funciones cached_* de este módulo.
    """
    config = DB_CONFIG_LOGISTICA if database == "logistica" else DB_CONFIG_IMILE
    try:
        conn = mysql.connector.connect(**config)
        return conn
    except mysql.connector.Error as err:
        st.error(f"Error al conectar a la base de datos {database}: {err}")
        return None


# ── Conexiones cacheadas por sesión (evitan reconectar en cada rerun) ──────────

@st.cache_resource(show_spinner=False)
def _pool_logistica():
    """Pool de conexiones para logistica. Una por proceso Streamlit."""
    return mysql.connector.connect(**DB_CONFIG_LOGISTICA)

@st.cache_resource(show_spinner=False)
def _pool_imile():
    """Pool de conexiones para imile. Una por proceso Streamlit."""
    return mysql.connector.connect(**DB_CONFIG_IMILE)

def get_cached_connection(database="logistica"):
    """
    Devuelve la conexión cacheada, reconectando si expiró.
    Usar solo para LECTURAS dentro de páginas con muchos reruns.
    Para escrituras, seguir usando get_connection() para conexiones frescas.
    """
    conn = _pool_logistica() if database == "logistica" else _pool_imile()
    try:
        conn.ping(reconnect=True, attempts=3, delay=0.5)
    except Exception:
        # Si ping falla, limpiar caché y crear nueva
        if database == "logistica":
            _pool_logistica.clear()
            conn = _pool_logistica()
        else:
            _pool_imile.clear()
            conn = _pool_imile()
    return conn


# ── Queries de lectura más frecuentes con caché ────────────────────────────────

@st.cache_data(ttl=300, show_spinner=False)
def cached_personal() -> pd.DataFrame:
    """Lista de personal activo. Refresca cada 5 min."""
    conn = get_connection("logistica")
    if not conn:
        return pd.DataFrame()
    try:
        df = pd.read_sql("SELECT id, nombre, codigo, cargo FROM personal WHERE activo = TRUE ORDER BY nombre", conn)
        return df
    finally:
        conn.close()

@st.cache_data(ttl=600, show_spinner=False)
def cached_clientes() -> pd.DataFrame:
    """Lista de clientes activos. Refresca cada 10 min."""
    conn = get_connection("logistica")
    if not conn:
        return pd.DataFrame()
    try:
        df = pd.read_sql("SELECT id, nombre_empresa FROM clientes WHERE activo = TRUE ORDER BY nombre_empresa", conn)
        return df
    finally:
        conn.close()

@st.cache_data(ttl=3600, show_spinner=False)
def cached_tarifas(tipo_servicio: str) -> float:
    """Tarifa vigente para un tipo de servicio. Refresca cada hora."""
    conn = get_connection("logistica")
    if not conn:
        return 0.0
    try:
        cursor = conn.cursor(dictionary=True)
        cursor.execute("""
            SELECT tarifa FROM tarifas_servicios
            WHERE tipo_servicio = %s AND activo = TRUE
            ORDER BY vigencia_desde DESC LIMIT 1
        """, (tipo_servicio,))
        row = cursor.fetchone()
        cursor.close()
        return float(row['tarifa']) if row else 0.0
    finally:
        conn.close()

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