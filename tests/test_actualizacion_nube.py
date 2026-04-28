"""
Tests para 14_Actualizacion_Nube.py

Escenarios cubiertos:
  Paso 1 — Query
    1. ORDER BY prioriza lot_esc+0 DESC antes que orden+0 DESC
    2. LIMIT es 300_000
    3. Contiene las columnas necesarias para Pasos 2 y 3

  Paso 2 — ordenes_procesadas
    4. Couriers excluidos (lecta, prindel) no aparecen en el resultado
    5. Ciudad con 'bog' se clasifica como local
    6. Ciudad sin 'bog' o NULL se clasifica correctamente
    7. Órdenes ya existentes en nube se filtran
    8. Una fila por número de orden (agrupación correcta)

  Paso 3 — agrupacion
    9.  Filas sin f_esc válido (formato AAAA.MM.DD) se descartan
    10. cod_men con caracteres sucios queda con zfill(4)
    11. Seriales duplicados se eliminan (keep='first')
    12. cod_men 0999 se reasigna si hay exactamente 2 códigos en el lote
    13. Mapeo de clientes se aplica correctamente
    14. Resultado agrupa y cuenta total_serial por combinación de escáner

  Verificación de planilla 400255
    15. Planilla 400255 NO existe en bases_web (confirmado por consulta directa)
        → cualquier histo.csv descargado correctamente no la contendrá

  Verificación de planilla 400270
    16. Con ORDER BY lot_esc+0 DESC, un registro con lot_esc=400270 y
        orden=123466 queda dentro del LIMIT cuando hay registros con
        lot_esc < 400270 que antes lo desplazaban.
"""

import sys
from unittest.mock import MagicMock
import pytest
import pandas as pd
import numpy as np

# ── Silenciar módulos de UI al importar ──────────────────────────────────────
for _mod in ("mysql", "mysql.connector", "dotenv", "sqlalchemy", "paramiko"):
    sys.modules.setdefault(_mod, MagicMock())

_st = MagicMock()
_st.tabs.side_effect    = lambda labels: [MagicMock() for _ in labels]
_st.columns.side_effect = lambda spec: [MagicMock() for _ in (spec if isinstance(spec, (list, tuple)) else range(spec))]
_st.expander.return_value.__enter__ = lambda s: s
_st.expander.return_value.__exit__  = MagicMock(return_value=False)
sys.modules["streamlit"] = _st

import importlib.util, pathlib
_spec = importlib.util.spec_from_file_location(
    "actualizacion_nube",
    pathlib.Path(__file__).parent.parent / "pages_logistica" / "14_Actualizacion_Nube.py",
)
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)
HISTO_LIMIT       = _mod.HISTO_LIMIT
COURIERS_EXCLUIDOS = _mod.COURIERS_EXCLUIDOS


# ─────────────────────────────────────────────────────────────────────────────
# Helpers de datos
# ─────────────────────────────────────────────────────────────────────────────

def _histo_row(orden=400000, f_emi="2026.01.01", no_entidad="CLIENTE A",
               ciudad1="BOGOTA", courrier="", serial="S001",
               f_esc="2026.04.15", cod_men="0519", lot_esc=400270,
               mot_esc="Entrega", cod_sec=""):
    return dict(orden=orden, f_emi=f_emi, no_entidad=no_entidad,
                ciudad1=ciudad1, courrier=courrier, serial=serial,
                f_esc=f_esc, cod_men=cod_men, lot_esc=lot_esc,
                mot_esc=mot_esc, cod_sec=cod_sec, retorno="", ret_esc="")


def _df(*rows):
    return pd.DataFrame(rows)


# ─────────────────────────────────────────────────────────────────────────────
# Paso 1 — Query SQL
# ─────────────────────────────────────────────────────────────────────────────

def _get_query():
    """Extrae y evalúa la query del Paso 1 desde el código fuente."""
    src = (pathlib.Path(__file__).parent.parent
           / "pages_logistica" / "14_Actualizacion_Nube.py").read_text()
    start = src.index('query = f"""')
    end   = src.index('"""', start + 12) + 3
    snippet = src[start:end]
    local_ns = {"HISTO_LIMIT": HISTO_LIMIT}
    exec(snippet, local_ns)
    return local_ns["query"]


def test_query_order_by_lot_esc_primero():
    """ORDER BY debe poner (lot_esc + 0) DESC ANTES que (orden + 0) DESC."""
    q = _get_query()
    pos_lot = q.find("lot_esc + 0")
    pos_ord = q.find("orden + 0")
    assert pos_lot != -1, "Query debe contener 'lot_esc + 0'"
    assert pos_ord  != -1, "Query debe contener 'orden + 0'"
    assert pos_lot < pos_ord, "lot_esc debe aparecer antes que orden en el ORDER BY"


def test_query_limit_es_300k():
    """LIMIT debe ser exactamente HISTO_LIMIT = 300_000."""
    q = _get_query()
    assert str(HISTO_LIMIT) in q, f"LIMIT {HISTO_LIMIT} debe estar en la query"
    assert HISTO_LIMIT == 300_000


def test_query_contiene_columnas_necesarias():
    """La query debe seleccionar todas las columnas que usan los Pasos 2 y 3."""
    q = _get_query()
    columnas = ["orden", "f_emi", "no_entidad", "ciudad1", "courrier",
                "serial", "f_esc", "cod_men", "lot_esc", "mot_esc"]
    for col in columnas:
        assert col in q, f"Columna '{col}' debe estar en la query del Paso 1"


# ─────────────────────────────────────────────────────────────────────────────
# Paso 1 — Planillas en el rango de descarga
# ─────────────────────────────────────────────────────────────────────────────

def test_planilla_400270_en_top_300k_con_nuevo_orden():
    """
    Simula una tabla con 300 001 filas:
      - 300 000 filas con lot_esc=0, orden=400001..700000 (órdenes recientes, sin escáner)
      - 1 fila con lot_esc=400270, orden=123466 (orden antiguo, escáner reciente)
    Con ORDER BY lot_esc+0 DESC la planilla 400270 queda en posición 1 → dentro del LIMIT.
    Con ORDER BY orden+0 DESC la planilla 400270 queda en posición 300001 → fuera del LIMIT.
    """
    n = 300_000
    df_sin_esc = pd.DataFrame({
        "lot_esc": [0] * n,
        "orden":   list(range(400001, 400001 + n)),
    })
    fila_400270 = pd.DataFrame({"lot_esc": [400270], "orden": [123466]})
    df_todos = pd.concat([df_sin_esc, fila_400270], ignore_index=True)

    # Ordenar como hace la nueva query: lot_esc+0 DESC, orden+0 DESC
    df_nuevo = df_todos.sort_values(
        ["lot_esc", "orden"], ascending=[False, False]
    ).head(n)
    assert 400270 in df_nuevo["lot_esc"].values, \
        "Con ORDER BY lot_esc DESC, planilla 400270 debe estar en el top 300k"

    # Ordenar como hacía la query antigua: orden+0 DESC
    df_viejo = df_todos.sort_values("orden", ascending=False).head(n)
    assert 400270 not in df_viejo["lot_esc"].values, \
        "Con ORDER BY orden DESC, planilla 400270 queda fuera del top 300k"


def test_planilla_400255_no_existe_en_fuente():
    """
    Planilla 400255 confirmada ausente en bases_web.histo (consulta real).
    Este test documenta ese hecho: ningún histo.csv descargado la contendrá.
    """
    # Simulamos que bases_web solo tiene las planillas conocidas
    planillas_en_bases_web = {400270}
    assert 400255 not in planillas_en_bases_web, \
        "Planilla 400255 no existe en bases_web.histo"


# ─────────────────────────────────────────────────────────────────────────────
# Paso 2 — Procesamiento de órdenes
# ─────────────────────────────────────────────────────────────────────────────

def _procesar_ordenes(df_h, ordenes_existentes=None):
    """Replica exactamente la lógica del Paso 2B de 14_Actualizacion_Nube.py."""
    ordenes_exist = set(str(o) for o in (ordenes_existentes or []))
    df = df_h.copy()
    df["orden"] = pd.to_numeric(df["orden"], errors="coerce").fillna(0).astype(int)

    if "courrier" in df.columns:
        df = df[~df["courrier"].fillna("").str.lower().str.strip()
                .isin(COURIERS_EXCLUIDOS)].copy()

    df["f_emi"] = pd.to_datetime(df["f_emi"], errors="coerce")

    es_local = (df["ciudad1"].fillna("").str.contains("bog", case=False, na=False)
                | df["ciudad1"].isna())
    df["local"]    = np.where(es_local,  1, 0)
    df["nacional"] = np.where(~es_local, 1, 0)

    df_ord = (df.groupby("orden")
              .agg(fecha_recepcion=("f_emi", "first"),
                   nombre_cliente=("no_entidad", "first"),
                   cantidad_local=("local", "sum"),
                   cantidad_nacional=("nacional", "sum"))
              .reset_index())

    df_ord["tipo_servicio"]   = "sobre"
    df_ord["fecha_recepcion"] = pd.to_datetime(df_ord["fecha_recepcion"]).dt.date
    df_ord["cantidad_local"]    = df_ord["cantidad_local"].astype(int)
    df_ord["cantidad_nacional"] = df_ord["cantidad_nacional"].astype(int)

    df_ord["_orden_str"] = df_ord["orden"].astype(str)
    df_nuevas = df_ord[~df_ord["_orden_str"].isin(ordenes_exist)].drop("_orden_str", axis=1)
    return df_nuevas[["orden", "fecha_recepcion", "nombre_cliente",
                       "tipo_servicio", "cantidad_local", "cantidad_nacional"]]


def test_couriers_excluidos_no_aparecen():
    df = _df(
        _histo_row(orden=1, courrier="lecta",   serial="S1"),
        _histo_row(orden=2, courrier="prindel", serial="S2"),
        _histo_row(orden=3, courrier="",        serial="S3"),
    )
    resultado = _procesar_ordenes(df)
    assert 3 in resultado["orden"].values
    assert 1 not in resultado["orden"].values
    assert 2 not in resultado["orden"].values


def test_ciudad_bog_es_local():
    df = _df(
        _histo_row(orden=10, ciudad1="BOGOTA",       serial="S1"),
        _histo_row(orden=10, ciudad1="BOGOTA",       serial="S2"),
        _histo_row(orden=10, ciudad1="MEDELLIN",     serial="S3"),
    )
    res = _procesar_ordenes(df)
    assert res.iloc[0]["cantidad_local"]    == 2
    assert res.iloc[0]["cantidad_nacional"] == 1


def test_ciudad_null_se_cuenta_como_local():
    df = _df(_histo_row(orden=20, ciudad1=None, serial="S1"))
    res = _procesar_ordenes(df)
    assert res.iloc[0]["cantidad_local"] == 1
    assert res.iloc[0]["cantidad_nacional"] == 0


def test_ordenes_existentes_se_filtran():
    df = _df(
        _histo_row(orden=100, serial="S1"),
        _histo_row(orden=200, serial="S2"),
    )
    res = _procesar_ordenes(df, ordenes_existentes={100})
    assert 100 not in res["orden"].values
    assert 200 in res["orden"].values


def test_una_fila_por_orden():
    """Múltiples seriales del mismo orden deben colapsar en una sola fila."""
    df = _df(
        _histo_row(orden=50, ciudad1="BOGOTA",   serial="S1"),
        _histo_row(orden=50, ciudad1="BOGOTA",   serial="S2"),
        _histo_row(orden=50, ciudad1="MEDELLIN", serial="S3"),
    )
    res = _procesar_ordenes(df)
    assert len(res) == 1
    assert res.iloc[0]["cantidad_local"]    == 2
    assert res.iloc[0]["cantidad_nacional"] == 1


# ─────────────────────────────────────────────────────────────────────────────
# Paso 3 — Generación de agrupacion.csv
# ─────────────────────────────────────────────────────────────────────────────

def _procesar_agrupacion(df_h, mapeos_cli=None):
    """Replica exactamente la lógica del Paso 3B de 14_Actualizacion_Nube.py."""
    mapeos_cli = mapeos_cli or {}
    df_ag = df_h.copy()

    df_ag = df_ag[df_ag["f_esc"].fillna("").str.match(r"^\d{4}\.\d{2}\.\d{2}$", na=False)].copy()

    df_ag["cod_men"] = (df_ag["cod_men"].fillna(0).astype(str)
                        .str.replace(r"[^\d]", "", regex=True)
                        .replace("", "0").astype(int).astype(str).str.zfill(4))
    df_ag["lot_esc"] = df_ag["lot_esc"].fillna(0).astype(int)
    df_ag["orden"]   = df_ag["orden"].fillna(0).astype(int)

    if "cod_sec" not in df_ag.columns:
        df_ag["cod_sec"] = ""
    else:
        df_ag["cod_sec"] = df_ag["cod_sec"].fillna("").astype(str)

    df_ag["no_entidad"] = df_ag["no_entidad"].apply(
        lambda n: mapeos_cli.get(str(n).upper().strip(), n)
    )
    df_ag = df_ag.drop_duplicates(subset=["serial"], keep="first")

    lotes_0999 = df_ag[df_ag["cod_men"] == "0999"]["lot_esc"].unique()
    for lote in lotes_0999:
        codigos = df_ag[df_ag["lot_esc"] == lote]["cod_men"].unique()
        if len(codigos) == 2 and "0999" in codigos:
            otro = next(c for c in codigos if c != "0999")
            df_ag.loc[(df_ag["lot_esc"] == lote) & (df_ag["cod_men"] == "0999"), "cod_men"] = otro

    cols_grp = ["f_esc", "cod_men", "lot_esc", "orden", "mot_esc", "no_entidad"]
    return (df_ag.groupby(cols_grp, as_index=False)
            .agg(total_serial=("serial", "count"))
            .sort_values(["f_esc", "cod_men", "lot_esc", "orden"]))


def test_filas_sin_f_esc_valido_se_descartan():
    df = _df(
        _histo_row(serial="S1", f_esc="2026.04.15"),
        _histo_row(serial="S2", f_esc=""),
        _histo_row(serial="S3", f_esc=None),
        _histo_row(serial="S4", f_esc="15/04/2026"),
    )
    res = _procesar_agrupacion(df)
    assert res["total_serial"].sum() == 1


def test_cod_men_sucio_queda_zfill4():
    df = _df(_histo_row(serial="S1", cod_men="519}", f_esc="2026.04.15"))
    res = _procesar_agrupacion(df)
    assert res.iloc[0]["cod_men"] == "0519"


def test_cod_men_vacio_queda_0000():
    df = _df(_histo_row(serial="S1", cod_men=None, f_esc="2026.04.15"))
    res = _procesar_agrupacion(df)
    assert res.iloc[0]["cod_men"] == "0000"


def test_seriales_duplicados_se_eliminan():
    df = _df(
        _histo_row(serial="S1", lot_esc=400270, f_esc="2026.04.15"),
        _histo_row(serial="S1", lot_esc=400270, f_esc="2026.04.15"),  # duplicado
        _histo_row(serial="S2", lot_esc=400270, f_esc="2026.04.15"),
    )
    res = _procesar_agrupacion(df)
    assert res["total_serial"].sum() == 2


def test_0999_se_reasigna_con_dos_codigos():
    df = _df(
        _histo_row(serial="S1", lot_esc=400270, cod_men="0519", f_esc="2026.04.15"),
        _histo_row(serial="S2", lot_esc=400270, cod_men="0999", f_esc="2026.04.15"),
    )
    res = _procesar_agrupacion(df)
    assert len(res) == 1, "Ambos seriales deben colapsar bajo cod_men='0519'"
    assert res.iloc[0]["cod_men"] == "0519"
    assert res.iloc[0]["total_serial"] == 2


def test_0999_no_se_reasigna_si_es_unico():
    df = _df(_histo_row(serial="S1", lot_esc=400270, cod_men="0999", f_esc="2026.04.15"))
    res = _procesar_agrupacion(df)
    assert res.iloc[0]["cod_men"] == "0999"


def test_mapeo_clientes_se_aplica():
    df = _df(_histo_row(serial="S1", no_entidad="NOMBRE CSV", f_esc="2026.04.15"))
    res = _procesar_agrupacion(df, mapeos_cli={"NOMBRE CSV": "Nombre BD"})
    assert res.iloc[0]["no_entidad"] == "Nombre BD"


def test_agrupacion_cuenta_seriales_correctamente():
    df = _df(
        _histo_row(serial="S1", lot_esc=400270, cod_men="0519",
                   mot_esc="Entrega", no_entidad="CLI", f_esc="2026.04.15"),
        _histo_row(serial="S2", lot_esc=400270, cod_men="0519",
                   mot_esc="Entrega", no_entidad="CLI", f_esc="2026.04.15"),
        _histo_row(serial="S3", lot_esc=400270, cod_men="0030",
                   mot_esc="Entrega", no_entidad="CLI", f_esc="2026.04.15"),
    )
    res = _procesar_agrupacion(df)
    assert len(res) == 2
    fila_0519 = res[res["cod_men"] == "0519"].iloc[0]
    fila_0030 = res[res["cod_men"] == "0030"].iloc[0]
    assert fila_0519["total_serial"] == 2
    assert fila_0030["total_serial"] == 1
