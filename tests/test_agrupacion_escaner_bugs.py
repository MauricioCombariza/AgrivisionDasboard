"""
Tests para los bugs detectados en Agrupacion_Escaner:

1. cargar_personal_bd retorna {} cuando la conexión está caída → mensajeros "Sin asignar"
2. Registros insertados=0 | actualizados=0 cuando editado_manualmente=1 bloquea UPDATE
3. Formato de cod_men (zfill 4) debe coincidir con lo que devuelve la BD
4. Lógica de reasignación de código 0999
5. get_db() intenta reconexion cuando la conexión cached está caída
"""
import sys
from unittest.mock import MagicMock, patch, call
import pytest
import pandas as pd

# ── Silenciar módulos de UI al importar ──────────────────────────────────────
for _mod in ('mysql', 'mysql.connector', 'dotenv'):
    sys.modules.setdefault(_mod, MagicMock())

_st = MagicMock()
_st.tabs.side_effect    = lambda labels: [MagicMock() for _ in labels]
_st.columns.side_effect = lambda spec: [MagicMock() for _ in (spec if isinstance(spec, (list, tuple)) else range(spec))]
sys.modules['streamlit'] = _st

from pages_home.Agrupacion_Escaner import (  # noqa: E402
    sincronizar_periodo,
    cargar_personal_bd,
    get_db,
    conectar_db,
)


# ─────────────────────────────────────────────────────────────────────────────
# Bug 1: cargar_personal_bd retorna {} cuando la conexión está caída
# ─────────────────────────────────────────────────────────────────────────────

def test_cargar_personal_bd_conexion_caida_retorna_vacio():
    """Si el cursor lanza excepción (conexión caída), debe retornar {} sin crashear."""
    conn = MagicMock()
    conn.cursor.side_effect = Exception("MySQL Connection not available")

    resultado = cargar_personal_bd(conn)

    assert resultado == {}, "Debe retornar dict vacío ante conexión caída"


def test_cargar_personal_bd_retorna_datos_correctos():
    """Con conexión OK, debe mapear codigo → {id, nombre}."""
    conn = MagicMock()
    cursor = MagicMock()
    cursor.fetchall.return_value = [
        {'codigo': '0599', 'id': 42, 'nombre_completo': 'Juan Perez'},
        {'codigo': '0022', 'id': 10, 'nombre_completo': 'Luis Gomez'},
    ]
    conn.cursor.return_value = cursor

    resultado = cargar_personal_bd(conn)

    assert '0599' in resultado, "0599 debe estar en el resultado"
    assert resultado['0599']['id'] == 42
    assert resultado['0599']['nombre'] == 'Juan Perez'
    assert '0022' in resultado


def test_cargar_personal_bd_codigo_formato_4_digitos():
    """El lookup usa zfill(4); si la BD guarda '599' sin padding no coincide → bug latente."""
    conn = MagicMock()
    cursor = MagicMock()
    # BD guarda CON padding (correcto)
    cursor.fetchall.return_value = [{'codigo': '0599', 'id': 1, 'nombre_completo': 'X'}]
    conn.cursor.return_value = cursor

    resultado = cargar_personal_bd(conn)

    # El cod_men del CSV pasa por zfill(4) → '0599'
    assert resultado.get('0599') is not None, "Lookup '0599' debe encontrar el registro"
    # Si la BD guardara '599' (sin padding) no habría match — este test documenta el contrato
    assert resultado.get('599') is None, "Sin padding no debe existir como key"


# ─────────────────────────────────────────────────────────────────────────────
# Bug 2: editado_manualmente=1 bloquea UPDATE → 0 | 0 sin mensaje claro
# ─────────────────────────────────────────────────────────────────────────────

def _conn_para_sync(revisadas=(), candado=(), existente=None, rowcount=0):
    conn = MagicMock()
    cur_rev  = MagicMock(); cur_rev.fetchall.return_value  = [(r,) for r in revisadas]
    cur_lock = MagicMock(); cur_lock.fetchall.return_value = [(c,) for c in candado]
    cur_reg  = MagicMock(); cur_reg.fetchone.return_value  = existente
    cur_reg.rowcount = rowcount
    conn.cursor.side_effect = [cur_rev, cur_lock, cur_reg]
    return conn, cur_reg


_PATCHES = (
    patch('pages_home.Agrupacion_Escaner.cargar_mapeos',            return_value={}),
    patch('pages_home.Agrupacion_Escaner.cargar_precios_mensajero', return_value={}),
    patch('pages_home.Agrupacion_Escaner.cargar_personal_bd',       return_value={}),
)

def _apply(fn):
    for p in reversed(_PATCHES):
        fn = p(fn)
    return fn


@_apply
def test_update_bloqueado_por_candado_manual_da_0_actualizados(*_):
    """
    Si el registro existe (fetchone devuelve un id) pero tiene editado_manualmente=1
    (rowcount=0 en el UPDATE), actualizados debe ser 0.
    Este es el escenario donde el usuario ve 'insertados: 0 | actualizados: 0'.
    """
    conn, cur_reg = _conn_para_sync(existente=(99,), rowcount=0)
    df = pd.DataFrame([
        dict(f_esc='2025.04.09', cod_men='0519', lot_esc='400202',
             orden=1, mot_esc='Entrega', no_entidad='CLIENTE A', serial='S001'),
    ])

    result = sincronizar_periodo(df, conn)

    assert result['actualizados'] == 0
    assert result['insertados'] == 0
    # Verifica que el UPDATE sí se intentó (pero rowcount fue 0)
    sqls = [c.args[0].upper() for c in cur_reg.execute.call_args_list if c.args]
    assert any('UPDATE' in s for s in sqls), "Debe intentar UPDATE aunque editado_manualmente lo bloquee"


@_apply
def test_registro_nuevo_libre_se_inserta(*_):
    """Registro nuevo (existente=None) en planilla sin candado → INSERT ejecutado."""
    conn, cur_reg = _conn_para_sync(existente=None)
    df = pd.DataFrame([
        dict(f_esc='2025.04.09', cod_men='0519', lot_esc='400202',
             orden=1, mot_esc='Entrega', no_entidad='CLIENTE A', serial='S001'),
    ])

    result = sincronizar_periodo(df, conn)

    assert result['insertados'] == 1
    sqls = [c.args[0].upper() for c in cur_reg.execute.call_args_list if c.args]
    assert any('INSERT' in s for s in sqls)


@_apply
def test_registro_existente_sin_candado_se_actualiza(*_):
    """Registro existente + editado_manualmente=0 (rowcount=1) → actualizados=1."""
    conn, cur_reg = _conn_para_sync(existente=(99,), rowcount=1)
    df = pd.DataFrame([
        dict(f_esc='2025.04.09', cod_men='0519', lot_esc='400202',
             orden=1, mot_esc='Entrega', no_entidad='CLIENTE A', serial='S001'),
    ])

    result = sincronizar_periodo(df, conn)

    assert result['actualizados'] == 1
    assert result['insertados'] == 0


# ─────────────────────────────────────────────────────────────────────────────
# Formato cod_men: zfill(4) en sincronizar_periodo
# ─────────────────────────────────────────────────────────────────────────────

@_apply
def test_cod_men_con_caracter_sucio_se_normaliza(*_):
    """
    Codigo con '}' u otros no-dígitos debe limpiarse y quedar con zfill(4).
    Ej: '519}' → '0519'
    """
    conn, cur_reg = _conn_para_sync(existente=None)
    df = pd.DataFrame([
        dict(f_esc='2025.04.09', cod_men='519}', lot_esc='400202',
             orden=1, mot_esc='Entrega', no_entidad='CLIENTE A', serial='S001'),
    ])

    result = sincronizar_periodo(df, conn)

    # El INSERT debe haberse llamado con cod_mensajero='0519'
    insert_calls = [c for c in cur_reg.execute.call_args_list
                    if c.args and 'INSERT' in c.args[0].upper()]
    assert len(insert_calls) == 1
    params = insert_calls[0].args[1]  # tupla de parámetros
    cod_idx = 1  # posicion de cod_mensajero en el INSERT
    assert params[cod_idx] == '0519', f"Se esperaba '0519', se obtuvo '{params[cod_idx]}'"


# ─────────────────────────────────────────────────────────────────────────────
# Reasignación de código 0999
# ─────────────────────────────────────────────────────────────────────────────

@_apply
def test_0999_se_reasigna_cuando_hay_exactamente_2_codigos(*_):
    """
    Lote con cod 0999 y otro cod → 0999 debe reasignarse al otro código antes de INSERT.
    """
    conn, cur_reg = _conn_para_sync(existente=None)
    df = pd.DataFrame([
        dict(f_esc='2025.04.09', cod_men='0519', lot_esc='400202',
             orden=1, mot_esc='Entrega', no_entidad='CLIENTE A', serial='S001'),
        dict(f_esc='2025.04.09', cod_men='0999', lot_esc='400202',
             orden=1, mot_esc='Entrega', no_entidad='CLIENTE A', serial='S002'),
    ])

    result = sincronizar_periodo(df, conn)

    # Tras reasignación, ambos S001 y S002 tienen cod_men='0519' → 1 grupo, 2 seriales
    assert result['grupos'] == 1, "Deben agruparse bajo un solo codigo tras reasignacion"
    insert_calls = [c for c in cur_reg.execute.call_args_list
                    if c.args and 'INSERT' in c.args[0].upper()]
    assert len(insert_calls) == 1
    params = insert_calls[0].args[1]
    assert params[1] == '0519', "El INSERT debe usar '0519', no '0999'"


@_apply
def test_0999_no_se_reasigna_cuando_es_el_unico_codigo(*_):
    """Lote con solo 0999 (sin otro código) no se toca."""
    conn, cur_reg = _conn_para_sync(existente=None)
    df = pd.DataFrame([
        dict(f_esc='2025.04.09', cod_men='0999', lot_esc='400202',
             orden=1, mot_esc='Entrega', no_entidad='CLIENTE A', serial='S001'),
    ])

    sincronizar_periodo(df, conn)

    insert_calls = [c for c in cur_reg.execute.call_args_list
                    if c.args and 'INSERT' in c.args[0].upper()]
    assert len(insert_calls) == 1
    params = insert_calls[0].args[1]
    assert params[1] == '0999', "Sin reasignacion posible debe quedar como 0999"


# ─────────────────────────────────────────────────────────────────────────────
# get_db: reconexion cuando la conexion cached está caída
# ─────────────────────────────────────────────────────────────────────────────

def test_get_db_reconnects_when_ping_fails():
    """
    get_db() debe llamar ping(reconnect=True). Si falla, limpia cache y reconecta.
    """
    conn_vivo = MagicMock()
    conn_vivo.ping.side_effect = Exception("gone away")

    with patch('pages_home.Agrupacion_Escaner.conectar_db') as mock_cache:
        # Primera llamada: conexion caída; segunda: conexion nueva
        conn_nuevo = MagicMock()
        conn_nuevo.ping.return_value = None
        mock_cache.side_effect = [conn_vivo, conn_nuevo]
        mock_cache.clear = MagicMock()

        result = get_db()

        mock_cache.clear.assert_called_once()
        assert result is conn_nuevo


def test_get_db_devuelve_conexion_sana_sin_reconectar():
    """Si ping tiene éxito, devuelve la misma conexion sin limpiar cache."""
    conn_ok = MagicMock()
    conn_ok.ping.return_value = None

    with patch('pages_home.Agrupacion_Escaner.conectar_db', return_value=conn_ok) as mock_cache:
        mock_cache.clear = MagicMock()

        result = get_db()

        mock_cache.clear.assert_not_called()
        assert result is conn_ok
