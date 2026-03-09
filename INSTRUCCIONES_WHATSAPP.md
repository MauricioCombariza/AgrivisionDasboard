# 📱 Guía de Configuración - Envío Automático WhatsApp

## ✅ Mejoras Implementadas

1. **Chrome siempre maximizado** - Elimina problemas de ventanas con diferentes tamaños
2. **Triple sistema de respaldo** - 3 métodos diferentes para enviar el mensaje
3. **Configuración manual de coordenadas** - Si falla, puedes configurar manualmente

---

## 🚀 Cómo Usar

### Opción 1: Modo Automático (Recomendado)

1. Ejecuta la aplicación:
   ```bash
   streamlit run pages/wa.py
   ```

2. Sube tu archivo Excel con la columna `serial`

3. Asegúrate de tener **WhatsApp Web ya logueado** en Chrome

4. Click en **"⏳ Iniciar Envíos"** o **"⏳ Confirmar entregas"**

5. El sistema intentará enviar automáticamente

---

### Opción 2: Configuración Manual (Si falla el automático)

Si los mensajes no se envían automáticamente, sigue estos pasos:

#### Paso 1: Obtener las Coordenadas del Botón

```bash
python obtener_coordenadas.py
```

Sigue las instrucciones en pantalla:
- Abre WhatsApp Web MAXIMIZADO
- Abre cualquier chat
- Mueve el mouse sobre el **botón de envío** (flecha verde)
- Presiona `Ctrl+C`
- Copia las coordenadas que aparecen

#### Paso 2: Configurar las Coordenadas

1. En la aplicación de Streamlit, abre **"⚙️ Configuración Avanzada"**
2. Ingresa las coordenadas X e Y que obtuviste
3. Verás el mensaje: **"✅ Coordenadas configuradas"**
4. Ahora intenta enviar de nuevo

---

## 🔧 Solución de Problemas

### Problema: Chrome se abre pero no envía

**Solución:**
- Asegúrate de estar logueado en WhatsApp Web
- Espera 15 segundos completos antes de que intente enviar
- Si sigue fallando, usa la Opción 2 (configuración manual)

### Problema: Se envía a número incorrecto

**Solución:**
- Verifica que los números en la base de datos MySQL tengan el formato correcto
- Ejemplo: `+573001234567` (con código de país)

### Problema: Chrome no se encuentra

**Solución:**
- El script busca Chrome en: `/mnt/c/Program Files/Google/Chrome/Application/`
- Si tu Chrome está en otra ubicación, modifica la ruta en `pages/wa.py:47-48`

---

## 📊 Formato del Excel

El archivo Excel debe tener al menos una columna:
- **serial**: El número serial del paquete

Ejemplo:
```
serial
ABC123
DEF456
GHI789
```

---

## 🔄 Flujo del Sistema

1. Lee el Excel
2. Por cada fila:
   - Busca datos en MySQL por serial
   - Abre WhatsApp Web en Chrome maximizado
   - Carga el mensaje pre-escrito
   - Espera 15 segundos
   - **Intenta enviar con 3 métodos:**
     1. Click en cuadro de texto + Tab + Enter
     2. Click en coordenadas relativas (93% ancho, 93% alto)
     3. Atajo de teclado Ctrl+Enter
   - Cierra la pestaña
   - Espera 5 segundos antes del siguiente

---

## ⚡ Consejos para Mejor Rendimiento

1. **Cierra otras aplicaciones** - Para que pyautogui funcione mejor
2. **No muevas el mouse** - Durante el proceso de envío
3. **Mantén Chrome maximizado** - Abre manualmente WhatsApp Web antes de iniciar
4. **Prueba con 2-3 contactos primero** - Antes de enviar masivamente
5. **Sesión activa de WhatsApp** - Debes estar logueado antes de comenzar

---

## 📝 Notas Técnicas

- **Tiempo por mensaje:** ~22 segundos (15s carga + 5s espera + 2s cierre)
- **Conexión:** MySQL local (host: localhost, db: imile)
- **Navegador:** Google Chrome (detecta versiones automáticamente)
- **Automatización:** pyautogui con múltiples métodos de respaldo

---

¿Tienes problemas? Revisa los logs en la terminal donde ejecutaste Streamlit.
