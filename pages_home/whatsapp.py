# whatsapp.py
import streamlit as st
import os
from supabase import create_client
from dotenv import load_dotenv
import urllib.parse

# Cargar variables de entorno desde .env
load_dotenv()


st.title("Sistema de Notificación de Paquetes")

# Configuración de Supabase
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
if not SUPABASE_URL or not SUPABASE_KEY:
    st.error("Error: No se encontraron las credenciales de Supabase en .env")
    st.stop()

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

# Funciones de BD
def buscar_paquete(serial_number):
    resp = supabase.table("paquetes").select("*").eq("serial_number", serial_number).execute()
    return resp.data[0] if resp.data else None

def actualizar_estado_whatsapp(id_paquete):
    supabase.table("paquetes").update({"whatsapp": 1}).eq("id", id_paquete).execute()

# Formulario
with st.form("formulario_codigo_barras"):
    codigo_barras = st.text_input("Ingrese el código de barras:")
    boton_enviar = st.form_submit_button("Fuera de zona")

if boton_enviar:
    if not codigo_barras:
        st.warning("Por favor, ingrese un código de barras.")
    else:
        paquete = buscar_paquete(codigo_barras)
        if not paquete:
            st.error(f"No se encontró paquete: {codigo_barras}")
        elif paquete.get("whatsapp") == 1:
            st.warning("Ya se envió un WhatsApp para este paquete.")
        else:
            # Preparar mensaje
            nombre = paquete.get("nombre", "Cliente")
            direccion = paquete.get("direccion_origen", "dirección registrada")
            telefono = paquete.get("telefono", "")
            serial = paquete.get("serial_number", "serial")
            if not telefono:
                st.error("El paquete no tiene número de teléfono registrado.")
            else:
                if not telefono.startswith("+"):
                    telefono = "+" + telefono

                mensaje = (
                    f"Hola {nombre}, le saludamos cordialmente. "
                    f"Notamos que en su envio con serial: '{serial} su dirección registrada es '{direccion}' y queremos informarle "
                    "que somos la empresa encargada de enviar sus paquetes de Temu. "
                    "Hemos detectado que esta dirección no corresponde a la localidad de Barrios Unidos. "
                    "¿Podría por favor confirmarnos la dirección correcta? Gracias."
                )

                # Mostrar mensaje y enlace
                st.subheader("Mensaje generado:")
                st.text(mensaje)

                texto_enc = urllib.parse.quote(mensaje)
                url_whatsapp = f"https://api.whatsapp.com/send?phone={telefono}&text={texto_enc}"

                st.subheader("Abrir WhatsApp:")
                st.markdown(f"[📲 Enviar WhatsApp]({url_whatsapp})", unsafe_allow_html=True)
                st.code(url_whatsapp, language="text")

                if st.button("Marcar como enviado"):
                    actualizar_estado_whatsapp(paquete["id"])
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
