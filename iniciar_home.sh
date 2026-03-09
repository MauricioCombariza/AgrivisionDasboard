#!/bin/bash

# ================================================================
# Script de inicio para Sistema WhatsApp / iMile
# Usa symlinks para cambiar entre diferentes conjuntos de páginas
# ================================================================

set -e  # Salir si hay errores

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

PAGES_DIR="pages"
TARGET_DIR="pages_home"
MAIN_FILE="home.py"
PORT=8505

# Colores para output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo "===================================="
echo " Sistema WhatsApp / iMile"
echo "===================================="
echo ""

# ================================================================
# Función de limpieza al salir
# ================================================================
cleanup() {
    echo ""
    echo -e "${YELLOW}Deteniendo servidor y limpiando...${NC}"

    # Eliminar symlink si existe
    if [ -L "$PAGES_DIR" ]; then
        rm -f "$PAGES_DIR"
        echo -e "${GREEN}✓ Symlink eliminado${NC}"
    fi

    echo -e "${GREEN}Limpieza completada.${NC}"
}

# Registrar función cleanup para ejecutarse al salir (Ctrl+C o error)
trap cleanup EXIT INT TERM

# ================================================================
# Verificar que existe el directorio de páginas objetivo
# ================================================================
if [ ! -d "$TARGET_DIR" ]; then
    echo -e "${RED}✗ Error: No existe el directorio '$TARGET_DIR'${NC}"
    echo "Por favor verifica la estructura de directorios."
    exit 1
fi

# ================================================================
# Verificar que existe el archivo principal
# ================================================================
if [ ! -f "$MAIN_FILE" ]; then
    echo -e "${RED}✗ Error: No existe el archivo '$MAIN_FILE'${NC}"
    exit 1
fi

# ================================================================
# Limpiar configuración anterior (si existe)
# ================================================================
if [ -e "$PAGES_DIR" ]; then
    if [ -L "$PAGES_DIR" ]; then
        # Es un symlink, eliminarlo
        echo -e "${YELLOW}Eliminando symlink anterior...${NC}"
        rm -f "$PAGES_DIR"
    elif [ -d "$PAGES_DIR" ]; then
        # Es un directorio real, hacer backup
        echo -e "${YELLOW}⚠ Advertencia: '$PAGES_DIR' es un directorio real${NC}"
        BACKUP_NAME="${PAGES_DIR}_backup_$(date +%Y%m%d_%H%M%S)"
        mv "$PAGES_DIR" "$BACKUP_NAME"
        echo -e "${GREEN}✓ Backup creado: $BACKUP_NAME${NC}"
    else
        # Es un archivo u otra cosa, eliminar
        rm -f "$PAGES_DIR"
    fi
fi

# ================================================================
# Crear symlink a las páginas correctas
# ================================================================
echo -e "${BLUE}Configurando módulos de WhatsApp...${NC}"
ln -s "$TARGET_DIR" "$PAGES_DIR"

if [ -L "$PAGES_DIR" ]; then
    echo -e "${GREEN}✓ Módulos de WhatsApp activados${NC}"
else
    echo -e "${RED}✗ Error: No se pudo crear el symlink${NC}"
    exit 1
fi

# ================================================================
# Verificar que streamlit está instalado
# ================================================================
if ! command -v streamlit &> /dev/null; then
    echo -e "${RED}✗ Error: Streamlit no está instalado${NC}"
    echo "Instalar con: pip install streamlit"
    exit 1
fi

# ================================================================
# Iniciar servidor Streamlit
# ================================================================
echo ""
echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN} Sistema iniciado correctamente${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""
echo -e "📱 Aplicación: ${BLUE}WhatsApp / iMile${NC}"
echo -e "🌐 URL Local:  ${BLUE}http://localhost:$PORT${NC}"
echo -e "📁 Páginas:    ${BLUE}$TARGET_DIR/${NC}"
echo ""
echo -e "${YELLOW}Presiona Ctrl+C para detener el servidor${NC}"
echo ""

# Iniciar Streamlit con configuración específica
streamlit run "$MAIN_FILE" \
    --server.port=$PORT \
    --server.headless=true \
    --browser.gatherUsageStats=false \
    --server.runOnSave=true
