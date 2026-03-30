import streamlit as st
import subprocess
import tempfile
import os
import paramiko
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

st.title("🔄 Sincronizar con VPS")
st.info("Sube las tablas locales al servidor web (VPS). Ejecuta esto después de procesar datos con Selenium o iMile.")

# ── Configuración ─────────────────────────────────────────────────────────────
VPS_HOST = "204.168.150.196"
VPS_USER = "root"
VPS_KEY  = os.path.expanduser("~/.ssh/agrivision_vps")

LOCAL_USER = "root"
LOCAL_PASS = ""

VPS_DB_USER = "root"
VPS_DB_PASS = "Root2024!"

TABLAS_SYNC = {
    "imile":     ["paquetes"],
    "logistica": ["gestiones_mensajero", "ordenes"],
}

# Tablas que se descargan del VPS a local (la nube es fuente de verdad)
TABLAS_BAJAR = {
    "logistica": ["personal"],
}

# ── Estado del VPS ────────────────────────────────────────────────────────────
def verificar_conexion_vps():
    try:
        client = paramiko.SSHClient()
        client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        client.connect(VPS_HOST, username=VPS_USER, key_filename=VPS_KEY, timeout=10)
        _, stdout, _ = client.exec_command("echo OK")
        resultado = stdout.read().decode().strip()
        client.close()
        return resultado == "OK"
    except Exception as e:
        return False

# ── Sincronizar una tabla ─────────────────────────────────────────────────────
def sincronizar_tabla(db, tabla, ssh_client, sftp, progreso_placeholder, log):
    try:
        # 1. Dump local
        with tempfile.NamedTemporaryFile(suffix=".sql", delete=False) as f:
            ruta_sql = f.name

        cmd_dump = ["mysqldump", f"-u{LOCAL_USER}"]
        if LOCAL_PASS:
            cmd_dump.append(f"-p{LOCAL_PASS}")
        cmd_dump += ["--single-transaction", "--no-tablespaces", db, tabla]

        resultado = subprocess.run(cmd_dump, capture_output=True, text=True)
        if resultado.returncode != 0:
            log.append(f"❌ Error dumping {db}.{tabla}: {resultado.stderr[:200]}")
            return False

        with open(ruta_sql, "w", encoding="utf-8") as f:
            f.write(resultado.stdout)

        # 2. Subir al VPS via SFTP
        ruta_remota = f"/tmp/{db}_{tabla}.sql"
        sftp.put(ruta_sql, ruta_remota)

        # 3. Importar en VPS
        cmd_import = f"mysql -u{VPS_DB_USER} -p{VPS_DB_PASS} {db} < {ruta_remota} && rm {ruta_remota}"
        _, stdout, stderr = ssh_client.exec_command(cmd_import, timeout=300)
        # Leer stdout y stderr ANTES de recv_exit_status para drenar los buffers
        # del canal SSH y evitar deadlock (si stderr se llena, el proceso remoto
        # queda bloqueado esperando que se drene, y recv_exit_status nunca retorna)
        stdout.read()  # usualmente vacío para mysql import
        err = stderr.read().decode().strip()
        stdout.channel.recv_exit_status()

        # Ignorar warnings de password (son normales)
        err_real = "\n".join([l for l in err.splitlines() if "Warning" not in l]).strip()
        if err_real:
            log.append(f"⚠️ {db}.{tabla}: {err_real[:200]}")
        else:
            filas = resultado.stdout.count("INSERT INTO")
            log.append(f"✅ {db}.{tabla} sincronizada")

        os.unlink(ruta_sql)
        return True

    except Exception as e:
        log.append(f"❌ {db}.{tabla}: {e}")
        return False


# ── Descargar tabla del VPS a local ───────────────────────────────────────────
def descargar_tabla(db, tabla, ssh_client, sftp, log):
    try:
        ruta_remota = f"/tmp/{db}_{tabla}_dl.sql"
        cmd_dump = f"mysqldump -u{VPS_DB_USER} -p{VPS_DB_PASS} --single-transaction --no-tablespaces {db} {tabla} > {ruta_remota}"
        _, stdout, stderr = ssh_client.exec_command(cmd_dump, timeout=300)
        # Drenar buffers antes de recv_exit_status para evitar deadlock SSH
        stdout.read()  # vacío (dump va al archivo via >)
        stderr.read()  # drenar warnings
        stdout.channel.recv_exit_status()

        with tempfile.NamedTemporaryFile(suffix=".sql", delete=False) as f:
            ruta_local = f.name
        sftp.get(ruta_remota, ruta_local)
        ssh_client.exec_command(f"rm {ruta_remota}")

        cmd_import = ["mysql", f"-u{LOCAL_USER}"]
        if LOCAL_PASS:
            cmd_import.append(f"-p{LOCAL_PASS}")
        cmd_import.append(db)
        with open(ruta_local, "r", encoding="utf-8") as f:
            resultado = subprocess.run(cmd_import, input=f.read(), capture_output=True, text=True)

        os.unlink(ruta_local)

        if resultado.returncode != 0:
            err = "\n".join([l for l in resultado.stderr.splitlines() if "Warning" not in l]).strip()
            log.append(f"❌ Error importando {db}.{tabla} localmente: {err[:200]}")
            return False

        log.append(f"✅ {db}.{tabla} descargada del VPS a local")
        return True
    except Exception as e:
        log.append(f"❌ {db}.{tabla}: {e}")
        return False


# ── UI ────────────────────────────────────────────────────────────────────────
col1, col2 = st.columns(2)

with col1:
    st.markdown("### Tablas a sincronizar")
    for db, tablas in TABLAS_SYNC.items():
        for tabla in tablas:
            st.write(f"• `{db}.{tabla}`")

with col2:
    st.markdown("### Destino")
    st.write(f"🖥️ VPS: `{VPS_HOST}`")
    st.write(f"🔑 Clave: `{os.path.basename(VPS_KEY)}`")

st.divider()

# Verificar conexión
if st.button("🔍 Verificar conexión al VPS"):
    with st.spinner("Conectando..."):
        if verificar_conexion_vps():
            st.success("✅ Conexión al VPS exitosa")
        else:
            st.error(f"❌ No se pudo conectar al VPS. Verifica que la clave SSH esté en `{VPS_KEY}`")

st.divider()

# Botón de sincronización
st.markdown("### Sincronizar ahora")
st.warning("Esto reemplazará los datos en el VPS con los datos locales.")

if st.button("🚀 Sincronizar con VPS", type="primary"):
    log = []
    exitosos = 0
    fallidos = 0

    try:
        with st.spinner("Conectando al VPS..."):
            client = paramiko.SSHClient()
            client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            client.connect(VPS_HOST, username=VPS_USER, key_filename=VPS_KEY, timeout=15)
            sftp = client.open_sftp()

        total_tablas = sum(len(t) for t in TABLAS_SYNC.values())
        barra = st.progress(0)
        idx = 0

        for db, tablas in TABLAS_SYNC.items():
            for tabla in tablas:
                placeholder = st.empty()
                placeholder.info(f"Sincronizando `{db}.{tabla}`...")
                exito = sincronizar_tabla(db, tabla, client, sftp, placeholder, log)
                if exito:
                    exitosos += 1
                else:
                    fallidos += 1
                idx += 1
                barra.progress(idx / total_tablas)
                placeholder.empty()

        sftp.close()
        client.close()

        barra.progress(1.0)
        hora = datetime.now().strftime("%H:%M:%S")

        if fallidos == 0:
            st.success(f"✅ Sincronización completada a las {hora} — {exitosos} tablas sincronizadas")
        else:
            st.warning(f"⚠️ Sincronización con errores — {exitosos} ok, {fallidos} fallidas")

    except Exception as e:
        st.error(f"❌ Error de conexión SSH: {e}")
        log.append(f"❌ SSH: {e}")

    # Mostrar log
    if log:
        with st.expander("Ver detalles"):
            for linea in log:
                st.write(linea)

st.divider()

# Bajar tablas del VPS a local
st.markdown("### Descargar del VPS a local")
st.info("Descarga tablas que se administran en el VPS (ej. personal) hacia la BD local.")
for db, tablas in TABLAS_BAJAR.items():
    for tabla in tablas:
        st.write(f"• `{db}.{tabla}`")

if st.button("⬇️ Descargar personal del VPS", type="secondary"):
    log2 = []
    try:
        with st.spinner("Conectando al VPS..."):
            client2 = paramiko.SSHClient()
            client2.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            client2.connect(VPS_HOST, username=VPS_USER, key_filename=VPS_KEY, timeout=15)
            sftp2 = client2.open_sftp()

        for db, tablas in TABLAS_BAJAR.items():
            for tabla in tablas:
                st.info(f"Descargando `{db}.{tabla}`...")
                descargar_tabla(db, tabla, client2, sftp2, log2)

        sftp2.close()
        client2.close()

        hora = datetime.now().strftime("%H:%M:%S")
        errores = [l for l in log2 if l.startswith("❌")]
        if not errores:
            st.success(f"✅ Descarga completada a las {hora}")
        else:
            st.warning("⚠️ Descarga con errores")
    except Exception as e:
        st.error(f"❌ Error de conexión SSH: {e}")
        log2.append(f"❌ SSH: {e}")

    if log2:
        with st.expander("Ver detalles"):
            for linea in log2:
                st.write(linea)
