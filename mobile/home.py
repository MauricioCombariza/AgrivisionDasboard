import streamlit as st
import socket

st.set_page_config(page_title="Servilla Mobile", page_icon="📦", layout="centered")

st.title("📦 Servilla Mobile")
st.caption("Acceso desde celular")

st.divider()

# Muestra la IP local para que el usuario sepa a qué conectarse
try:
    ip = socket.gethostbyname(socket.gethostname())
except Exception:
    ip = "desconocida"

st.info(f"**IP local de este servidor:** `{ip}:8502`\n\nConéctate desde tu celular (misma WiFi) a esa dirección.")

st.markdown("""
### Módulos disponibles

- **📦 Devoluciones iMile** — Envío de WhatsApp + subida a portal iMile

Usa el menú lateral (☰) para navegar.
""")
