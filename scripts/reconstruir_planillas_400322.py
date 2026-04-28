"""
Reconstruye gestiones_mensajero para planillas 400322+ desde histo (bases_web).

Estas planillas fueron eliminadas del VPS durante la limpieza de cod_men mal formados.
No están en dashboard.csv, por lo que Agrupacion_Escaner no puede restaurarlas.

Fuente: bases_web.histo (servidor remoto)
Destino: logistica.gestiones_mensajero (local y VPS via SSH)
"""

import os
import sys
import subprocess
import tempfile
import mysql.connector
from datetime import date

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))

# ── Configuración ─────────────────────────────────────────────────────────────
BASES_WEB = dict(
    host=os.getenv("DB_HOST_BASES_WEB", "186.180.15.66"),
    port=12539,
    user=os.getenv("DB_USER_BASES_WEB", "servilla_remoto"),
    password=os.getenv("DB_PASSWORD_BASES_WEB", ""),
    database=os.getenv("DB_NAME_BASES_WEB", "bases_web"),
    connect_timeout=15,
)

LOCAL = dict(
    host="localhost",
    user="root",
    password=os.getenv("DB_PASSWORD_LOCAL", ""),
    database="logistica",
    connect_timeout=10,
)

VPS_HOST = "204.168.150.196"
VPS_USER = "root"
VPS_KEY  = "/home/mauro/.ssh/agrivision_vps"
VPS_DB_USER = "root"
VPS_DB_PASS = os.getenv("DB_PASSWORD", "Root2024!")

LOT_ESC_INICIO = 400321
FECHA_REGISTRO = date.today().isoformat()

# ── Conectar ──────────────────────────────────────────────────────────────────

def conectar(cfg):
    return mysql.connector.connect(**cfg)


# ── Cargar mapeo de nombres de clientes (histo → local) ───────────────────────
def cargar_mapeo_clientes(conn_local):
    cur = conn_local.cursor()
    cur.execute("SELECT nombre_csv, nombre_bd FROM mapeo_clientes")
    rows = cur.fetchall()
    cur.close()
    # nombre_csv en histo → nombre_bd en local; claves en mayúsculas para comparación
    return {r[0].upper().strip(): r[1] for r in rows}


# ── Cargar precios mensajero (costo_mensajero_entrega/devolucion) ─────────────
def cargar_precios_mensajero(conn_local):
    cur = conn_local.cursor()
    cur.execute("""
        SELECT c.nombre_empresa, pc.costo_mensajero_entrega, pc.costo_mensajero_devolucion
        FROM precios_cliente pc
        JOIN clientes c ON pc.cliente_id = c.id
        WHERE pc.activo = TRUE AND pc.ambito = 'bogota' AND pc.zona IS NULL
    """)
    rows = cur.fetchall()
    cur.close()
    precios = {}
    for nombre, ent, dev in rows:
        key = nombre.upper().strip()
        if key not in precios:
            precios[key] = {'entrega': 0, 'devolucion': 0}
        if ent:
            v = float(ent)
            if precios[key]['entrega'] == 0 or v < precios[key]['entrega']:
                precios[key]['entrega'] = v
        if dev:
            v = float(dev)
            if v > precios[key]['devolucion']:
                precios[key]['devolucion'] = v
    return precios


# ── Cargar personal (cod_mensajero → mensajero_id) ────────────────────────────
def cargar_personal(conn_local):
    cur = conn_local.cursor()
    cur.execute("SELECT codigo, id FROM personal WHERE activo = TRUE")
    rows = cur.fetchall()
    cur.close()
    return {r[0]: r[1] for r in rows}


# ── Leer datos desde histo ────────────────────────────────────────────────────
def leer_histo(conn_web):
    """
    Devuelve filas agrupadas por (lot_esc, cod_men, f_esc, no_entidad, mot_esc, orden).
    - Usa f_esc (fecha de escaneo) como fecha_escaner, NO f_lleva.
    - Incluye cod_men='0000' (paquetes pendientes sin mensajero asignado).
    - Solo filtra códigos no numéricos o vacíos.
    """
    cur = conn_web.cursor()
    cur.execute("""
        SELECT
            lot_esc,
            LPAD(TRIM(cod_men), 4, '0') AS cod_men_pad,
            f_esc,
            no_entidad,
            mot_esc,
            orden,
            COUNT(*)                    AS total_seriales
        FROM histo
        WHERE CAST(lot_esc AS UNSIGNED) >= %s
          -- Códigos numéricos de 1-4 dígitos O vacíos (pendientes sin mensajero asignado)
          AND (TRIM(cod_men) REGEXP '^[0-9]{1,4}$' OR TRIM(cod_men) = '')
          -- f_esc debe ser una fecha válida (no vacía ni '.  .')
          AND TRIM(f_esc) != ''
          AND TRIM(f_esc) NOT LIKE '.%%'
        GROUP BY lot_esc, cod_men_pad, f_esc, no_entidad, mot_esc, orden
        ORDER BY lot_esc, cod_men_pad, orden
    """, (LOT_ESC_INICIO,))
    rows = cur.fetchall()
    cur.close()
    return rows


# ── Insertar en gestiones_mensajero ───────────────────────────────────────────
INSERT_SQL = """
    INSERT IGNORE INTO gestiones_mensajero
        (fecha_escaner, cod_mensajero, mensajero_id, lot_esc, orden,
         tipo_gestion, cliente, total_seriales,
         valor_unitario, valor_total,
         fecha_registro, editado_manualmente)
    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 1)
"""

def insertar_en_local(conn_local, filas, mapeo, precios, personal):
    cur = conn_local.cursor()
    insertados = 0
    ignorados = 0
    sin_precio = set()

    import re as _re
    rechazados = []

    for lot_esc, cod_men, f_esc, no_entidad, mot_esc, orden, total in filas:
        # '0000' = pendiente sin mensajero (cod_men vacío en histo → LPAD → '0000')
        # Rechazar solo si no es exactamente 4 dígitos
        if not _re.match(r'^\d{4}$', str(cod_men)):
            rechazados.append(f"{lot_esc}/{cod_men}")
            continue

        # Mapear nombre de cliente de histo a nombre local
        key_histo = (no_entidad or "").upper().strip()
        nombre_bd = mapeo.get(key_histo, no_entidad)  # fallback al nombre histo

        # Tipo de gestion para calculo de precio
        tipo_lower = (mot_esc or "").lower()
        tipo_precio = 'entrega' if 'entrega' in tipo_lower else 'devolucion'

        # Buscar precio por nombre_bd
        precio_key = nombre_bd.upper().strip()
        valor_unit = precios.get(precio_key, {}).get(tipo_precio, 0)
        if valor_unit == 0:
            # Intentar también con el nombre original de histo
            valor_unit = precios.get(key_histo, {}).get(tipo_precio, 0)
            if valor_unit == 0:
                sin_precio.add(no_entidad)

        mensajero_id = personal.get(cod_men)
        valor_total  = valor_unit * total

        cur.execute(INSERT_SQL, (
            f_esc, cod_men, mensajero_id, lot_esc, str(orden),
            mot_esc, nombre_bd, total,
            valor_unit, valor_total,
            FECHA_REGISTRO,
        ))
        if cur.rowcount:
            insertados += 1
        else:
            ignorados += 1

    conn_local.commit()
    cur.close()

    if rechazados:
        print(f"  ⛔ Rechazados (cod_men inválido): {rechazados[:10]}")
    if sin_precio:
        print(f"  ⚠️  Sin precio: {sin_precio}")
    return insertados, ignorados


# ── Dump local y subida al VPS ────────────────────────────────────────────────
def sincronizar_con_vps(lot_esc_inicio):
    """Dump gestiones_mensajero filtrado por lot_esc >= lot_esc_inicio y lo importa en VPS."""
    with tempfile.NamedTemporaryFile(suffix=".sql", delete=False, mode="w") as f:
        ruta_sql = f.name

    # Dump solo los registros nuevos para minimizar tamaño
    dump_cmd = [
        "mysqldump", "-uroot",
        f"--password={os.getenv('DB_PASSWORD_LOCAL', '')}",
        "--single-transaction", "--no-tablespaces",
        "--where", f"lot_esc >= '{lot_esc_inicio}'",
        "logistica", "gestiones_mensajero",
    ]
    r = subprocess.run(dump_cmd, capture_output=True, text=True)
    if r.returncode != 0:
        print(f"  ❌ mysqldump falló: {r.stderr[:300]}")
        os.unlink(ruta_sql)
        return False

    with open(ruta_sql, "w") as f:
        f.write(r.stdout)

    # Subir al VPS via SCP
    ruta_remota = f"/tmp/gestiones_rebuild_{lot_esc_inicio}.sql"
    scp_cmd = ["scp", "-i", VPS_KEY, "-o", "StrictHostKeyChecking=no",
                ruta_sql, f"{VPS_USER}@{VPS_HOST}:{ruta_remota}"]
    r2 = subprocess.run(scp_cmd, capture_output=True, text=True, timeout=120)
    if r2.returncode != 0:
        print(f"  ❌ SCP falló: {r2.stderr[:300]}")
        os.unlink(ruta_sql)
        return False

    # Importar en VPS
    import_cmd = (
        f"mysql -u{VPS_DB_USER} -p{VPS_DB_PASS} logistica < {ruta_remota} "
        f"&& rm {ruta_remota}"
    )
    ssh_cmd = ["ssh", "-i", VPS_KEY, "-o", "StrictHostKeyChecking=no",
               f"{VPS_USER}@{VPS_HOST}", import_cmd]
    r3 = subprocess.run(ssh_cmd, capture_output=True, text=True, timeout=300)

    os.unlink(ruta_sql)

    if r3.returncode != 0:
        err = "\n".join(l for l in r3.stderr.splitlines() if "Warning" not in l)
        print(f"  ❌ Importación VPS falló: {err[:300]}")
        return False

    return True


# ── Main ──────────────────────────────────────────────────────────────────────
def main():
    print("=== Reconstruyendo planillas 400322+ desde histo ===\n")

    print("Conectando a bases_web...")
    conn_web = conectar(BASES_WEB)

    print("Conectando a BD local...")
    conn_local = conectar(LOCAL)

    print("Cargando tablas auxiliares...")
    mapeo   = cargar_mapeo_clientes(conn_local)
    precios = cargar_precios_mensajero(conn_local)
    personal = cargar_personal(conn_local)

    print(f"  Mapeos cargados: {len(mapeo)}")
    print(f"  Clientes con precio: {list(precios.keys())}")
    print(f"  Mensajeros activos: {len(personal)}\n")

    print("Leyendo histo desde bases_web...")
    filas = leer_histo(conn_web)
    print(f"  {len(filas)} grupos encontrados en histo para lot_esc >= {LOT_ESC_INICIO}\n")

    planillas_unicas = sorted({r[0] for r in filas})
    print(f"  Planillas afectadas: {len(planillas_unicas)}")
    print(f"  Rango: {planillas_unicas[0]} – {planillas_unicas[-1]}\n")

    print("Insertando en BD local (INSERT IGNORE)...")
    insertados, ignorados = insertar_en_local(conn_local, filas, mapeo, precios, personal)
    print(f"  ✅ Insertados: {insertados}")
    print(f"  ⏭️  Ignorados (ya existían): {ignorados}\n")

    conn_web.close()
    conn_local.close()

    if insertados == 0:
        print("Nada nuevo que subir al VPS.")
        return

    respuesta = input("¿Sincronizar con VPS? (s/N): ").strip().lower()
    if respuesta != 's':
        print("Sincronización con VPS omitida.")
        return

    print("\nSincronizando con VPS...")
    ok = sincronizar_con_vps(LOT_ESC_INICIO)
    if ok:
        print("  ✅ VPS actualizado correctamente")
    else:
        print("  ❌ Falló la sincronización con VPS")


if __name__ == "__main__":
    main()
