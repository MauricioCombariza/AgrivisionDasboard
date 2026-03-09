import streamlit as st
from PIL import Image
import requests

st.title("Bienvenido a la Aplicación de Análisis de Datos de Servilla")
st.write("Utiliza el menú de la izquierda para navegar entre las páginas.")

image_url = "https://res.cloudinary.com/combariza/image/upload/v1727436471/Servilla/Servilla_sin_fondo_mwigkk.png"

try:
  response = requests.get(image_url)
  response.raise_for_status()  # Raise an exception for non-2xx status codes
  st.image(response.content, width=500)
except requests.exceptions.RequestException as e:
  st.error(f"Error downloading image: {e}")