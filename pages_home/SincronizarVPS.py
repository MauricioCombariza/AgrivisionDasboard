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
    "logistica": ["gestiones_mensajero", "ordenes", "planillas_revisadas", "personal"],
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
        _, stdout, stderr = ssh_client.exec_command(cmd_import)
        stdout.channel.recv_exit_status()
        err = stderr.read().decode().strip()

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
