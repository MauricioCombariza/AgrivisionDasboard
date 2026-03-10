# -*- coding: utf-8 -*-
"""
Estandarización de Direcciones Colombianas + Dirección Numérica
================================================================

Procesa y estandariza direcciones colombianas, y genera la dirección numérica
de 18 dígitos.

Formato dirección numérica (18 dígitos):
  [1]     Cardinal: NORTE/nada=1, SUR=2, SUR ESTE=3, ESTE=4
  [2]     Tipo vía: CL/DG=1, CR/TR=3
  [3-5]   Número vía principal (zero-padded)
  [6-8]   Letras vía principal (codificadas)
  [9]     Separador: CL/DG + placa par=3, impar=1; CR/TR + placa par=1, impar=3
  [10-12] Número vía secundaria (zero-padded)
  [13-15] Letras vía secundaria (codificadas)
  [16-18] Placa (zero-padded)
"""

import re
import os
import csv
import pandas as pd
import warnings
warnings.filterwarnings('ignore')


# ========== DATOS DE PRUEBA ==========

datos_prueba = [
    # (dirección original, dirección estandarizada esperada, dirección numérica esperada)
    ("CL 102 AA 89 25 MZ 110 CA 14", "CL 102A 89 25", None),
    ("CL 21 33 40", "CL 21 33 40", "110211003033100040"),
    ("CR 19 57 60 BL 5 AP 302", "CR 19 57 60", "130191001057100060"),
    ("CL 13 9 36 AP 202 ED CRN", "CL 13 9 36", "110131003009100036"),
    ("CL 15 13 73", "CL 15 13 73", "110151001013100073"),
    ("CR 41F 20D 52", "CR 41F 20D 52", "130412741020216052"),
    ("DG 142F 34 19", "DG 142F 34 19", "111422741034100019"),
    ("DG 43 34 20 AP 232 TO 4 CURASAO EST", "DG 43 34 20 ESTE", "410431003034100020"),
    ("CL 54A 50 92 AP 201", "CL 54A 50 92", "110541293050100092"),
    ("CL 37 45 200 AP 1521 TO 6 CONJ LA VIDA ES B", "CL 37 45 200", "110371003045100200"),
    ("CL 57A 66 BB 96 LC DOS ESQUINAS", "CL 57A 66B 96", None),
    ("calle 95 # 49-22 clinica del pie y spa", "CL 95 49 22", None),
    ("Calle 63f #28A-11 Panaderia mil delicias", "CL 63F 28A 11", None),
    ("KR 21 A 83 21 CASA,Bogota, D.C.~~~Barrios Unidos~~~~~~KR 21 A 83 21 CASA", "CR 21A 83 21", None),
    ("Cr 60 D # 90 04 apartamento 614,Bogota, D.C.~~~Barrios Unidos~~~~~~Cr 60 D # 90 04 apartamento 614", "CR 60D 90 04", None),
    ("cra67#67a-10 apto 203 Cundinamarca,Bogota, D.C.~~~Barrios Unidos~~~~~~cra67#67a-10 apto 203 Cundinamarca", "CR 67 67A 10", None),
    ("carrera 28 63 g 46 casa,Bogota, D.C.~~~Bogota~~~~~~carrera 28 63 g 46 casa", "CR 28 63G 46", None),
    ("CLL 72# 20-03 401,Bogota, D.C.~~~Bogota~~~~~~CLL 72# 20-03 401", "CL 72 20 03", None),
    ("carrera 26 # 63b-13 casa,Bogota, D.C.~~~Barrios Unidos~~~~~~carrera 26 # 63b-13 casa", "CR 26 63B 13", None),
    ("Carrera 22#63c-68 Carrera 22#63c-68,Bogota, D.C.~~~Barrios Unidos~~~~~~Carrera 22#63c-68 Carrera 22#63c-68", "CR 22 63C 68", None),
    ("cra 27 a # 66-38 almacén kimautos,Bogota, D.C.~~~Barrios Unidos~~~~~~cra 27 a # 66-38 almacén kimautos", "CR 27A 66 38", None),
    ("Calle 71 # 21-21, Barrio Alcazarez Casa, Piso 2.,Bogota, D.C.~~~Barrios Unidos~~~~~~Calle 71 # 21-21, Barrio Alcazarez Casa, Piso 2.", "CL 71 21 21", None),
    ("calle 68 #28b17 tirnda de bicicletas local", "CL 68 68B 17", None),
    ("transversal 14B Nu 42-43", "TR 14B 42 43", None),
    # Casos con bis y puntos cardinales
    ("CR 79Fbis 36A 16 BL8 INT 2 AP 403 SUR", "CR 79FBIS 36A 16 SUR", None),
    ("CR 80 35 24 BL 45 INT 01 AP 401 SUR", "CR 80 35 24 SUR", None),
    ("CL 39A 73A 26 PS 2 SUR", "CL 39A 73A 26 SUL", None),
    ("CR 73Bbis 26 81B 9 AP 313 SUPERMANZANA 2 SU", "CR 73BBIS 26 81 SUR", None),
    ("CL 36B 73F 15 SUR ESTE", "CL 36B 73F 15 SUR ESTE", None),
    ("CR 78J 3539 BL 29 INT 04 AP 404 SUPER MANZ", "CR 78J 35 39 SUR", None),
    ("CR 78I 38A 09 SUR", "CR 78I 38A 09 SUR", None),
    ("TR 73D 38C 41 PS 3 SUR", "TR 73D 38C 41 SUR", None),
    ("CL 39 78G 09 SUR", "CL 39 78G 09 SUL", None),
    # Casos adicionales para validar dirección numérica
    ("CR 69D 1 51 TRR 3 AP 924 TORRES DE SAN ISID SUR", "CR 69D 1 51 SUR", "230692163001100051"),
    ("CL 3 69D 34 CS 103 SUR", "CL 3 69D 34 SUR", "210031001069216034"),
    ("CL 3 70 25 CS 94 ARBOLEDA SAN GABRIEL V SUR", "CL 3 70 25 SUR", "210031003070100025"),
    ("CR 69D 1 60 SUR", "CR 69D 1 60 SUR", "230692161001100060"),
    ("CR 51Dbis 42B 49 SUR", "CR 51Dbis 42B 49 SUR", "230512173042158049"),
    ("CR 68CbisA 38C 42 SUR", "CR 68CbisA 38C 42 SUR", "230681891038187042"),
]


# ========== FUNCIONES DE ESTANDARIZACION ==========

def preprocesar_direccion(direccion):
    """
    Preprocesamiento: limpia ruido antes de la estandarizacion.
    - Corta en ~~~ (toma primera parte)
    - Elimina parentesis y su contenido
    - Elimina puntos
    - Maneja tipos compuestos (AVDA calle, AC, AK)
    - Reemplaza No/No./numero por espacio
    - Maneja formato invertido (nums antes del tipo)
    - Descarta prefijos de ciudad
    """
    # Normalizar tildes/acentos en tipos de via
    tildes = {'á': 'a', 'é': 'e', 'í': 'i', 'ó': 'o', 'ú': 'u',
              'Á': 'A', 'É': 'E', 'Í': 'I', 'Ó': 'O', 'Ú': 'U'}
    for t, s in tildes.items():
        direccion = direccion.replace(t, s)

    # Cortar en ~~~ (toma primera parte)
    if '~~~' in direccion:
        direccion = direccion.split('~~~')[0]

    # Eliminar contenido entre parentesis
    direccion = re.sub(r'\([^)]*\)', ' ', direccion)

    # Eliminar puntos
    direccion = re.sub(r'\.', ' ', direccion)

    # Avenidas con nombre propio → equivalente numérico
    nombres_vias = {
        r'\bAV\w*\s+(?:EL\s+)?DORADO\b': 'CL 26',
        r'\bAV\w*\s+(?:DE\s+LAS\s+|LAS\s+)?AMERICAS\b': 'CL 6',
        r'\bAV\w*\s+BOYACA\b': 'CR 72',
        r'\bAV\w*\s+CIUDAD\s+DE\s+CALI\b': 'CR 86',
    }
    for patron, reemplazo in nombres_vias.items():
        direccion = re.sub(patron, reemplazo, direccion, flags=re.IGNORECASE)

    # AV + número (sin nombre) → CR (Avenida/Carrera): "AV 9" → "CR 9"
    direccion = re.sub(r'\b(?:AV|AVENIDA)\s+(\d)', r'CR \1', direccion, flags=re.IGNORECASE)

    # Tipos compuestos: AVDA calle/call → CL (eliminar AVDA antes de calle/call)
    direccion = re.sub(r'\bAVDA\s+', '', direccion, flags=re.IGNORECASE)
    # AC (Avenida Calle) → CL, AK (Avenida Carrera) → CR
    direccion = re.sub(r'\bAC\b', 'CL', direccion, flags=re.IGNORECASE)
    direccion = re.sub(r'\bAK\b', 'CR', direccion, flags=re.IGNORECASE)

    # No / No. / numero / n (antes de digito) → espacio (equivalentes a #)
    direccion = re.sub(r'\bnumero\b', ' ', direccion, flags=re.IGNORECASE)
    direccion = re.sub(r'\b(No|Nu)\b', ' ', direccion, flags=re.IGNORECASE)
    direccion = re.sub(r'\bn(?=\d)', ' ', direccion, flags=re.IGNORECASE)

    # Normalizar espacios
    direccion = re.sub(r'\s+', ' ', direccion).strip()

    # Separar tipo pegado a numero antes de buscar: "call100" → "call 100"
    direccion = re.sub(
        r'\b(calle|call|cl|cll|carrera|carre|crra|crr|cr|kr|kra|cra|diagonal|dig|dg|transversal|trv|tv|tr|avenida|av)(\d)',
        r'\1 \2', direccion, flags=re.IGNORECASE
    )

    # Buscar primer tipo de via reconocido
    tipo_pattern = (
        r'\b(calle|call|cl|cll|carrera|carre|crra|crr|cr|kr|kra|cra|'
        r'diagonal|dig|dg|transversal|trv|tv|tr|avenida|av)\b'
    )
    match = re.search(tipo_pattern, direccion, flags=re.IGNORECASE)

    if match:
        before = direccion[:match.start()].strip()
        from_type = direccion[match.start():]

        # Extraer numeros del texto antes del tipo
        nums = re.findall(r'\d+[A-Za-z]?', before)

        if nums and not re.search(r'[a-zA-Z]{3,}', re.sub(r'\d+[A-Za-z]?', '', before).strip()):
            # Formato invertido: "28B-21 Calle 74" → "Calle 74 28B 21"
            nums_str = ' '.join(nums)
            # Insertar nums despues del tipo+via
            tipo_via_match = re.match(
                r'(\w+\s+\d+[A-Za-z]*(?:\s*bis\s*[A-Za-z]?)?)(.*)',
                from_type, re.IGNORECASE
            )
            if tipo_via_match:
                tipo_via = tipo_via_match.group(1)
                resto = tipo_via_match.group(2)
                direccion = f"{tipo_via} {nums_str}{resto}"
            else:
                direccion = f"{from_type} {nums_str}"
        else:
            # Prefijo de ciudad/texto → descartar
            direccion = from_type

    direccion = re.sub(r'\s+', ' ', direccion).strip()
    return direccion


def normalizar_tipo_via(direccion):
    tipos_via = {
        r'\b(calle|call|cl|cll)\b': 'CL',
        r'\b(carrera|carre|crra|crr|cr|kr|kra|cra)\b': 'CR',
        r'\b(diagonal|dig|dg)\b': 'DG',
        r'\b(transversal|trv|tv|tr)\b': 'TR',
        r'\b(avenida|av)\b': 'AV'
    }
    for patron, reemplazo in tipos_via.items():
        direccion = re.sub(patron, reemplazo, direccion, flags=re.IGNORECASE)
    return direccion


def separar_componentes_pegados(direccion):
    # Separar tipo pegado a numero: "calle75" → "calle 75", "call100" → "call 100"
    direccion = re.sub(
        r'\b(calle|call|cl|cll|carrera|carre|crra|crr|cr|kr|kra|cra|diagonal|dig|dg|transversal|trv|tv|tr|avenida|av)(\d)',
        r'\1 \2', direccion, flags=re.IGNORECASE
    )
    # Separar # pegado: "#67" → "# 67"
    direccion = re.sub(r'#(\d)', r'# \1', direccion)
    # Eliminar "NO" pegado a numero+letra (NO = #): "23GNO" → "23G"
    direccion = re.sub(r'(\d+[A-Za-z]?)NO\b', r'\1', direccion, flags=re.IGNORECASE)
    # Separar cardinal pegado a numero: "16sur" → "16 sur", "20este" → "20 este"
    direccion = re.sub(
        r'(\d+)(sur\s*este|sureste|sur\s*oeste|suroeste|norte\s*este|noreste|'
        r'norte\s*oeste|noroeste|sur|norte|este|oeste)\b',
        r'\1 \2', direccion, flags=re.IGNORECASE
    )
    # Separar bis pegado: "79Fbis" → "79F bis"
    direccion = re.sub(r'(\d+[A-Za-z]?)(bis)\b', r'\1 \2', direccion, flags=re.IGNORECASE)
    # Separar letra+digitos: "28b17" → "28b 17" (loop para cascadas: "75A27a28" → "75A 27a 28")
    while True:
        nueva = re.sub(r'(\d+[A-Za-z])(\d+)', r'\1 \2', direccion)
        if nueva == direccion:
            break
        direccion = nueva
    # Separar 5+ digitos: ultimos 2 son placa: "11537" → "115 37"
    direccion = re.sub(r'(?<!\d)(\d{3,})(\d{2})(?!\d)', r'\1 \2', direccion)
    # Separar 4 digitos en pares: "3539" → "35 39"
    direccion = re.sub(r'(?<!\d)(\d{2})(\d{2})(?!\d)', r'\1 \2', direccion)
    return direccion


def limpiar_caracteres_especiales(direccion):
    direccion = re.sub(r'[#\-()\.]', ' ', direccion)
    direccion = re.sub(r'[,~]', ' ', direccion)
    direccion = re.sub(r'\s+', ' ', direccion)
    return direccion.strip()


def extraer_punto_cardinal(direccion):
    # Primero: extraer cardinal del medio entre dos números: "48B Sur 40 ..." → "48B 40 ..."
    # No requiere $ al final, funciona con texto adicional después
    m_mid = re.search(
        r'(\d+[A-Za-z]*)\s+(Sur\s*Este|Sureste|Sur\s*Oeste|Suroeste|'
        r'Norte\s*Este|Noreste|Norte\s*Oeste|Noroeste|Sur|Norte|Este|Oeste)\s+(\d+[A-Za-z]*)',
        direccion, flags=re.IGNORECASE
    )
    cardinal_medio = None
    if m_mid:
        cardinal_medio = m_mid.group(2)
        # Remover el cardinal del medio, mantener todo lo demás
        direccion = (direccion[:m_mid.start()] + m_mid.group(1) + ' ' +
                     m_mid.group(3) + direccion[m_mid.end():])
        direccion = re.sub(r'\s+', ' ', direccion).strip()

    # Cardinal después de número seguido de texto no-numérico (ruido):
    # "61 sur Multifamiliar Choco" → extraer "sur", quitar del string
    # El texto que sigue NO debe ser otro cardinal (para no romper "SUR ESTE" compuesto)
    m_post = re.search(
        r'(\d+[A-Za-z]*)\s+(Sur\s*Este|Sureste|Sur\s*Oeste|Suroeste|'
        r'Norte\s*Este|Noreste|Norte\s*Oeste|Noroeste|Sur|Norte|Este|Oeste)'
        r'\s+(?!Este\b|Oeste\b|Sur\b|Norte\b)([A-Za-z]{3,})',
        direccion, flags=re.IGNORECASE
    )
    if m_post and not cardinal_medio:
        cardinal_medio = m_post.group(2)
        # Remover solo el cardinal, mantener el número antes y el texto después
        direccion = (direccion[:m_post.start()] + m_post.group(1) + ' ' +
                     m_post.group(3) + direccion[m_post.end():])
        direccion = re.sub(r'\s+', ' ', direccion).strip()

    patron = (
        r'\b(SUR\s*ESTE|SUREST|SURESTE|SUR\s*OESTE|SUROESTE|'
        r'NORTE\s*ESTE|NORESTE|NOREST|NORTE\s*OESTE|NOROESTE|'
        r'SUR|NORTE|ESTE|OESTE|EST|SUL)\s*$'
    )
    match = re.search(patron, direccion, flags=re.IGNORECASE)
    if match:
        cardinal = match.group(1).upper().strip()
        if cardinal in ('EST', 'ESTE'):
            cardinal = 'ESTE'
        elif cardinal in ('SURESTE', 'SUREST'):
            cardinal = 'SUR ESTE'
        elif cardinal == 'SUROESTE':
            cardinal = 'SUR OESTE'
        elif cardinal in ('NORESTE', 'NOREST'):
            cardinal = 'NORTE ESTE'
        elif cardinal == 'NOROESTE':
            cardinal = 'NORTE OESTE'
        cardinal = re.sub(r'\s+', ' ', cardinal)
        direccion_sin_cardinal = direccion[:match.start()].strip()
        return direccion_sin_cardinal, cardinal

    # Si se encontró cardinal en el medio (entre números), usarlo
    if cardinal_medio:
        cardinal_medio = cardinal_medio.upper().strip()
        if cardinal_medio in ('EST', 'ESTE'):
            cardinal_medio = 'ESTE'
        elif cardinal_medio in ('SURESTE', 'SUREST'):
            cardinal_medio = 'SUR ESTE'
        elif cardinal_medio == 'SUROESTE':
            cardinal_medio = 'SUR OESTE'
        elif cardinal_medio in ('NORESTE', 'NOREST'):
            cardinal_medio = 'NORTE ESTE'
        elif cardinal_medio == 'NOROESTE':
            cardinal_medio = 'NORTE OESTE'
        cardinal_medio = re.sub(r'\s+', ' ', cardinal_medio)
        return direccion, cardinal_medio

    return direccion, None


def eliminar_info_adicional(direccion):
    palabras_eliminar = [
        r'\bAP\b.*', r'\bAPO\b.*', r'\bapto\b.*', r'\bapartamento\b.*',
        r'\bBL\d*\b', r'\bbloque\b.*',
        r'\bTO\b.*', r'\btorre\b.*',
        r'\bMZ\b.*', r'\bmanzana\b.*',
        r'\bCA\b.*', r'\bcasa\b.*',
        r'\bLC\b.*', r'\blocal\b.*',
        r'\bED\b.*', r'\bedificio\b.*',
        r'\bOF\b.*', r'\boficina\b.*',
        r'\bCONJ\b.*', r'\bconjunto\b.*',
        r'\bBarrios?\b.*', r'\bBogota.*', r'\bCundinamarca.*',
        r'\bPiso.*', r'\bPS\b.*',
        r'\bINT\b.*', r'\binterior\b.*',
        r'\bEST\b.*',
        r'\bSUPERMANZANA.*', r'\bSUPER\s*MANZ.*',
        r'\bSU\s*$',
        r'\bTRR\b.*', r'\bCS\b.*',
        r'\bTORRES\b.*', r'\bARBOLEDA\b.*',
        r'\bBUZON\b.*', r'\bPAQUETES\b.*',
        r'\bUnidad\b.*', r'\bmetropolis\b.*',
        r'\bCc\b.*', r'\bMac\b.*',
        r'\bvilla\b.*',
        r'\bSalamanca\b.*', r'\bresidencial\b.*',
        r'\bparque\b.*',
        r'\bbodega\b.*',
        r'\bpeluqueria\b.*',
        r'\betapa\b.*',
        r'\b\d+er\b', r'\b\d+do\b', r'\b\d+ro\b',
        r'\bD\s*C\b',
    ]
    for patron in palabras_eliminar:
        direccion = re.sub(patron, '', direccion, flags=re.IGNORECASE)
    direccion = re.sub(r'\s+', ' ', direccion).strip()
    return direccion


def pegar_letras_a_numeros(direccion):
    # Pegar bis a numeros: "79F bis" → "79Fbis"
    direccion = re.sub(r'(\d+[A-Za-z]?)\s+(bis)\b', r'\1\2', direccion, flags=re.IGNORECASE)
    # Pegar letras sueltas a numeros: "21 A" → "21A"
    direccion = re.sub(r'(\d+)\s+([A-Za-z])(?=\s|\d|$)', r'\1\2', direccion)
    # Re-pegar bis despues de letra: "63D bis" → "63Dbis" (para "63 D bis" → "63D" → "63Dbis")
    direccion = re.sub(r'(\d+[A-Za-z])\s+(bis)\b', r'\1\2', direccion, flags=re.IGNORECASE)
    # Simplificar letras repetidas: "102AA" → "102A"
    direccion = re.sub(r'(\d+)([A-Za-z])\2+', r'\1\2', direccion)
    return direccion


def convertir_mayusculas(direccion):
    return direccion.upper()


def extraer_componentes(direccion):
    patron = r'\b(CL|CR|DG|TR|AV)\s+(\d+[A-Za-z]*(?:BIS)?[A-Za-z]?)\s+(\d+[A-Za-z]*)\s+(\d+[A-Za-z]*)'
    match = re.search(patron, direccion, flags=re.IGNORECASE)
    if match:
        return (match.group(1).upper(), match.group(2).upper(),
                match.group(3).upper(), match.group(4).upper())
    return None, None, None, None


def reconstruir_direccion(tipo, via1, via2, numero, cardinal=None):
    if all([tipo, via1, via2, numero]):
        base = f"{tipo} {via1} {via2} {numero}"
        return f"{base} {cardinal}" if cardinal else base
    return None


def estandarizar_direccion(direccion_original):
    if pd.isna(direccion_original) or direccion_original == '':
        return None
    direccion = direccion_original

    # Paso 0: Preprocesamiento (~~~, parentesis, puntos, No, formato invertido)
    direccion = preprocesar_direccion(direccion)

    # Paso 1: Separar componentes pegados
    direccion = separar_componentes_pegados(direccion)

    # Paso 2: Limpiar caracteres especiales
    direccion = limpiar_caracteres_especiales(direccion)

    # Paso 3: Simplificar letras repetidas sueltas
    direccion = re.sub(r'\b([A-Z])\1+\b', r'\1', direccion, flags=re.IGNORECASE)

    # Paso 3.5: Eliminar "D C" / "DC" (Distrito Capital) antes de extraer cardinal
    direccion = re.sub(r'\bD\s*C\b', '', direccion, flags=re.IGNORECASE)
    direccion = re.sub(r'\s+', ' ', direccion).strip()

    # Paso 4: Extraer punto cardinal (tambien maneja cardinal en medio)
    direccion, cardinal = extraer_punto_cardinal(direccion)

    # Paso 5: Eliminar info adicional
    direccion = eliminar_info_adicional(direccion)

    # Paso 6: Pegar letras a numeros y bis
    direccion = pegar_letras_a_numeros(direccion)

    # Paso 7: Normalizar tipo de via
    direccion = normalizar_tipo_via(direccion)

    # Paso 7.5: Eliminar segundo tipo de via (separador): "CL 71A CR 29B 14" → "CL 71A 29B 14"
    direccion = re.sub(
        r'(\b(?:CL|CR|DG|TR|AV)\s+\d+[A-Za-z]*(?:BIS[A-Za-z]?)?)\s+(?:CL|CR|DG|TR|AV)\s+',
        r'\1 ', direccion, flags=re.IGNORECASE
    )

    # Paso 8: Mayusculas
    direccion = convertir_mayusculas(direccion)

    # Paso 9: Extraer componentes
    tipo, via1, via2, numero = extraer_componentes(direccion)

    # Paso 10: Reconstruir
    return reconstruir_direccion(tipo, via1, via2, numero, cardinal)


# ========== FUNCIONES DE DIRECCION NUMERICA ==========

def codificar_letras(letras):
    """
    Codifica combinaciones de letras a 3 dígitos.

    Tabla de codificación (ordenada, BIS es el menor, A la letra mas pequeña):
      Sin letras     -> 100
      BIS            -> 101
      BIS+Y          -> 101 + pos(Y)         [A=1..Z=26]
      X              -> 129 + 29*pos(X)       [A=0..Z=25]
      X+BIS          -> 129 + 29*pos(X) + 1
      X+BIS+Y        -> 129 + 29*pos(X) + 1 + pos(Y)  [A=1..Z=26]
    """
    if not letras:
        return 100

    letras = letras.upper().strip()
    if not letras:
        return 100

    # BIS solo
    if letras == 'BIS':
        return 101

    # BIS + letra (ej: BISA, BISB)
    m = re.match(r'^BIS([A-Z])$', letras)
    if m:
        return 101 + (ord(m.group(1)) - ord('A') + 1)

    # Letra sola (ej: A, F, D)
    m = re.match(r'^([A-Z])$', letras)
    if m:
        return 129 + 29 * (ord(m.group(1)) - ord('A'))

    # Letra + BIS (ej: DBIS, FBIS)
    m = re.match(r'^([A-Z])BIS$', letras)
    if m:
        return 129 + 29 * (ord(m.group(1)) - ord('A')) + 1

    # Letra + BIS + letra (ej: CBISA, DBISB)
    m = re.match(r'^([A-Z])BIS([A-Z])$', letras)
    if m:
        return (129 + 29 * (ord(m.group(1)) - ord('A'))
                + 1 + (ord(m.group(2)) - ord('A') + 1))

    # Fallback: primera letra
    if letras[0].isalpha():
        return 129 + 29 * (ord(letras[0]) - ord('A'))

    return 100


def parsear_componente_via(componente):
    """
    Separa un componente de vía en (número, letras).
    Ej: '41F' -> (41, 'F'), '51DBIS' -> (51, 'DBIS'), '33' -> (33, '')
    """
    m = re.match(r'^(\d+)(.*)', componente.upper())
    if m:
        return int(m.group(1)), m.group(2).strip()
    return None, ''


def generar_direccion_numerica(dir_estandarizada):
    """
    Genera la dirección numérica de 18 dígitos.

    Formato:
      [1]     Cardinal: NORTE/nada=1, SUR=2, SUR ESTE=3, ESTE=4
      [2]     Tipo vía: CL/DG=1, CR/TR=3
      [3-5]   Numero vía principal (3 dígitos, zero-padded)
      [6-8]   Letras vía principal (3 dígitos, codificadas)
      [9]     Separador: CL/DG + placa par=3, impar=1; CR/TR + placa par=1, impar=3
      [10-12] Numero vía secundaria (3 dígitos, zero-padded)
      [13-15] Letras vía secundaria (3 dígitos, codificadas)
      [16-18] Placa (3 dígitos, zero-padded)
    """
    if not dir_estandarizada:
        return None

    partes = dir_estandarizada.upper().split()

    # --- Extraer cardinal al final ---
    cardinal = None
    cardinales_compuestos = {'SUR ESTE', 'SUR OESTE', 'NORTE ESTE', 'NORTE OESTE'}
    if len(partes) >= 2 and ' '.join(partes[-2:]) in cardinales_compuestos:
        cardinal = ' '.join(partes[-2:])
        partes = partes[:-2]
    elif len(partes) >= 1 and partes[-1] in ('SUR', 'NORTE', 'ESTE', 'OESTE', 'SUL'):
        cardinal = partes[-1]
        if cardinal == 'SUL':
            cardinal = 'SUR'
        partes = partes[:-1]

    # Codificar cardinal
    if cardinal is None or cardinal == 'NORTE':
        d_cardinal = 1
    elif cardinal == 'SUR':
        d_cardinal = 2
    elif cardinal in ('SUR ESTE', 'SURESTE'):
        d_cardinal = 3
    elif cardinal == 'ESTE':
        d_cardinal = 4
    else:
        d_cardinal = 1

    # --- Tipo y componentes ---
    if len(partes) < 4:
        return None

    tipo = partes[0]
    via1_str = partes[1]
    via2_str = partes[2]
    placa_str = partes[3]

    # Codificar tipo de vía (CL/DG=1, CR/TR=3)
    tipo_map = {'CL': 1, 'DG': 1, 'CR': 3, 'TR': 3}
    d_tipo = tipo_map.get(tipo)
    if d_tipo is None:
        return None

    # Separador según tipo y paridad de la placa
    # CL/DG: placa par→3, placa impar→1
    # CR/TR: placa par→1, placa impar→3
    placa_num_tmp, _ = parsear_componente_via(placa_str)
    placa_es_par = (placa_num_tmp % 2 == 0) if placa_num_tmp is not None else True
    if tipo in ('CL', 'DG'):
        d_sep = 3 if placa_es_par else 1
    else:
        d_sep = 1 if placa_es_par else 3

    # --- Parsear componentes ---
    via1_num, via1_let = parsear_componente_via(via1_str)
    via2_num, via2_let = parsear_componente_via(via2_str)
    placa_num, _ = parsear_componente_via(placa_str)

    if via1_num is None or via2_num is None or placa_num is None:
        return None

    # --- Codificar letras ---
    d_via1_let = codificar_letras(via1_let)
    d_via2_let = codificar_letras(via2_let)

    # --- Construir dirección numérica ---
    dir_num = (
        f"{d_cardinal}"
        f"{d_tipo}"
        f"{via1_num:03d}"
        f"{d_via1_let:03d}"
        f"{d_sep}"
        f"{via2_num:03d}"
        f"{d_via2_let:03d}"
        f"{placa_num:03d}"
    )

    return dir_num


def debug_direccion_numerica(dir_estandarizada):
    """Muestra el desglose de cada campo de la dirección numérica."""
    if not dir_estandarizada:
        print("  (sin direccion estandarizada)")
        return

    partes = dir_estandarizada.upper().split()

    cardinal = None
    cardinales_compuestos = {'SUR ESTE', 'SUR OESTE', 'NORTE ESTE', 'NORTE OESTE'}
    if len(partes) >= 2 and ' '.join(partes[-2:]) in cardinales_compuestos:
        cardinal = ' '.join(partes[-2:])
        partes = partes[:-2]
    elif len(partes) >= 1 and partes[-1] in ('SUR', 'NORTE', 'ESTE', 'OESTE', 'SUL'):
        cardinal = partes[-1]
        if cardinal == 'SUL':
            cardinal = 'SUR'
        partes = partes[:-1]

    if len(partes) < 4:
        print(f"  No se pueden extraer 4 componentes de: {partes}")
        return

    tipo = partes[0]
    via1_num, via1_let = parsear_componente_via(partes[1])
    via2_num, via2_let = parsear_componente_via(partes[2])
    placa_num, _ = parsear_componente_via(partes[3])

    tipo_map = {'CL': 1, 'DG': 1, 'CR': 3, 'TR': 3}

    if cardinal is None or cardinal == 'NORTE':
        d_cardinal = 1
    elif cardinal == 'SUR':
        d_cardinal = 2
    elif cardinal in ('SUR ESTE',):
        d_cardinal = 3
    elif cardinal in ('ESTE',):
        d_cardinal = 4
    else:
        d_cardinal = 1

    placa_es_par = (placa_num % 2 == 0) if placa_num else True
    if tipo in ('CL', 'DG'):
        d_sep = 3 if placa_es_par else 1
    else:
        d_sep = 1 if placa_es_par else 3

    print(f"  Entrada:     {dir_estandarizada}")
    print(f"  [1] Cardinal:    {cardinal or 'ninguno'} -> {d_cardinal}")
    print(f"  [2] Tipo:        {tipo} -> {tipo_map.get(tipo, '?')}")
    print(f"  [3-5] Via1 num:  {via1_num} -> {via1_num:03d}")
    print(f"  [6-8] Via1 let:  '{via1_let}' -> {codificar_letras(via1_let):03d}")
    print(f"  [9] Separador:   {tipo} placa={placa_num} ({'par' if placa_es_par else 'impar'}) -> {d_sep}")
    print(f"  [10-12] Via2 num:  {via2_num} -> {via2_num:03d}")
    print(f"  [13-15] Via2 let:  '{via2_let}' -> {codificar_letras(via2_let):03d}")
    print(f"  [16-18] Placa:     {placa_num} -> {placa_num:03d}")
    print(f"  Resultado:   {generar_direccion_numerica(dir_estandarizada)}")


# ========== FUNCIONES DE SECTOR ==========

_SECTORES = None

def _cargar_sectores():
    ruta = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'sectores.csv')
    sectores = []
    with open(ruta, 'r', encoding='utf-8') as f:
        for row in csv.DictReader(f):
            sectores.append(row)
    return sectores


def buscar_sector(dinum):
    """
    Dado un dinum de 18 dígitos, retorna el CODIGO del sector al que pertenece.

    Compara en dos mitades de 9 dígitos:
      dinum[0:9]  -> via principal (cardinal + tipo + num + letras + separador)
      dinum[9:18] -> via secundaria + letras + placa

    Para CL/DG (tipo=1): usa columnas CL_XN e CL_YN
    Para CR/TR (tipo=3): usa columnas CR_XN e CR_YN
    """
    global _SECTORES
    if _SECTORES is None:
        _SECTORES = _cargar_sectores()

    if not dinum or len(dinum) != 18:
        return None

    x9   = dinum[:9]
    y9   = dinum[9:]
    tipo = dinum[1]  # '1'=CL/DG, '3'=CR/TR

    for s in _SECTORES:
        if tipo == '1':
            if s['CL_XN_INI'] <= x9 <= s['CL_XN_FIN'] and s['CL_YN_INI'] <= y9 <= s['CL_YN_FIN']:
                return s['CODIGO']
        else:
            if s['CR_XN_INI'] <= x9 <= s['CR_XN_FIN'] and s['CR_YN_INI'] <= y9 <= s['CR_YN_FIN']:
                return s['CODIGO']
    return None


# ========== FUNCIONES DE CODIGO POSTAL ==========

_LIMITES_POSTALES = None
_ZONAS_POSTALES   = None   # lista pre-procesada y ordenada por restricción
_LOCALIDADES      = None   # dict {codigo_postal: localidad}


def _cargar_limites_postales():
    ruta = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                        'limites_estandarizados.xlsx')
    df = pd.read_excel(ruta)
    # El Excel a veces exporta las columnas este/oeste con nombres vacíos
    rename = {}
    cols = df.columns.tolist()
    if 'limite_este' not in cols and 'limite_' in cols:
        rename['limite_'] = 'limite_este'
    if 'limite_oeste' not in cols and 'limite_.1' in cols:
        rename['limite_.1'] = 'limite_oeste'
    if rename:
        df = df.rename(columns=rename)
    return df


def _parsear_via_limite(via_str):
    """
    Parsea una vía de límite estandarizada en (tipo, num, letras_code, cardinal).
    Ej: 'CL 63'      → ('CL', 63, 100, None)
        'CL 49 SUR'  → ('CL', 49, 100, 'SUR')
        'CR 30 ESTE' → ('CR', 30, 100, 'ESTE')
    """
    if not via_str or (isinstance(via_str, float) and pd.isna(via_str)):
        return None, None, None, None
    partes = str(via_str).upper().split()

    cardinal = None
    compuestos = {'SUR ESTE', 'SUR OESTE', 'NORTE ESTE', 'NORTE OESTE'}
    if len(partes) >= 3 and ' '.join(partes[-2:]) in compuestos:
        cardinal = ' '.join(partes[-2:])
        partes = partes[:-2]
    elif len(partes) >= 2 and partes[-1] in ('SUR', 'NORTE', 'ESTE', 'OESTE'):
        cardinal = partes[-1]
        partes = partes[:-1]

    if len(partes) < 2:
        return None, None, None, cardinal

    tipo = partes[0]
    m = re.match(r'^(\d+)(.*)', partes[1])
    if not m:
        return tipo, None, None, cardinal

    num = int(m.group(1))
    letras_code = codificar_letras(m.group(2).strip())
    return tipo, num, letras_code, cardinal


def _posicion_cl(tipo, num, letras_code, cardinal):
    """
    Posición N-S como entero comparable.
    Positivo = Norte (mayor = más al norte).
    Negativo = Sur  (más negativo = más al sur).
    Válido para tipos CL y DG.
    """
    if tipo not in ('CL', 'DG') or num is None:
        return None
    pos = num * 10000 + (letras_code - 100)
    return -pos if cardinal == 'SUR' else pos


def _posicion_cr(tipo, num, letras_code, cardinal=None):
    """
    Posición E-O como entero comparable (mayor = más al Oeste).
    Válido para tipos CR y TR.
    Cardinal ESTE → posición negativa (al oriente del eje CR 1).
    """
    if tipo not in ('CR', 'TR') or num is None:
        return None
    pos = num * 10000 + (letras_code - 100)
    return -pos if cardinal == 'ESTE' else pos


def _coordenadas_dir(dir_estandarizada):
    """
    Extrae (cl_pos, cr_pos) de una dirección estandarizada.
      cl_pos : posición N-S (int, positivo=Norte, negativo=Sur)
      cr_pos : posición E-O (int, mayor=Oeste)
    Para CL/DG: via1=calle (cl_pos), via2=carrera (cr_pos).
    Para CR/TR: via1=carrera (cr_pos), via2=calle (cl_pos).
    """
    if not dir_estandarizada:
        return None, None

    partes = dir_estandarizada.upper().split()

    cardinal = None
    compuestos = {'SUR ESTE', 'SUR OESTE', 'NORTE ESTE', 'NORTE OESTE'}
    if len(partes) >= 2 and ' '.join(partes[-2:]) in compuestos:
        cardinal = ' '.join(partes[-2:])
        partes = partes[:-2]
    elif partes and partes[-1] in ('SUR', 'NORTE', 'ESTE', 'OESTE', 'SUL'):
        cardinal = partes[-1]
        if cardinal == 'SUL':
            cardinal = 'SUR'
        partes = partes[:-1]

    if len(partes) < 4:
        return None, None

    tipo = partes[0]
    m1 = re.match(r'^(\d+)(.*)', partes[1])
    m2 = re.match(r'^(\d+)(.*)', partes[2])
    if not m1 or not m2:
        return None, None

    via1_num = int(m1.group(1))
    via1_let = codificar_letras(m1.group(2).strip())
    via2_num = int(m2.group(1))
    via2_let = codificar_letras(m2.group(2).strip())

    if tipo in ('CL', 'DG'):
        cl_p = via1_num * 10000 + (via1_let - 100)
        if cardinal == 'SUR':
            cl_p = -cl_p
        cr_p = via2_num * 10000 + (via2_let - 100)
        return cl_p, cr_p

    if tipo in ('CR', 'TR'):
        cr_p = via1_num * 10000 + (via1_let - 100)
        if cardinal == 'ESTE':
            cr_p = -cr_p
        cl_p = via2_num * 10000 + (via2_let - 100)
        if cardinal == 'SUR':
            cl_p = -cl_p
        return cl_p, cr_p

    return None, None


def _inicializar_zonas_postales():
    """
    Pre-procesa los límites postales y construye una lista ordenada de zonas,
    de más a menos restrictiva, para que buscar_codigo_postal siempre prefiera
    zonas con restricciones completas sobre zonas con datos parciales.

    Para cada zona se recolectan TODAS las posiciones CL/DG (de los 4 límites)
    y TODAS las posiciones CR/TR.  Así se manejan zonas donde la columna
    'norte' tiene una carrera o 'este' tiene una calle.

    Una dimensión es "válida" si hay ≥ 2 posiciones distintas.
    """
    global _LIMITES_POSTALES, _ZONAS_POSTALES
    if _LIMITES_POSTALES is None:
        _LIMITES_POSTALES = _cargar_limites_postales()

    zonas = []
    for _, row in _LIMITES_POSTALES.iterrows():
        all_lim = [
            _parsear_via_limite(row['limite_norte']),
            _parsear_via_limite(row['limite_sur']),
            _parsear_via_limite(row['limite_este']),
            _parsear_via_limite(row['limite_oeste']),
        ]

        # Acumular posiciones únicas por dimensión (de cualquier columna de límite)
        cl_vals = sorted({_posicion_cl(t, n, l, c)
                          for t, n, l, c in all_lim} - {None})
        cr_vals = sorted({_posicion_cr(t, n, l, c)
                          for t, n, l, c in all_lim} - {None})

        cl_valid = len(cl_vals) >= 2 and cl_vals[-1] > cl_vals[0]
        cr_valid = len(cr_vals) >= 2 and cr_vals[-1] > cr_vals[0]
        n_dims   = (1 if cl_valid else 0) + (1 if cr_valid else 0)

        if n_dims == 0:
            continue  # Sin restricciones útiles: descartar

        zonas.append((
            n_dims,
            int(row['codigo_postal']),
            cl_vals[0] if cl_valid else None,   # cl_min
            cl_vals[-1] if cl_valid else None,  # cl_max
            cr_vals[0] if cr_valid else None,   # cr_min
            cr_vals[-1] if cr_valid else None,  # cr_max
        ))

    # Más restrictivas primero → evita que zonas con datos incompletos ganen
    zonas.sort(key=lambda z: -z[0])
    _ZONAS_POSTALES = zonas


def buscar_codigo_postal(dir_estandarizada):
    """
    Dado una dirección estandarizada retorna el código postal de Bogotá.

    Estrategia:
    - Extrae (cl_pos, cr_pos) de la dirección (escala: num*10000 + letras_offset,
      negativo para SUR).
    - Recorre las zonas ordenadas de más a menos restrictiva.
    - Una zona coincide cuando la dirección cae dentro de sus rangos CL y/o CR.
    - Solo se evalúa una dimensión si tiene rango válido (≥ 2 valores distintos).

    Retorna int(codigo_postal) o None.
    """
    global _ZONAS_POSTALES
    if _ZONAS_POSTALES is None:
        _inicializar_zonas_postales()

    addr_cl, addr_cr = _coordenadas_dir(dir_estandarizada)
    if addr_cl is None and addr_cr is None:
        return None

    for _, cp, cl_min, cl_max, cr_min, cr_max in _ZONAS_POSTALES:
        cl_ok = True
        if addr_cl is not None and cl_min is not None:
            cl_ok = cl_min <= addr_cl <= cl_max

        cr_ok = True
        if addr_cr is not None and cr_min is not None:
            cr_ok = cr_min <= addr_cr <= cr_max

        if cl_ok and cr_ok:
            return cp

    return None


# ========== FUNCIONES DE LOCALIDAD ==========

def _cargar_localidades():
    ruta = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                        'localidad_codigo_postal_bogota.xlsx')
    df = pd.read_excel(ruta)
    return dict(zip(df['CODIGO POSTAL'].astype(int), df['LOCALIDAD']))


def buscar_localidad(dir_estandarizada):
    """
    Dado una dirección estandarizada retorna la localidad de Bogotá.
    Primero obtiene el código postal y luego lo cruza con el archivo
    localidad_codigo_postal_bogota.xlsx.
    Retorna str o None.
    """
    global _LOCALIDADES
    if _LOCALIDADES is None:
        _LOCALIDADES = _cargar_localidades()

    cp = buscar_codigo_postal(dir_estandarizada)
    if cp is None:
        return None
    return _LOCALIDADES.get(int(cp))


# ========== EJECUCION ==========

if __name__ == '__main__':
    print("=" * 80)
    print("ESTANDARIZACION DE DIRECCIONES + DIRECCION NUMERICA")
    print("=" * 80)

    df = pd.DataFrame(datos_prueba, columns=['dirdes1', 'dir_pred', 'dir_num_esperado'])

    # Paso 1: Estandarizar direcciones
    df['dir_calculada'] = df['dirdes1'].apply(estandarizar_direccion)
    df['coincide_std'] = df['dir_calculada'] == df['dir_pred']

    # Paso 2: Generar dirección numérica (desde dir_pred para validar la fórmula)
    df['dir_num_calc'] = df['dir_pred'].apply(generar_direccion_numerica)
    df['sector']       = df['dir_num_calc'].apply(buscar_sector)
    df['coincide_num'] = df.apply(
        lambda r: r['dir_num_calc'] == r['dir_num_esperado']
        if pd.notna(r['dir_num_esperado']) and r['dir_num_esperado']
        else None,
        axis=1
    )

    # Paso 3: Código postal y localidad (desde dir_calculada, pipeline completo)
    df['cod_postal'] = df['dir_calculada'].apply(buscar_codigo_postal)
    df['localidad']  = df['dir_calculada'].apply(buscar_localidad)

    # --- Resultados de estandarizacion ---
    print(f"\n--- ESTANDARIZACION ---")
    n_std = df['coincide_std'].sum()
    print(f"Coincidencias: {n_std}/{len(df)} ({n_std / len(df) * 100:.1f}%)")

    dif_std = df[~df['coincide_std']]
    if len(dif_std) > 0:
        print(f"\nDiferencias en estandarizacion:")
        for idx, row in dif_std.iterrows():
            print(f"  [{idx}] Original:  {row['dirdes1'][:70]}")
            print(f"       Esperado:  {row['dir_pred']}")
            print(f"       Calculado: {row['dir_calculada']}")

    # --- Resultados de dirección numérica ---
    df_num = df[df['dir_num_esperado'].notna()].copy()
    print(f"\n--- DIRECCION NUMERICA ---")
    n_num = df_num['coincide_num'].sum()
    print(f"Coincidencias: {int(n_num)}/{len(df_num)} ({n_num / len(df_num) * 100:.1f}%)")

    dif_num = df_num[df_num['coincide_num'] == False]
    if len(dif_num) > 0:
        print(f"\nDiferencias en direccion numerica:")
        for idx, row in dif_num.iterrows():
            print(f"\n  [{idx}] Dir estandarizada: {row['dir_pred']}")
            print(f"       Esperado:  {row['dir_num_esperado']}")
            print(f"       Calculado: {row['dir_num_calc']}")
            # Descomponer esperado
            esp = row['dir_num_esperado']
            print(f"       Esperado desglosado:  "
                  f"cardinal={esp[0]} tipo={esp[1]} via1={esp[2:5]} "
                  f"let1={esp[5:8]} sep={esp[8]} via2={esp[9:12]} "
                  f"let2={esp[12:15]} placa={esp[15:18]}")
            debug_direccion_numerica(row['dir_pred'])

    # --- Tabla completa ---
    print(f"\n\n{'=' * 110}")
    print("TODAS LAS DIRECCIONES CON DIRECCION NUMERICA, SECTOR, CODIGO POSTAL Y LOCALIDAD")
    print("=" * 110)
    for idx, row in df.iterrows():
        marca_std = "OK" if row['coincide_std'] else "!!"
        marca_num = ""
        if pd.notna(row['dir_num_esperado']) and row['dir_num_esperado']:
            marca_num = " NUM_OK" if row['coincide_num'] else " NUM_!!"
        sector    = str(row['sector'])    if pd.notna(row['sector'])    else "---"
        cp        = str(row['cod_postal']) if pd.notna(row['cod_postal']) else "---"
        localidad = str(row['localidad'])  if pd.notna(row['localidad'])  else "---"
        print(f"  [{idx:2d}] {marca_std} {str(row['dir_pred']):<28s} "
              f"-> {str(row['dir_num_calc']):<20s}{marca_num:<10} "
              f"sector={sector:<12} cp={cp:<8} loc={localidad}")
