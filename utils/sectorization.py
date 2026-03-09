import pandas as pd
import numpy as np
import os
import streamlit as st
from typing import Tuple

from utils.db_connection import actualizar_sector_ruta
from utils.direcciones import extraer_componentes_direccion
from utils.routing import nearest_neighbor_route

def cargar_reglas_sectorizacion():
    """
    Carga las reglas de sectorización desde el archivo CSV.
    
    Returns:
        pandas.DataFrame: DataFrame con las reglas de sectorización o None si hay error.
    """
    try:
        df_sec = pd.read_csv("sectores.csv", encoding="latin1", sep=";", header=0)
        return df_sec
    except FileNotFoundError:
        st.error("El archivo 'sectores.csv' no se encontró.")
        return None
    except Exception as e:
        st.error(f"Error al cargar el archivo de sectores: {e}")
        return None

def asignar_sectores(df: pd.DataFrame) -> pd.DataFrame:
    """
    Asigna sectores a las direcciones en el DataFrame.
    
    Args:
        df (pd.DataFrame): DataFrame con direcciones procesadas.
        
    Returns:
        pd.DataFrame: DataFrame con sectores asignados.
    """
    # Crear una copia del DataFrame para no modificar el original
    df_proc = df.copy()
    
    # Cargar reglas de sectorización
    df_sec = cargar_reglas_sectorizacion()
    if df_sec is None:
        return df_proc
    
    # Asignar sectores por defecto
    df_proc['Sector'] = 'Fuera de sector'
    
    # Asignar sectores según las reglas
    for _, row in df_sec.iterrows():
        mask = (
            (df_proc['Calle'].astype(float) >= row['Calle_min']) &
            (df_proc['Calle'].astype(float) <= row['Calle_max']) &
            (df_proc['Carrera'].astype(float) >= row['Carrera_min']) &
            (df_proc['Carrera'].astype(float) <= row['Carrera_max'])
        )
        df_proc.loc[mask, 'Sector'] = row['Sector']
    
    return df_proc

def calcular_ruta(df: pd.DataFrame) -> pd.DataFrame:
    """
    Calcula la ruta para cada sector en el DataFrame.
    
    Args:
        df (pd.DataFrame): DataFrame con sectores asignados.
        
    Returns:
        pd.DataFrame: DataFrame con rutas calculadas.
    """
    # Crear una copia del DataFrame para no modificar el original
    df_proc = df.copy()
    
    # Calcular la ruta solo para los registros con sector asignado
    sectores_asignados = df_proc[df_proc['Sector'] != 'Fuera de sector']['Sector'].unique()
    
    if len(sectores_asignados) > 0:
        ruta_por_sector = nearest_neighbor_route(df_proc, 'Sector')
        
        # Asignar el número de serie a la columna 'Ruta'
        for serial, row in df_proc.iterrows():
            sector = row['Sector']
            if sector != 'Fuera de sector' and sector in ruta_por_sector:
                rutas = ruta_por_sector[sector]
                if serial in rutas:
                    df_proc.at[serial, 'Ruta'] = rutas.index(serial) + 1
    else:
        df_proc['Ruta'] = None
    
    return df_proc

def sectorizar_inicial(df: pd.DataFrame) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """
    Realiza la sectorización inicial de las direcciones.
    
    Args:
        df (pd.DataFrame): DataFrame con direcciones.
        
    Returns:
        Tuple[pd.DataFrame, pd.DataFrame]: (DataFrame con sectores asignados, 
                                         DataFrame con direcciones sin sector)
    """
    # Extraer componentes de dirección
    df_proc = extraer_componentes_direccion(df)
    
    # Asignar sectores
    df_proc = asignar_sectores(df_proc)
    
    # Calcular ruta
    df_proc = calcular_ruta(df_proc)
    
    # Separar direcciones sin sector
    df_sin_sector = df_proc[df_proc['Sector'] == 'Fuera de sector'].copy()
    
    return df_proc, df_sin_sector

def actualizar_bd_con_sectores(df: pd.DataFrame) -> int:
    """
    Actualiza la base de datos con los sectores y rutas asignados.
    
    Args:
        df (pd.DataFrame): DataFrame con sectores y rutas.
        
    Returns:
        int: Número de registros actualizados correctamente.
    """
    registros_actualizados = 0
    
    for _, row in df.iterrows():
        serial = row['serial']
        sector = row['Sector'] if row['Sector'] != 'Fuera de sector' else None
        ruta = row['Ruta']
        
        if actualizar_sector_ruta(serial, sector, ruta):
            registros_actualizados += 1
    
    return registros_actualizados

def sectorizar_con_correcciones(df_original: pd.DataFrame, correcciones: dict) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """
    Realiza la sectorización con direcciones corregidas manualmente.
    
    Args:
        df_original (pd.DataFrame): DataFrame original con todas las direcciones.
        correcciones (dict): Diccionario con {serial: direccion_corregida}.
        
    Returns:
        Tuple[pd.DataFrame, pd.DataFrame]: (DataFrame completo con sectores actualizados,
                                         DataFrame con direcciones que siguen sin sector)
    """
    # Crear copia del DataFrame original para no modificarlo
    df_con_correcciones = df_original.copy()
    
    # Aplicar correcciones
    for serial, direccion_corregida in correcciones.items():
        mask = df_con_correcciones['serial'] == serial
        if mask.any():
            df_con_correcciones.loc[mask, 'direccion'] = direccion_corregida
    
    # Realizar sectorización con las correcciones
    df_actualizado, df_sin_sector = sectorizar_inicial(df_con_correcciones)
    
    return df_actualizado, df_sin_sector