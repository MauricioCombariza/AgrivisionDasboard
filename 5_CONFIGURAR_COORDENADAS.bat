@echo off
echo ============================================================
echo  OBTENER COORDENADAS DEL BOTON DE ENVIO
echo ============================================================
echo.
echo PASOS:
echo.
echo 1. Abre Chrome y ve a https://web.whatsapp.com
echo 2. MAXIMIZA Chrome (F11 o boton maximizar)
echo 3. Presiona Ctrl+0 para zoom al 100%%
echo 4. Abre cualquier chat
echo 5. Escribe algo (para que aparezca el boton de envio)
echo.
echo Cuando todo este listo, presiona Enter aqui...
pause
echo.

call conda activate carvajal

echo Ejecutando obtener_coordenadas.py...
echo.
echo IMPORTANTE:
echo - Mueve el mouse sobre el BOTON DE ENVIO (flecha verde)
echo - Presiona Ctrl+C cuando estes sobre el boton
echo.

python obtener_coordenadas.py

echo.
echo ============================================================
echo.
echo Ahora configura esas coordenadas en la aplicacion:
echo.
echo 1. Abre Streamlit si no esta abierto
echo 2. Despliega "Configuracion Avanzada"
echo 3. Ingresa las coordenadas X e Y
echo 4. Click en "Probar Posicion" para verificar
echo 5. Intenta enviar un mensaje de prueba
echo.
pause
