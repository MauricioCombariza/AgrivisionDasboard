import pandas as pd
import numpy as np

def insertar_punto_por_sector(df_ruta):
    """
    Para cada sector en df_ruta, toma el punto con número de 'orden' máximo, 
    calcula cuál es el punto (entre el resto) cuya coordenada es la más cercana,
    inserta el punto removido luego de ese punto y reajusta el 'orden' secuencialmente.
    """
    df_resultados = []  # Aquí se almacenarán los dataframes por sector ya ajustados
    
    # Itera por cada sector (asumiendo que la columna 'Sector' existe)
    for sector in df_ruta['Sector'].unique():
        # Extrae el subconjunto del sector actual y crea una copia para trabajar sin modificar el original
        df_sector = df_ruta[df_ruta['Sector'] == sector].copy()
        
        # Ordena el dataframe por 'orden' (por si no se encuentra ordenado)
        df_sector.sort_values('orden', inplace=True)
        
        # Toma la fila con orden máximo (el último de la secuencia)
        idx_max = df_sector['orden'].idxmax()
        fila_max = df_sector.loc[idx_max]
        
        # Elimina la fila extraída para poder comparar con el resto
        df_sector_temp = df_sector.drop(idx_max).copy()
        
        # Verifica que haya al menos un punto para calcular la distancia
        if df_sector_temp.empty:
            # Si no hay ningún otro punto, se conserva como está
            df_resultados.append(df_sector)
            continue

        # Calcula la distancia euclidiana entre la fila_max y las demás filas
        # Suponiendo que las coordenadas son las columnas 'Calle' y 'Carrera'
        distancias = np.sqrt((df_sector_temp['Calle'] - fila_max['Calle'])**2 +
                             (df_sector_temp['Carrera'] - fila_max['Carrera'])**2)
        # Obtén el índice (del df original) de la fila más cercana
        idx_cercano = distancias.idxmin()
        
        # Reordena el dataframe temporal por 'orden' y resetea el índice
        # Usando drop=False para conservar el índice original en una columna llamada 'index'
        df_sector_temp.sort_values('orden', inplace=True)
        df_sector_temp.reset_index(drop=False, inplace=True)
        
        # Busca la posición de la fila cuyo índice original ('index') coincide con idx_cercano
        matching_rows = df_sector_temp[df_sector_temp['index'] == idx_cercano]
        if matching_rows.empty:
            # En caso de no encontrarla, se omite este sector o se toma otra acción
            df_resultados.append(df_sector)
            continue
        posicion_cercano = matching_rows.index[0]
        
        # Se genera el nuevo DataFrame insertando la fila_max justo después de la posición encontrada
        # Antes de concatenar, se elimina la columna 'index' para evitar confusiones posteriores
        df_sector_temp = df_sector_temp.drop(columns='index')
        df_insercion = pd.concat([
            df_sector_temp.iloc[:posicion_cercano + 1],
            pd.DataFrame([fila_max]),
            df_sector_temp.iloc[posicion_cercano + 1:]
        ], ignore_index=True)
        
        # Se reasigna el número de 'orden' de 1 a n para reflejar la nueva secuencia
        df_insercion['orden'] = np.arange(1, len(df_insercion) + 1)
        # Se asegura que la columna 'Sector' esté presente
        df_insercion['Sector'] = sector
        
        # Se añade el dataframe ajustado al listado de resultados
        df_resultados.append(df_insercion)
    
    # Combina los dataframes de cada sector en uno solo
    df_final = pd.concat(df_resultados, ignore_index=True)
    return df_final


