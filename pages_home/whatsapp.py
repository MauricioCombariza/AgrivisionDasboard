# whatsapp.py
import streamlit as st
import os
import sys
from pathlib import Path
import urllib.parse

from dotenv import load_dotenv

load_dotenv(Path(__file__).parent.parent / ".env", override=True)

_ROOT = str(Path(__file__).parent.parent)
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from utils.db_connection import conectar_bd

st.title("Sistema de Notificación de Paquetes")


def buscar_paquete(serial: str):
    conn = conectar_bd()
    if not conn:
        return None
    try:
        cur = conn.cursor(dictionary=True)
        cur.execute("SELECT * FROM paquetes WHERE TRIM(serial) = %s", (serial.strip(),))
        return cur.fetchone()
    except Exception as e:
        st.error(f"Error al consultar la base de datos: {e}")
        return None
    finally:
        conn.close()


def marcar_whatsapp_enviado(serial: str):
    conn = conectar_bd()
    if not conn:
        return
    try:
        cur = conn.cursor()
        cur.execute("UPDATE paquetes SET whatsapp = 1 WHERE serial = %s", (serial,))
        conn.commit()
    except Exception as e:
        st.error(f"Error al actualizar el estado: {e}")
    finally:
        conn.close()


# Formulario
with st.form("formulario_codigo_barras"):
    codigo_barras = st.text_input("Ingrese el código de barras:")
    boton_enviar = st.form_submit_button("Fuera de zona")

if boton_enviar:
    if not codigo_barras:
        st.warning("Por favor, ingrese un código de barras.")
    else:
        serial_buscado = codigo_barras.strip()
        paquete = buscar_paquete(serial_buscado)

        if not paquete:
            st.error(f"No se encontró paquete con serial: **{serial_buscado}**")
        elif paquete.get("whatsapp") == 1:
            st.warning("Ya se envió un WhatsApp para este paquete.")
        else:
            nombre   = paquete.get("nombre", "Cliente")
            direccion = paquete.get("direccion", "dirección registrada")
            telefono  = paquete.get("telefono", "")
            serial    = paquete.get("serial", serial_buscado)

            if not telefono:
                st.error("El paquete no tiene número de teléfono registrado.")
            else:
                if not telefono.startswith("+"):
                    telefono = "+" + telefono

                mensaje = (
                    f"Hola {nombre}, le saludamos cordialmente. "
                    f"Notamos que en su envio con serial: '{serial}' su dirección registrada es '{direccion}' y queremos informarle "
                    "que somos la empresa encargada de enviar sus paquetes de Temu. "
                    "Hemos detectado que esta dirección no corresponde a la localidad de Barrios Unidos. "
                    "¿Podría por favor confirmarnos la dirección correcta? Gracias."
                )

                st.subheader("Mensaje generado:")
                st.text(mensaje)

                texto_enc = urllib.parse.quote(mensaje)
                url_whatsapp = f"https://api.whatsapp.com/send?phone={telefono}&text={texto_enc}"

                st.subheader("Abrir WhatsApp:")
                st.markdown(f"[📲 Enviar WhatsApp]({url_whatsapp})", unsafe_allow_html=True)
                st.code(url_whatsapp, language="text")

                if st.button("Marcar como enviado"):
                    marcar_whatsapp_enviado(serial)
                    st.success("Estado actualizado: whatsapp = 1")

# Sidebar
st.sidebar.header("Instrucciones")
st.sidebar.write("""
1. Ingrese el código de barras
2. Haga clic en 'Fuera de zona'
3. Verifique el mensaje y enlace generado
4. Haga clic en el enlace para enviar el mensaje por WhatsApp
5. Luego pulse 'Marcar como enviado' para actualizar el estado
""")
