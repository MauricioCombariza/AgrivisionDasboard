"""
Tests: protección de planillas_revisadas + courier_externos solo desde histo.

test_sincronizar_planillas.py ya cubre sincronizar_periodo de Agrupacion_Escaner.
Este archivo cubre los demás módulos y el sync de courier_externos en Paso 5.

Escenarios:
  ── Paso 5 (14_Actualizacion_Nube.py) ─────────────────────────────────────
  A1. df_work excluye planillas revisadas antes de cualquier query
  A2. df_work excluye courier_externos (se sincronizan por bloque separado)
  A3. Sync courier_ext: planilla revisada no genera INSERT aunque esté en histo
  A4. Sync courier_ext: planilla revisada no genera UPDATE aunque esté en histo
  A5. Sync courier_ext: registro revisado NO se elimina aunque sea huérfano
  A6. Sync courier_ext: registro con editado_manualmente=1 no se elimina
  A7. Sync courier_ext: registro con liquidado=1 no se elimina
  A8. Sync courier_ext: registro huérfano sin protección SÍ se elimina
  A9. Sync courier_ext: todas las inserciones provienen de histo (solo-histo)

  ── Agrupacion_Escaner.py — botón "Registrar" (análisis estático) ─────────
  B1. El código del botón Registrar contiene la guarda _planillas_rev_reg

  ── 7_Gestion_Pagos.py — guardas SQL (análisis estático) ─────────────────
  C1. Tab4 Recalcular incluye planillas_revisadas en el WHERE de preview
  C2. Tab4 Recalcular incluye planillas_revisadas en el WHERE del UPDATE
  C3. BCS/Tab5 incluye planillas_revisadas en su SELECT y UPDATE

  ── 3_Ordenes.py y Procesador_Ordenes.py ────────────────────────────────
  D1. 3_Ordenes.py no escribe en gestiones_mensajero
  D2. Procesador_Ordenes.py no escribe en gestiones_mensajero
"""

import pathlib
import sys
from unittest.mock import MagicMock

import pandas as pd
import pytest

ROOT = pathlib.Path(__file__).parent.parent

# ─── Importar COURIER_EXTERNOS_SET desde 14_Actualizacion_Nube ───────────────
# Se silencian los módulos de UI antes de cargar el módulo.
for _m in ("mysql", "mysql.connector", "dotenv", "sqlalchemy", "paramiko"):
    sys.modules.setdefault(_m, MagicMock())

_st14 = MagicMock()
_st14.tabs.side_effect = lambda labels: [MagicMock() for _ in labels]
_st14.columns.side_effect = lambda spec: [
    MagicMock() for _ in (spec if isinstance(spec, (list, tuple)) else range(spec))
]
_st14.expander.return_value.__enter__ = lambda s: s
_st14.expander.return_value.__exit__ = MagicMock(return_value=False)
sys.modules.setdefault("streamlit", _st14)

import importlib.util as _ilu

_nube_spec = _ilu.spec_from_file_location(
    "actualizacion_nube_pm",
    ROOT / "pages_logistica" / "14_Actualizacion_Nube.py",
)
_nube_mod = _ilu.module_from_spec(_nube_spec)
_nube_spec.loader.exec_module(_nube_mod)

COURIER_EXTERNOS_SET: set = _nube_mod.COURIER_EXTERNOS_SET


# ═══════════════════════════════════════════════════════════════════════════════
# HELPERS — replican la lógica exacta de Paso 5 como funciones puras testeables
# ═══════════════════════════════════════════════════════════════════════════════

def _norm_lot(v):
    """Idéntico a _norm_lot en Paso 5: convierte lot_esc a str sin decimales."""
    try:
        return str(int(float(v)))
    except (ValueError, TypeError):
        return str(v)


def _filter_df_work(df: pd.DataFrame, planillas_revisadas: set,
                    courier_externos_set: set) -> pd.DataFrame:
    """
    Replica los dos filtros que aplica Paso 5 al df_work antes de cualquier query:
      1. Excluir planillas revisadas
      2. Excluir courier_externos (se sincronizan desde histo por separado)
    """
    df = df.copy()
    df["_lot"] = df["lot_esc"].apply(_norm_lot)
    df = df[~df["_lot"].isin(planillas_revisadas)]
    df = df[~df["cod_men"].astype(str).str.strip().isin(courier_externos_set)]
    return df


def _ids_a_borrar(gm_ext_rows: list, histo_keys: set,
                  planillas_revisadas: set) -> list:
    """
    Replica la lógica de selección de registros huérfanos de courier_externos
    a eliminar del Paso 5.

    gm_ext_rows: lista de tuplas (id, cod_mensajero, lot_esc,
                                   editado_manualmente, cliente, liquidado)
    histo_keys:  set de (cod_men, planilla, cliente) válidos en histo
    """
    return [
        r[0] for r in gm_ext_rows
        if (str(r[1]), str(r[2]), str(r[4])) not in histo_keys
        and str(r[2]) not in planillas_revisadas
        and not r[3]    # editado_manualmente == 0
        and not r[5]    # liquidado == 0
    ]


def _planillas_a_insertar(histo_ext: list, planillas_revisadas: set,
                           gm_ext_dict: dict) -> list:
    """
    Replica el loop insert/update de courier_externos del Paso 5.
    Devuelve las planillas para las que se emitiría INSERT.
    """
    insertadas = []
    for r in histo_ext:
        planilla = str(r["planilla"])
        if planilla in planillas_revisadas:
            continue
        cod = str(r["cod_men"])
        cli = str(r["no_entidad"])
        key = (cod, planilla, cli)
        if key not in gm_ext_dict:
            insertadas.append(planilla)
    return insertadas


def _planillas_a_actualizar(histo_ext: list, planillas_revisadas: set,
                             gm_ext_dict: dict) -> list:
    """Replica la rama UPDATE del mismo loop."""
    actualizadas = []
    for r in histo_ext:
        planilla = str(r["planilla"])
        if planilla in planillas_revisadas:
            continue
        key = (str(r["cod_men"]), planilla, str(r["no_entidad"]))
        if key in gm_ext_dict and not gm_ext_dict[key]["editado"]:
            actualizadas.append(planilla)
    return actualizadas


# ═══════════════════════════════════════════════════════════════════════════════
# PART A: Paso 5 — lógica de sincronización courier_externos
# ═══════════════════════════════════════════════════════════════════════════════

class TestPaso5DfWork:
    """A1-A2: filtros sobre df_work antes de procesar gestiones normales."""

    def test_a1_planillas_revisadas_excluidas_de_df_work(self):
        """A1: Filas con lot_esc marcado como revisado no llegan a ninguna query."""
        df = pd.DataFrame({
            "lot_esc": [351300, 351301, 351302],
            "cod_men": ["0050", "0050", "0050"],
        })
        planillas_revisadas = {"351300", "351301"}
        resultado = _filter_df_work(df, planillas_revisadas, set())
        lots = set(resultado["_lot"].tolist())
        assert "351300" not in lots
        assert "351301" not in lots
        assert "351302" in lots

    def test_a2_courier_externos_excluidos_de_df_work(self):
        """A2: Courier externos se excluyen de df_work (su sync es por bloque propio)."""
        df = pd.DataFrame({
            "lot_esc": [100, 200, 300],
            "cod_men": ["1001", "0050", "1030"],
        })
        resultado = _filter_df_work(df, set(), COURIER_EXTERNOS_SET)
        assert set(resultado["cod_men"].tolist()) == {"0050"}

    def test_a2_cod_men_sin_strip_sigue_siendo_excluido(self):
        """A2: cod_men con espacios accidentales igualmente se excluye."""
        df = pd.DataFrame({
            "lot_esc": [100],
            "cod_men": [" 1001 "],
        })
        resultado = _filter_df_work(df, set(), COURIER_EXTERNOS_SET)
        assert resultado.empty


class TestPaso5CourierExtSync:
    """A3-A9: lógica de insert/update/delete en el bloque courier_externos."""

    # ── datos de histo comunes ──────────────────────────────────────────────
    _HISTO = [
        {"cod_men": "1001", "planilla": "351100", "no_entidad": "Cliente A",
         "fecha_min": "2026-01-10", "total_seriales": 50},
        {"cod_men": "1001", "planilla": "351200", "no_entidad": "Cliente A",
         "fecha_min": "2026-01-11", "total_seriales": 30},
    ]

    def test_a3_insert_se_salta_si_planilla_revisada(self):
        """A3: Planilla revisada en histo no genera INSERT."""
        planillas_revisadas = {"351100"}
        insertadas = _planillas_a_insertar(self._HISTO, planillas_revisadas, {})
        assert "351100" not in insertadas
        assert "351200" in insertadas

    def test_a4_update_se_salta_si_planilla_revisada(self):
        """A4: Planilla revisada en histo no genera UPDATE aunque exista en gestiones."""
        planillas_revisadas = {"351100"}
        gm_dict = {
            ("1001", "351100", "Cliente A"): {"editado": 0},
            ("1001", "351200", "Cliente A"): {"editado": 0},
        }
        actualizadas = _planillas_a_actualizar(self._HISTO, planillas_revisadas, gm_dict)
        assert "351100" not in actualizadas
        assert "351200" in actualizadas

    def test_a5_delete_no_borra_planilla_revisada(self):
        """A5: Registro huérfano con lot_esc revisado NO entra en ids_borrar."""
        # (id, cod_men, lot_esc, editado_manualmente, cliente, liquidado)
        gm_ext = [
            (10, "1001", "351300", 0, "Cliente A", 0),   # huérfano PERO revisado
            (11, "1001", "351301", 0, "Cliente B", 0),   # huérfano y libre → debe borrarse
        ]
        histo_keys: set = set()
        planillas_revisadas = {"351300"}
        ids = _ids_a_borrar(gm_ext, histo_keys, planillas_revisadas)
        assert 10 not in ids, "Registro revisado no debe borrarse"
        assert 11 in ids, "Registro huérfano libre debe borrarse"

    def test_a6_delete_no_borra_editado_manualmente(self):
        """A6: Registro con editado_manualmente=1 no se elimina aunque sea huérfano."""
        gm_ext = [
            (20, "1001", "351400", 1, "Cliente A", 0),   # editado_manualmente=1
            (21, "1001", "351401", 0, "Cliente A", 0),   # normal huérfano
        ]
        ids = _ids_a_borrar(gm_ext, set(), set())
        assert 20 not in ids
        assert 21 in ids

    def test_a7_delete_no_borra_liquidado(self):
        """A7: Registro con liquidado=1 no se elimina aunque sea huérfano."""
        gm_ext = [
            (30, "1001", "351500", 0, "Cliente A", 1),   # liquidado=1
            (31, "1001", "351501", 0, "Cliente A", 0),   # normal huérfano
        ]
        ids = _ids_a_borrar(gm_ext, set(), set())
        assert 30 not in ids
        assert 31 in ids

    def test_a8_delete_si_borra_huerfano_sin_proteccion(self):
        """A8: Registro huérfano sin ninguna protección sí se incluye en ids_borrar."""
        gm_ext = [
            (40, "1001", "351600", 0, "Cliente A", 0),   # huérfano sin protección
            (41, "1001", "351700", 0, "Cliente B", 0),   # en histo → no se borra
        ]
        histo_keys = {("1001", "351700", "Cliente B")}
        ids = _ids_a_borrar(gm_ext, histo_keys, set())
        assert 40 in ids
        assert 41 not in ids

    def test_a9_inserciones_provienen_solo_de_histo(self):
        """A9: Las planillas que se insertan son un subconjunto de las planillas en histo."""
        histo_ext = [
            {"cod_men": "1001", "planilla": "351100", "no_entidad": "A",
             "fecha_min": "2026-01-10", "total_seriales": 20},
            {"cod_men": "1003", "planilla": "351200", "no_entidad": "B",
             "fecha_min": "2026-01-11", "total_seriales": 15},
            {"cod_men": "1006", "planilla": "351300", "no_entidad": "C",
             "fecha_min": "2026-01-12", "total_seriales": 10},
        ]
        planillas_revisadas = {"351300"}   # una marcada
        insertadas = _planillas_a_insertar(histo_ext, planillas_revisadas, {})

        histo_planillas = {str(r["planilla"]) for r in histo_ext}
        for p in insertadas:
            assert p in histo_planillas, (
                f"Planilla {p!r} insertada no proviene de histo"
            )
        # La revisada no se inserta
        assert "351300" not in insertadas


# ═══════════════════════════════════════════════════════════════════════════════
# PART B: Agrupacion_Escaner.py — botón "Registrar" (análisis estático)
# ═══════════════════════════════════════════════════════════════════════════════

class TestAgrupacionEscanerRegistrar:

    _src = (ROOT / "pages_home" / "Agrupacion_Escaner.py").read_text()

    def test_b1_registrar_carga_planillas_revisadas(self):
        """B1: El botón Registrar lee planillas_revisadas antes de insertar."""
        assert "planillas_revisadas" in self._src, (
            "Agrupacion_Escaner.py debe consultar planillas_revisadas en el botón Registrar"
        )

    def test_b1_registrar_salta_planilla_marcada(self):
        """B1: El botón Registrar usa _planillas_rev_reg para omitir lotes marcados."""
        assert "_planillas_rev_reg" in self._src, (
            "La variable _planillas_rev_reg debe existir en el botón Registrar"
        )
        assert "omitidos_rev" in self._src, (
            "Se debe contar los registros omitidos por planilla revisada"
        )

    def test_b1_sincronizar_periodo_respeta_planillas_revisadas(self):
        """B1: sincronizar_periodo también tiene la guarda planillas_revisadas_set."""
        assert "planillas_revisadas_set" in self._src


# ═══════════════════════════════════════════════════════════════════════════════
# PART C: 7_Gestion_Pagos.py — guardas SQL (análisis estático)
# ═══════════════════════════════════════════════════════════════════════════════

class TestGestionPagosGuardas:

    _src = (ROOT / "pages_logistica" / "7_Gestion_Pagos.py").read_text()

    def test_c1_recalcular_preview_incluye_guarda(self):
        """C1: La consulta de preview de Tab4 incluye NOT IN planillas_revisadas."""
        assert (
            "NOT IN (SELECT lot_esc FROM planillas_revisadas)" in self._src
        ), "Tab4 preview debe filtrar planillas_revisadas"

    def test_c2_recalcular_update_incluye_guarda(self):
        """C2: El UPDATE de Tab4 incluye la guarda planillas_revisadas al menos 2 veces."""
        count = self._src.count(
            "NOT IN (SELECT lot_esc FROM planillas_revisadas)"
        )
        assert count >= 2, (
            f"Se esperan al menos 2 ocurrencias de la guarda planillas_revisadas "
            f"(preview + update); se encontraron {count}"
        )

    def test_c3_guardas_van_acompanadas_de_editado_manualmente(self):
        """C3: Las guardas de planillas_revisadas coexisten con editado_manualmente = 0."""
        assert "editado_manualmente = 0" in self._src or \
               "editado_manualmente=0" in self._src, (
            "Las queries de actualización deben proteger también editado_manualmente"
        )


# ═══════════════════════════════════════════════════════════════════════════════
# PART D: 3_Ordenes.py y Procesador_Ordenes.py — no escriben gestiones_mensajero
# ═══════════════════════════════════════════════════════════════════════════════

class TestModulosNoEscribenGestiones:

    def test_d1_ordenes_no_escribe_gestiones_mensajero(self):
        """D1: 3_Ordenes.py solo inserta en tabla ordenes, no en gestiones_mensajero."""
        src = (ROOT / "pages_logistica" / "3_Ordenes.py").read_text().upper()
        assert "INSERT INTO GESTIONES_MENSAJERO" not in src, \
            "3_Ordenes.py no debe insertar en gestiones_mensajero"
        assert "UPDATE GESTIONES_MENSAJERO" not in src, \
            "3_Ordenes.py no debe actualizar gestiones_mensajero"
        assert "DELETE FROM GESTIONES_MENSAJERO" not in src, \
            "3_Ordenes.py no debe eliminar de gestiones_mensajero"

    def test_d2_procesador_ordenes_no_escribe_gestiones_mensajero(self):
        """D2: Procesador_Ordenes.py solo actualiza tabla ordenes, no gestiones_mensajero."""
        src = (ROOT / "pages_home" / "Procesador_Ordenes.py").read_text().upper()
        assert "INSERT INTO GESTIONES_MENSAJERO" not in src, \
            "Procesador_Ordenes.py no debe insertar en gestiones_mensajero"
        assert "UPDATE GESTIONES_MENSAJERO" not in src, \
            "Procesador_Ordenes.py no debe actualizar gestiones_mensajero"
        assert "DELETE FROM GESTIONES_MENSAJERO" not in src, \
            "Procesador_Ordenes.py no debe eliminar de gestiones_mensajero"
