# 🪟 Guía de Instalación y Ejecución - Windows con Conda

## 📋 Requisitos Previos

Antes de comenzar, asegúrate de tener instalado:

1. **Anaconda** o **Miniconda** en Windows
   - Descarga Anaconda: https://www.anaconda.com/download
   - O Miniconda (más ligero): https://docs.conda.io/en/latest/miniconda.html

2. **Google Chrome** instalado

3. **MySQL Server** corriendo en localhost
   - Usuario: root
   - Contraseña: Vale2010
   - Base de datos: imile

---

## 🚀 Instalación (SOLO LA PRIMERA VEZ)

### Paso 1: Abrir Terminal de Conda en Windows

1. Presiona `Windows + R`
2. Escribe: `cmd`
3. Presiona Enter

O busca **"Anaconda Prompt"** en el menú inicio

---

### Paso 2: Navegar a la Carpeta del Proyecto

```cmd
cd C:\Users\mcomb\Desktop\Carvajal\python\dashboard
```

---

### Paso 3: Ejecutar el Script de Instalación

**Opción A - Usando el script automático (RECOMENDADO):**
```cmd
1_INSTALAR_AMBIENTE.bat
```

**Opción B - Manualmente:**
```cmd
conda env create -f environment.yml
```

Esto creará un ambiente virtual llamado **"whatsapp_sender"** con todas las dependencias.

⏱️ **Tiempo estimado:** 2-5 minutos

---

## ▶️ Ejecución (CADA VEZ QUE QUIERAS USAR LA APP)

### Método 1: Usando el Script Automático (MÁS FÁCIL)

1. Ve a la carpeta: `C:\Users\mcomb\Desktop\Carvajal\python\dashboard`
2. Haz doble click en: **`2_EJECUTAR_APP.bat`**
3. Se abrirá la ventana de comandos con los LOGS
4. Automáticamente se abrirá el navegador con la aplicación

---

### Método 2: Manualmente

Abre **Anaconda Prompt** y ejecuta:

```cmd
cd C:\Users\mcomb\Desktop\Carvajal\python\dashboard
conda activate whatsapp_sender
streamlit run pages\wa.py
```

---

## 📱 Uso de la Aplicación

### Antes de Enviar Mensajes:

1. **Inicia sesión en WhatsApp Web** en Chrome
   - Ve a: https://web.whatsapp.com
   - Escanea el código QR con tu teléfono
   - Mantén la sesión iniciada

2. **Prepara tu archivo Excel**
   - Columna requerida: `serial`
   - Ejemplo:
     ```
     serial
     ABC123
     DEF456
     ```

3. **Verifica que MySQL esté corriendo**

---

### Enviar Mensajes:

1. Abre la aplicación (ejecuta `2_EJECUTAR_APP.bat`)
2. Sube tu archivo Excel
3. Click en **"⏳ Iniciar Envíos"** o **"⏳ Confirmar entregas"**
4. **NO TOQUES EL MOUSE** mientras se envían los mensajes
5. **Observa la ventana de comandos** para ver los logs en tiempo real

---

## 🔍 Logs y Depuración

Mientras se envían los mensajes, en la **ventana de comandos** verás:

```
============================================================
🚀 INICIANDO ENVÍO DE MENSAJE
============================================================
📱 Número: +573001234567
🌐 Chrome encontrado: C:\Program Files\Google\Chrome\Application\chrome.exe
🔄 Abriendo Chrome...
⏳ Esperando 15 segundos para carga de WhatsApp Web...
🎯 Usando coordenadas PREDETERMINADAS: (960, 1026)
📺 Tamaño de pantalla: 1920x1080
🖱️  Posición actual del mouse: (500, 600)
➡️  Moviendo mouse a (960, 1026)...
✅ Mouse movido a: (960, 1026)
🖱️  Haciendo click en (960, 1026)...
✅ Click ejecutado
🔒 Cerrando pestaña...
✅ ENVÍO COMPLETADO
============================================================
```

**Esto te permite saber EXACTAMENTE qué está haciendo el programa en cada momento.**

---

## ⚙️ Ajustar Coordenadas del Botón (Si es necesario)

Si el mouse no hace click en el botón correcto:

### Paso 1: Obtener las Coordenadas Correctas

En **Anaconda Prompt**:
```cmd
cd C:\Users\mcomb\Desktop\Carvajal\python\dashboard
conda activate whatsapp_sender
python obtener_coordenadas.py
```

Sigue las instrucciones:
1. Abre WhatsApp Web MAXIMIZADO
2. Mueve el mouse sobre el botón de envío (flecha verde)
3. Presiona `Ctrl+C`
4. Copia las coordenadas X e Y

### Paso 2: Configurar en la Aplicación

1. En la app de Streamlit, despliega **"⚙️ Configuración Avanzada"**
2. Ingresa las coordenadas X e Y que obtuviste
3. Click en **"🎯 Probar Posición"** para verificar
4. Intenta enviar de nuevo

---

## 🛠️ Comandos Útiles

### Ver ambientes de conda disponibles:
```cmd
conda env list
```

### Activar el ambiente:
```cmd
conda activate whatsapp_sender
```

### Desactivar el ambiente:
```cmd
conda deactivate
```

### Eliminar el ambiente (si necesitas reinstalar):
```cmd
conda env remove -n whatsapp_sender
```

### Actualizar una dependencia:
```cmd
conda activate whatsapp_sender
pip install --upgrade streamlit
```

---

## ❌ Solución de Problemas

### Problema: "conda: command not found"
**Solución:** Abre **Anaconda Prompt** en lugar de CMD normal

### Problema: "Environment already exists"
**Solución:**
```cmd
conda env remove -n whatsapp_sender
conda env create -f environment.yml
```

### Problema: El mouse no se mueve
**Solución:**
1. Asegúrate de ejecutar desde Windows (NO desde WSL)
2. Verifica con: `python obtener_coordenadas.py`
3. Si no funciona, verifica que pyautogui esté instalado: `pip list | findstr pyautogui`

### Problema: No encuentra Google Chrome
**Solución:**
- Edita `pages\wa.py` línea 55
- Cambia la ruta a donde tengas Chrome instalado

### Problema: Error de conexión a MySQL
**Solución:**
- Verifica que MySQL esté corriendo
- Verifica usuario/contraseña en `pages\wa.py` líneas 82-85
- Usa MySQL Workbench para probar la conexión

---

## 📊 Rendimiento

- **Tiempo por mensaje:** ~25 segundos
  - 15s: Carga de WhatsApp Web
  - 5s: Envío y confirmación
  - 5s: Espera antes del siguiente

- **Mensajes por hora:** ~144 mensajes/hora
- **Recomendación:** Enviar máximo 50-100 mensajes por sesión para evitar bloqueos de WhatsApp

---

## ✅ Checklist Antes de Enviar Masivamente

- [ ] WhatsApp Web está abierto y con sesión iniciada
- [ ] Chrome al 100% de zoom (Ctrl+0)
- [ ] MySQL corriendo y base de datos accesible
- [ ] Archivo Excel preparado con columna `serial`
- [ ] Probado con 2-3 contactos primero
- [ ] Ventana de comandos visible para ver logs
- [ ] No vas a usar el mouse durante el proceso

---

## 🆘 Soporte

Si tienes problemas:
1. Revisa los logs en la ventana de comandos
2. Verifica que todos los requisitos estén instalados
3. Prueba con `python test_pyautogui.py` para verificar que pyautogui funcione
4. Asegúrate de estar ejecutando desde Windows nativo (NO WSL)

---

**¡Listo! Ahora puedes usar la aplicación desde Windows con control completo del mouse.**
