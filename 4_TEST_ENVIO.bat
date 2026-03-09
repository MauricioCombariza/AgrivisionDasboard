@echo off
echo ============================================================
echo  TEST DE ENVIO DE WHATSAPP - PASO POR PASO
echo ============================================================
echo.
echo Este test simula el proceso completo de envio
echo con pausas para que puedas observar cada paso
echo.
echo ANTES DE EJECUTAR:
echo 1. Abre Chrome y ve a https://web.whatsapp.com
echo 2. Escanea el codigo QR si no estas logueado
echo 3. Deja Chrome abierto
echo.
pause

call conda activate carvajal

python TEST_ENVIO_SIMPLE.py

pause
