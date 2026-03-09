import pandas as pd
import numpy as np
import mysql.connector
import streamlit as st  # Importa streamlit para mostrar errores
import os
from dotenv import load_dotenv

load_dotenv()

def conectar_bd():
    try:
        mydb = mysql.connector.connect(
            host=os.environ.get("DB_HOST", "localhost"),
            user=os.environ.get("DB_USER", "root"),
            password=os.environ.get("DB_PASSWORD", ""),
            database=os.environ.get("DB_NAME_IMILE", "imile")
        )
        return mydb
    except mysql.connector.Error as err:
        st.error(f"Error al conectar a la base de datos en zonificador: {err}")
        return None

def zonificador() -> pd.DataFrame:
    mydb = conectar_bd()
    if mydb is None:
        return pd.DataFrame()  # Retorna un DataFrame vacío si no hay conexión

    mycursor = mydb.cursor()
    query = "SELECT serial, nombre, telefono, direccion FROM paquetes"
    mycursor.execute(query)
    resultados = mycursor.fetchall()
    mycursor.close()
    mydb.close()

    df = pd.DataFrame(resultados, columns=['Serial', 'Nombre', 'Telefono', 'direccion'])
    df['dirajustada'] = df['direccion'].str.lower().str.replace(r'\s+', ' ', regex=True).str.strip()
    df['dirajustada'] = (df['dirajustada'].str.replace(r'#', ' ', regex=True)
                      .str.replace(r'\b(no|n|No)\b', ' ', regex=True)
                      .str.replace(r'[-_]', ' ', regex=True)
                      .str.replace(r'[.]', ' ', regex=True)
                      .str.replace(r'\b(kra|cra|carrera|carera|kr|cr|Carrera|av cra|avenida carrera|ave carrera)\b', 'cra', regex=True)
                      .str.replace(r'\b(calle|cale|kalle|avenida calle|av calle|av cl|clle|cll|ave calle)\b', 'cl', regex=True)
                      .str.replace(r'\b(diagonal|diag)\b', 'dg', regex=True)
                      .str.replace(r'\b(avenida caracas|av caracas)\b', 'cra 14', regex=True)
                      .str.replace(r'\b(transversal|trans|transv)\b', 'tv', regex=True)
                      .str.replace(r'([a-zA-Z]+)(\d+)', r'\1 \2', regex=True)
                      .str.replace(r'(\d+)([a-zA-Z]+)', r'\1 \2', regex=True)
                      .str.replace(r'(\d+)\s+bis\s+([a-zA-Z]+)', r'\1bis\2', regex=True)
                      .str.replace(r'([a-zA-Z]+)\s+bis\s+([a-zA-Z]+)', r'\1bis\2', regex=True)
                      .str.replace(r'([a-zA-Z]+)\s+bis', r'\1bis', regex=True)
                      .str.replace(r'bis\s+([a-zA-Z]+)', r'bis\1', regex=True)
                      .str.strip())
    df[['tipo_calle', 'num1', 'letras', 'num2', 'letras2', 'placa']] = df['dirajustada'].str.extract(
        r'^([a-zA-Z]+)\s+(\d+)(?:\s+([a-zA-Z]+))?\s+(\d+)(?:\s+([a-zA-Z]+))?\s+(\d+)(?:\s+.*)?$',
        expand=True
    )
    df['Calle'] = np.where(df['tipo_calle'].str.lower().isin(['cl', 'calle', 'clle', 'dg', 'av  cl']) , df['num1'],
                          np.where(df['tipo_calle'].str.lower().isin(['cra', 'carrera', 'tv', 'av  cra']), df['num2'], np.nan))
    df['letras_cl'] = np.where(df['tipo_calle'].str.lower().isin(['cl', 'calle', 'clle', 'dg', 'av  cl']) , df['letras'],
                              np.where(df['tipo_calle'].str.lower().isin(['cra', 'carrera', 'tv', 'av  cra']), df['letras2'], np.nan))
    df['letras_cr'] = np.where(df['tipo_calle'].str.lower().isin(['cl', 'calle', 'clle', 'dg', 'av  cl']) , df['letras2'],
                              np.where(df['tipo_calle'].str.lower().isin(['cra', 'carrera', 'tv', 'av  cra']), df['letras'], np.nan))
    df['Carrera'] = np.where(df['tipo_calle'].str.lower().isin(['cl', 'calle', 'clle', 'dg', 'av  cl']) , df['num2'],
                            np.where(df['tipo_calle'].str.lower().isin(['cra', 'carrera', 'tv', 'av  cra']), df['num1'], np.nan))
    df = df[['Serial','Nombre','Telefono','direccion', 'dirajustada', 'tipo_calle', 'Calle', 'letras_cl', 'Carrera', 'letras_cr', 'placa']]
    return df