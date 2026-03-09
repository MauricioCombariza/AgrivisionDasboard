@echo off
chcp 65001 >nul
echo ====================================
echo  Sistema de Logistica - Agrivision
echo ====================================
echo.

cd /d "%~dp0"

REM Verificar si pages existe y hacer backup
if exist pages (
    echo Guardando configuracion anterior...
    if exist pages_temp rmdir /s /q pages_temp
    move pages pages_temp >nul 2>&1
)

REM Activar pages de logistica
echo Activando modulos de logistica...
if exist pages_logistica (
    move pages_logistica pages >nul 2>&1
)

echo.
echo Iniciando sistema de logistica en http://localhost:8502
echo Presiona Ctrl+C para detener el servidor
echo.

streamlit run home_logistica.py --server.port=8502

REM Al cerrar, restaurar carpetas
echo.
echo Restaurando configuracion...
if exist pages (
    move pages pages_logistica >nul 2>&1
)

if exist pages_temp (
    move pages_temp pages >nul 2>&1
)

echo Listo.
pause
