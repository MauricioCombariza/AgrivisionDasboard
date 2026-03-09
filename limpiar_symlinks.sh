#!/bin/bash

# ================================================================
# Script de utilidad para limpiar symlinks y backups
# Usar si los scripts de inicio tienen problemas
# ================================================================

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

# Colores
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

echo "===================================="
echo " Limpieza de Symlinks y Backups"
echo "===================================="
echo ""

# ================================================================
# Eliminar symlink pages si existe
# ================================================================
if [ -L "pages" ]; then
    echo -e "${YELLOW}Eliminando symlink 'pages'...${NC}"
    rm -f "pages"
    echo -e "${GREEN}✓ Symlink eliminado${NC}"
elif [ -d "pages" ]; then
    echo -e "${RED}⚠ Advertencia: 'pages' es un directorio real${NC}"
    echo -e "${YELLOW}¿Desea hacer backup de este directorio? (s/n)${NC}"
    read -r respuesta
    if [ "$respuesta" = "s" ] || [ "$respuesta" = "S" ]; then
        BACKUP_NAME="pages_backup_$(date +%Y%m%d_%H%M%S)"
        mv "pages" "$BACKUP_NAME"
        echo -e "${GREEN}✓ Backup creado: $BACKUP_NAME${NC}"
    else
        echo -e "${YELLOW}Directorio 'pages' no modificado${NC}"
    fi
elif [ -e "pages" ]; then
    echo -e "${YELLOW}Eliminando archivo 'pages'...${NC}"
    rm -f "pages"
    echo -e "${GREEN}✓ Archivo eliminado${NC}"
else
    echo -e "${BLUE}ℹ No existe 'pages' - todo está limpio${NC}"
fi

# ================================================================
# Eliminar directorio pages_temp si existe
# ================================================================
if [ -d "pages_temp" ]; then
    echo ""
    echo -e "${YELLOW}Encontrado directorio temporal 'pages_temp'${NC}"
    echo -e "${YELLOW}¿Desea eliminarlo? (s/n)${NC}"
    read -r respuesta
    if [ "$respuesta" = "s" ] || [ "$respuesta" = "S" ]; then
        rm -rf "pages_temp"
        echo -e "${GREEN}✓ Directorio temporal eliminado${NC}"
    else
        echo -e "${YELLOW}Directorio 'pages_temp' no modificado${NC}"
    fi
fi

# ================================================================
# Listar backups existentes
# ================================================================
echo ""
echo -e "${BLUE}Backups existentes:${NC}"
BACKUPS=$(ls -d pages_backup_* 2>/dev/null || echo "")
if [ -n "$BACKUPS" ]; then
    ls -lhd pages_backup_*
    echo ""
    echo -e "${YELLOW}¿Desea eliminar TODOS los backups? (s/n)${NC}"
    read -r respuesta
    if [ "$respuesta" = "s" ] || [ "$respuesta" = "S" ]; then
        rm -rf pages_backup_*
        echo -e "${GREEN}✓ Todos los backups eliminados${NC}"
    else
        echo -e "${YELLOW}Backups no modificados${NC}"
    fi
else
    echo -e "${BLUE}ℹ No hay backups${NC}"
fi

# ================================================================
# Verificar estructura final
# ================================================================
echo ""
echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN} Verificación de estructura${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""

if [ -d "pages_home" ]; then
    echo -e "${GREEN}✓ pages_home/ existe${NC}"
else
    echo -e "${RED}✗ pages_home/ NO existe${NC}"
fi

if [ -d "pages_logistica" ]; then
    echo -e "${GREEN}✓ pages_logistica/ existe${NC}"
else
    echo -e "${RED}✗ pages_logistica/ NO existe${NC}"
fi

if [ -e "pages" ]; then
    if [ -L "pages" ]; then
        echo -e "${YELLOW}⚠ pages/ es un symlink (se eliminará al cerrar la aplicación)${NC}"
    else
        echo -e "${YELLOW}⚠ pages/ existe como directorio/archivo${NC}"
    fi
else
    echo -e "${GREEN}✓ pages/ no existe (correcto)${NC}"
fi

echo ""
echo -e "${GREEN}Limpieza completada.${NC}"
echo ""
echo -e "${BLUE}Ahora puede ejecutar:${NC}"
echo -e "  ${YELLOW}./iniciar_home.sh${NC}      - Para sistema WhatsApp"
echo -e "  ${YELLOW}./iniciar_logistica.sh${NC} - Para sistema de Logística"
echo ""
