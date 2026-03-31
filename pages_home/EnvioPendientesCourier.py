import pandas as pd
import streamlit as st
from datetime import date
import io
import os
import smtplib
from email.message import EmailMessage
import sys
from dotenv import load_dotenv

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from utils.db_connection import get_connection

load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))

# ── Configuración ─────────────────────────────────────────────────────────────
CSV_PATH       = "/mnt/c/Users/mcomb/Desktop/Carvajal/python/dashboard.csv"
DOWNLOADS_BASE = "/mnt/c/Users/mcomb/Downloads/pendientes_courriers"
GMAIL_FROM     = os.getenv("GMAIL_FROM", "mauricio.combariza@gruposervilla.com")
GMAIL_APP_PASS = os.getenv("GMAIL_APP_PASSWORD", "")
ORDEN_INICIO   = 122000
ORDEN_FIN      = 128000


# ── Helpers ───────────────────────────────────────────────────────────────────

def carpeta_hoy():
    ruta = os.path.join(DOWNLOADS_BASE, date.today().strftime("%Y-%m-%d"))
    os.makedirs(ruta, exist_ok=True)
    return ruta


def cargar_couriers():
    # Intenta remoto primero, cae a local (sin contraseña) si no hay conexión
    intentos = [
        {"host": os.getenv("DB_HOST", "204.168.150.196"), "password": os.getenv("DB_PASSWORD", "")},
        {"host": "localhost", "password": ""},
    ]
    for cfg_extra in intentos:
        try:
            import mysql.connector
            conn = mysql.connector.connect(
                host=cfg_extra["host"],
                user=os.getenv("DB_USER", "root"),
                password=cfg_extra["password"],
                database=os.getenv("DB_NAME_LOGISTICA", "logistica"),
                connect_timeout=5,
            )
            df = pd.read_sql(
                "SELECT codigo, nombre_completo, email FROM personal "
                "WHERE activo = TRUE AND tipo_personal = 'courier_externo' ORDER BY nombre_completo",
                conn,
            )
            conn.close()
            return df
        except Exception:
            continue
    return pd.DataFrame()


def filtrar_pendientes(df_csv, codigos):
    df = df_csv.copy()
    df["orden"]   = pd.to_numeric(df["orden"],   errors="coerce")
    df["cod_men"] = pd.to_numeric(df["cod_men"], errors="coerce")
    mask = (
        df["cod_men"].isin(codigos)
        & df["orden"].between(ORDEN_INICIO, ORDEN_FIN)
        & ~df["retorno"].isin(["D", "o"])
        & df["ret_esc"].isin(["i", "p"])
    )
    cols = ["serial", "orden", "cod_men", "f_emi", "no_entidad", "nombred",
            "dirdes1", "cod_sec", "ciudad1", "dpto1", "retorno", "ret_esc", "motivo"]
    resultado = {}
    for cod in codigos:
        sub = df[mask & (df["cod_men"] == cod)].drop_duplicates("serial", keep="first")[cols]
        if not sub.empty:
            resultado[cod] = sub
    return resultado


def guardar_excel(pendientes, couriers_df, carpeta):
    rutas = {}
    for cod, df_p in pendientes.items():
        fila   = couriers_df[couriers_df["codigo"] == cod]
        nombre = fila["nombre_completo"].iloc[0].replace(" ", "_") if not fila.empty else str(int(cod))
        ruta   = os.path.join(carpeta, f"pendientes_{int(cod)}_{nombre}.xlsx")
        with pd.ExcelWriter(ruta, engine="openpyxl") as w:
            df_p.to_excel(w, index=False, sheet_name="Pendientes")
        rutas[cod] = ruta
    return rutas


def enviar_correo(destinatario, nombre, ruta_excel, app_password, n_pendientes):
    msg = EmailMessage()
    msg["From"]    = GMAIL_FROM
    msg["To"]      = destinatario
    msg["Subject"] = f"Pendientes de entrega – {nombre} – {date.today().strftime('%d/%m/%Y')}"
    msg.set_content(
        f"Hola {nombre},\n\n"
        f"Adjunto encontrará el listado de sus paquetes pendientes de entrega "
        f"(órdenes {ORDEN_INICIO:,} a {ORDEN_FIN:,}).\n\n"
        f"Total pendientes: {n_pendientes}\n\n"
        f"Por favor gestionar a la brevedad.\n\n"
        f"Saludos,\nGrupo Servilla"
    )
    with open(ruta_excel, "rb") as f:
        msg.add_attachment(
            f.read(),
            maintype="application",
            subtype="vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            filename=os.path.basename(ruta_excel),
        )
    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as smtp:
        smtp.login(GMAIL_FROM, app_password)
        smtp.send_message(msg)


# ── UI ────────────────────────────────────────────────────────────────────────

st.title("Envío Automático de Pendientes – Couriers Externos")
st.caption(f"Órdenes {ORDEN_INICIO:,} – {ORDEN_FIN:,}  ·  CSV: `{CSV_PATH}`")

# Contraseña de app (desde .env o ingresada manualmente)
app_pass = GMAIL_APP_PASS
if not app_pass:
    st.warning("No se encontró `GMAIL_APP_PASSWORD` en el archivo `.env`.")
    app_pass = st.text_input(
        "Ingresa el App Password de Gmail (16 caracteres):",
        type="password",
        placeholder="xxxx xxxx xxxx xxxx",
        help="Generar en: myaccount.google.com/apppasswords",
    )

st.divider()

# Verificar CSV
if not os.path.exists(CSV_PATH):
    st.error(f"Archivo CSV no encontrado: `{CSV_PATH}`")
    st.stop()

# Cargar couriers y CSV
couriers_df = cargar_couriers()
if couriers_df.empty:
    st.warning("No hay couriers externos activos en la base de datos.")
    st.stop()

with st.spinner("Leyendo CSV y filtrando pendientes..."):
    df_csv   = pd.read_csv(CSV_PATH, low_memory=False, encoding="latin1")
    codigos  = couriers_df["codigo"].dropna().astype(float).tolist()
    pendientes = filtrar_pendientes(df_csv, codigos)

if not pendientes:
    st.info("No hay pendientes para couriers externos en el rango de órdenes especificado.")
    st.stop()

# Guardar archivos
carpeta = carpeta_hoy()
rutas   = guardar_excel(pendientes, couriers_df, carpeta)
st.success(f"Archivos guardados en: `{carpeta}`")

# Tabla resumen
rows = []
for cod, df_p in pendientes.items():
    fila = couriers_df[couriers_df["codigo"] == cod]
    rows.append({
        "cod_men":    int(cod),
        "Nombre":     fila["nombre_completo"].iloc[0] if not fila.empty else "—",
        "Email":      fila["email"].iloc[0]            if not fila.empty else "",
        "Pendientes": len(df_p),
    })
df_resumen = pd.DataFrame(rows)

# Marcar sin email
df_resumen["Estado email"] = df_resumen["Email"].apply(
    lambda e: "✅ OK" if e and "@" in str(e) else "⚠️ Sin email"
)
st.dataframe(df_resumen, use_container_width=True)

st.divider()

# ── Descargas ─────────────────────────────────────────────────────────────────
st.subheader("Descargar archivos")
cols_dl = st.columns(min(len(rutas), 4))
for i, (cod, ruta) in enumerate(rutas.items()):
    fila   = couriers_df[couriers_df["codigo"] == cod]
    nombre = fila["nombre_completo"].iloc[0] if not fila.empty else str(int(cod))
    with open(ruta, "rb") as f:
        cols_dl[i % len(cols_dl)].download_button(
            f"📥 {nombre}\n({len(pendientes[cod])} pendientes)",
            f.read(),
            file_name=os.path.basename(ruta),
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            key=f"dl_{int(cod)}",
        )

st.divider()

# ── Envío de correos ──────────────────────────────────────────────────────────
st.subheader("Enviar correos")

if not app_pass:
    st.info("Ingresa el App Password arriba para habilitar el envío.")
    st.stop()

enviar_todos = st.button("📧 Enviar a TODOS los couriers", type="primary", use_container_width=True)

st.write("")
for _, row in df_resumen.iterrows():
    cod        = row["cod_men"]
    nombre     = row["Nombre"]
    email_dest = row["Email"]
    tiene_email = email_dest and "@" in str(email_dest)
    ruta_xls   = rutas.get(float(cod)) or rutas.get(cod)

    c1, c2 = st.columns([4, 1])
    c1.write(f"**{nombre}** · {email_dest or '⚠️ sin email'} · {row['Pendientes']} pendientes")
    enviar_uno = c2.button("Enviar", key=f"send_{cod}", disabled=not tiene_email)

    if (enviar_todos or enviar_uno) and tiene_email:
        try:
            enviar_correo(email_dest, nombre, ruta_xls, app_pass, row["Pendientes"])
            st.success(f"✅ Correo enviado a **{nombre}** ({email_dest})")
        except smtplib.SMTPAuthenticationError:
            st.error("Error de autenticación: verifica el App Password en `.env`.")
            st.stop()
        except Exception as e:
            st.error(f"Error enviando a {nombre}: {e}")
    elif (enviar_todos or enviar_uno) and not tiene_email:
        st.warning(f"Sin email registrado para **{nombre}**. Actualizar en módulo Personal.")
