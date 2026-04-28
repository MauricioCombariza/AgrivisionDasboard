# -*- coding: utf-8 -*-
"""
Ajuste Direcciones Leonisa
==========================
Carga un .xlsx con columna "Dirección Residencia", aplica
normalización al formato Leonisa y genera la columna "dir_ajustada".

Transformaciones principales:
  - CARRERA / CRA / KR  → KRA
  - CALLE / CLL / CL    → CLL
  - DIAGONAL            → DG
  - TRANSVERSAL / TR    → TV
  - Elimina # y guiones entre dígitos
  - Une número + letra suelta: "78 K" → "78K", "57 C" → "57C"
  - Colapsa espacios múltiples
  - Elimina comas
"""

import io
import os
import re

import streamlit as st
import pandas as pd

# ── Tabla de abreviaciones de tipo de vía ────────────────────────────────────
# El orden importa: los patrones más largos primero para evitar reemplazos parciales
_VIA_MAP = [
    # ── Compuestos primero (AV CARRERA → KRA, AV CALLE → CLL) ──────────────────
    (r"\bAV(?:ENIDA)?\s+(?:CARRERA|CARERA|CARR|CRA|CR|KRA|KR)\b", "KRA"),
    (r"\bAV(?:ENIDA)?\s+(?:CALLE|CALE|CALL|CLL|CL)\b",            "CLL"),
    (r"\bAV(?:ENIDA)?\s+(?:DIAGONAL|DIAG|DG)\b",                  "DG"),
    (r"\bAV(?:ENIDA)?\s+(?:TRANSVERSAL|TRANSV|TV|TR)\b",          "TV"),
    # ── Simples ─────────────────────────────────────────────────────────────────
    (r"\bCALLE\b",       "CLL"),
    (r"\bCALL\b",        "CLL"),
    (r"\bCALE\b",        "CLL"),   # typo (una L)
    (r"\bCLLE\b",        "CLL"),   # typo (letras invertidas)
    (r"\bCLL\b",         "CLL"),
    (r"\bCL\b",          "CLL"),
    (r"\bCARRERA\b",     "KRA"),
    (r"\bCARERA\b",      "KRA"),   # typo frecuente (una R)
    (r"\bCARR\b",        "KRA"),
    (r"\bKRR\b",         "KRA"),   # typo frecuente (tres letras)
    (r"\bCRA\b",         "KRA"),
    (r"\bCR\b",          "KRA"),
    (r"\bKR\b",          "KRA"),
    (r"\bAK\b",          "KRA"),   # Autopista / Avenida Carrera abreviada
    (r"\bDIAGONAL\b",    "DG"),
    (r"\bDIAG\b",        "DG"),
    (r"\bTRANSVERSAL\b", "TV"),
    (r"\bTRANSV\b",      "TV"),
    (r"\bTR\b",          "TV"),
    (r"\bAVENIDA\b",     "AV"),
]

# ── Parser por tokens ────────────────────────────────────────────────────────
# Abreviaciones canónicas para keywords de complemento
_COMP_ABBREV: dict[str, str] = {
    'APARTAMENTO': 'APTO', 'APTO': 'APTO', 'AP': 'APTO',
    'TORRE': 'TORRE', 'TRR': 'TORRE',
    'PISO': 'PS', 'PS': 'PS',
    'BLOQUE': 'BLQ', 'BLQ': 'BLQ', 'BL': 'BLQ',
    'INTERIOR': 'INT', 'INT': 'INT',
    'LOCAL': 'LC', 'LC': 'LC',
    'CASA': 'CASA', 'CS': 'CASA',
    'MZA': 'MZA', 'MZ': 'MZA',
}

_CARDINALS_COMPOUND = ('SUR ESTE', 'SUR OESTE', 'NORTE ESTE', 'NORTE OESTE')
_CARDINALS_SIMPLE   = ('SUR', 'NORTE', 'ESTE', 'OESTE')

_VIA_TYPE_RE   = re.compile(r'^(KRA|CLL|DG|TV|AV)$')
_COORD_TOK_RE  = re.compile(r'^\d+[A-Z]*$')  # número con letras opcionales: 54C, 88I, 65, 79FBIS
_COMP_VAL_RE   = re.compile(r'^\d+[A-Z]*$|^[A-Z]$')  # valor tras keyword: 1106, 4, A


def _next_cardinal(tokens: list[str], i: int) -> tuple[str | None, int]:
    """Devuelve (cardinal, nuevo_índice) o (None, i) si no hay cardinal en posición i."""
    if i >= len(tokens):
        return None, i
    if i + 1 < len(tokens):
        comp = tokens[i] + ' ' + tokens[i + 1]
        if comp in _CARDINALS_COMPOUND:
            return comp, i + 2
    if tokens[i] in _CARDINALS_SIMPLE:
        return tokens[i], i + 1
    return None, i


_SPLIT_COORD_RE = re.compile(r'^\d{4,5}$')  # bloque numérico de 4-5 dígitos → partir


def _parse_y_limpiar(text: str) -> tuple[str, int]:
    """
    Parsea la dirección token a token.
    Retorna (resultado, coord_count) donde coord_count es el número de tokens
    de coordenada encontrados (necesitamos al menos 3 para una dirección válida).

      1. Busca el tipo de vía (KRA/CLL/…) en cualquier posición — descarta lo anterior
         (barrios, localidades, etc. que preceden a la dirección)
      2. Hasta 3 tokens de coordenada (\d+[A-Z]*), con cardinales intercalados
         • Si un token es un bloque de 4-5 dígitos puros, lo divide: últimos 2 = placa,
           el resto = número de cruce  ("4977" → "49" + "77")
      3. Cardinal final opcional
      4. Solo keywords de complemento + su valor (TORRE 4, APTO 1106, PS 1…)
         — el resto (nombres de conjuntos, instrucciones) se descarta
    """
    tokens = text.split()
    if not tokens:
        return text, 0

    # Encontrar la posición del tipo de vía (puede venir precedida de barrio/localidad)
    via_start = next((idx for idx, t in enumerate(tokens) if _VIA_TYPE_RE.match(t)), None)
    if via_start is None:
        return text, 0  # sin tipo de vía reconocido → no modificar

    parts: list[str] = [tokens[via_start]]
    i = via_start + 1

    # Si quedaron dos tipos de vía consecutivos (p.ej. "AV" + "KRA"), usar el segundo
    while i < len(tokens) and _VIA_TYPE_RE.match(tokens[i]):
        parts[0] = tokens[i]
        i += 1

    coord_count = 0

    # Leer coordenadas (máx 3 números) con cardinales intercalados
    while i < len(tokens) and coord_count < 3:
        card, new_i = _next_cardinal(tokens, i)
        if card:
            parts.append(card)
            i = new_i
            continue
        if _COORD_TOK_RE.match(tokens[i]):
            tok = tokens[i]
            # Bloque de 4-5 dígitos puros → cruce + placa concatenados, separar
            if _SPLIT_COORD_RE.match(tok):
                parts.append(tok[:-2])      # primeros dígitos → número de cruce
                coord_count += 1
                if coord_count < 3:
                    parts.append(tok[-2:])  # últimos 2 → placa
                    coord_count += 1
            else:
                parts.append(tok)
                coord_count += 1
            i += 1
        else:
            break  # token no reconocido → fin del bloque de coordenadas

    # Cardinal trailing (después del 3.er número)
    card, i = _next_cardinal(tokens, i)
    if card:
        parts.append(card)

    # Extraer solo complementos conocidos; ignorar el resto
    while i < len(tokens):
        tok = tokens[i]
        if tok in _COMP_ABBREV:
            abbrev = _COMP_ABBREV[tok]
            i += 1
            if i < len(tokens) and _COMP_VAL_RE.match(tokens[i]):
                parts.append(f"{abbrev} {tokens[i]}")
                i += 1
            else:
                parts.append(abbrev)
        else:
            i += 1  # descartar: nombre de conjunto, instrucción, etc.

    return ' '.join(parts), coord_count


def ajustar_dir_leonisa(raw: str) -> str:
    """
    Transforma una dirección al formato Leonisa (mínimo espacio, sin ruido).

    Ejemplos:
      "CARRERA 78 K  # 50   53 CASA"                                        → "KRA 78K 50 53 CASA"
      "KRA.81H 51C-81 SUR"                                                  → "KRA 81H 51C 81 SUR"
      "CLL 54C SUR 88I 65 CONJUNTO RESIDENCIAL TANGARA 1 TORRE 4 APTO 1106" → "CLL 54C SUR 88I 65 TORRE 4 APTO 1106"
      "CLL 51 SUR 87D-79 PISO 1 ENTREGAR DE LUNES A VIERNES 8 AM A 5 PM"   → "CLL 51 SUR 87D 79 PS 1"
    """
    if not isinstance(raw, str) or not raw.strip():
        return ""

    text = raw.upper().strip()

    # 1. Comas, puntos y símbolos de grado → espacio  ("KRA.81H" → "KRA 81H", "N°" → "N ")
    text = text.replace(",", " ").replace(".", " ").replace("°", " ").replace("º", " ")

    # 2. # → espacio
    text = text.replace("#", " ")

    # 2b. Indicadores de "número" usados como separador → eliminar
    #     NO., NRO, NUM, NUMERO son equivalentes a #
    text = re.sub(r'\b(?:NUMERO|NRO|NUM|NR|NO)\b', ' ', text)

    # 3. Guión entre cualquier par alfanumérico → espacio
    #    "50-53"→"50 53",  "87D-79"→"87D 79",  "81-J"→"81 J",  "86C-69-A"→"86C 69 A"
    #    Lookahead/lookbehind (zero-width) para no consumir los vecinos y así
    #    resolver cadenas como "93-B-08" en un solo paso sin perder el segundo guión.
    text = re.sub(r'(?<=[A-Z0-9])\s*-\s*(?=[A-Z0-9])', ' ', text)

    # 4. Insertar espacio entre letra y dígito contiguos
    #    ("CALLE56F" → "CALLE 56F", "99D19" → "99D 19", "49C27" → "49C 27")
    text = re.sub(r'([A-Z])(\d)', r'\1 \2', text)

    # 5. Sustituir tipo de vía
    for pattern, repl in _VIA_MAP:
        text = re.sub(pattern, repl, text)

    # 6. Separar dígito pegado a cardinal: "27SUR" → "27 SUR", "16NORTE" → "16 NORTE"
    text = re.sub(
        r'(\d+)(SUR\s+ESTE|SUR\s+OESTE|NORTE\s+ESTE|NORTE\s+OESTE|SUR|NORTE|ESTE|OESTE)\b',
        r'\1 \2', text,
    )

    # 7. Mover dígito antepuesto a keyword de complemento: "3PISO" → "PISO 3", "4TORRE" → "TORRE 4"
    _KW_PATTERN = r'APARTAMENTO|APTO|TORRE|TRR|PISO|BLOQUE|BLQ|INTERIOR|INT|LOCAL|CASA|MZA'
    text = re.sub(rf'(\d+)({_KW_PATTERN})\b', r'\2 \1', text)

    # 8. Unir número + letra suelta: "78 K" → "78K", "87 D" → "87D"
    text = re.sub(r'(\d+)\s+([A-Z])(?!\w)', r'\1\2', text)

    # 8b. Unir número + token "letras+BIS": "81 GBIS" → "81GBIS"
    #     Cubre el caso donde el BIS viene pegado a la letra del número ("GBis" como un token)
    text = re.sub(r'(\d+)\s+([A-Z]+BIS)\b', r'\1\2', text)

    # 9. Unir BIS al token anterior cuando BIS es un token separado: "87D BIS" → "87DBIS"
    text = re.sub(r'(\d+[A-Z]+)\s+BIS\b', r'\1BIS', text)

    # 10. Unir alfanumérico + letra suelta: "88IBIS A"→"88IBISA", "57ABIS B"→"57ABISB"
    #     Corre después de BIS para capturar la letra que le sigue al BIS
    text = re.sub(r'(\d+[A-Z]+)\s+([A-Z])(?!\w)', r'\1\2', text)

    # 11. Colapsar espacios
    text = re.sub(r'\s+', ' ', text).strip()

    # 12. Parser de tokens: coordenadas + complementos, descarta ruido
    result, coord_count = _parse_y_limpiar(text)

    # Validación: una dirección válida necesita vía + 3 coords (número, cruce, placa).
    # Si el parser extrajo menos de 3, la dirección quedó recortada → conservar original.
    if coord_count < 3:
        return raw.strip()

    return result


_DOWNLOADS = "/mnt/c/Users/mcomb/Downloads"
_COL_IDX    = 5          # columna 6 del archivo (índice 0-based)
_ENCODING   = "latin-1"  # codificación del .txt de Leonisa


def _guardar_txt(df: pd.DataFrame, nombre: str) -> str:
    """Guarda el DataFrame como .txt separado por pipe en Downloads y retorna la ruta."""
    ruta = os.path.join(_DOWNLOADS, nombre)
    df.to_csv(ruta, sep="|", header=False, index=False, encoding=_ENCODING)
    return ruta


# ════════════════════════════════════════════════════════════════════════════════
# UI
# ════════════════════════════════════════════════════════════════════════════════
st.title("📍 Ajuste Direcciones Leonisa")
st.markdown(
    "Carga el archivo `.txt` separado por `|` (sin encabezados). "
    "La herramienta normaliza la **columna 6** al formato estándar Leonisa "
    "y genera el archivo de salida con el mismo nombre del número de orden."
)

# ── Número de orden y archivo en la misma fila ────────────────────────────────
col_izq, col_der = st.columns([1, 2])
with col_izq:
    numero_orden = st.text_input("Número de orden", placeholder="Ej: 20240423")
with col_der:
    archivo = st.file_uploader("Archivo de texto (.txt)", type=["txt"])

if archivo is None:
    st.stop()

# ── Leer el archivo y mostrar conteo inmediatamente ───────────────────────────
try:
    df_raw = pd.read_csv(
        archivo, sep="|", header=None, encoding=_ENCODING, dtype=str
    )
except Exception as e:
    st.error(f"Error al leer el archivo: {e}")
    st.stop()

if df_raw.shape[1] <= _COL_IDX:
    st.error(
        f"El archivo solo tiene {df_raw.shape[1]} columna(s). "
        f"Se necesitan al menos {_COL_IDX + 1}."
    )
    st.stop()

st.success(f"Archivo cargado: **{len(df_raw):,} filas** — {df_raw.shape[1]} columnas")

if not numero_orden:
    st.info("Ingresa el número de orden para continuar.")
    st.stop()

# ── Procesar ──────────────────────────────────────────────────────────────────
if "leonisa_df" not in st.session_state:
    st.session_state["leonisa_df"] = None

if st.button("⚙️ Ajustar direcciones", type="primary"):
    with st.spinner("Procesando…"):
        df_out = df_raw.copy()
        df_out[_COL_IDX] = df_out[_COL_IDX].apply(ajustar_dir_leonisa)
    st.session_state["leonisa_df"] = df_out
    st.success(f"✅ {len(df_out)} filas procesadas")

df_result: pd.DataFrame | None = st.session_state.get("leonisa_df")

if df_result is None:
    st.stop()

# ── Vista comparativa ─────────────────────────────────────────────────────────
st.divider()
st.subheader("Resultado")

edited = st.data_editor(
    df_result,
    use_container_width=True,
    hide_index=False,
    disabled=[c for c in df_result.columns if df_result.columns.get_loc(c) != _COL_IDX],
    key="tabla_leonisa",
    height=500,
)

# Sincronizar ediciones manuales del usuario en la columna 6
# data_editor puede devolver columnas como strings aunque sean enteras → usar iloc
st.session_state["leonisa_df"].iloc[:, _COL_IDX] = edited.iloc[:, _COL_IDX].values

# ── Guardar en Downloads ──────────────────────────────────────────────────────
st.divider()
nombre_archivo = f"{numero_orden}.txt"
st.info(f"El archivo se guardará en `{_DOWNLOADS}` como **{nombre_archivo}**")

if st.button("💾 Guardar en Downloads", type="primary"):
    try:
        ruta = _guardar_txt(st.session_state["leonisa_df"], nombre_archivo)
        st.success(f"✅ Archivo guardado en: `{ruta}`")
    except Exception as e:
        st.error(f"Error al guardar: {e}")

# ── Vista previa de transformaciones ─────────────────────────────────────────
with st.expander("🔍 Ver muestra de transformaciones (columna 6)"):
    muestra = pd.DataFrame(
        {"original": df_raw[_COL_IDX], "ajustada": df_result[_COL_IDX]}
    ).drop_duplicates().head(30)
    st.dataframe(muestra, use_container_width=True, hide_index=True)
