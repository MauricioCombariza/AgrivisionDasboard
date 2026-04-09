"""
Tests: sincronizar_periodo no modifica planillas aseguradas.

Escenarios cubiertos:
  1. Planilla en planillas_revisadas     → no toca nada (ni SELECT)
  2. Planilla con candado (editado=1)    → el SELECT se hace pero no INSERT
  3. Registro con candado a nivel fila   → UPDATE WHERE editado_manualmente=0 no cuenta
  4. Planilla libre, registro nuevo      → INSERT normal
  5. Planilla libre, registro existente  → UPDATE normal
"""
import sys
from unittest.mock import MagicMock, patch
import pytest
import pandas as pd

# ── Silenciar módulos que ejecutan código de UI al importar ──────────────────
for _mod in ('mysql', 'mysql.connector', 'dotenv'):
    sys.modules.setdefault(_mod, MagicMock())

# streamlit: tabs y columns devuelven iterables del tamaño correcto
_st = MagicMock()
_st.tabs.side_effect    = lambda labels: [MagicMock() for _ in labels]
_st.columns.side_effect = lambda spec: [MagicMock() for _ in (spec if isinstance(spec, (list, tuple)) else range(spec))]
sys.modules['streamlit'] = _st

# load_dotenv() se llama al importar el módulo; con el mock no hace nada
from pages_home.Agrupacion_Escaner import sincronizar_periodo  # noqa: E402


# ── Helpers ──────────────────────────────────────────────────────────────────
def _row(lot_esc='400202', cod_men='0519', serial='S001',
         f_esc='2025.04.09', orden=1, mot_esc='Entrega', no_entidad='CLIENTE A'):
    """Fila mínima que representa un registro del CSV."""
    return dict(f_esc=f_esc, cod_men=cod_men, lot_esc=lot_esc,
                orden=orden, mot_esc=mot_esc, no_entidad=no_entidad, serial=serial)


def _make_conn(revisadas=(), candado=(), existente=None, rowcount=0):
    """
    Construye un MagicMock de conexión MySQL para sincronizar_periodo.

    Con las funciones helper parcheadas, el código llama cursor() exactamente
    3 veces en orden:
      1. _cur_rev   → planillas_revisadas
      2. _cur_lock  → lotes con editado_manualmente=1
      3. cursor_reg → loop principal (SELECT / UPDATE / INSERT)

    revisadas : iterable de lot_esc que están en planillas_revisadas
    candado   : iterable de lot_esc que tienen algún registro con editado=1
    existente : valor que devuelve fetchone() al buscar registro en DB
                None  → no existe → candidato a INSERT
                (42,) → existe   → candidato a UPDATE
    rowcount  : filas afectadas por el último UPDATE (0 = bloqueado por candado)
    """
    conn = MagicMock()

    cur_rev = MagicMock()
    cur_rev.fetchall.return_value = [(r,) for r in revisadas]

    cur_lock = MagicMock()
    cur_lock.fetchall.return_value = [(c,) for c in candado]

    cur_reg = MagicMock()
    cur_reg.fetchone.return_value = existente
    cur_reg.rowcount = rowcount

    conn.cursor.side_effect = [cur_rev, cur_lock, cur_reg]
    return conn, cur_reg


def _sql_calls(cur_reg):
    """Devuelve la lista de SQLs enviados al cursor principal."""
    return [
        (c.args[0] if c.args else '').upper()
        for c in cur_reg.execute.call_args_list
    ]


# ── Decoradores comunes ───────────────────────────────────────────────────────
_PATCH = (
    patch('pages_home.Agrupacion_Escaner.cargar_mapeos',            return_value={}),
    patch('pages_home.Agrupacion_Escaner.cargar_precios_mensajero', return_value={}),
    patch('pages_home.Agrupacion_Escaner.cargar_personal_bd',       return_value={}),
)


def _apply_patches(fn):
    for p in reversed(_PATCH):
        fn = p(fn)
    return fn


# ── Test 1: planilla en planillas_revisadas → no se toca nada ────────────────
@_apply_patches
def test_planilla_revisada_no_ejecuta_sql(*_):
    """
    Si lot_esc está en planillas_revisadas el sync hace 'continue' antes
    de cualquier consulta: cursor_reg nunca debe llamarse.
    """
    conn, cur_reg = _make_conn(revisadas=['400202'])
    df = pd.DataFrame([
        _row(lot_esc='400202', cod_men='0519', serial='S001'),
        _row(lot_esc='400202', cod_men='0030', serial='S002'),
    ])

    result = sincronizar_periodo(df, conn)

    assert result['insertados'] == 0, "No debe insertar en planilla revisada"
    assert result['actualizados'] == 0, "No debe actualizar en planilla revisada"
    cur_reg.execute.assert_not_called()


# ── Test 2: planilla con candado → no se inserta registro nuevo ──────────────
@_apply_patches
def test_planilla_con_candado_bloquea_insert(*_):
    """
    Si lot_esc tiene algún registro con editado_manualmente=1 (lotes_con_candado),
    y el CSV trae un registro que no existe en DB, no debe ejecutarse INSERT.
    El SELECT para verificar existencia sí se ejecuta.
    """
    conn, cur_reg = _make_conn(candado=['400202'], existente=None)
    df = pd.DataFrame([_row(lot_esc='400202', cod_men='0000', serial='S099')])

    result = sincronizar_periodo(df, conn)

    assert result['insertados'] == 0, "No debe insertar en planilla con candado"
    sqls = _sql_calls(cur_reg)
    assert not any('INSERT' in s for s in sqls), f"INSERT inesperado. SQLs: {sqls}"


# ── Test 3: registro con candado a nivel fila → UPDATE no cuenta ─────────────
@_apply_patches
def test_registro_con_candado_fila_no_actualiza(*_):
    """
    El UPDATE incluye WHERE editado_manualmente = 0.
    Si el registro tiene editado_manualmente=1, rowcount=0 y no se cuenta
    como actualizado.
    """
    # existente=(42,) → registro existe; rowcount=0 → el WHERE bloqueó el UPDATE
    conn, cur_reg = _make_conn(existente=(42,), rowcount=0)
    df = pd.DataFrame([_row(lot_esc='400100', serial='S010')])

    result = sincronizar_periodo(df, conn)

    assert result['actualizados'] == 0, "No debe contar UPDATE bloqueado por candado"
    sqls = _sql_calls(cur_reg)
    assert any('UPDATE' in s for s in sqls), "El UPDATE debe intentarse (WHERE filtra)"
    assert result['insertados'] == 0


# ── Test 4: planilla libre, registro nuevo → INSERT ──────────────────────────
@_apply_patches
def test_planilla_libre_inserta(*_):
    """
    Planilla sin revisada ni candado, registro no existe en DB → INSERT.
    """
    conn, cur_reg = _make_conn(existente=None)
    df = pd.DataFrame([_row(lot_esc='400300', serial='S020')])

    result = sincronizar_periodo(df, conn)

    assert result['insertados'] == 1
    sqls = _sql_calls(cur_reg)
    assert any('INSERT' in s for s in sqls)


# ── Test 5: planilla libre, registro existente desbloqueado → UPDATE cuenta ──
@_apply_patches
def test_planilla_libre_actualiza(*_):
    """
    Planilla libre, registro existe en DB con editado_manualmente=0 → UPDATE
    afecta la fila y se cuenta como actualizado.
    """
    conn, cur_reg = _make_conn(existente=(55,), rowcount=1)
    df = pd.DataFrame([_row(lot_esc='400300', serial='S030')])

    result = sincronizar_periodo(df, conn)

    assert result['actualizados'] == 1
    assert result['insertados'] == 0
