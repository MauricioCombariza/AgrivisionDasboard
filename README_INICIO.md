# Sistema de Inicio de Aplicaciones

Este documento explica cómo iniciar correctamente las diferentes aplicaciones Streamlit del proyecto.

---

## 📁 Estructura de Directorios

```
dashboard/
├── home.py                    # Aplicación principal WhatsApp/iMile
├── home_logistica.py          # Aplicación principal Logística
├── pages_home/                # Páginas de WhatsApp/iMile (permanente)
│   ├── DespachoCourrier.py
│   ├── Subir_devoluciones.py
│   └── ...
├── pages_logistica/           # Páginas de Logística (permanente)
│   ├── 1_Clientes_Precios.py
│   ├── 2_Personal.py
│   ├── 3_Ordenes.py
│   ├── 4_Facturacion.py
│   └── 5_Reportes.py
├── pages/                     # Symlink temporal (se crea/elimina automáticamente)
├── iniciar_home.sh            # Script para iniciar WhatsApp
├── iniciar_logistica.sh       # Script para iniciar Logística
└── limpiar_symlinks.sh        # Script de utilidad para limpiar
```

---

## 🚀 Cómo Iniciar las Aplicaciones

### Sistema WhatsApp / iMile

```bash
./iniciar_home.sh
```

- **Puerto:** 8501
- **URL:** http://localhost:8501
- **Páginas:** `pages_home/`

### Sistema de Logística

```bash
./iniciar_logistica.sh
```

- **Puerto:** 8502
- **URL:** http://localhost:8502
- **Páginas:** `pages_logistica/`

---

## 🔧 Cómo Funciona

### Sistema de Symlinks

Cada script de inicio:

1. **Verifica** que existen los directorios necesarios
2. **Limpia** cualquier configuración anterior (symlinks o backups)
3. **Crea un symlink** `pages/` → `pages_home/` o `pages_logistica/`
4. **Inicia** Streamlit en el puerto correspondiente
5. **Limpia automáticamente** al salir (Ctrl+C)

### Ventajas de esta Solución

✅ **Robusta:** No mueve archivos reales, solo crea/elimina symlinks
✅ **Segura:** Hace backups automáticos si encuentra directorios reales
✅ **Rápida:** Los symlinks son instantáneos
✅ **Limpia:** Se limpia automáticamente al salir (trap EXIT)
✅ **Independiente:** Cada aplicación usa su propio puerto
✅ **Sin conflictos:** Puedes correr ambas aplicaciones simultáneamente

---

## ⚠️ Solución de Problemas

### Error: "No se pudo crear el symlink"

**Causa:** Ya existe un directorio `pages/` real

**Solución:**
```bash
./limpiar_symlinks.sh
```

El script de limpieza te preguntará qué hacer con el directorio existente.

### Error: "No existe el directorio 'pages_home'"

**Causa:** Falta el directorio de páginas

**Solución:**
Verifica que existen los directorios:
```bash
ls -l | grep pages
```

Deberías ver:
- `pages_home/` (permanente)
- `pages_logistica/` (permanente)
- `pages/` (symlink, solo cuando hay una app corriendo)

### La aplicación muestra las páginas equivocadas

**Causa:** Hay un symlink residual de otra sesión

**Solución:**
```bash
./limpiar_symlinks.sh
./iniciar_logistica.sh  # o iniciar_home.sh
```

### Quiero ejecutar ambas aplicaciones al mismo tiempo

**Solución:** Ambos scripts usan puertos diferentes, así que puedes ejecutarlos simultáneamente:

Terminal 1:
```bash
./iniciar_home.sh
```

Terminal 2:
```bash
./iniciar_logistica.sh
```

Ahora tendrás:
- WhatsApp en http://localhost:8501
- Logística en http://localhost:8502

---

## 🛠️ Scripts Disponibles

### `iniciar_home.sh`
Inicia el sistema WhatsApp/iMile
- Crea symlink: `pages → pages_home`
- Puerto: 8501
- Auto-limpieza al salir

### `iniciar_logistica.sh`
Inicia el sistema de Logística
- Crea symlink: `pages → pages_logistica`
- Puerto: 8502
- Auto-limpieza al salir

### `limpiar_symlinks.sh`
Script de utilidad para limpiar manualmente
- Elimina symlinks residuales
- Maneja backups antiguos
- Verifica la estructura de directorios
- **Usar solo si hay problemas**

---

## 📝 Notas Importantes

1. **NO modifiques manualmente el directorio `pages/`**
   - Es un symlink temporal
   - Se crea/elimina automáticamente

2. **Modifica las páginas en sus directorios originales:**
   - WhatsApp: edita en `pages_home/`
   - Logística: edita en `pages_logistica/`

3. **Los cambios se reflejan inmediatamente:**
   - Streamlit detecta cambios automáticamente
   - No necesitas reiniciar el servidor

4. **Al cerrar la aplicación (Ctrl+C):**
   - El symlink se elimina automáticamente
   - No quedan archivos residuales

5. **Backups automáticos:**
   - Si el script encuentra un directorio `pages/` real
   - Crea un backup con timestamp
   - Formato: `pages_backup_YYYYMMDD_HHMMSS`

---

## 🔍 Verificar Estado Actual

Para ver qué hay en el directorio `pages/`:

```bash
ls -la | grep pages
```

- Si ves `lrwxrwxrwx` → Es un symlink (correcto)
- Si ves `drwxrwxrwx` → Es un directorio real (ejecutar limpieza)

Para ver a dónde apunta el symlink:

```bash
ls -l pages
```

---

## 🎯 Migración Completada

✅ Se renombró `pages/` → `pages_logistica/`
✅ Se crearon scripts robustos con symlinks
✅ Se agregó auto-limpieza al salir
✅ Se implementaron validaciones y backups
✅ Se documentó el nuevo sistema

---

## 📞 Soporte

Si tienes problemas:

1. Ejecutar `./limpiar_symlinks.sh`
2. Verificar que existen `pages_home/` y `pages_logistica/`
3. Intentar iniciar la aplicación nuevamente

Si el problema persiste, verificar los logs en la terminal.
