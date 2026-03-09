# 🐧 Ejecutar Sistemas desde WSL2

## 📋 Scripts Disponibles

### Para Sistema de Logística:
```bash
./iniciar_logistica.sh
```
- Activa automáticamente `pages_logistica`
- Inicia en: http://localhost:8502
- Presiona `Ctrl+C` para detener

### Para Sistema WhatsApp/iMile:
```bash
./iniciar_home.sh
```
- Activa automáticamente `pages_home`
- Inicia en: http://localhost:8501
- Presiona `Ctrl+C` para detener

---

## 🚀 Inicio Rápido

### Desde WSL2:

```bash
# 1. Navegar al directorio
cd /mnt/c/Users/mcomb/Desktop/Carvajal/python/dashboard

# 2. Ejecutar el sistema deseado
./iniciar_logistica.sh    # Para Logística
# O
./iniciar_home.sh          # Para WhatsApp/iMile
```

### Desde Windows:

```bash
# Doble clic en:
INICIAR_LOGISTICA.bat     # Para Logística
INICIAR_WHATSAPP.bat      # Para WhatsApp/iMile
```

---

## ⚙️ Cómo Funcionan los Scripts

Ambos scripts (.sh y .bat) hacen lo mismo:

1. **Backup**: Guardan la carpeta `pages` actual si existe
2. **Activación**: Renombran la carpeta correspondiente a `pages`
3. **Inicio**: Ejecutan streamlit en el puerto correspondiente
4. **Restauración**: Al cerrar (Ctrl+C), restauran las carpetas originales

Esto permite ejecutar ambos sistemas sin conflictos.

---

## 🔧 Solución de Problemas

### Error: "Permission denied"
```bash
chmod +x iniciar_logistica.sh iniciar_home.sh
```

### Error: "streamlit: command not found"
```bash
# Verificar instalación
which streamlit

# Si no está instalado:
pip install streamlit
```

### Puerto ocupado
```bash
# Ver qué proceso usa el puerto
lsof -i :8502  # Para logística
lsof -i :8501  # Para WhatsApp

# Matar el proceso
kill -9 <PID>
```

### Carpetas no se restauran
```bash
# Restaurar manualmente:
mv pages pages_logistica  # Si quedó en pages
# O
mv pages pages_home       # Si quedó en pages
```

---

## 🎯 Ejecutar Ambos Sistemas a la Vez

Sí, puedes ejecutar ambos simultáneamente:

### Opción 1: Dos terminales WSL2
```bash
# Terminal 1:
./iniciar_logistica.sh

# Terminal 2 (nueva terminal):
./iniciar_home.sh
```

### Opción 2: Background
```bash
# Iniciar en background:
./iniciar_logistica.sh &

# Ver procesos:
jobs

# Traer al foreground:
fg %1

# Matar proceso en background:
kill %1
```

---

## 📁 Estructura de Archivos

```
dashboard/
├── iniciar_logistica.sh    ← Ejecuta desde WSL2
├── iniciar_home.sh          ← Ejecuta desde WSL2
├── INICIAR_LOGISTICA.bat    ← Ejecuta desde Windows
├── INICIAR_WHATSAPP.bat     ← Ejecuta desde Windows
│
├── home_logistica.py        → Sistema de Logística
├── home.py                  → Sistema WhatsApp
│
├── pages_logistica/         → 5 páginas de Logística
└── pages_home/              → ~18 páginas de WhatsApp
```

---

## 💡 Tips

1. **Usa tab-completion**: Escribe `./inic` y presiona Tab
2. **Historial de comandos**: Presiona flecha arriba ↑
3. **Matar proceso**: `Ctrl+C` en la terminal
4. **Ver logs**: Los errores se muestran en tiempo real
5. **Acceder desde Windows**: Ambos puertos son accesibles desde el navegador Windows

---

## 🔐 Primer Uso - Base de Datos

Si es la primera vez usando el sistema de logística:

```bash
# Desde WSL2:
python3 init_db_logistica.py

# O desde Windows:
# Doble clic en: INICIALIZAR_BD_LOGISTICA.bat
```

---

## 📞 Recursos Adicionales

- `README_LOGISTICA.md` - Documentación completa del sistema
- `INSTRUCCIONES_INICIO.txt` - Guía general
- `INSTRUCCIONES_WHATSAPP.md` - Docs sistema WhatsApp
