import streamlit as st
import subprocess
import sys
import os



st.title("⬆️ Subir Devoluciones")

# Input del código
codigo = st.text_input("Ingresa el código de la devolución:")

if st.button("Procesar devolución"):
    if codigo.strip() == "":
        st.warning("⚠️ Debes ingresar un código.")
    else:
        # Llama a tu script con el argumento (igual que haces en n8n)
        python_exec = os.path.expanduser("~/venv_imile/bin/python")
        script_path = os.path.expanduser("~/devoluciones_app/captura_final_n8n.py")

        try:
            result = subprocess.run(
                [python_exec, script_path, codigo],
                capture_output=True,
                text=True,
                check=True
            )
            st.success("✅ Script ejecutado con éxito")
            st.text_area("Salida del script:", result.stdout, height=200)
        except subprocess.CalledProcessError as e:
            st.error("❌ Error al ejecutar el script")
            st.text_area("Error:", e.stderr, height=200)
