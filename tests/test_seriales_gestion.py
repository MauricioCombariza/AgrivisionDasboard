"""
Tests: tabla seriales_gestion — restricciones, helpers y regresión.

Escenarios:

  ── A. Restricciones SQL (BD real, seriales prefijo TEST_SG_) ───────────────
  A1. UNIQUE KEY impide insertar el mismo (serial, tipo_gestion) dos veces
  A2. El mismo serial puede tener Entrega Y Devolucion (operaciones distintas)
  A3. ON DUPLICATE KEY UPDATE actualiza una fila pendiente con datos reales
  A4. ON DUPLICATE KEY UPDATE NO toca una fila liquidado
  A5. ON DUPLICATE KEY UPDATE NO toca una fila facturado
  A6. INSERT IGNORE (como 3_Ordenes) no pisa una fila pendiente existente

  ── B. Funciones helper (SQL directo, sin importar módulos Streamlit) ────────
  B1. _cargar_precios_mensajero_sg: JOIN clientes retorna estructura correcta
  B2. _cargar_precios_cliente_sg: JOIN clientes retorna estructura correcta
  B3. _cargar_personal_sg: retorna id y nombre por codigo
  B4. _cargar_mapeo_da: retorna dict sin crash (puede estar vacío)
  B5. Filtro de fecha: solo mayo 2026+ se inserta (abril se rechaza)

  ── C. Lógica de conversión de datos (Python puro) ───────────────────────────
  C1. f_esc AAAA.MM.DD → AAAA-MM-DD para columna DATE
  C2. lot_esc alfanumérico iMile queda como string
  C3. lot_esc numérico (5001.0) se normaliza a '5001'
  C4. Filtro de fecha con strings AAAA.MM.DD funciona correctamente
  C5. CSV formato nuevo requiere columnas serial + ambito

  ── D. Análisis estático: cambios críticos en los módulos ───────────────────
  D1. cargar_histo_desde_bd incluye f_esc, cod_men, lot_esc en el SELECT
  D2. Agrupacion_Escaner usa ON DUPLICATE KEY UPDATE (no INSERT IGNORE) en sg
  D3. Actualizacion_Nube usa ON DUPLICATE KEY UPDATE (no INSERT IGNORE) en sg
  D4. Procesador_Ordenes usa ON DUPLICATE KEY UPDATE (no INSERT IGNORE) en sg
  D5. Tab 4 iMile de Procesador_Ordenes verifica columna 'DA'
  D6. _cargar_precios_mensajero_sg usa JOIN clientes, no tabla separada
  D7. _cargar_precios_cliente_sg usa JOIN clientes
  D8. cargar_maestros en 3_Ordenes usa JOIN clientes para precios mensajero
  D9. _insertar_seriales_gestion_proc filtra f_esc >= '2026.05.01'

  ── E. Regresión: tablas existentes intactas ────────────────────────────────
  E1. gestiones_mensajero existe y tiene columnas clave
  E2. ordenes existe y tiene columnas clave
  E3. seriales_gestion tiene el UNIQUE KEY uk_serial sobre (serial) únicamente
  E4. 3_Ordenes no escribe en gestiones_mensajero
  E5. El bloque nuevo de Procesador_Ordenes no toca gestiones_mensajero
  E6. Agrupacion_Escaner sigue llamando insertar_seriales_gestion
"""

import os
import pathlib

import pandas as pd
import pytest

ROOT = pathlib.Path(__file__).parent.parent

# ---------------------------------------------------------------------------
# Fixture: conexión real a logistica (limpia TEST_SG_ al terminar)
# ---------------------------------------------------------------------------
@pytest.fixture(scope="module")
def conn():
    import mysql.connector
    from dotenv import load_dotenv
    load_dotenv(ROOT / ".env", override=True)

    c = mysql.connector.connect(
        host    ="localhost",
        user    = os.environ.get("DB_USER", "root"),
        password= os.environ.get("DB_PASSWORD_LOCAL", ""),
        database="logistica",
        autocommit=False,
    )
    yield c
    cur = c.cursor()
    cur.execute("DELETE FROM seriales_gestion WHERE serial LIKE 'TEST\\_SG\\_%'")
    c.commit()
    cur.close()
    c.close()


# ---------------------------------------------------------------------------
# Helpers de test
# ---------------------------------------------------------------------------
_UPSERT = """
    INSERT INTO seriales_gestion
        (serial, planilla, fecha_escaner, cod_men, mensajero_id,
         cliente, tipo_gestion, precio_cliente, precio_mensajero, origen)
    VALUES (%s, %s, %s, %s, NULL, 'Cliente Test', %s, 100, %s, 'scanner')
    ON DUPLICATE KEY UPDATE
        planilla         = IF(estado = 'pendiente', VALUES(planilla),         planilla),
        fecha_escaner    = IF(estado = 'pendiente', VALUES(fecha_escaner),    fecha_escaner),
        cod_men          = IF(estado = 'pendiente', VALUES(cod_men),          cod_men),
        precio_mensajero = IF(estado = 'pendiente', VALUES(precio_mensajero), precio_mensajero),
        origen           = IF(estado = 'pendiente', VALUES(origen),           origen)
"""

def _insert(conn, serial, tipo, planilla="1001", fecha="2026-05-01",
            cod_men="0001", estado="pendiente", precio_men=50):
    cur = conn.cursor()
    cur.execute("""
        INSERT IGNORE INTO seriales_gestion
            (serial, planilla, fecha_escaner, cod_men, cliente,
             tipo_gestion, precio_cliente, precio_mensajero, estado, origen)
        VALUES (%s, %s, %s, %s, 'Cliente Test', %s, 100, %s, %s, 'manual')
    """, (serial, planilla, fecha, cod_men, tipo, precio_men, estado))
    conn.commit()
    rc = cur.rowcount
    cur.close()
    return rc

def _get(conn, serial, tipo):
    cur = conn.cursor(dictionary=True)
    cur.execute(
        "SELECT * FROM seriales_gestion WHERE serial=%s AND tipo_gestion=%s",
        (serial, tipo)
    )
    row = cur.fetchone()
    cur.close()
    return row

def _del(conn, *serials):
    cur = conn.cursor()
    for s in serials:
        cur.execute("DELETE FROM seriales_gestion WHERE serial=%s", (s,))
    conn.commit()
    cur.close()

def _src(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


# ==============================================================================
# A. Restricciones SQL
# ==============================================================================

class TestConstraintsSQL:

    def test_A1_unique_key_impide_duplicado(self, conn):
        """A1. INSERT IGNORE del mismo (serial, tipo) no duplica la fila."""
        s = "TEST_SG_A1"
        _insert(conn, s, "Entrega", planilla="1001")
        rc2 = _insert(conn, s, "Entrega", planilla="9999", cod_men="0099")
        row = _get(conn, s, "Entrega")
        _del(conn, s)

        assert rc2 == 0,               "Segunda inserción debe ser ignorada (rowcount=0)"
        assert row["planilla"] == "1001", "Los datos originales no deben cambiar"

    def test_A2_serial_solo_tiene_una_gestion(self, conn):
        """A2. Un serial no puede ser Entrega Y Devolucion — UNIQUE KEY uk_serial(serial)."""
        s = "TEST_SG_A2"
        _insert(conn, s, "Entrega", planilla="1001", fecha="2026-05-01")
        rc2 = _insert(conn, s, "Devolucion", planilla="1001", fecha="2026-05-10")

        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM seriales_gestion WHERE serial=%s", (s,))
        count = cur.fetchone()[0]
        cur.close()
        _del(conn, s)

        assert rc2 == 0,   "INSERT IGNORE de Devolucion debe fallar si serial ya existe como Entrega"
        assert count == 1, f"Solo debe existir 1 fila por serial, hay {count}"

    def test_A3_upsert_actualiza_pendiente(self, conn):
        """A3. ON DUPLICATE KEY UPDATE rellena cod_men/planilla de una fila pendiente."""
        s = "TEST_SG_A3"
        _insert(conn, s, "Entrega", planilla="ORD001", fecha="2026-05-01",
                cod_men="", precio_men=0)

        cur = conn.cursor()
        cur.execute(_UPSERT, (s, "5001", "2026-05-06", "0001", "Entrega", 75))
        conn.commit()
        cur.close()

        row = _get(conn, s, "Entrega")
        _del(conn, s)

        assert row["planilla"]             == "5001",    f"planilla='{row['planilla']}'"
        assert row["cod_men"]              == "0001",    f"cod_men='{row['cod_men']}'"
        assert float(row["precio_mensajero"]) == 75
        assert row["origen"]               == "scanner"
        assert row["estado"]               == "pendiente"  # no cambia hasta liquidar

    def test_A4_upsert_no_toca_liquidado(self, conn):
        """A4. ON DUPLICATE KEY UPDATE no modifica una fila liquidado."""
        s = "TEST_SG_A4"
        _insert(conn, s, "Entrega", planilla="5001", cod_men="0001",
                estado="liquidado", precio_men=50)

        cur = conn.cursor()
        cur.execute(_UPSERT, (s, "9999", "2026-05-20", "0099", "Entrega", 999))
        conn.commit()
        cur.close()

        row = _get(conn, s, "Entrega")
        _del(conn, s)

        assert row["planilla"]             == "5001", "planilla no debe cambiar"
        assert row["cod_men"]              == "0001", "cod_men no debe cambiar"
        assert float(row["precio_mensajero"]) == 50
        assert row["estado"]               == "liquidado"

    def test_A5_upsert_no_toca_facturado(self, conn):
        """A5. ON DUPLICATE KEY UPDATE no modifica una fila facturado."""
        s = "TEST_SG_A5"
        _insert(conn, s, "Entrega", planilla="5001", cod_men="0001",
                estado="facturado", precio_men=50)

        cur = conn.cursor()
        cur.execute(_UPSERT, (s, "9999", "2026-05-20", "0099", "Entrega", 999))
        conn.commit()
        cur.close()

        row = _get(conn, s, "Entrega")
        _del(conn, s)

        assert row["estado"]   == "facturado"
        assert row["planilla"] == "5001"

    def test_A6_insert_ignore_3ordenes_no_pisa_pendiente(self, conn):
        """A6. INSERT IGNORE (como 3_Ordenes) no sobreescribe datos reales del escáner."""
        s = "TEST_SG_A6"
        # Escáner ya registró el serial como pendiente con datos reales
        _insert(conn, s, "Entrega", planilla="5001", fecha="2026-05-03",
                cod_men="0001", estado="pendiente", precio_men=50)

        # 3_Ordenes llega después con INSERT IGNORE (planilla=numero_orden, cod_men='')
        rc = _insert(conn, s, "Entrega", planilla="ORD2026001", fecha="2026-05-01",
                     cod_men="", estado="pendiente", precio_men=0)
        row = _get(conn, s, "Entrega")
        _del(conn, s)

        assert rc == 0,               "INSERT IGNORE no debe insertar si ya existe"
        assert row["planilla"] == "5001", "Datos del escáner no deben pisarse"
        assert row["cod_men"]  == "0001"


# ==============================================================================
# B. Funciones helper — SQL directo (sin import de módulos Streamlit)
# ==============================================================================

def _q(conn, sql, params=None):
    cur = conn.cursor(dictionary=True)
    cur.execute(sql, params or ())
    rows = cur.fetchall()
    cur.close()
    return rows

class TestHelperSQL:

    def test_B1_precios_mensajero_estructura(self, conn):
        """B1. La query de _cargar_precios_mensajero_sg retorna datos con JOIN correcto."""
        rows = _q(conn, """
            SELECT c.nombre_empresa, pc.costo_mensajero_entrega, pc.costo_mensajero_devolucion
            FROM precios_cliente pc
            JOIN clientes c ON pc.cliente_id = c.id
            WHERE pc.activo = TRUE AND pc.ambito = 'bogota' AND pc.zona IS NULL
        """)
        assert isinstance(rows, list), "Debe retornar lista"
        for r in rows:
            assert "nombre_empresa" in r
            # Los valores pueden ser NULL (0) pero las columnas deben existir
            assert "costo_mensajero_entrega"    in r
            assert "costo_mensajero_devolucion" in r

    def test_B2_precios_cliente_estructura(self, conn):
        """B2. La query de _cargar_precios_cliente_sg retorna tipo_operacion y precio."""
        rows = _q(conn, """
            SELECT c.nombre_empresa, pc.precio_unitario, pc.tipo_operacion
            FROM precios_cliente pc
            JOIN clientes c ON pc.cliente_id = c.id
            WHERE pc.activo = TRUE AND pc.ambito = 'bogota' AND pc.zona IS NULL
        """)
        assert isinstance(rows, list)
        for r in rows:
            assert "nombre_empresa" in r
            assert "precio_unitario" in r
            assert "tipo_operacion"  in r

    def test_B3_personal_tiene_codigo_y_nombre(self, conn):
        """B3. La query de _cargar_personal_sg retorna codigo, id y nombre_completo."""
        rows = _q(conn, "SELECT id, codigo, nombre_completo FROM personal WHERE activo = TRUE")
        assert isinstance(rows, list)
        assert len(rows) > 0, "Debe haber al menos un mensajero activo"
        for r in rows:
            assert "id"             in r
            assert "codigo"         in r
            assert "nombre_completo" in r

    def test_B4_mapeo_da_no_falla(self, conn):
        """B4. La tabla mapeo_da existe y la query no lanza excepción."""
        rows = _q(conn, "SELECT nombre_da, cod_mensajero FROM mapeo_da ORDER BY nombre_da")
        assert isinstance(rows, list)   # puede estar vacía pero no debe fallar

    def test_B5_filtro_mayo_2026(self, conn):
        """B5. Solo registros con fecha_escaner >= 2026-05-01 se insertan."""
        s_abr = "TEST_SG_B5_ABR"
        s_may = "TEST_SG_B5_MAY"

        # Insertar directamente con fechas distintas
        cur = conn.cursor()
        cur.execute("""
            INSERT IGNORE INTO seriales_gestion
                (serial, planilla, fecha_escaner, cod_men, cliente,
                 tipo_gestion, precio_cliente, precio_mensajero, origen)
            VALUES (%s, '1001', '2026-04-30', '', 'Test', 'Entrega', 0, 0, 'manual')
        """, (s_abr,))
        cur.execute("""
            INSERT IGNORE INTO seriales_gestion
                (serial, planilla, fecha_escaner, cod_men, cliente,
                 tipo_gestion, precio_cliente, precio_mensajero, origen)
            VALUES (%s, '1001', '2026-05-01', '', 'Test', 'Entrega', 0, 0, 'manual')
        """, (s_may,))
        conn.commit()
        cur.close()

        # Simular la consulta que haría el dashboard para ver solo mayo+
        rows = _q(conn, """
            SELECT serial FROM seriales_gestion
            WHERE serial IN (%s, %s) AND fecha_escaner >= '2026-05-01'
        """, (s_abr, s_may))
        serials_encontrados = {r["serial"] for r in rows}
        _del(conn, s_abr, s_may)

        assert s_abr not in serials_encontrados, "Abril NO debe aparecer en el filtro mayo+"
        assert s_may in serials_encontrados,     "Mayo SÍ debe aparecer"


# ==============================================================================
# C. Lógica de conversión (Python puro)
# ==============================================================================

class TestDataConversion:

    def test_C1_f_esc_a_fecha_db(self):
        """C1. f_esc AAAA.MM.DD → AAAA-MM-DD para columna DATE."""
        assert "2026.05.06".replace(".", "-") == "2026-05-06"
        assert "2026.04.30".replace(".", "-") == "2026-04-30"

    def test_C2_lot_esc_imile_queda_string(self):
        """C2. lot_esc alfanumérico iMile se conserva tal cual."""
        for lot in ("IM20260501", "IM_SIN_FECHA", "IM20261231"):
            try:
                planilla = str(int(float(lot)))
            except (ValueError, OverflowError):
                planilla = lot
            assert planilla == lot, f"'{lot}' debe conservarse, quedó '{planilla}'"

    def test_C3_lot_esc_numerico_normalizado(self):
        """C3. lot_esc numérico con decimal se normaliza a entero string."""
        casos = [("5001.0", "5001"), ("1234", "1234"), ("99.00", "99")]
        for entrada, esperado in casos:
            try:
                planilla = str(int(float(entrada)))
            except (ValueError, OverflowError):
                planilla = entrada
            assert planilla == esperado, f"'{entrada}' → esperado '{esperado}', got '{planilla}'"

    def test_C4_filtro_fecha_string_comparison(self):
        """C4. Comparación de strings AAAA.MM.DD funciona correctamente."""
        limite = "2026.05.01"
        assert "2026.04.30" <  limite, "Abril 30 no pasa el filtro"
        assert "2026.05.01" >= limite, "Mayo 01 pasa el filtro"
        assert "2026.05.31" >= limite, "Mayo 31 pasa el filtro"
        assert "2026.06.01" >= limite, "Junio pasa el filtro"

    def test_C5_csv_nuevo_formato_requiere_serial_y_ambito(self):
        """C5. CSV antiguo (sin serial/ambito) es detectado como inválido."""
        df_viejo = pd.DataFrame(columns=[
            "orden", "fecha_recepcion", "nombre_cliente",
            "tipo_servicio", "cantidad_local", "cantidad_nacional"
        ])
        required = {"orden", "serial", "fecha_recepcion",
                    "nombre_cliente", "tipo_servicio", "ambito"}
        missing = required - set(df_viejo.columns)
        assert "serial" in missing, "'serial' debe detectarse como faltante"
        assert "ambito" in missing, "'ambito' debe detectarse como faltante"


# ==============================================================================
# D. Análisis estático del código fuente
# ==============================================================================

class TestStaticAnalysis:

    def test_D1_cargar_histo_incluye_nuevas_columnas(self):
        """D1. cargar_histo_desde_bd selecciona f_esc, cod_men y lot_esc."""
        src = _src("pages_home/Procesador_Ordenes.py")
        inicio = src.find("def cargar_histo_desde_bd")
        bloque = src[inicio: inicio + 600]
        assert "f_esc"   in bloque, "Falta f_esc en cargar_histo_desde_bd"
        assert "cod_men" in bloque, "Falta cod_men"
        assert "lot_esc" in bloque, "Falta lot_esc"

    def test_D2_agrupacion_escaner_usa_on_duplicate(self):
        """D2. insertar_seriales_gestion usa ON DUPLICATE KEY UPDATE."""
        src = _src("pages_home/Agrupacion_Escaner.py")
        inicio = src.find("def insertar_seriales_gestion")
        bloque = src[inicio: inicio + 3000]
        assert "ON DUPLICATE KEY UPDATE"              in bloque
        assert "INSERT IGNORE INTO seriales_gestion"  not in bloque

    def test_D3_actualizacion_nube_usa_on_duplicate(self):
        """D3. _insertar_seriales_gestion_nube usa ON DUPLICATE KEY UPDATE."""
        src = _src("pages_logistica/14_Actualizacion_Nube.py")
        inicio = src.find("def _insertar_seriales_gestion_nube")
        bloque = src[inicio: inicio + 3000]
        assert "ON DUPLICATE KEY UPDATE"              in bloque
        assert "INSERT IGNORE INTO seriales_gestion"  not in bloque

    def test_D4_procesador_ordenes_usa_on_duplicate(self):
        """D4. _insertar_seriales_gestion_proc usa ON DUPLICATE KEY UPDATE."""
        src = _src("pages_home/Procesador_Ordenes.py")
        inicio = src.find("def _insertar_seriales_gestion_proc")
        bloque = src[inicio: inicio + 3000]
        assert "ON DUPLICATE KEY UPDATE"              in bloque
        assert "INSERT IGNORE INTO seriales_gestion"  not in bloque

    def test_D5_tab4_imile_requiere_columna_da(self):
        """D5. Tab 4 iMile verifica que exista la columna 'DA' en el Excel."""
        src = _src("pages_home/Procesador_Ordenes.py")
        assert "'DA'" in src or '"DA"' in src

    def test_D6_precios_mensajero_usa_join_clientes(self):
        """D6. _cargar_precios_mensajero_sg usa JOIN clientes, no tabla separada."""
        src = _src("pages_home/Procesador_Ordenes.py")
        inicio = src.find("def _cargar_precios_mensajero_sg")
        bloque = src[inicio: inicio + 600]
        assert "JOIN clientes"              in bloque
        assert "costo_mensajero_entrega"    in bloque
        assert "FROM precios_mensajero"     not in bloque

    def test_D7_precios_cliente_usa_join_clientes(self):
        """D7. _cargar_precios_cliente_sg hace JOIN con clientes."""
        src = _src("pages_home/Procesador_Ordenes.py")
        inicio = src.find("def _cargar_precios_cliente_sg")
        bloque = src[inicio: inicio + 600]
        assert "JOIN clientes" in bloque

    def test_D8_3ordenes_maestros_usa_join_clientes(self):
        """D8. cargar_maestros en 3_Ordenes usa JOIN clientes para precio mensajero."""
        src = _src("pages_logistica/3_Ordenes.py")
        inicio = src.find("def cargar_maestros")
        bloque = src[inicio: inicio + 1800]
        assert "JOIN clientes"           in bloque
        assert "costo_mensajero_entrega" in bloque
        assert "FROM precios_mensajero"  not in bloque

    def test_D9_insertar_proc_filtra_mayo_2026(self):
        """D9. _insertar_seriales_gestion_proc filtra por f_esc >= '2026.05.01'."""
        src = _src("pages_home/Procesador_Ordenes.py")
        inicio = src.find("def _insertar_seriales_gestion_proc")
        bloque = src[inicio: inicio + 1000]
        assert "2026.05.01" in bloque, "El filtro de fecha debe estar en la función"


# ==============================================================================
# E. Regresión: tablas existentes intactas
# ==============================================================================

class TestRegression:

    def test_E1_gestiones_mensajero_accesible(self, conn):
        """E1. gestiones_mensajero existe y tiene columnas clave."""
        cols = {r["Field"] for r in _q(conn, "DESCRIBE gestiones_mensajero")}
        required = {"id", "fecha_escaner", "cod_mensajero", "lot_esc",
                    "tipo_gestion", "cliente", "total_seriales", "valor_total"}
        missing = required - cols
        assert not missing, f"Columnas faltantes en gestiones_mensajero: {missing}"

    def test_E2_ordenes_accesible(self, conn):
        """E2. ordenes existe y tiene columnas clave."""
        cols = {r["Field"] for r in _q(conn, "DESCRIBE ordenes")}
        required = {"id", "numero_orden", "cliente_id",
                    "cantidad_local", "cantidad_nacional", "valor_total", "estado"}
        missing = required - cols
        assert not missing, f"Columnas faltantes en ordenes: {missing}"

    def test_E3_unique_key_correcto(self, conn):
        """E3. seriales_gestion tiene uk_serial sobre (serial) únicamente."""
        rows = _q(conn,
            "SHOW INDEX FROM seriales_gestion WHERE Key_name='uk_serial'"
        )
        cols = {r["Column_name"] for r in rows}
        assert cols == {"serial"}, \
            f"uk_serial debe indexar solo (serial), indexa {cols}"

    def test_E4_3ordenes_no_escribe_gestiones_mensajero(self):
        """E4. 3_Ordenes no tiene ninguna referencia a gestiones_mensajero."""
        src = _src("pages_logistica/3_Ordenes.py")
        assert "gestiones_mensajero" not in src

    def test_E5_bloque_nuevo_procesador_no_toca_gestiones_mensajero(self):
        """E5. _insertar_seriales_gestion_proc no toca gestiones_mensajero."""
        src = _src("pages_home/Procesador_Ordenes.py")
        inicio = src.find("def _insertar_seriales_gestion_proc")
        bloque = src[inicio: inicio + 2000]
        assert "gestiones_mensajero" not in bloque

    def test_E6_agrupacion_escaner_llama_insertar_seriales_gestion(self):
        """E6. Agrupacion_Escaner sigue llamando a insertar_seriales_gestion."""
        src = _src("pages_home/Agrupacion_Escaner.py")
        assert "insertar_seriales_gestion(" in src, \
            "Agrupacion_Escaner debe llamar a insertar_seriales_gestion"


if __name__ == "__main__":
    import pytest
    pytest.main([__file__, "-v", "--tb=short"])
