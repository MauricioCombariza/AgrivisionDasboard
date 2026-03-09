from datetime import datetime
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt

df = pd.read_csv('basesHisto.csv', low_memory=False)
dfC = df.copy()
df_entidad = pd.read_excel('./JupyterNotebook/entidad.xlsx')
df_merge = dfC.merge(df_entidad, on='no_entidad', how='left')

codigoEntidad = int(input("Escribe cuel es el codigo de la entidad que quieres filtrar? "))
filter_entidad = df_merge['cod_entidad'] == codigoEntidad

df_filter_entidad = df_merge[filter_entidad]
df_filter_entidad['ones'] = 1
df_filter_entidad = df_filter_entidad[['orden', 'retorno', 'ret_esc', 'ones']]
df_filter_entidad['estado'] = np.where(df_filter_entidad['ret_esc'] == 'E', 'entrega', 'pendiente')
pivot_table = pd.pivot_table(df_filter_entidad, 
                             index='orden',      # Columna que queremos como filas en la tabla pivote
                             columns='estado',   # Columna que queremos como columnas en la tabla pivote
                             values='ones',      # Columna que queremos sumar
                             aggfunc='sum',      # Función de agregación (suma de los valores en 'ones')
                             fill_value=0)

# Verificar si el número de órdenes es mayor a 10
if len(pivot_table) > 10:
    # Mostrar solo las últimas 10 órdenes
    pivot_table = pivot_table.tail(10)

# Crear el gráfico de barras con Matplotlib
fig, ax = plt.subplots()
pivot_table.plot(kind='bar', stacked=True, ax=ax)

# Establecer título y etiquetas del eje x e y
ax.set_title('Estado de las ordenes por cliente')
ax.set_xlabel('Orden')
ax.set_ylabel('Total envíos')

# Cambiar la orientación de las etiquetas del eje x a horizontal
plt.xticks(rotation=0)

# Mostrar el gráfico
plt.show()