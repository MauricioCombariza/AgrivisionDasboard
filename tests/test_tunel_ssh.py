"""
Tests para la gestión del túnel SSH en 14_Actualizacion_Nube.py
"""

import sys
import subprocess
from unittest.mock import MagicMock, patch, call
import pytest

# ── Silenciar módulos de UI al importar ──────────────────────────────────────
for _mod_name in ("mysql", "mysql.connector", "dotenv", "sqlalchemy", "paramiko"):
    sys.modules.setdefault(_mod_name, MagicMock())

_st = MagicMock()
_st.tabs.side_effect    = lambda labels: [MagicMock() for _ in labels]
_st.columns.side_effect = lambda spec: [MagicMock() for _ in (spec if isinstance(spec, (list, tuple)) else range(spec))]
_st.expander.return_value.__enter__ = lambda s: s
_st.expander.return_value.__exit__  = MagicMock(return_value=False)
_st.spinner.return_value.__enter__  = lambda s: s
_st.spinner.return_value.__exit__   = MagicMock(return_value=False)
sys.modules["streamlit"] = _st

import importlib.util, pathlib
_spec = importlib.util.spec_from_file_location(
    "actualizacion_nube",
    pathlib.Path(__file__).parent.parent / "pages_logistica" / "14_Actualizacion_Nube.py",
)
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)

_LG_PORT = _mod._LG_PORT
ERR_111  = Exception(f"2003 (HY000): Can't connect to MySQL server on 'localhost:{_LG_PORT}' (111)")


# ─────────────────────────────────────────────────────────────────────────────
# _tunel_activo — parchamos subprocess dentro del módulo cargado
# ─────────────────────────────────────────────────────────────────────────────

def _mock_ss(stdout_text):
    r = MagicMock()
    r.stdout = stdout_text
    return r


def test_tunel_activo_cuando_puerto_aparece_en_ss():
    stdout = f"LISTEN 0 128 127.0.0.1:{_LG_PORT} 0.0.0.0:*\n"
    with patch.object(_mod.subprocess, "run", return_value=_mock_ss(stdout)):
        assert _mod._tunel_activo() is True


def test_tunel_inactivo_cuando_puerto_no_aparece():
    # Usar _LG_PORT+1 para que el stdout nunca contenga el puerto real del túnel
    otro_puerto = _LG_PORT + 1
    stdout = f"LISTEN 0 128 127.0.0.1:{otro_puerto} 0.0.0.0:*\n"
    with patch.object(_mod.subprocess, "run", return_value=_mock_ss(stdout)):
        assert _mod._tunel_activo() is False


def test_tunel_inactivo_si_ss_lanza_excepcion():
    with patch.object(_mod.subprocess, "run", side_effect=Exception("ss no disponible")):
        assert _mod._tunel_activo() is False


# ─────────────────────────────────────────────────────────────────────────────
# _abrir_tunel — parchamos _tunel_activo y subprocess en el módulo
# ─────────────────────────────────────────────────────────────────────────────

def test_abrir_tunel_exitoso():
    # _tunel_activo: False (primer check) → True (en el polling)
    with patch.object(_mod, "_tunel_activo", side_effect=[False, True]), \
         patch.object(_mod.subprocess, "Popen", return_value=MagicMock()), \
         patch.object(_mod.time, "sleep"):
        ok, msg = _mod._abrir_tunel()
    assert ok is True


def test_abrir_tunel_no_lanza_ssh_si_ya_activo():
    with patch.object(_mod, "_tunel_activo", return_value=True), \
         patch.object(_mod.subprocess, "Popen") as mock_popen:
        ok, msg = _mod._abrir_tunel()
    mock_popen.assert_not_called()
    assert ok is True


def test_abrir_tunel_falla_si_popen_lanza_excepcion():
    with patch.object(_mod, "_tunel_activo", return_value=False), \
         patch.object(_mod.subprocess, "Popen", side_effect=OSError("ssh no encontrado")):
        ok, msg = _mod._abrir_tunel()
    assert ok is False
    assert len(msg) > 0


def test_abrir_tunel_falla_si_puerto_no_levanta_tras_ssh():
    # Popen tiene éxito pero el puerto nunca levanta en el polling
    with patch.object(_mod, "_tunel_activo", return_value=False), \
         patch.object(_mod.subprocess, "Popen", return_value=MagicMock()), \
         patch.object(_mod.time, "sleep"):
        ok, msg = _mod._abrir_tunel()
    assert ok is False


# ─────────────────────────────────────────────────────────────────────────────
# _conectar_logistica — auto-apertura de túnel
# ─────────────────────────────────────────────────────────────────────────────

def test_conectar_abre_tunel_automaticamente_en_error_111():
    conn_ok = MagicMock()
    with patch.object(_mod.mysql.connector, "connect",
                      side_effect=[ERR_111, conn_ok]), \
         patch.object(_mod, "_abrir_tunel", return_value=(True, "Túnel abierto")):
        result = _mod._conectar_logistica()
    assert result is conn_ok


def test_conectar_retorna_none_si_tunel_abre_pero_mysql_sigue_fallando():
    with patch.object(_mod.mysql.connector, "connect",
                      side_effect=[ERR_111, ERR_111]), \
         patch.object(_mod, "_abrir_tunel", return_value=(True, "OK")):
        result = _mod._conectar_logistica()
    assert result is None


def test_conectar_retorna_none_si_tunel_no_puede_abrirse():
    with patch.object(_mod.mysql.connector, "connect", side_effect=ERR_111), \
         patch.object(_mod, "_abrir_tunel", return_value=(False, "SSH falló")):
        result = _mod._conectar_logistica()
    assert result is None


def test_conectar_no_intenta_tunel_en_error_distinto_a_111():
    """Errores que no son Connection refused no deben intentar abrir túnel."""
    err_otro = Exception("Access denied for user 'root'")
    with patch.object(_mod.mysql.connector, "connect", side_effect=err_otro), \
         patch.object(_mod, "_abrir_tunel") as mock_tunel:
        result = _mod._conectar_logistica()
    mock_tunel.assert_not_called()
    assert result is None


# ─────────────────────────────────────────────────────────────────────────────
# Estado real del túnel (informativo, nunca falla)
# ─────────────────────────────────────────────────────────────────────────────

def test_tunel_activo_en_entorno_actual():
    activo = _mod._tunel_activo()
    print(f"\nEstado túnel SSH (puerto {_LG_PORT}): {'ACTIVO' if activo else 'INACTIVO'}")
