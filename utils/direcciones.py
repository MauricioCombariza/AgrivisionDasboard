import pandas as pd
import numpy as np
import re

def normalizar_direccion(direccion):
    """
    Normaliza una dirección para el procesamiento posterior.
    
    Args:
        direccion (str): Dirección original.
        
    Returns:
        str: Dirección normalizada.
    """
    if pd.isna(direccion):
        return ""
    
    dir_norm = direccion.lower().replace(r'\s+', ' ', regex=True).strip()
    dir_norm = (dir_norm.replace('#', ' ')
                .replace(r'\b(no|n|No)\b', ' ', regex=True)
                .replace(r'[-_]', ' ', regex=True)
                .replace(r'[.]', ' ', regex=True)
                .replace(r'\b(kra|cra|carrera|carera|kr|cr|Carrera|av cra|avenida carrera|ave carrera)\b', 'cra', regex=True)
                .replace(r'\b(calle|cale|kalle|avenida calle|av calle|av cl|clle|cll|ave calle)\b', 'cl', regex=True)
                .replace(r'\b(diagonal|diag)\b', 'dg', regex=True)
                .replace(r'\b(avenida caracas|av caracas)\b', 'cra 14', regex=True)
                .replace(r'\b(transversal|trans|transv)\b', 'tv', regex=True)
                .replace(r'([a-zA-Z]+)(\d+)', r'\1 \2', regex=True)
                .replace(r'(\d+)([a-zA-Z]+)', r'\1 \2', regex=True)
                .replace(r'(\d+)\s+bis\s+([a-zA-Z]+)', r'\1bis\2', regex=True)
                .replace(r'([a-zA-Z]+)\s+bis\s+([a-zA-Z]+)', r'\1bis\2', regex=True)
                .replace(r'([a-zA-Z]+)\s+bis', r'\1bis', regex=True)
                .replace(r'bis\s+([a-zA-Z]+)', r'bis\1', regex=True)
                .strip())
    
    return dir_norm
    
def extraer_componentes_direccion(df):
    """
    Extrae los componentes de las direcciones en un DataFrame.
    
    Args:
        df (pandas.DataFrame): DataFrame con direcciones.
        
    Returns:
        pandas.DataFrame: DataFrame con componentes extraídos.
    """
    # Crear una copia del DataFrame para no modificar el original
    df_proc = df.copy()
    
    # Normalizar direcciones
    df_proc['dirajustada'] = df_proc['direccion'].apply(normalizar_direccion)
    
    # Extraer componentes con regex
    pattern = r'^([a-zA-Z]+)\s+(\d+)(?:\s+([a-zA-Z]+))?\s+(\d+)(?:\s+([a-zA-Z]+))?\s+(\d+)(?:\s+.*)?$'
    components = df_proc['dirajustada'].str.extract(pattern, expand=True)
    
    if not components.empty:
        df_proc[['tipo_calle', 'num1', 'letras', 'num2', 'letras2', 'placa']] = components
    
    # Determinar calles y carreras
    df_proc['Calle'] = np.where(
        df_proc['tipo_calle'].str.lower().isin(['cl', 'calle', 'clle', 'dg', 'av cl']), 
        df_proc['num1'],
        np.where(
            df_proc['tipo_calle'].str.lower().isin(['cra', 'carrera', 'tv', 'av cra']), 
            df_proc['num2'], 
            np.nan
        )
    )
    
    df_proc['letras_cl'] = np.where(
        df_proc['tipo_calle'].str.lower().isin(['cl', 'calle', 'clle', 'dg', 'av cl']), 
        df_proc['letras'],
        np.where(
            df_proc['tipo_calle'].str.lower().isin(['cra', 'carrera', 'tv', 'av cra']), 
            df_proc['letras2'], 
            np.nan
        )
    )
    
    df_proc['letras_cr'] = np.where(
        df_proc['tipo_calle'].str.lower().isin(['cl', 'calle', 'clle', 'dg', 'av cl']), 
        df_proc['letras2'],
        np.where(
            df_proc['tipo_calle'].str.lower().isin(['cra', 'carrera', 'tv', 'av cra']), 
            df_proc['letras'], 
            np.nan
        )
    )
    
    df_proc['Carrera'] = np.where(
        df_proc['tipo_calle'].str.lower().isin(['cl', 'calle', 'clle', 'dg', 'av cl']), 
        df_proc['num2'],
        np.where(
            df_proc['tipo_calle'].str.lower().isin(['cra', 'carrera', 'tv', 'av cra']), 
            df_proc['num1'], 
            np.nan
        )
    )
    
    # Convertir las columnas numéricas
    for col in ['Calle', 'Carrera']:
        df_proc[col] = pd.to_numeric(df_proc[col], errors='coerce')
    
    return df_proc
