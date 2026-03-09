@echo off
echo ============================================================
echo  TEST DE CONTROL DE MOUSE - PyAutoGUI
echo ============================================================
echo.
echo Este test verificara que PyAutoGUI puede controlar el mouse
echo.
echo IMPORTANTE: OBSERVA LA PANTALLA
echo El mouse deberia moverse automaticamente
echo.
pause

call conda activate carvajal

python TEST_MOUSE_WINDOWS.py

pause
