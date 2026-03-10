import streamlit as st
import yaml
import os
from yaml.loader import SafeLoader
import streamlit_authenticator as stauth

st.set_page_config(
    page_title="Carvajal - Sistema Unificado",
    page_icon="📦",
    layout="wide"
)

# ── Autenticación ────────────────────────────────────────────────────────────

_AUTH_FILE = os.path.join(os.path.dirname(__file__), "auth", "users.yaml")

with open(_AUTH_FILE, encoding="utf-8") as f:
    _config = yaml.load(f, Loader=SafeLoader)

authenticator = stauth.Authenticate(
    _config["credentials"],
    _config["cookie"]["name"],
    _config["cookie"]["key"],
    _config["cookie"]["expiry_days"],
    auto_hash=False,
)

authenticator.login(location="main")

if st.session_state.get("authentication_status") is False:
    st.error("Usuario o contraseña incorrectos")
    st.stop()
elif not st.session_state.get("authentication_status"):
    st.warning("Por favor ingresa tus credenciales")
    st.stop()

# Usuario autenticado
username = st.session_state["username"]
name = st.session_state["name"]
role = _config["credentials"]["usernames"][username].get("role", "paquetes")
st.session_state["role"] = role
st.session_state["user_name"] = name

authenticator.logout("Cerrar sesión", location="sidebar")
st.sidebar.write(f"👤 {name} ({role})")

# ── Páginas por rol ───────────────────────────────────────────────────────────

PAGES_DASHBOARD = [
    st.Page("home_logistica.py", title="Logística", icon="📦"),
    st.Page("home.py", title="Servilla", icon="📱"),
]

PAGES_LOGISTICA = [
    st.Page("pages_logistica/1_Clientes_Precios.py", title="Clientes y Precios", icon="👥"),
    st.Page("pages_logistica/2_Personal.py", title="Personal", icon="🚚"),
    st.Page("pages_logistica/3_Ordenes.py", title="Órdenes", icon="📦"),
    st.Page("pages_logistica/4_Facturacion.py", title="Facturación", icon="💰"),
    st.Page("pages_logistica/5_Reportes.py", title="Reportes", icon="📊"),
    st.Page("pages_logistica/6_Registro_Labores.py", title="Registro Labores", icon="⏱️"),
    st.Page("pages_logistica/7_Gestion_Pagos.py", title="Gestión Pagos", icon="💰"),
    st.Page("pages_logistica/8_Facturas_Transporte.py", title="Facturas Transporte", icon="🚚"),
    st.Page("pages_logistica/9_Gastos_Administrativos.py", title="Gastos Admin", icon="💼"),
    st.Page("pages_logistica/10_Flujo_Caja.py", title="Flujo de Caja", icon="💸"),
    st.Page("pages_logistica/11_Nomina.py", title="Nómina", icon="💼"),
    st.Page("pages_logistica/12_Detalle_Gestiones.py", title="Detalle Gestiones", icon="📋"),
    st.Page("pages_logistica/13_Planillas_Mensajeros_Check.py", title="Planillas Mensajeros", icon="📑"),
]

PAGES_PAQUETES = [
    st.Page("pages_home/Agrupacion_Escaner.py", title="Agrupación Escáner"),
    st.Page("pages_home/BuscarDirecciones.py", title="Buscar Direcciones"),
    st.Page("pages_home/BuscarPaquete.py", title="Buscar Paquete", icon="🔍"),
    st.Page("pages_home/ExcelACSV.py", title="Excel a CSV", icon="📄"),
    st.Page("pages_home/Devoluciones_iMile.py", title="Devoluciones iMile", icon="🔄"),
    st.Page("pages_home/EstandarizarDirecciones.py", title="Estandarizar Direcciones", icon="📍"),
    st.Page("pages_home/captura_imile.py", title="Captura iMile"),
    st.Page("pages_home/Cumplimiento_imile.py", title="Cumplimiento iMile"),
    st.Page("pages_home/Data.py", title="Data"),
    st.Page("pages_home/DespachoCourrier.py", title="Despacho Courrier"),
    st.Page("pages_home/GestionPendiente.py", title="Gestión Pendiente"),
    st.Page("pages_home/Ingreso_paquetes.py", title="Ingreso Paquetes"),
    st.Page("pages_home/Paquetes.py", title="Paquetes"),
    st.Page("pages_home/Pendientes.py", title="Pendientes"),
    st.Page("pages_home/Planillas.py", title="Planillas"),
    st.Page("pages_home/Procesador_Ordenes.py", title="Procesador Órdenes", icon="🔄"),
    st.Page("pages_home/Reclamos.py", title="Reclamos"),
    st.Page("pages_home/Sectores.py", title="Sectores"),
    st.Page("pages_home/Subir_devoluciones.py", title="Subir Devoluciones"),
    st.Page("pages_home/Ventas.py", title="Ventas"),
    st.Page("pages_home/wa.py", title="WhatsApp Sender"),
    st.Page("pages_home/whatsapp.py", title="Notificación Paquetes"),
]

paginas = {"Dashboard": PAGES_DASHBOARD}

if role in ("admin", "logistica"):
    paginas["Logística"] = PAGES_LOGISTICA

if role in ("admin", "paquetes"):
    paginas["WhatsApp / Paquetes"] = PAGES_PAQUETES

nav = st.navigation(paginas)
nav.run()
