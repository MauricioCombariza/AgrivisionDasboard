#!/bin/bash
# ============================================================
# WhatsApp Sender - Ejecutar desde WSL2
# ============================================================

echo "============================================================"
echo " WhatsApp Sender - Ejecutando desde WSL2"
echo "============================================================"
echo ""

# Verificar que Python de Windows tenga PyAutoGUI
echo "Verificando Python de Windows..."

# Buscar Python en el ambiente carvajal de Windows
PYTHON_WIN=""
if [ -f "/mnt/c/Users/mcomb/miniconda3/envs/carvajal/python.exe" ]; then
    PYTHON_WIN="/mnt/c/Users/mcomb/miniconda3/envs/carvajal/python.exe"
elif [ -f "/mnt/c/Users/mcomb/anaconda3/envs/carvajal/python.exe" ]; then
    PYTHON_WIN="/mnt/c/Users/mcomb/anaconda3/envs/carvajal/python.exe"
fi

if [ -n "$PYTHON_WIN" ]; then
    echo "✓ Python de Windows encontrado: $PYTHON_WIN"

    # Verificar PyAutoGUI
    "$PYTHON_WIN" -c "import pyautogui" 2>/dev/null

    if [ $? -eq 0 ]; then
        echo "✓ PyAutoGUI instalado correctamente en Windows"
    else
        echo ""
        echo "⚠️  ADVERTENCIA: PyAutoGUI no está instalado en el ambiente carvajal de Windows"
        echo ""
        echo "Pero puedes continuar, el script lo instalará automáticamente si falta"
        echo ""
        read -p "Presiona Enter para continuar..."
    fi
else
    echo "⚠️  No se encontró Python del ambiente carvajal en Windows"
    echo "Continuando de todos modos..."
    echo ""
fi

echo ""
echo "Buscando ambiente carvajal en WSL2..."

# Buscar Python del ambiente carvajal en WSL2
PYTHON_WSL=""
STREAMLIT_WSL=""

# Buscar en las ubicaciones comunes de conda
if [ -f "$HOME/miniconda3/envs/carvajal/bin/python" ]; then
    PYTHON_WSL="$HOME/miniconda3/envs/carvajal/bin/python"
    STREAMLIT_WSL="$HOME/miniconda3/envs/carvajal/bin/streamlit"
elif [ -f "$HOME/anaconda3/envs/carvajal/bin/python" ]; then
    PYTHON_WSL="$HOME/anaconda3/envs/carvajal/bin/python"
    STREAMLIT_WSL="$HOME/anaconda3/envs/carvajal/bin/streamlit"
fi

if [ -z "$PYTHON_WSL" ]; then
    echo "❌ ERROR: No se encontró el ambiente 'carvajal' en WSL2"
    echo ""
    echo "Crea el ambiente primero:"
    echo "  conda create -n carvajal python=3.12 -y"
    echo "  conda activate carvajal"
    echo "  pip install streamlit pandas mysql-connector-python openpyxl numpy"
    echo ""
    exit 1
fi

echo "✓ Python WSL2: $PYTHON_WSL"

# Verificar streamlit
if [ ! -f "$STREAMLIT_WSL" ]; then
    echo "⚠️  Streamlit no encontrado, instalando..."
    "$PYTHON_WSL" -m pip install streamlit
    STREAMLIT_WSL="$PYTHON_WSL -m streamlit"
else
    echo "✓ Streamlit encontrado"
fi

echo ""
echo "Ejecutando Streamlit..."
echo ""
echo "============================================================"
echo "IMPORTANTE:"
echo "- El sistema detectará automáticamente que estás en WSL2"
echo "- Llamará al script de Windows para controlar el mouse"
echo "- Los logs aparecerán en esta ventana"
echo "============================================================"
echo ""

# Ejecutar streamlit con el archivo principal para mostrar todas las páginas
$STREAMLIT_WSL run home.py

echo ""
echo "Streamlit cerrado"
