import pandas as pd
import io

def to_csv(df: pd.DataFrame) -> bytes:
    """
    Convierte un DataFrame a formato CSV.
    
    Args:
        df (pd.DataFrame): DataFrame a convertir.
        
    Returns:
        bytes: Contenido del CSV.
    """
    return df.to_csv(index=False).encode('utf-8')

def to_excel(df: pd.DataFrame) -> bytes:
    """
    Convierte un DataFrame a formato Excel.
    
    Args:
        df (pd.DataFrame): DataFrame a convertir.
        
    Returns:
        bytes: Contenido del Excel.
    """
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        df.to_excel(writer, index=False, sheet_name='Hoja1')
    return output.getvalue()
