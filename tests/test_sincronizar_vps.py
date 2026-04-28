"""
Tests para pages_home/SincronizarVPS.py

Cubre:
  1. Clave SSH encontrada en la ruta correcta
  2. verificar_conexion_vps() devuelve (True, None) cuando SSH responde OK
  3. verificar_conexion_vps() devuelve (False, mensaje) si la clave no existe
  4. verificar_conexion_vps() devuelve (False, mensaje) si SSH lanza excepción
  5. sincronizar_tabla() ejecuta dump → sftp.put → exec_command
  6. sincronizar_tabla() registra error si mysqldump falla
  7. descargar_tabla() ejecuta dump remoto → sftp.get → mysql local
  8. INTEGRACIÓN: SSH real al VPS responde OK
  9. INTEGRACIÓN: VPS tiene gestiones_mensajero actualizado (fecha reciente)
 10. INTEGRACIÓN: alerta si VPS tiene MENOS registros que local (sync perdería datos)
"""

import sys
import os
import subprocess
from unittest.mock import MagicMock, patch, call
import pytest

# ── Silenciar módulos de UI ───────────────────────────────────────────────────
for _mod in ("dotenv",):
    sys.modules.setdefault(_mod, MagicMock())

_st = MagicMock()
_st.title = MagicMock()
_st.info  = MagicMock()
_st.columns.side_effect = lambda spec: [MagicMock() for _ in (spec if isinstance(spec, (list, tuple)) else range(spec))]
_st.expander.return_value.__enter__ = lambda s: s
_st.expander.return_value.__exit__  = MagicMock(return_value=False)
sys.modules["streamlit"] = _st

import importlib.util, pathlib

_spec = importlib.util.spec_from_file_location(
    "sincronizar_vps",
    pathlib.Path(__file__).parent.parent / "pages_home" / "SincronizarVPS.py",
)
_mod = importlib.util.module_from_spec(_spec)

# Parchear paramiko y subprocess ANTES de ejecutar el módulo
_paramiko_mock = MagicMock()
sys.modules.setdefault("paramiko", _paramiko_mock)

with patch("subprocess.run", return_value=MagicMock(returncode=0, stdout="", stderr="")):
    _spec.loader.exec_module(_mod)

verificar_conexion_vps = _mod.verificar_conexion_vps
sincronizar_tabla      = _mod.sincronizar_tabla
descargar_tabla        = _mod.descargar_tabla
VPS_HOST               = _mod.VPS_HOST
VPS_KEY                = _mod.VPS_KEY
VPS_USER               = _mod.VPS_USER

SSH_KEY_REAL = "/home/mauro/.ssh/agrivision_vps"

# ─────────────────────────────────────────────────────────────────────────────
# TESTS UNITARIOS
# ─────────────────────────────────────────────────────────────────────────────

class TestClaveSSH:
    def test_clave_resuelta_correctamente(self):
        """VPS_KEY debe apuntar a un archivo existente (fallback a /home/mauro)."""
        assert os.path.exists(VPS_KEY), (
            f"Clave SSH no encontrada en '{VPS_KEY}'. "
            f"Verifica que exista en {SSH_KEY_REAL}"
        )

    def test_clave_no_es_directorio_root(self):
        """La ruta no debe resolver a /root/.ssh si la clave está en /home/mauro."""
        if os.path.exists(SSH_KEY_REAL):
            assert VPS_KEY == SSH_KEY_REAL, (
                f"VPS_KEY apunta a '{VPS_KEY}' pero la clave real está en '{SSH_KEY_REAL}'. "
                "Streamlit corre como root y ~ expande a /root."
            )


class TestVerificarConexion:
    def test_conexion_exitosa(self):
        """Devuelve (True, None) cuando SSH responde 'OK'."""
        with patch("os.path.exists", return_value=True):
            mock_client = MagicMock()
            mock_stdout = MagicMock()
            mock_stdout.read.return_value = b"OK"
            mock_client.exec_command.return_value = (MagicMock(), mock_stdout, MagicMock())

            with patch("paramiko.SSHClient", return_value=mock_client):
                ok, err = verificar_conexion_vps()

        assert ok is True
        assert err is None

    def test_clave_no_existe(self):
        """Devuelve (False, mensaje) cuando la clave SSH no existe en disco."""
        with patch("os.path.exists", return_value=False):
            ok, err = verificar_conexion_vps()

        assert ok is False
        assert err is not None
        assert "no encontrada" in err.lower() or "ssh" in err.lower()

    def test_excepcion_ssh_expone_mensaje(self):
        """Devuelve (False, str(e)) cuando paramiko lanza excepción."""
        with patch("os.path.exists", return_value=True):
            mock_client = MagicMock()
            mock_client.connect.side_effect = Exception("Connection timed out")

            with patch("paramiko.SSHClient", return_value=mock_client):
                ok, err = verificar_conexion_vps()

        assert ok is False
        assert "Connection timed out" in err


class TestSincronizarTabla:
    def _make_sftp(self):
        return MagicMock()

    def _make_ssh(self, stderr_output=b""):
        ssh = MagicMock()
        stdout = MagicMock()
        stdout.read.return_value = b""
        stdout.channel.recv_exit_status.return_value = 0
        stderr = MagicMock()
        stderr.read.return_value = stderr_output
        ssh.exec_command.return_value = (MagicMock(), stdout, stderr)
        return ssh

    def test_dump_exitoso_sube_y_ejecuta_import(self):
        """Happy path: dump → sftp.put → exec_command en VPS."""
        sftp = self._make_sftp()
        ssh  = self._make_ssh()
        log  = []

        dump_result = MagicMock(returncode=0, stdout="INSERT INTO ...", stderr="")

        with patch("subprocess.run", return_value=dump_result), \
             patch("os.unlink"):
            ok = sincronizar_tabla("logistica", "gestiones_mensajero",
                                   ssh, sftp, MagicMock(), log)

        assert ok is True
        sftp.put.assert_called_once()
        ssh.exec_command.assert_called_once()
        assert any("✅" in l for l in log)

    def test_dump_fallido_registra_error(self):
        """Si mysqldump devuelve returncode != 0, retorna False y loguea el error."""
        log = []
        dump_result = MagicMock(returncode=1, stdout="", stderr="Access denied")

        with patch("subprocess.run", return_value=dump_result):
            ok = sincronizar_tabla("logistica", "gestiones_mensajero",
                                   MagicMock(), MagicMock(), MagicMock(), log)

        assert ok is False
        assert any("❌" in l for l in log)

    def test_warnings_mysql_se_ignoran(self):
        """Los 'Warning' del stderr de mysql no deben aparecer en el log."""
        sftp = self._make_sftp()
        ssh  = self._make_ssh(stderr_output=b"Warning: Using a password on the command line\n")
        log  = []

        dump_result = MagicMock(returncode=0, stdout="INSERT INTO ...", stderr="")

        with patch("subprocess.run", return_value=dump_result), \
             patch("os.unlink"):
            ok = sincronizar_tabla("logistica", "gestiones_mensajero",
                                   ssh, sftp, MagicMock(), log)

        assert ok is True
        assert not any("Warning" in l for l in log)


class TestDescargarTabla:
    def test_descarga_exitosa(self):
        """Ejecuta dump remoto → sftp.get → mysql local → True."""
        ssh = MagicMock()
        stdout = MagicMock()
        stdout.read.return_value = b""
        stdout.channel.recv_exit_status.return_value = 0
        stderr = MagicMock()
        stderr.read.return_value = b""
        ssh.exec_command.return_value = (MagicMock(), stdout, stderr)

        sftp = MagicMock()
        log  = []

        import_result = MagicMock(returncode=0, stderr="")

        with patch("subprocess.run", return_value=import_result), \
             patch("builtins.open", MagicMock(return_value=MagicMock(
                 __enter__=lambda s: s,
                 __exit__=MagicMock(return_value=False),
                 read=MagicMock(return_value="-- SQL content")
             ))), \
             patch("os.unlink"):
            ok = descargar_tabla("logistica", "personal", ssh, sftp, log)

        assert ok is True
        sftp.get.assert_called_once()
        assert any("✅" in l for l in log)


# ─────────────────────────────────────────────────────────────────────────────
# TESTS DE INTEGRACIÓN (requieren acceso real al VPS vía SSH)
# ─────────────────────────────────────────────────────────────────────────────

def _ssh_disponible():
    """Devuelve True si la clave SSH existe y el VPS responde."""
    if not os.path.exists(SSH_KEY_REAL):
        return False
    try:
        r = subprocess.run(
            ["ssh", "-i", SSH_KEY_REAL, "-o", "StrictHostKeyChecking=no",
             "-o", "ConnectTimeout=8",
             f"root@{VPS_HOST}", "echo OK"],
            capture_output=True, text=True, timeout=12
        )
        return r.returncode == 0 and "OK" in r.stdout
    except Exception:
        return False


def _mysql_vps(query):
    """Ejecuta una query en el MySQL del VPS vía SSH y devuelve el stdout."""
    r = subprocess.run(
        ["ssh", "-i", SSH_KEY_REAL, "-o", "StrictHostKeyChecking=no",
         f"root@{VPS_HOST}",
         f'mysql -uroot -pRoot2024! logistica -e "{query}"'],
        capture_output=True, text=True, timeout=30
    )
    return r.stdout.strip()


def _mysql_local(query):
    """Ejecuta una query en MySQL local."""
    r = subprocess.run(
        ["mysql", "-uroot", "-pVale2010", "logistica", "-e", query],
        capture_output=True, text=True, timeout=30
    )
    return r.stdout.strip()


@pytest.mark.skipif(not _ssh_disponible(), reason="VPS no accesible vía SSH")
class TestIntegracionVPS:
    def test_ssh_conecta_y_responde(self):
        """La conexión SSH al VPS funciona y el servidor responde."""
        r = subprocess.run(
            ["ssh", "-i", SSH_KEY_REAL, "-o", "StrictHostKeyChecking=no",
             f"root@{VPS_HOST}", "echo OK"],
            capture_output=True, text=True, timeout=12
        )
        assert r.returncode == 0, f"SSH falló: {r.stderr}"
        assert "OK" in r.stdout

    def test_vps_mysql_accesible(self):
        """MySQL en el VPS responde a consultas."""
        salida = _mysql_vps("SELECT 1 AS ping;")
        assert "1" in salida, f"MySQL VPS no respondió correctamente: {salida}"

    def test_vps_tiene_tabla_gestiones(self):
        """La tabla gestiones_mensajero existe en el VPS."""
        salida = _mysql_vps("SHOW TABLES LIKE 'gestiones_mensajero';")
        assert "gestiones_mensajero" in salida

    def test_comparar_conteos_local_vs_vps(self):
        """
        Compara registros en gestiones_mensajero entre local y VPS.
        ALERTA si VPS tiene MÁS registros que local — sincronizar eliminaría datos.
        """
        local_raw = _mysql_local("SELECT COUNT(*) FROM gestiones_mensajero;")
        vps_raw   = _mysql_vps("SELECT COUNT(*) FROM gestiones_mensajero;")

        local_count = int([l for l in local_raw.splitlines() if l.strip().isdigit()][0])
        vps_count   = int([l for l in vps_raw.splitlines()   if l.strip().isdigit()][0])

        print(f"\n  Local : {local_count:,} registros")
        print(f"  VPS   : {vps_count:,} registros")
        print(f"  Delta : {vps_count - local_count:+,}")

        # El VPS tiene MÁS registros → sincronizar (local→VPS) borraría datos del VPS
        assert vps_count <= local_count, (
            f"⚠️  PELIGRO DE DATOS: VPS tiene {vps_count:,} registros pero local solo "
            f"{local_count:,}. Sincronizar ahora ELIMINARÍA {vps_count - local_count:,} "
            f"registros del VPS. Primero descarga del VPS a local."
        )

    def test_vps_ultima_fecha_reciente(self):
        """La fecha más reciente en el VPS no debe ser de hace más de 30 días."""
        from datetime import date, timedelta
        salida = _mysql_vps("SELECT MAX(fecha_escaner) FROM gestiones_mensajero;")
        ultima = [l for l in salida.splitlines() if l.strip() and "fecha" not in l.lower()]

        assert ultima, "No se pudo obtener la última fecha del VPS"

        fecha_str = ultima[0].replace(".", "-")
        fecha_vps = date.fromisoformat(fecha_str)
        limite    = date.today() - timedelta(days=30)

        assert fecha_vps >= limite, (
            f"VPS desactualizado: última fecha {fecha_vps} es anterior a {limite}"
        )
