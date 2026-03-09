@echo off
chcp 65001 >nul
echo ====================================
echo  Sistema WhatsApp / iMile
echo ====================================
echo.

cd /d "%~dp0"

REM Verificar si pages existe y hacer backup
if exist pages (
    echo Guardando configuracion anterior...
    if exist pages_temp rmdir /s /q pages_temp
    move pages pages_temp >nul 2>&1
)

REM Activar pages de home/whatsapp
echo Activando modulos de WhatsApp...
if exist pages_home (
    move pages_home pages >nul 2>&1
)

echo.
echo Iniciando sistema WhatsApp en http://localhost:8501
echo Presiona Ctrl+C para detener el servidor
echo.

streamlit run home.py --server.port=8501

REM Al cerrar, restaurar carpetas
echo.
echo Restaurando configuracion...
if exist pages (
    move pages pages_home >nul 2>&1
)

if exist pages_temp (
    move pages_temp pages >nul 2>&1
)

echo Listo.
pause
