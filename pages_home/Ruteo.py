import streamlit as st
import pandas as pd
import numpy as np
import re
import io
from pathlib import Path
from python_tsp.heuristics import solve_tsp_local_search
from python_tsp.distances import euclidean_distance_matrix

# ── Configuración ──────────────────────────────────────────────────────────────
BASES_HISTO    = "/mnt/c/Users/mcomb/Desktop/Carvajal/python/basesHisto.csv"
FACTORES_CSV   = Path(__file__).parent / "malla_vial_factores.csv"
FACTOR_DEFAULT = 1667    # fallback: soporta hasta 5 letras sin colisión
METROS_X_UNIDAD = 0.015  # ~1 calle(10000u) ≈ 150 m en Bogotá norte

COLS_HISTO = ["serial", "cod_sec", "dirdes1", "dir_num"]

st.set_page_config(page_title="Ruteo", layout="wide")
st.title("🗺️ Ruteo por Sector")
st.caption("Sube un Excel con seriales → busca en basesHisto → extrae coordenadas → ruta óptima por sector")

# ── Tabla de factores reales por vía (Malla Vial Catastro Bogotá) ─────────────
@st.cache_data(show_spinner="Cargando tabla de factores viales…")
def cargar_factores() -> dict:
    if not FACTORES_CSV.exists():
        return {}
    df = pd.read_csv(FACTORES_CSV, dtype={"tipo": str, "numero": int, "factor": int})
    tipo_map = {"CL": 1, "AC": 1, "DG": 1, "KR": 3, "AK": 3, "TV": 3}
    tabla = {}
    for _, row in df.iterrows():
        t = tipo_map.get(str(row["tipo"]).strip())
        if t is not None:
            key = (t, int(row["numero"]))
            if key not in tabla or int(row["factor"]) < tabla[key]:
                tabla[key] = int(row["factor"])
    return tabla

# ── Carga base histórica (cacheada) ───────────────────────────────────────────
@st.cache_data(show_spinner="Cargando base histórica…")
def cargar_base(cols: tuple):
    df = pd.read_csv(
        BASES_HISTO,
        dtype=str,
        low_memory=False,
        usecols=lambda c: c in cols,
    )
    df.columns = df.columns.str.strip().str.lower()
    df["serial"] = df["serial"].str.strip()
    return df

# ── Parsing dir_num (18 dígitos) → coordenadas (x, y) ────────────────────────
def coordenadas_dirnum(raw, factores: dict):
    """
    Extrae (x, y) desde un dir_num de 18 dígitos usando el factor de letra
    real para cada vía (Malla Vial Catastro Bogotá).
    """
    try:
        d = str(raw).strip().zfill(18)
        if len(d) != 18 or not d.isdigit():
            return None, None

        cardinal = int(d[0])
        tipo     = int(d[1])
        via1_num = int(d[2:5])
        via1_let = int(d[5:8])
        via2_num = int(d[9:12])
        via2_let = int(d[12:15])

        tipo_via2 = 3 if tipo == 1 else 1
        lf1 = factores.get((tipo,      via1_num), FACTOR_DEFAULT)
        lf2 = factores.get((tipo_via2, via2_num), FACTOR_DEFAULT)

        v1 = via1_num * 10000 + (via1_let - 100) * lf1
        v2 = via2_num * 10000 + (via2_let - 100) * lf2

        if tipo == 1:
            x = -v1 if cardinal == 2 else v1
            y =  v2
        elif tipo == 3:
            x = -v2 if cardinal == 2 else v2
            y = -v1 if cardinal == 4 else v1
        else:
            return None, None

        return float(x), float(y)
    except Exception:
        return None, None

# ── Conversión texto → dir_num ────────────────────────────────────────────────
_TIPO_DIRNUM = {
    "CL": 1, "DG": 1, "AC": 1,
    "CR": 3, "KR": 3, "TR": 3, "TV": 3, "AK": 3,
}
_LETRA_OFF = {chr(65 + i): i + 1 for i in range(26)}  # A→1, B→2, …

def texto_a_dirnum(texto: str) -> str | None:
    """
    Convierte una dirección de texto en dir_num de 18 dígitos.
    Ejemplos válidos:
      "CL 127A 7 53"   → CL tipo1, via1=127A, via2=7, placa=53
      "CR 7B 130 69"   → CR tipo3, via1=7B, via2=130, placa=69
      "CL 128 7C 22"   → CL tipo1, via1=128, via2=7C, placa=22
    """
    s = re.sub(r'\b(AP|APTO|INT|CA|LOCAL|PISO|BL|BLQ|BLOQUE|TORRE)\b.*', '', texto, flags=re.I)
    s = s.strip().upper()
    tokens = s.split()
    if len(tokens) < 3:
        return None

    tipo_str = tokens[0]
    tipo = _TIPO_DIRNUM.get(tipo_str)
    if tipo is None:
        return None

    def parsear_via(tok):
        m = re.match(r'^(\d{1,3})([A-Z]?)(?:BIS)?$', tok)
        if not m:
            return None, None
        num = int(m.group(1))
        let = _LETRA_OFF.get(m.group(2), 0)
        return num, 100 + let

    via1_num, via1_let = parsear_via(tokens[1])
    via2_num, via2_let = parsear_via(tokens[2])
    if via1_num is None or via2_num is None:
        return None

    placa = 0
    if len(tokens) >= 4:
        digits = re.sub(r'\D', '', tokens[3])
        placa = int(digits[:3]) if digits else 0

    # Cardinal: Norte(1) por defecto; Sur(2) si la calle es < 26 y tipo CL
    cardinal = 2 if (tipo == 1 and via1_num < 26) else 1

    d = f"{cardinal}{tipo}{via1_num:03d}{via1_let:03d}0{via2_num:03d}{via2_let:03d}{placa:03d}"
    return d if len(d) == 18 else None

# ── Algoritmo de ruteo: NN + Local Search (2-opt) con depot fijo ──────────────
def rutear_sector(df_sec: pd.DataFrame, depot_xy: tuple | None = None) -> pd.DataFrame:
    """
    Calcula la ruta óptima para un sector usando:
      1. Nearest Neighbor como solución inicial.
      2. Local Search (2-opt) para mejorar la solución.

    Si se provee `depot_xy` (x, y), el depot se inserta en posición 0 como
    nodo fijo de inicio y fin (tour circular). La ruta resultante parte y
    termina en el depot.

    Columnas agregadas: `ruta`, `dist_m`, `dist_acum_m`.
    Filas sin coordenadas válidas van al final con ruta=NaN.
    """
    df_ok  = df_sec.dropna(subset=["x", "y"]).copy()
    df_sin = df_sec[df_sec[["x", "y"]].isna().any(axis=1)].copy()

    if df_ok.empty:
        df_sec["ruta"]        = range(1, len(df_sec) + 1)
        df_sec["dist_m"]      = pd.NA
        df_sec["dist_acum_m"] = pd.NA
        return df_sec

    pts = df_ok[["x", "y"]].to_numpy(dtype=float)

    # ── Con depot: tour circular ──────────────────────────────────────────────
    if depot_xy is not None:
        depot_pt = np.array([[depot_xy[0], depot_xy[1]]])
        pts_full = np.vstack([depot_pt, pts])       # depot en índice 0
        D        = euclidean_distance_matrix(pts_full)

        # Semilla: Nearest Neighbor desde depot
        n = len(pts_full)
        visited = [False]*n; route_nn = [0]; visited[0] = True
        for _ in range(n-1):
            last = route_nn[-1]
            nxt  = min((j for j in range(n) if not visited[j]),
                       key=lambda j: D[last][j])
            route_nn.append(nxt); visited[nxt] = True

        # Local Search (2-opt) mejora el tour cerrado
        route_ls, _ = solve_tsp_local_search(D, x0=route_nn)

        # Rotar para que empiece en depot (índice 0) y cerrar el ciclo
        r = list(route_ls)
        i0 = r.index(0)
        ordered = r[i0:] + r[:i0]   # [0, a, b, c, …]

        # Asignar orden a las filas de entrega (índices 1..n-1 en pts_full)
        df_ok = df_ok.reset_index(drop=True)
        rank = {delivery_idx - 1: pos + 1
                for pos, depot_or_del in enumerate(ordered)
                if (delivery_idx := depot_or_del) != 0}
        df_ok["ruta"] = df_ok.index.map(rank)
        df_ok = df_ok.sort_values("ruta").reset_index(drop=True)

        # Reconstruir coordenadas en el orden de visita (depot + entregas + depot)
        xy_ordered = np.vstack([
            depot_pt,
            df_ok[["x","y"]].to_numpy(dtype=float),
            depot_pt,
        ])

    # ── Sin depot: ruta abierta ───────────────────────────────────────────────
    else:
        D = euclidean_distance_matrix(pts)
        n = len(pts)
        visited = [False]*n; route_nn = [0]; visited[0] = True
        for _ in range(n-1):
            last = route_nn[-1]
            nxt  = min((j for j in range(n) if not visited[j]),
                       key=lambda j: D[last][j])
            route_nn.append(nxt); visited[nxt] = True

        route_ls, _ = solve_tsp_local_search(D, x0=route_nn)
        r = list(route_ls)
        i0 = r.index(0)
        ordered = r[i0:] + r[:i0]

        df_ok = df_ok.reset_index(drop=True)
        rank  = {idx: pos+1 for pos, idx in enumerate(ordered)}
        df_ok["ruta"] = df_ok.index.map(rank)
        df_ok = df_ok.sort_values("ruta").reset_index(drop=True)
        xy_ordered = df_ok[["x","y"]].to_numpy(dtype=float)

    # ── Distancias ────────────────────────────────────────────────────────────
    dists  = np.linalg.norm(np.diff(xy_ordered, axis=0), axis=1) * METROS_X_UNIDAD
    # dists tiene len = N_entregas + (1 si depot, 0 si no) segmentos
    # El último segmento (vuelta al depot) no pertenece a ninguna entrega específica
    dist_por_entrega = dists[:len(df_ok)]          # un valor por entrega
    df_ok["dist_m"]      = np.round(dist_por_entrega, 0)
    df_ok["dist_acum_m"] = np.round(np.cumsum(dist_por_entrega), 0)

    if not df_sin.empty:
        df_sin["ruta"]        = pd.NA
        df_sin["dist_m"]      = pd.NA
        df_sin["dist_acum_m"] = pd.NA

    return pd.concat([df_ok, df_sin])

# ═══════════════════════════════════════════════════════════════════════════════
# UI
# ═══════════════════════════════════════════════════════════════════════════════

# ── Subir archivo ─────────────────────────────────────────────────────────────
archivo = st.file_uploader(
    "📂 Sube el Excel con seriales",
    type=["xlsx", "xls"],
    help="El archivo debe tener al menos una columna con los números de serial",
)

if not archivo:
    st.info("Sube un archivo Excel para comenzar.")
    st.stop()

try:
    df_excel = pd.read_excel(archivo, dtype=str)
except Exception as e:
    st.error(f"No se pudo leer el Excel: {e}")
    st.stop()

st.subheader("Vista previa del archivo subido")
st.dataframe(df_excel.head(10), use_container_width=True)

col_serial = st.selectbox(
    "Columna que contiene el serial",
    options=df_excel.columns.tolist(),
    index=next(
        (i for i, c in enumerate(df_excel.columns) if "serial" in c.lower()),
        0,
    ),
)

seriales = df_excel[col_serial].dropna().str.strip().unique().tolist()
st.caption(f"**{len(seriales)}** seriales únicos en el archivo")

# ── Buscar en basesHisto ──────────────────────────────────────────────────────
base = cargar_base(tuple(COLS_HISTO))

df_match = base[base["serial"].isin(seriales)].drop_duplicates("serial").copy()
no_encontrados = [s for s in seriales if s not in df_match["serial"].values]

col1, col2, col3 = st.columns(3)
col1.metric("Seriales subidos",  len(seriales))
col2.metric("Encontrados",       len(df_match))
col3.metric("No encontrados",    len(no_encontrados),
            delta=f"-{len(no_encontrados)}" if no_encontrados else None,
            delta_color="inverse")

if no_encontrados:
    with st.expander(f"⚠️ {len(no_encontrados)} seriales no encontrados en basesHisto"):
        st.dataframe(pd.DataFrame({"serial": no_encontrados}), use_container_width=True)

if df_match.empty:
    st.warning("Ningún serial coincide con la base histórica.")
    st.stop()

# ── Coordenadas desde dir_num ─────────────────────────────────────────────────
factores = cargar_factores()
coords = df_match["dir_num"].apply(lambda v: coordenadas_dirnum(v, factores))
df_match["x"] = coords.apply(lambda t: t[0])
df_match["y"] = coords.apply(lambda t: t[1])

# ── Aplicar correcciones manuales (session_state) ─────────────────────────────
if "correcciones" not in st.session_state:
    st.session_state.correcciones = {}   # {serial: {"dir_num": ..., "x": ..., "y": ...}}

for serial, cor in st.session_state.correcciones.items():
    mask = df_match["serial"] == serial
    df_match.loc[mask, "dir_num"] = cor["dir_num"]
    df_match.loc[mask, "x"]       = cor["x"]
    df_match.loc[mask, "y"]       = cor["y"]

sin_coords = df_match[["x", "y"]].isna().any(axis=1).sum()
if sin_coords:
    st.warning(f"⚠️ {sin_coords} registros sin dir_num válido — irán al final de su sector.")

# ── Depot (punto de inicio y fin de cada ruta) ────────────────────────────────
st.divider()
with st.expander("🏠 Configurar punto de partida / llegada (depot)", expanded=True):
    col_dep1, col_dep2 = st.columns([3, 1])
    depot_texto = col_dep1.text_input(
        "Dirección del depot (formato: CL/CR número[letra] número[letra] placa)",
        value="CL 128 7C 35",
        help="Ej: CL 128 7C 35 · CR 7 127 10 · DG 45 32 8"
    )
    usar_depot = col_dep2.checkbox("Activar depot", value=True)

depot_xy = None
if usar_depot:
    dn_depot = texto_a_dirnum(depot_texto)
    if dn_depot:
        depot_xy = coordenadas_dirnum(dn_depot, factores)
        if depot_xy[0] is None:
            st.error(f"No se pudieron calcular coordenadas para el depot '{depot_texto}'.")
            depot_xy = None
        else:
            st.caption(f"Depot → dir_num: `{dn_depot}`  ·  x={depot_xy[0]:.0f}  y={depot_xy[1]:.0f}")
    else:
        st.error(f"No se pudo interpretar '{depot_texto}'. Formato: CL 128 7C 35")

# ── Ruteo por sector ──────────────────────────────────────────────────────────
st.divider()
st.subheader("🚦 Rutas por sector")

sectores           = df_match["cod_sec"].dropna().unique()
sectores_ordenados = sorted(sectores)
frames_rutados     = []

for sector in sectores_ordenados:
    df_sec = df_match[df_match["cod_sec"] == sector].copy()
    df_sec = rutear_sector(df_sec, depot_xy=depot_xy)
    df_sec["ruta"] = df_sec["ruta"].astype("Int64")
    frames_rutados.append(df_sec)

    n_total   = len(df_sec)
    n_validos = df_sec["ruta"].notna().sum()
    dist_total = df_sec["dist_m"].sum(skipna=True)

    with st.expander(f"📍 Sector **{sector}** — {n_total} entregas · {dist_total:,.0f} m totales", expanded=False):

        # ── Tabla de ruta con distancias ──────────────────────────────────────
        cols_mostrar = ["ruta", "serial", "dirdes1", "cod_sec", "dist_m", "dist_acum_m"]
        df_show = df_sec[cols_mostrar].sort_values("ruta").reset_index(drop=True)
        st.dataframe(
            df_show.style.format(
                {"dist_m": "{:.0f} m", "dist_acum_m": "{:.0f} m"},
                na_rep="—",
            ),
            use_container_width=True,
            height=min(400, 35 * len(df_show) + 40),
        )
        st.caption(f"{n_validos} con coordenadas · {n_total - n_validos} sin dir_num · distancia total ≈ **{dist_total:,.0f} m**")

        # ── Corrección de dirección ───────────────────────────────────────────
        with st.expander("✏️ Corregir dirección de este sector"):
            seriales_sec = df_sec["serial"].dropna().tolist()
            serial_sel   = st.selectbox(
                "Serial a corregir",
                options=seriales_sec,
                key=f"sel_{sector}",
                format_func=lambda s: f"{s}  —  {df_sec.loc[df_sec['serial']==s, 'dirdes1'].values[0] if s in df_sec['serial'].values else ''}",
            )

            dir_actual = df_sec.loc[df_sec["serial"] == serial_sel, "dirdes1"].values
            dir_actual = dir_actual[0] if len(dir_actual) else ""

            nueva_dir = st.text_input(
                "Nueva dirección (ej: CL 127A 7 53)",
                value=dir_actual,
                key=f"dir_{sector}_{serial_sel}",
            )

            if st.button("Calcular y aplicar", key=f"btn_{sector}_{serial_sel}"):
                dn = texto_a_dirnum(nueva_dir)
                if dn is None:
                    st.error("No se pudo interpretar la dirección. Formato esperado: CL/CR/DG número[letra] número[letra] placa")
                else:
                    xy = coordenadas_dirnum(dn, factores)
                    if xy[0] is None:
                        st.error(f"dir_num generado ({dn}) no produce coordenadas válidas.")
                    else:
                        st.session_state.correcciones[serial_sel] = {
                            "dir_num": dn,
                            "x":       xy[0],
                            "y":       xy[1],
                        }
                        st.success(f"Corregido: dir_num={dn}  x={xy[0]:.0f}  y={xy[1]:.0f}")
                        st.rerun()

# ── Resultado consolidado ─────────────────────────────────────────────────────
st.divider()
df_final = pd.concat(frames_rutados, ignore_index=True)
df_final = df_final[["ruta", "serial", "cod_sec", "dirdes1", "dir_num", "dist_m", "dist_acum_m"]]

st.subheader("📋 Resultado consolidado")
st.dataframe(
    df_final.style.format(
        {"dist_m": "{:.0f} m", "dist_acum_m": "{:.0f} m"},
        na_rep="—",
    ),
    use_container_width=True,
    height=400,
)

# ── Descargar ─────────────────────────────────────────────────────────────────
buf = io.BytesIO()
with pd.ExcelWriter(buf, engine="openpyxl") as writer:
    df_final.to_excel(writer, index=False, sheet_name="Ruteo")
    for sector in sectores_ordenados:
        df_s = df_final[df_final["cod_sec"] == sector].copy()
        nombre_hoja = re.sub(r"[\\/*?:\[\]]", "_", str(sector))[:31]
        df_s.to_excel(writer, index=False, sheet_name=nombre_hoja)

st.download_button(
    "⬇️ Descargar resultado Excel",
    data=buf.getvalue(),
    file_name="ruteo_sectores.xlsx",
    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    type="primary",
)
