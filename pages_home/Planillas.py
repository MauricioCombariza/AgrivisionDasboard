import pandas as pd
import streamlit as st
from datetime import datetime
import io
from openpyxl import Workbook
import mysql.connector
import os
from dotenv import load_dotenv

load_dotenv()

st.title("Pendientes - Filtrado de Datos")

# ── Conexión a BD local ───────────────────────────────────────────────────────
def _conectar_bd():
    try:
        return mysql.connector.connect(
            host="localhost",
            user="root",
            password=os.environ.get("DB_PASSWORD_LOCAL", "Vale2010"),
            database="logistica",
            connect_timeout=8,
        )
    except Exception:
        return None


# ── Sección de entradas ───────────────────────────────────────────────────────
st.header("Parámetros de Filtro")

planilla = st.text_input("Selecciona la Orden inicial:")

uploaded_file = st.file_uploader("Sube tu archivo CSV", type="csv")

if uploaded_file is not None:
    planilla_num = pd.to_numeric(planilla, errors='coerce')

    df = pd.read_csv(uploaded_file, low_memory=False, encoding='latin1')
    df['planilla'] = pd.to_numeric(df['planilla'], errors='coerce')
    st.write("Datos cargados exitosamente. Vista previa del archivo:")
    st.dataframe(df.head())

    if planilla:
        try:
            df['cod_men'] = pd.to_numeric(df['cod_men'], errors='coerce')

            df_filtrado = df[df['planilla'] == planilla_num]

            df_filtrado = df_filtrado[[
                'serial', 'orden', 'f_emi', 'cod_men', 'cod_sec',
                'cliente', 'retorno', 'ret_esc', 'comentario',
                'nombred', 'dirdes1', 'planilla'
            ]]

            if not df_filtrado.empty:

                # ── Precios desde gestiones_mensajero ─────────────────────────
                conn = _conectar_bd()
                if conn:
                    try:
                        cur = conn.cursor(dictionary=True)
                        cur.execute("""
                            SELECT
                                gm.cod_mensajero,
                                p.nombre_completo  AS nombre_mensajero,
                                gm.cliente,
                                gm.lot_esc         AS planilla_bd,
                                gm.total_seriales,
                                gm.valor_unitario,
                                gm.valor_total,
                                gm.tipo_gestion,
                                gm.liquidado,
                                gm.editado_manualmente
                            FROM gestiones_mensajero gm
                            LEFT JOIN personal p ON gm.mensajero_id = p.id
                            WHERE gm.lot_esc = %s
                            ORDER BY gm.cod_mensajero
                        """, (str(int(planilla_num)),))
                        registros_bd = cur.fetchall()
                        cur.close()
                        conn.close()
                    except Exception as e:
                        registros_bd = []
                        st.warning(f"No se pudo consultar BD: {e}")
                else:
                    registros_bd = []

                # ── Resumen de precios ────────────────────────────────────────
                if registros_bd:
                    st.divider()
                    st.markdown("### Precios registrados en BD para esta planilla")

                    total_val = sum(r['valor_total'] or 0 for r in registros_bd)
                    total_ser = sum(r['total_seriales'] or 0 for r in registros_bd)

                    col1, col2, col3 = st.columns(3)
                    col1.metric("Seriales en BD", f"{total_ser:,}")
                    col2.metric("Seriales en CSV", f"{len(df_filtrado):,}")
                    col3.metric("Valor total", f"${total_val:,.0f}")

                    df_bd = pd.DataFrame([{
                        "Courier":          r['cod_mensajero'],
                        "Mensajero":        r['nombre_mensajero'] or "—",
                        "Cliente":          r['cliente'],
                        "Seriales BD":      r['total_seriales'],
                        "Precio unitario":  f"${r['valor_unitario']:,.2f}" if r['valor_unitario'] else "$0",
                        "Valor total":      f"${r['valor_total']:,.0f}"    if r['valor_total']    else "$0",
                        "Tipo":             r['tipo_gestion'],
                        "Liquidado":        "✅" if r['liquidado'] else "—",
                        "Editado manual":   "🔒" if r['editado_manualmente'] else "—",
                    } for r in registros_bd])
                    st.dataframe(df_bd, use_container_width=True, hide_index=True)
                else:
                    st.info("Esta planilla aún no tiene precio registrado en gestiones_mensajero.")

                st.divider()
                st.markdown("### Detalle de seriales (CSV)")

                buf = io.BytesIO()
                with pd.ExcelWriter(buf, engine="openpyxl") as writer:
                    df_filtrado.to_excel(writer, index=False, sheet_name="Hoja1")
                st.download_button(
                    "📥 Descargar Excel",
                    buf.getvalue(),
                    f"planilla_{planilla_num}.xlsx",
                    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                )
                st.dataframe(df_filtrado, use_container_width=True)

            else:
                st.write(f"No se encontraron coincidencias para la planilla: {planilla_num}")

        except ValueError:
            st.error("El número de planilla ingresado no es válido.")
    else:
        st.write("Por favor, ingresa un numero de planilla")

else:
    st.info("Por favor, sube un archivo CSV para comenzar.")
