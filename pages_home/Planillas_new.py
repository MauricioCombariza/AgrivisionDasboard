# pages/Planillas.py
import streamlit as st
import pandas as pd
# from utils.sectorization_new import process_addresses

def planillas_page():
    st.title("Procesamiento de Planillas")

    # Subir el archivo Excel
    uploaded_file = st.file_uploader("Sube el archivo de planillas (.xlsx)", type="xlsx")

    if uploaded_file is not None:
        # Leer el archivo y crear un DataFrame
        df = pd.read_excel(uploaded_file)
        st.write("Datos originales:")
        st.dataframe(df)

        # Asumimos que la columna de direcciones se llama 'direccion'
        # Si no, ajusta el nombre de la columna aquí
        if 'direccion' in df.columns:
            # Procesar las direcciones para asignar el sector
            # df_processed = process_addresses(df.copy())

            st.write("Datos con sectorización:")
            # st.dataframe(df_processed[['serial', 'direccion', 'sector']])

            # Opción para descargar el archivo procesado
            # csv_data = df_processed.to_csv(index=False).encode('utf-8')
            st.download_button(
                label="Descargar archivo sectorizado",
                # data=csv_data,
                file_name="planillas_sectorizadas.csv",
                mime="text/csv"
            )
        else:
            st.error("El archivo no contiene una columna llamada 'direccion'.")

# Si este script se ejecuta directamente
if __name__ == "__main__":
    planillas_page()