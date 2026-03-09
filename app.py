import streamlit as st

st.set_page_config(
    page_title="Carvajal - Sistema Unificado",
    page_icon="📦",
    layout="wide"
)

# Definir páginas agrupadas
paginas = {
    "Dashboard": [
        st.Page("home_logistica.py", title="Logística", icon="📦"),
        st.Page("home.py", title="Servilla", icon="📱"),
    ],
    "Logística": [
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
    ],
    "WhatsApp / Paquetes": [
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
    ],
}

nav = st.navigation(paginas)
nav.run()
