@echo off
:: ─────────────────────────────────────────────────────────────
:: Doble clic para iniciar la app móvil de Servilla
:: ─────────────────────────────────────────────────────────────
title Servilla Mobile

echo.
echo  Iniciando Servilla Mobile...
echo  (Esta ventana debe quedar abierta mientras uses el celular)
echo.

wsl -e bash -c "cd /mnt/c/Users/mcomb/Desktop/Carvajal/python/dashboard/mobile && bash iniciar.sh"

echo.
echo  El servidor se detuvo.
pause
