"""
Reemplaza registros de courier_externo en gestiones_mensajero (VPS/logistica)
con los datos reales de bases_web.histo (Servilla cloud) para enero y febrero 2026.

- Conserva registros con liquidado = 1
- Elimina los no liquidados de courier_externo para ene-feb 2026
- Inserta un registro por (cod_men, planilla, cliente) desde histo
- Planillas vacías quedan como 'SIN NUMERO'
"""

import mysql.connector
import subprocess
import sys

COURIER_EXTERNOS = ['1001','1003','1006','1010','1011','1016','1017','1018','1019','1020','1027','1030']

MENSAJERO_IDS = {
    '1001': 32, '1003': 33, '1006': 35, '1010': 34,
    '1011': 37, '1016': 41, '1017': 38, '1018': 39,
    '1019': 40, '1020': 42, '1027': 36, '1030': 43
}

CLIENTE_MAP = {
    'VEHIGROUP SAS': 'Vehigrupo SAS',
    'BANCO CAJA SOCIAL': 'BANCO CAJA SOCIAL',
}

SSH_KEY  = '/home/mauro/.ssh/agrivision_vps'
VPS_HOST = '204.168.150.196'
VPS_USER = 'root'
VPS_PASS = 'Root2024!'

def run_on_vps(sql: str) -> str:
    cmd = [
        'ssh', '-i', SSH_KEY, '-o', 'StrictHostKeyChecking=no',
        f'{VPS_USER}@{VPS_HOST}',
        f'mysql -u root -p{VPS_PASS} logistica -e "{sql}"'
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    return result.stdout.strip()

def pipe_sql_to_vps(sql: str) -> int:
    """Ejecuta un bloque SQL grande pasándolo por stdin al mysql del VPS."""
    cmd = [
        'ssh', '-i', SSH_KEY, '-o', 'StrictHostKeyChecking=no',
        f'{VPS_USER}@{VPS_HOST}',
        f'mysql -u root -p{VPS_PASS} logistica'
    ]
    result = subprocess.run(cmd, input=sql, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"  ERROR: {result.stderr[:300]}", file=sys.stderr)
        return -1
    return 0

# ── 1. Leer histo desde Servilla cloud ─────────────────────────────────────
print("Conectando a bases_web (Servilla)...")
conn_bw = mysql.connector.connect(
    host='186.180.15.66', port=12539,
    user='servilla_remoto', password='Servilla123',
    database='bases_web', connect_timeout=15
)
cur_bw = conn_bw.cursor(dictionary=True)

placeholders = ','.join(['%s'] * len(COURIER_EXTERNOS))
cur_bw.execute(f"""
    SELECT
        cod_men,
        COALESCE(NULLIF(TRIM(planilla), ''), 'SIN NUMERO') AS planilla,
        COALESCE(NULLIF(TRIM(no_entidad), ''), 'Sin Cliente') AS no_entidad,
        MIN(f_emi) AS fecha_min,
        COUNT(serial) AS total_seriales
    FROM histo
    WHERE cod_men IN ({placeholders})
      AND f_emi LIKE '2026.%%'
    GROUP BY cod_men, planilla, no_entidad
    ORDER BY cod_men, planilla
""", COURIER_EXTERNOS)

rows_histo = cur_bw.fetchall()
cur_bw.close()
conn_bw.close()
print(f"  {len(rows_histo)} grupos encontrados en histo")

# ── 2. Eliminar registros no liquidados de courier_externo ene-feb 2026 ──
print("Eliminando registros no liquidados en gestiones_mensajero...")
codigos_str = ','.join([f"'{c}'" for c in COURIER_EXTERNOS])
delete_sql = (
    f"DELETE FROM gestiones_mensajero "
    f"WHERE cod_mensajero IN ({codigos_str}) "
    f"AND fecha_escaner LIKE '2026.%%' "
    f"AND liquidado = 0;"
)
pipe_sql_to_vps(delete_sql)

# Verificar cuántos quedaron (liquidados conservados)
result = run_on_vps(
    f"SELECT COUNT(*) as cnt FROM gestiones_mensajero "
    f"WHERE cod_mensajero IN ({codigos_str}) "
    f"AND fecha_escaner LIKE '2026.%%';"
)
print(f"  Registros liquidados conservados: {result.split(chr(10))[-1] if result else '?'}")

# ── 3. Construir e insertar nuevos registros desde histo ──────────────────
print("Insertando registros desde histo...")

def esc(s):
    """Escapa comillas simples para SQL."""
    return str(s).replace("'", "''")

insert_lines = []
for row in rows_histo:
    cod_men     = esc(row['cod_men'])
    planilla    = esc(row['planilla'])
    no_entidad  = row['no_entidad']
    fecha_min   = esc(row['fecha_min'] or '2026.01.01')
    total_ser   = int(row['total_seriales'])
    mensajero_id = MENSAJERO_IDS.get(row['cod_men'], 'NULL')
    cliente     = esc(CLIENTE_MAP.get(no_entidad, no_entidad))
    fecha_reg   = fecha_min.replace('.', '-')

    mid_val = str(mensajero_id) if mensajero_id != 'NULL' else 'NULL'
    insert_lines.append(
        f"('{fecha_min}', '{cod_men}', {mid_val}, '{planilla}', NULL, "
        f"'Courier Externo', '{cliente}', {total_ser}, 0.00, 0.00, "
        f"'{fecha_reg}', 0, 0)"
    )

insert_sql = (
    "INSERT INTO gestiones_mensajero "
    "(fecha_escaner, cod_mensajero, mensajero_id, lot_esc, orden, "
    "tipo_gestion, cliente, total_seriales, valor_unitario, valor_total, "
    "fecha_registro, editado_manualmente, liquidado) VALUES\n"
    + ',\n'.join(insert_lines) + ';'
)

rc = pipe_sql_to_vps(insert_sql)
if rc == 0:
    print(f"  Insertados: {len(rows_histo)} registros")
else:
    print("  Error en inserción, revisa el log.")
    sys.exit(1)

# ── 4. Verificación final ──────────────────────────────────────────────────
print("\nVerificación final:")
result = run_on_vps(
    f"SELECT cod_mensajero, COUNT(*) as planillas, SUM(total_seriales) as seriales "
    f"FROM gestiones_mensajero "
    f"WHERE cod_mensajero IN ({codigos_str}) "
    f"AND fecha_escaner LIKE '2026.%%' "
    f"GROUP BY cod_mensajero ORDER BY cod_mensajero;"
)
print(result)
print("\nListo.")
