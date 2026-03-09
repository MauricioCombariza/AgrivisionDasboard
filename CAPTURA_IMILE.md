# 📸 Automatización de Captura iMile

## ✅ Solución Implementada

Integración de la automatización de n8n en Streamlit usando arquitectura híbrida WSL2 + Windows.

---

## 🚀 Funcionalidad

La automatización realiza automáticamente:

1. **Captura de Pantalla** de WhatsApp Web
   - Abre WhatsApp Web con Selenium
   - Espera 15 segundos para que cargue
   - Toma captura de pantalla completa
   - Recorta la imagen (elimina barra lateral y barras superior/inferior)
   - Guarda como `captura_{serial}.png` en Downloads

2. **Subida a iMile**
   - Login automático en ds.imile.com
   - Navega a gestión de problemas
   - Llena formulario con el serial
   - Selecciona "Debido al cliente" → "Dirección Incorrecta"
   - Sube la imagen capturada
   - Confirma el registro

---

## 📋 Requisitos

### En WSL2:
- ✅ Streamlit instalado
- ✅ Python con subprocess
- ✅ MySQL connector

### En Windows:
- ✅ Python (ambiente carvajal)
- ✅ PyAutoGUI (para captura de pantalla)
- ✅ Selenium (para subida a iMile)
- ✅ ChromeDriver en `C:\DriverChrome\chromedriver.exe`
- ✅ Google Chrome

---

## 🔧 Instalación de Selenium en Windows

**Importante:** La captura usa PyAutoGUI (ya instalado), pero la subida a iMile requiere Selenium.

Para instalar Selenium en Windows:

1. **Ejecuta el archivo BAT:**
   ```
   INSTALAR_SELENIUM_WINDOWS.bat
   ```

2. **O manualmente desde Anaconda Prompt:**
   ```cmd
   conda activate carvajal
   pip install selenium pillow
   ```

---

## 🎯 Cómo Usar

### Desde WSL2:

1. **Ejecutar Streamlit:**
   ```bash
   cd /mnt/c/Users/mcomb/Desktop/Carvajal/python/dashboard
   ./run_wsl.sh
   ```

2. **Abrir la página "Captura iMile"** en el menú lateral

3. **Ingresar el serial** del paquete

4. **Click en "🚀 Ejecutar"**

5. **Esperar el proceso:**
   - La aplicación abrirá Chrome automáticamente
   - Capturará la pantalla de WhatsApp
   - Subirá la imagen a iMile
   - Mostrará el resultado

---

## 🔧 Archivos Creados

```
dashboard/
├── pages/
│   └── captura_imile.py              # Interfaz Streamlit
├── captura_imile_windows.py          # Script de captura (Windows)
├── subir_imile_windows.py            # Script de subida (Windows)
└── CAPTURA_IMILE.md                  # Esta documentación
```

---

## 🔍 Arquitectura

```
┌─────────────────────────────────────────┐
│          WSL2 (Linux)                   │
│  ┌───────────────────────────────────┐  │
│  │  Streamlit - captura_imile.py    │  │
│  │  - Interfaz web                  │  │
│  │  - Input de serial               │  │
│  │  - Gestión de proceso            │  │
│  └───────────┬───────────────────────┘  │
│              │                           │
│              │ Detecta WSL2             │
│              ↓                           │
│  ┌───────────────────────────────────┐  │
│  │  Llama scripts de Windows        │  │
│  └───────────┬───────────────────────┘  │
└──────────────┼───────────────────────────┘
               │
               │ PowerShell
               ↓
┌─────────────────────────────────────────┐
│          Windows                         │
│  ┌───────────────────────────────────┐  │
│  │  captura_imile_windows.py        │  │
│  │  - Selenium + Chrome             │  │
│  │  - Captura WhatsApp Web          │  │
│  │  - Recorta imagen                │  │
│  └───────────────────────────────────┘  │
│  ┌───────────────────────────────────┐  │
│  │  subir_imile_windows.py          │  │
│  │  - Selenium + Chrome             │  │
│  │  - Login en iMile                │  │
│  │  - Llena formulario              │  │
│  │  - Sube imagen                   │  │
│  └───────────────────────────────────┘  │
└─────────────────────────────────────────┘
```

---

## 🔐 Credenciales

Las credenciales están hardcodeadas en `pages/captura_imile.py`:
- **Usuario:** 2103679801
- **Password:** Servilla@547

Para cambiarlas, edita las constantes al inicio del archivo.

---

## 🛠️ Solución de Problemas

### Problema: "ChromeDriver no encontrado"

**Solución:** Verifica que ChromeDriver esté en:
```
C:\DriverChrome\chromedriver.exe
```

Si está en otra ubicación, edita los scripts de Windows:
- `captura_imile_windows.py` línea 31
- `subir_imile_windows.py` línea 33

---

### Problema: "WhatsApp no carga"

**Solución:**
1. El perfil de Chrome debe tener sesión activa de WhatsApp Web
2. Abre Chrome manualmente y escanea QR de WhatsApp Web
3. Asegúrate de usar el perfil correcto: `C:\Users\mcomb\ChromeSeleniumProfile`

---

### Problema: "Error al subir imagen"

**Solución:**
1. Verifica que las credenciales sean correctas
2. Confirma que tienes acceso a ds.imile.com
3. Revisa que la imagen se haya capturado correctamente en Downloads

---

### Problema: "Imagen no se encuentra"

**Solución:**
1. El proceso de captura debe completarse primero
2. Verifica la carpeta Downloads:
   ```
   C:\Users\mcomb\Downloads\captura_{serial}.png
   ```

---

## 📊 Logs

Durante el proceso verás en Streamlit:

```
🔄 Procesando...
  📸 Capturando pantalla de WhatsApp...
  ✅ Captura completada
  📤 Subiendo imagen a iMile...
  ✅ Imagen subida exitosamente
✅ Proceso completado para serial XXXX
```

---

## 💡 Diferencias con n8n

### Antes (n8n):
- Formulario web separado
- Dos nodos de ejecución de comandos
- Configuración compleja
- Logs dispersos

### Ahora (Streamlit):
- Interfaz integrada con el resto del dashboard
- Proceso automatizado en un solo botón
- Logs claros y centralizados
- Historial de capturas recientes
- Detección automática WSL2/Windows

---

## 🎉 Ventajas

1. **Integración total** - Todo en un solo dashboard
2. **Más simple** - Un botón vs. múltiples pasos
3. **Mejor feedback** - Mensajes claros de progreso
4. **Historial** - Ver capturas recientes
5. **Portable** - Funciona desde WSL2 y Windows
6. **Mantenible** - Código Python limpio y documentado

---

**¡La automatización está lista para usar!** 🚀
