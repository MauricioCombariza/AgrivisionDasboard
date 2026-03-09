import pandas as pd

def compute(l, l2):
    # Normalizar entradas: convertir a string en minúscula y quitar espacios
    l = str(l).lower().strip() if pd.notna(l) else ""
    l2 = str(l2).lower().strip() if pd.notna(l2) else ""

    # Función auxiliar para saber si es una sola letra válida
    def letra_val(ch):
        return 1000 + ord(ch) - 96 if len(ch) == 1 and ch.isalpha() else 0

    # Parte base
    if l == "bis":
        base = 1000
    else:
        base = letra_val(l)

    # Parte adicional según la lógica
    if l == "bis" and len(l2) == 1 and l2.isalpha():
        extra = ord(l2) - 96
    elif l2 == "bis":
        extra = 100
    elif len(l2) == 1 and l2.isalpha():
        extra = 100 + ord(l2) - 96
    else:
        extra = 0

    return base + extra
