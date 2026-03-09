# 🐧 Ejecutar desde WSL2 - Solución Híbrida

## ✅ **Solución Implementada**

El sistema ahora soporta **ejecución desde WSL2** usando una arquitectura híbrida:

- **Streamlit** → Corre en WSL2 (tu ambiente `carvajal` de Linux)
- **Control de Mouse** → Se ejecuta en Windows (llamado automáticamente)

---

## 🚀 **Cómo Ejecutar desde WSL2**

### **Paso 1: Instalar PyAutoGUI en Windows**

Necesitas PyAutoGUI instalado en el **Python de Windows** (no el de WSL2):

En **Anaconda Prompt** (Windows):
```cmd
conda activate carvajal
pip install pyautogui pillow
```

---

### **Paso 2: Ejecutar Streamlit desde WSL2**

En tu terminal de **WSL2**:

```bash
cd /mnt/c/Users/mcomb/Desktop/Carvajal/python/dashboard

# Activar ambiente conda de WSL2
conda activate carvajal

# Ejecutar Streamlit
streamlit run pages/wa.py
```

---

### **Paso 3: Usar la Aplicación**

1. La aplicación se abrirá en el navegador
2. Sube tu archivo Excel
3. Click en "⏳ Iniciar Envíos"
4. **Automáticamente:**
   - Detecta que estás en WSL2
   - Llama al script de Windows
   - Windows controla el mouse y envía el mensaje

---

## 🔍 **Cómo Funciona**

```
┌─────────────────────────────────────────┐
│          WSL2 (Linux)                   │
│  ┌───────────────────────────────────┐  │
│  │  Streamlit App                    │  │
│  │  - Interfaz web                   │  │
│  │  - Lógica de negocio             │  │
│  │  - Conexión MySQL                │  │
│  └───────────┬───────────────────────┘  │
│              │                           │
│              │ Detecta WSL2             │
│              ↓                           │
│  ┌───────────────────────────────────┐  │
│  │  Llama script de Windows         │  │
│  └───────────┬───────────────────────┘  │
└──────────────┼───────────────────────────┘
               │
               │ PowerShell
               ↓
┌─────────────────────────────────────────┐
│          Windows                         │
│  ┌───────────────────────────────────┐  │
│  │  enviar_mensaje_windows.py       │  │
│  │  - Abre Chrome                   │  │
│  │  - Controla mouse (PyAutoGUI)    │  │
│  │  - Hace click en botón envío     │  │
│  └───────────────────────────────────┘  │
└─────────────────────────────────────────┘
```

---

## 📋 **Requisitos**

### **En WSL2 (Linux):**
- ✅ Conda con ambiente `carvajal`
- ✅ Streamlit
- ✅ Pandas, MySQL connector

### **En Windows:**
- ✅ Python (con conda)
- ✅ PyAutoGUI
- ✅ Google Chrome

---

## 🔧 **Configuración de Coordenadas**

Las coordenadas se configuran igual que antes:

1. En WSL2, ejecuta:
   ```bash
   conda activate carvajal
   python obtener_coordenadas.py
   ```

2. O desde Windows:
   ```cmd
   conda activate carvajal
   python obtener_coordenadas.py
   ```

3. Configura en la app web (Configuración Avanzada)

---

## 📊 **Logs**

En la terminal de WSL2 verás:

```
🚀 INICIANDO ENVÍO DE MENSAJE
============================================================
📱 Número: +573001234567
🐧 Detectado WSL2 - Usando script híbrido de Windows
🎯 Coordenadas predeterminadas: (1884, 979)
📞 Llamando script de Windows...

[Logs del script de Windows aparecen aquí]

🚀 INICIANDO ENVÍO DE MENSAJE (Windows)
📱 Número: +573001234567
🌐 Chrome: C:\Program Files\Google\Chrome\Application\chrome.exe
🔄 Abriendo Chrome...
⏳ Esperando 15 segundos...
🖱️  Moviendo a (1884, 979)...
✅ Click ejecutado
✅ ENVÍO COMPLETADO (desde Windows)
```

---

## ✅ **Ventajas de Esta Solución**

1. **Mantén tu ambiente WSL2** - No necesitas migrar todo a Windows
2. **Usa tu editor favorito** - VSCode, vim, etc. en WSL2
3. **MySQL en WSL2** - Mantén tu base de datos donde está
4. **Control de mouse funciona** - Windows maneja la parte crítica
5. **Sin duplicar código** - Una sola aplicación, dos modos de ejecución

---

## 🛠️ **Archivos Importantes**

```
dashboard/
├── pages/
│   └── wa.py                       # App principal (detecta WSL/Windows)
├── enviar_mensaje_windows.py      # Script de Windows para mouse
├── 2_EJECUTAR_APP.bat             # Ejecutar desde Windows
└── EJECUTAR_DESDE_WSL2.md         # Este archivo
```

---

## 🔍 **Solución de Problemas**

### **Problema: "python no se reconoce" desde WSL2**

El script intenta llamar al Python de Windows. Verifica que esté en el PATH.

**Solución:** Edita `pages/wa.py` línea 76 y especifica la ruta completa:

```python
result = sp.run([
    "powershell.exe", "-Command",
    f"C:\\Users\\mcomb\\miniconda3\\envs\\carvajal\\python.exe '{script_windows.replace('/mnt/c/', 'C:\\\\')}' ..."
])
```

---

### **Problema: "No se pudo abrir Chrome"**

El script de Windows no encuentra Chrome.

**Solución:** Verifica que Chrome esté instalado en Windows en las rutas estándar.

---

### **Problema: El mouse no se mueve**

PyAutoGUI no está instalado en el Python de **Windows**.

**Solución:**
```cmd
# En Anaconda Prompt (Windows)
conda activate carvajal
pip install pyautogui pillow
```

---

## 🎯 **Comandos Rápidos**

### **Desde WSL2:**
```bash
cd /mnt/c/Users/mcomb/Desktop/Carvajal/python/dashboard
conda activate carvajal
streamlit run pages/wa.py
```

### **Probar script de Windows:**
```bash
# Desde WSL2
powershell.exe -Command "python C:\\Users\\mcomb\\Desktop\\Carvajal\\python\\dashboard\\enviar_mensaje_windows.py '+573001234567' 'Mensaje de prueba' 1884 979"
```

---

## 📝 **Notas**

- El código detecta automáticamente si está en WSL2
- No necesitas cambiar nada en la app
- Las coordenadas se pasan automáticamente al script de Windows
- La configuración se comparte entre WSL2 y Windows

---

**¡Ahora puedes ejecutar desde WSL2 sin problemas!** 🎉
