# 📋 Actualizaciones del Sistema de Tarifas

## 🎯 Cambios Implementados

### 1. **Base de Datos - Nuevos Campos en `personal`**

Se agregaron 3 campos nuevos a la tabla `personal`:

```sql
ALTER TABLE personal
ADD COLUMN tarifa_entrega DECIMAL(10, 2) DEFAULT 0,
ADD COLUMN tarifa_devolucion DECIMAL(10, 2) DEFAULT 0,
ADD COLUMN costo_flete_sobre DECIMAL(10, 2) DEFAULT 0;
```

**Campos:**
- `tarifa_entrega`: Tarifa fija por entrega para couriers externos
- `tarifa_devolucion`: Tarifa fija por devolución (70% de entrega por default)
- `costo_flete_sobre`: Costo aproximado de flete terrestre por sobre

---

### 2. **Página de Personal - Tab 4 REEMPLAZADO**

**ANTES:**
- Tab 4: "Tarifas por Ciudad - Couriers Externos"
- Sistema complejo: Cada courier tenía tarifas diferentes para cada ciudad
- Tabla utilizada: `personal_ciudades`

**AHORA:**
- Tab 4: "Tarifas de Couriers Externos y Transportadoras"
- Sistema simplificado: Cada courier tiene tarifas FIJAS independientes de la ciudad
- Campos en tabla `personal`

**Funcionalidades:**
✅ Mostrar tarifas actuales de cada courier
✅ Editar tarifas: entrega, devolución, flete por sobre
✅ Auto-cálculo de devolución al 70% de la entrega (editable)
✅ Mostrar porcentaje de devolución vs entrega
✅ Nota informativa para mensajeros de Bogotá

---

### 3. **Página de Clientes - Tab 3 MEJORADO**

**Mejoras en "Gestión de Precios":**

✅ **Auto-sugerencia de devolución al 70%**
   - Al agregar precio de devolución, busca automáticamente el precio de entrega correspondiente
   - Calcula el 70% y lo muestra como valor sugerido
   - Totalmente editable por el usuario

✅ **Mensajes informativos**
   - Tip visual explicando el sistema del 70%
   - Alerta si no existe precio de entrega configurado
   - Help text en el campo de precio

✅ **Valor pre-llenado**
   - Si existe precio de entrega, el campo se llena automáticamente con el 70%
   - El usuario puede aceptarlo o modificarlo

---

## 🔄 Flujo de Trabajo Actualizado

### **Configurar Couriers Externos:**

1. Ir a **"2_Personal"** → Tab 4
2. Seleccionar courier de la lista
3. Ingresar:
   - Tarifa Entrega: $X
   - Tarifa Devolución: (Auto-calcula 70%, editable)
   - Costo Flete por Sobre: $Y
4. Guardar
5. Las tarifas aplican a TODAS las ciudades donde opere

### **Configurar Precios de Cliente:**

1. Ir a **"1_Clientes_Precios"** → Tab 3
2. Seleccionar cliente
3. Agregar precio de **ENTREGA** primero:
   - Tipo: Sobre/Paquete
   - Ámbito: Bogotá/Nacional
   - Precio: $Z
4. Agregar precio de **DEVOLUCIÓN**:
   - Mismo tipo y ámbito
   - El sistema auto-sugiere 70% del precio de entrega
   - Puedes aceptar o modificar

---

## 📊 Comparación: Antes vs Ahora

| Aspecto | ANTES | AHORA |
|---------|-------|-------|
| **Tarifas de Couriers** | Por ciudad (complejo) | Fijas por courier (simple) |
| **Tabla usada** | `personal_ciudades` | Campos en `personal` |
| **Devoluciones** | Ingreso manual | Auto-calculadas al 70% |
| **Flete terrestre** | Por ciudad en tabla `ciudades` | Por courier en `personal` |
| **Configuración** | Múltiples registros por ciudad | Un solo registro por courier |

---

## ✅ Ventajas del Nuevo Sistema

1. **Simplicidad**: Una sola tarifa por courier, no por ciudad
2. **Consistencia**: Mismo precio en todas las ciudades
3. **Automatización**: Devoluciones al 70% automáticas
4. **Menos errores**: Menos campos para configurar
5. **Más rápido**: Configuración en un solo lugar

---

## 📝 Notas Importantes

### **Mensajeros de Bogotá:**
- NO usan tarifas fijas
- Se pagan según la tarifa del CLIENTE
- No aparecen en Tab 4 de Personal

### **Couriers Externos/Transportadoras:**
- Usan tarifas fijas configuradas en Personal
- Independientes de la ciudad de destino
- Incluyen costo estimado de flete terrestre

### **Clientes:**
- Cada cliente tiene sus propias tarifas
- Las devoluciones por defecto son el 70% de entregas
- Totalmente personalizables

---

## 🚀 Cómo Aplicar los Cambios

Si ya tienes el sistema funcionando:

```bash
# 1. Aplicar cambios a la base de datos
mysql -u root -pVale2010 < actualizar_tarifas_personal.sql

# 2. Reiniciar el sistema
./iniciar_logistica.sh
# O desde Windows:
# INICIAR_LOGISTICA.bat
```

---

## 🔧 Archivos Modificados

1. ✅ `actualizar_tarifas_personal.sql` - Script de actualización BD
2. ✅ `pages_logistica/2_Personal.py` - Tab 4 completamente reescrito
3. ✅ `pages_logistica/1_Clientes_Precios.py` - Tab 3 con auto-cálculo de devoluciones

---

## 📅 Fecha de Actualización

**Implementado:** 6 de Enero de 2026
**Sistema:** Agrivision - Gestión Logística
