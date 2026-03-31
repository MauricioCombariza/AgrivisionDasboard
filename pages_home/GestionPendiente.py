import pandas as pd
import numpy as np
import streamlit as st
from datetime import datetime, date
import io
import os
import subprocess
from openpyxl import Workbook
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from utils.db_connection import get_connection

# ── Rutas fijas ──────────────────────────────────────────────────────────────
CSV_PATH = "/mnt/c/Users/mcomb/Desktop/Carvajal/python/dashboard.csv"
DOWNLOADS_BASE = "/mnt/c/Users/mcomb/Downloads/pendientes_courriers"
GMAIL_SKILL = os.path.expanduser("~/.claude/skills/gmail-skill/gmail_skill.py")
FROM_ACCOUNT = "mauricio.combariza@gruposervilla.com"

ORDEN_INICIO_AUTO = 122000
ORDEN_FIN_AUTO = 128000


def _carpeta_hoy():
    hoy = date.today().strftime("%Y-%m-%d")
    carpeta = os.path.join(DOWNLOADS_BASE, hoy)
    os.makedirs(carpeta, exist_ok=True)
    return carpeta


def _cargar_couriers_externos():
    """Devuelve DataFrame con código, nombre_completo y email de courier_externo activos."""
    conn = get_connection("logistica")
    if conn is None:
        return pd.DataFrame()
    try:
        df = pd.read_sql(
            "SELECT codigo, nombre_completo, email FROM personal "
            "WHERE activo = TRUE AND tipo_personal = 'courier_externo' ORDER BY nombre_completo",
            conn,
        )
        return df
    finally:
        conn.close()


def _generar_pendientes_courier(df_csv, codigos_courier):
    """Filtra el CSV y devuelve dict {cod_men: df_filtrado}."""
    df = df_csv.copy()
    df["orden"] = pd.to_numeric(df["orden"], errors="coerce")
    df["cod_men"] = pd.to_numeric(df["cod_men"], errors="coerce")

    mask = (
        df["cod_men"].isin(codigos_courier)
        & (df["orden"] >= ORDEN_INICIO_AUTO)
        & (df["orden"] <= ORDEN_FIN_AUTO)
        & ~df["retorno"].isin(["D", "o"])
        & df["ret_esc"].isin(["i", "p"])
    )
    df_filtrado = df[mask].copy()

    resultado = {}
    for cod in codigos_courier:
        sub = df_filtrado[df_filtrado["cod_men"] == cod].copy()
        if not sub.empty:
            sub = sub[
                ["serial", "orden", "cod_men", "f_emi", "no_entidad", "nombred",
                 "dirdes1", "cod_sec", "ciudad1", "dpto1", "retorno", "ret_esc", "motivo"]
            ]
            sub = sub.drop_duplicates(subset=["serial"], keep="first")
            resultado[cod] = sub
    return resultado


def _guardar_archivos(pendientes_dict, couriers_df, carpeta):
    """Guarda un Excel por courier y retorna lista de rutas."""
    rutas = {}
    for cod, df_p in pendientes_dict.items():
        fila = couriers_df[couriers_df["codigo"] == cod]
        nombre = fila["nombre_completo"].iloc[0].replace(" ", "_") if not fila.empty else str(int(cod))
        ruta = os.path.join(carpeta, f"pendientes_{int(cod)}_{nombre}.xlsx")
        with pd.ExcelWriter(ruta, engine="openpyxl") as writer:
            df_p.to_excel(writer, index=False, sheet_name="Pendientes")
        rutas[cod] = ruta
    return rutas


# Título de la página
st.title("Pendientes - Filtrado de Datos")

# ════════════════════════════════════════════════════════════════════════════
# SECCIÓN AUTOMÁTICA: Pendientes por Courier Externo
# ════════════════════════════════════════════════════════════════════════════
st.header("Pendientes Automáticos – Couriers Externos")
st.caption(f"Órdenes {ORDEN_INICIO_AUTO:,} – {ORDEN_FIN_AUTO:,} · CSV: {CSV_PATH}")

if not os.path.exists(CSV_PATH):
    st.error(f"No se encontró el archivo CSV en: {CSV_PATH}")
else:
    couriers_df = _cargar_couriers_externos()

    if couriers_df.empty:
        st.warning("No se encontraron couriers externos activos en la base de datos.")
    else:
        with st.spinner("Procesando pendientes..."):
            df_csv = pd.read_csv(CSV_PATH, low_memory=False, encoding="latin1")
            codigos = couriers_df["codigo"].dropna().astype(float).tolist()
            pendientes = _generar_pendientes_courier(df_csv, codigos)

        if not pendientes:
            st.info("No hay pendientes para couriers externos en el rango de órdenes especificado.")
        else:
            carpeta_hoy = _carpeta_hoy()
            rutas_archivos = _guardar_archivos(pendientes, couriers_df, carpeta_hoy)

            st.success(f"Archivos guardados en: `{carpeta_hoy}`")

            # Tabla resumen
            resumen_rows = []
            for cod, df_p in pendientes.items():
                fila = couriers_df[couriers_df["codigo"] == cod]
                nombre = fila["nombre_completo"].iloc[0] if not fila.empty else "—"
                email = fila["email"].iloc[0] if not fila.empty else ""
                resumen_rows.append({
                    "cod_men": int(cod),
                    "Nombre": nombre,
                    "Email": email or "⚠️ Sin email",
                    "Pendientes": len(df_p),
                    "Archivo": os.path.basename(rutas_archivos.get(cod, "")),
                })
            df_resumen = pd.DataFrame(resumen_rows)
            st.dataframe(df_resumen, use_container_width=True)

            # Descargas individuales
            st.subheader("Descargar archivos")
            for cod, ruta in rutas_archivos.items():
                fila = couriers_df[couriers_df["codigo"] == cod]
                nombre = fila["nombre_completo"].iloc[0] if not fila.empty else str(int(cod))
                with open(ruta, "rb") as f:
                    st.download_button(
                        f"📥 {nombre} ({len(pendientes[cod])} pendientes)",
                        f.read(),
                        file_name=os.path.basename(ruta),
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                        key=f"dl_{int(cod)}",
                    )

            # ── Envío de correos ─────────────────────────────────────────────
            st.subheader("Enviar correos a couriers")

            if not os.path.exists(GMAIL_SKILL):
                st.warning(
                    f"Gmail skill no encontrada en `{GMAIL_SKILL}`. "
                    "Configura la skill para habilitar el envío."
                )
            else:
                enviar_todos = st.button("📧 Enviar pendientes a TODOS los couriers", type="primary")

                for _, row in df_resumen.iterrows():
                    cod = row["cod_men"]
                    nombre = row["Nombre"]
                    email_dest = row["Email"]
                    ruta_archivo = rutas_archivos.get(float(cod), rutas_archivos.get(cod))

                    col1, col2 = st.columns([3, 1])
                    with col1:
                        st.write(f"**{nombre}** · {email_dest} · {row['Pendientes']} pendientes")
                    with col2:
                        enviar_uno = st.button(f"Enviar", key=f"send_{cod}")

                    if (enviar_todos or enviar_uno) and email_dest and not email_dest.startswith("⚠️"):
                        asunto = f"Pendientes de entrega – {nombre} – {date.today().strftime('%d/%m/%Y')}"
                        cuerpo = (
                            f"Hola {nombre},\n\n"
                            f"Adjunto encontrará el listado de sus paquetes pendientes de entrega "
                            f"(órdenes {ORDEN_INICIO_AUTO:,} a {ORDEN_FIN_AUTO:,}).\n\n"
                            f"Total pendientes: {row['Pendientes']}\n\n"
                            f"Por favor gestionar a la brevedad.\n\n"
                            f"Saludos,\nGrupo Servilla"
                        )
                        cmd = [
                            "python3", GMAIL_SKILL,
                            "send",
                            "--to", email_dest,
                            "--subject", asunto,
                            "--body", cuerpo,
                            "--account", FROM_ACCOUNT,
                        ]
                        try:
                            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
                            if result.returncode == 0:
                                st.success(f"✅ Correo enviado a {nombre} ({email_dest})")
                            else:
                                st.error(f"Error enviando a {nombre}: {result.stderr[:200]}")
                        except subprocess.TimeoutExpired:
                            st.error(f"Timeout al enviar correo a {nombre}")
                        except Exception as e:
                            st.error(f"Error: {e}")
                    elif (enviar_todos or enviar_uno) and (not email_dest or email_dest.startswith("⚠️")):
                        st.warning(f"Sin email configurado para {nombre}. Actualizar en Personal.")

st.divider()

# Sección de entradas
st.header("Parámetros de Filtro")

# Entrada para la orden inicial y final
orden_inicio = st.text_input("Selecciona la Orden inicial:")
orden_fin = st.text_input("Selecciona la Orden final:")

# Entrada para los códigos 'cod_men'
cod_men_input = st.text_input("Ingresa uno o varios códigos cod_men separados por coma:")

# Mostrar los códigos ingresados



# Cargar archivo CSV
uploaded_file = st.file_uploader("Sube tu archivo CSV", type="csv")

if uploaded_file is not None:
    # Leer archivo CSV
    if cod_men_input:
        cod_men_list = [int(c.strip()) for c in cod_men_input.split(",") if c.strip().isdigit()]
        if cod_men_list:
            st.write(f"Códigos ingresados: **{cod_men_list}**") 
            orden_inicio_num = pd.to_numeric(orden_inicio, errors='coerce')
            orden_fin_num = pd.to_numeric(orden_fin, errors='coerce')
                    
            df = pd.read_csv(uploaded_file, low_memory=False, encoding='latin1')
            df['orden'] = pd.to_numeric(df['orden'], errors='coerce')
            df['cod_men'] = pd.to_numeric(df['cod_men'], errors='coerce')
            filtro_cod_men = df['cod_men'].isin(cod_men_list)

            # Filtro 2: Excluir 'retorno' con valores 'D' o 'o'
            filtro_retorno = ~df['retorno'].isin(['D', 'o'])

            # Filtro 3: Filtrar por 'ret_esc' igual a 'i'
            # filtro_ret_esc = df['ret_esc'] == 'i'
            filtro_ret_esc = df['ret_esc'].isin(['i', 'p'])

            # Filtro 4: Filtrar por rango de 'orden' (solo si se ingresaron ambos valores)
            if pd.notna(orden_inicio_num) and pd.notna(orden_fin_num):
                filtro_orden = (df['orden'] >= orden_inicio_num) & (df['orden'] <= orden_fin_num)
                df_filtrado = df[filtro_cod_men & filtro_retorno & filtro_ret_esc & filtro_orden]
            else:
                df_filtrado = df[filtro_cod_men & filtro_retorno & filtro_ret_esc]
            df_filtrado = df_filtrado[['serial', 'orden','cod_men','f_emi', 'no_entidad', 'nombred', 'dirdes1','cod_sec', 'ciudad1', 'dpto1', 'retorno', 'ret_esc', 'motivo']]
            
            # Mostrar los resultados
            if not df_filtrado.empty:
                st.write("Resultados filtrados:", df_filtrado.head())
                st.write("Fecha inicial", df_filtrado['f_emi'].min())
                st.write("Fecha final", df_filtrado['f_emi'].max())
                st.write(f"Total de registros antes de eliminar duplicados: {len(df_filtrado)}")

                # Eliminar seriales duplicados
                total_antes = len(df_filtrado)
                df_filtrado = df_filtrado.drop_duplicates(subset=['serial'], keep='first')
                total_despues = len(df_filtrado)
                duplicados_eliminados = total_antes - total_despues

                if duplicados_eliminados > 0:
                    st.warning(f"Se eliminaron {duplicados_eliminados} seriales duplicados")
                st.write(f"**Total de pendientes mensajero (seriales únicos): {len(df_filtrado)}**")

                buf = io.BytesIO()
                with pd.ExcelWriter(buf, engine="openpyxl") as writer:
                    df_filtrado.to_excel(writer, index=False, sheet_name="Hoja1")
                nombre_xlsx = f"pendientes_códigos_{'_'.join(map(str, cod_men_list))}.xlsx"
                st.download_button("📥 Descargar Excel", buf.getvalue(), nombre_xlsx,
                                   "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
            else:
                st.write("No hay resultados para los filtros especificados.")
                
        else:
            st.write(f"No se encontraron coincidencias para los códigos cod_men: {cod_men_input}")
    else:
        st.write("Por favor, ingresa uno o varios códigos cod_men separados por coma.") 

else:
    st.info("Por favor, sube un archivo CSV para comenzar.")

    