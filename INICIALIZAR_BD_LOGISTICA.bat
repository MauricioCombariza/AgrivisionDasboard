@echo off
chcp 65001 >nul
echo ====================================================================
echo   INICIALIZACIÓN DE BASE DE DATOS - SISTEMA LOGÍSTICA
echo ====================================================================
echo.
echo Este script creará la base de datos 'logistica' con todas sus tablas
echo.
echo ADVERTENCIA: Si la base de datos ya existe, se mantendrá
echo              Solo se crearán las tablas que no existan
echo.
pause
echo.
echo Iniciando...
echo.

python init_db_logistica.py

echo.
echo.
pause
