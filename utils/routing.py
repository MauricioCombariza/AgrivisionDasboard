import pandas as pd
import numpy as np
from typing import Dict, List

def nearest_neighbor_route(df: pd.DataFrame, sector_column: str) -> Dict[str, List[int]]:
    """
    Calcula la ruta de vecino más cercano para cada sector en el DataFrame.

    Args:
        df (pd.DataFrame): DataFrame con puntos (direcciones) e información de sector.
        sector_column (str): Nombre de la columna que contiene la información del sector.

    Returns:
        Dict[str, List[int]]: Diccionario donde las claves son nombres de sectores y los valores
                              son listas de números de serie que representan la ruta para ese sector.
    """
    routes_by_sector = {}
    sectors = df[sector_column].unique()

    for sector in sectors:
        sector_df = df[df[sector_column] == sector].copy()
        if sector_df.empty:
            routes_by_sector[sector] = []
            continue

        # Usar 'serial' como identificador de punto. Crear una lista de tuplas (serial, x, y)
        points = [(row['serial'], float(row['Calle']), float(row['Carrera'])) 
                  for _, row in sector_df.iterrows()]
        
        # Iniciar desde el primer punto en el sector
        start_point_index = 0
        n = len(points)
        visited = [False] * n
        route_serials = []
        current_point_index = start_point_index

        # Añadir el número de serie del punto inicial
        route_serials.append(points[current_point_index][0])
        visited[current_point_index] = True

        # Algoritmo de vecino más cercano
        for _ in range(n - 1):
            next_point_index = None
            min_dist = float('inf')

            for j in range(n):
                if not visited[j]:
                    # Calcular distancia usando 'Calle' y 'Carrera'
                    dist = np.linalg.norm(
                        np.array([points[current_point_index][1], points[current_point_index][2]]) -
                        np.array([points[j][1], points[j][2]])
                    )
                    if dist < min_dist:
                        min_dist = dist
                        next_point_index = j

            if next_point_index is None:
                break  # No hay puntos no visitados

            route_serials.append(points[next_point_index][0])
            visited[next_point_index] = True
            current_point_index = next_point_index

        routes_by_sector[sector] = route_serials

    return routes_by_sector

def get_ordered_points_by_sector(df: pd.DataFrame) -> pd.DataFrame:
    """
    Ordena los puntos en un DataFrame de acuerdo con la ruta calculada.
    
    Args:
        df (pd.DataFrame): DataFrame con puntos y sus sectores.
        
    Returns:
        pd.DataFrame: DataFrame con puntos ordenados según la ruta.
    """
    if 'Sector' not in df.columns:
        return df
        
    # Calcular rutas
    routes = nearest_neighbor_route(df, 'Sector')
    
    # Agregar columna con el orden en la ruta
    df_result = df.copy()
    df_result['orden'] = 0
    
    for sector, route in routes.items():
        for i, serial in enumerate(route):
            mask = (df_result['serial'] == serial) & (df_result['Sector'] == sector)
            df_result.loc[mask, 'orden'] = i + 1  # Empezar desde 1
            
    return df_result
