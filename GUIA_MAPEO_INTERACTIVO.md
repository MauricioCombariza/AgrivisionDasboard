# Guía de Mapeo Interactivo de Clientes

**Funcionalidad:** Mapeo Interactivo en Procesador de Órdenes
**Ubicación:** Sistema WhatsApp/iMile > Procesador de Órdenes > Pestaña "Resultado"
**Versión:** 1.1 - 2026-01-08

---

## 📋 Descripción

El **Mapeo Interactivo** es una funcionalidad que permite asignar manualmente clientes del CSV a clientes existentes en la base de datos cuando no coinciden exactamente. Los mapeos se guardan automáticamente para ser reutilizados en futuras cargas.

---

## 🎯 ¿Cuándo se Necesita?

El mapeo interactivo aparece automáticamente cuando:

```
❌ Se detectan clientes en el CSV que NO existen en la BD
```

**Ejemplo:**
```
CSV contiene: "LEONISA"
BD contiene: "Leonisa S.A."
→ No coinciden → Mapeo interactivo requerido
```

---

## 🔧 Cómo Funciona

### Paso 1: Detección Automática

Cuando se validan los clientes, el sistema:
1. Compara nombres del CSV vs nombres en BD
2. Detecta los que no coinciden exactamente
3. Muestra interfaz de mapeo interactivo

### Paso 2: Interfaz de Mapeo

Se muestra una tabla con:

| Cliente en CSV | Cliente en Base de Datos | Estado |
|----------------|--------------------------|--------|
| LEONISA | [Selector dropdown] | ⏳ Nuevo |
| BANCO CAJA SOCIAL | [Selector dropdown] | ⏳ Nuevo |
| VEHIGROUP SAS | [Selector dropdown] | ⏳ Nuevo |

**Dropdown incluye:**
- `[No mapear - Crear cliente nuevo]` (opción por defecto)
- Lista completa de clientes activos en BD (ordenados alfabéticamente)

### Paso 3: Asignar Clientes

Para cada cliente del CSV:

1. **Seleccionar del dropdown** el cliente correcto de la BD
2. Si el cliente no existe en BD, dejar en "[No mapear...]"
3. Repetir para todos los clientes no encontrados

**Ejemplo:**
```
Cliente en CSV: LEONISA
Selección: Leonisa S.A.
```

### Paso 4: Guardar Mapeos

1. Hacer clic en **"💾 Guardar Mapeos"**
2. Sistema guarda todos los mapeos configurados
3. Los mapeos se almacenan en memoria (session_state)
4. Muestra confirmación: "✅ Se guardaron X mapeos"

### Paso 5: Aplicar Mapeos

1. Hacer clic en **"🔄 Aplicar Mapeos y Regenerar"**
2. Sistema:
   - Aplica los mapeos al DataFrame
   - Reemplaza nombres del CSV por nombres de BD
   - Recalcula clientes no encontrados
   - Regenera validación
3. Si todos los mapeos son correctos → ✅ Validación exitosa

---

## 💾 Persistencia de Mapeos

### Durante la Sesión

Los mapeos se guardan en `session_state` y se mantienen mientras:
- La aplicación esté abierta
- No se recargue la página completamente
- No se reinicie Streamlit

### Aplicación Automática

Una vez guardados, los mapeos se aplican **automáticamente** en:
- La misma sesión al procesar nuevo archivo
- Futuras validaciones durante la sesión

**Ventaja:** No necesitas mapear el mismo cliente dos veces en la misma sesión.

### Exportar Mapeos (Permanente)

Para guardar los mapeos permanentemente:

1. Ir a **Pestaña 2: "Mapeo de Clientes"**
2. Buscar sección **"Mapeos Interactivos"**
3. Hacer clic en **"📥 Exportar Mapeos Interactivos (JSON)"**
4. Se descarga archivo: `mapeos_clientes.json`
5. Guardar este archivo en lugar seguro

**Formato del archivo:**
```json
{
  "LEONISA": "Leonisa S.A.",
  "BANCO CAJA SOCIAL": "Banco Caja Social BCSC",
  "VEHIGROUP SAS": "Vehigroup S.A.S"
}
```

### Importar Mapeos (Cargar Guardados)

Para cargar mapeos previamente guardados:

1. Ir a **Pestaña 2: "Mapeo de Clientes"**
2. Buscar sección **"Importar Mapeos"**
3. Subir archivo `mapeos_clientes.json`
4. Hacer clic en **"✅ Confirmar Importación"**
5. Los mapeos se cargan automáticamente

**Uso típico:** Importar al inicio de cada sesión para tener todos los mapeos disponibles.

---

## 📊 Flujo Completo

### Primera Vez (Sin Mapeos Guardados)

```
1. Procesar archivo histórico
   ↓
2. Sistema detecta: LEONISA, BANCO CAJA SOCIAL, VEHIGROUP SAS no existen
   ↓
3. Aparece interfaz de mapeo interactivo
   ↓
4. Usuario asigna:
   - LEONISA → Leonisa S.A.
   - BANCO CAJA SOCIAL → Banco Caja Social BCSC
   - VEHIGROUP SAS → Vehigroup S.A.S
   ↓
5. Clic en "💾 Guardar Mapeos"
   ↓
6. Clic en "🔄 Aplicar Mapeos y Regenerar"
   ↓
7. ✅ Todos los clientes validados correctamente
   ↓
8. Descargar CSV con nombres corregidos
   ↓
9. OPCIONAL: Exportar mapeos para futuras sesiones
```

### Sesiones Siguientes (Con Mapeos Importados)

```
1. Importar archivo mapeos_clientes.json
   ↓
2. Procesar archivo histórico
   ↓
3. Sistema aplica mapeos automáticamente
   ↓
4. Solo aparecen clientes nuevos no mapeados (si los hay)
   ↓
5. Mapear solo los nuevos
   ↓
6. Guardar y aplicar
   ↓
7. Exportar mapeos actualizados
```

---

## 🎨 Características de la Interfaz

### Indicadores Visuales

**Estado "⏳ Nuevo":**
- Amarillo
- Cliente aún no ha sido mapeado
- Aparece en columna "Estado"

**Estado "✓ Guardado":**
- Verde
- Cliente ya tiene mapeo guardado
- Mapeo se aplica automáticamente

### Métricas

**Durante Mapeo:**
- Muestra: "Mapeos Guardados: X"
- Se actualiza al guardar nuevos mapeos

**En Sidebar:**
- "Mapeos Interactivos: X"
- Siempre visible
- Indica cuántos mapeos están activos

### Expandible "Ver Todos los Mapeos Guardados"

Muestra lista completa:
```
• LEONISA → Leonisa S.A.
• BANCO CAJA SOCIAL → Banco Caja Social BCSC
• VEHIGROUP SAS → Vehigroup S.A.S
```

---

## ⚙️ Gestión de Mapeos (Pestaña 2)

### Ver Mapeos Activos

En la sección **"Mapeos Interactivos"** puedes:

1. **Ver lista completa** (expandible)
   - Cliente CSV → Cliente BD
   - Botón ❌ para eliminar individualmente

2. **Exportar a JSON**
   - Descargar todos los mapeos
   - Archivo portable

3. **Limpiar todos**
   - Elimina todos los mapeos interactivos
   - Irreversible (a menos que tengas exportación)

### Importar Mapeos

1. Sección "Importar Mapeos"
2. Upload archivo JSON
3. Preview de mapeos a importar
4. Confirmar importación

---

## 💡 Casos de Uso

### Caso 1: Primera Carga de Archivo Histórico

**Situación:** Primera vez procesando basesHisto.csv

**Problema:**
- CSV tiene: "LEONISA", "BANCO CAJA SOCIAL", "VEHIGROUP SAS"
- BD tiene: "Leonisa S.A.", "Banco Caja Social BCSC", "Vehigroup S.A.S"

**Solución:**
1. Sistema detecta 3 clientes no encontrados
2. Aparecer interfaz de mapeo
3. Asignar cada uno manualmente
4. Guardar y aplicar
5. Exportar mapeos para próxima vez

**Resultado:** CSV generado con nombres correctos

### Caso 2: Carga Diaria con Mapeos Guardados

**Situación:** Carga diaria con mapeos ya configurados

**Proceso:**
1. Al inicio del día: Importar mapeos_clientes.json
2. Procesar archivo del día
3. Si hay clientes conocidos → Se mapean automáticamente
4. Si aparece cliente nuevo → Solo mapear el nuevo
5. Guardar y exportar mapeos actualizados

**Ventaja:** Solo mapeas clientes nuevos, no todos cada vez

### Caso 3: Cliente Nuevo en Archivo

**Situación:** Aparece "NUEVA EMPRESA SAS" en el CSV

**Opciones:**

**Opción A: Cliente ya existe en BD**
1. Seleccionar del dropdown: "Nueva Empresa S.A.S"
2. Guardar mapeo
3. Aplicar

**Opción B: Cliente NO existe en BD**
1. Dejar en "[No mapear - Crear cliente nuevo]"
2. Primero: Ir a Logística > Clientes y Precios
3. Crear el cliente "Nueva Empresa S.A.S"
4. Volver al procesador
5. Refrescar validación
6. Ahora aparecerá en el dropdown
7. Mapear y guardar

---

## 🔍 Validación Final

Después de aplicar mapeos, el sistema muestra:

### ✅ Todos Validados
```
✅ Todos los clientes existen en la base de datos o han sido mapeados correctamente
```
→ Puedes descargar CSV sin problemas

### ⚠️ Algunos Sin Mapear
```
⚠️ Quedan 2 clientes sin mapear. Configure el mapeo arriba.
```
→ Debes completar los mapeos o crear los clientes en BD

### 📥 Descarga con Advertencia
```
⚠️ Hay 2 clientes sin mapear. Algunas órdenes fallarán al cargar.
```
→ Puedes descargar, pero órdenes con clientes sin mapear fallarán en carga masiva

---

## ⚠️ Consideraciones Importantes

### 1. Exactitud de Nombres

Los nombres asignados deben coincidir **exactamente** con la BD:

❌ Incorrecto:
```
CSV: LEONISA
Mapeo: Leonisa
BD Real: Leonisa S.A.
→ Seguirá fallando
```

✅ Correcto:
```
CSV: LEONISA
Mapeo: Leonisa S.A.
BD Real: Leonisa S.A.
→ Funciona correctamente
```

### 2. Diferencia con Mapeo de Variaciones

**Mapeo Interactivo** (Pestaña 3):
- Asignación directa 1 a 1
- `"LEONISA"` → `"Leonisa S.A."`
- Se guarda: `LEONISA: Leonisa S.A.`

**Mapeo de Variaciones** (Pestaña 2):
- Agrupa múltiples variaciones
- Nombre correcto + lista de variaciones
- Se usa durante procesamiento inicial

**Cuándo usar cada uno:**
- **Variaciones**: Para normalizar durante procesamiento del archivo
- **Interactivo**: Para clientes que no se normalizaron y necesitan asignación manual

### 3. Persistencia

**Durante sesión:**
- ✅ Mapeos se mantienen
- ✅ Se aplican automáticamente
- ❌ Se pierden al cerrar Streamlit

**Entre sesiones:**
- ❌ Mapeos se pierden
- ✅ Solución: Exportar a JSON
- ✅ Importar al inicio de sesión

### 4. Sincronización con BD

Los mapeos NO sincronizan con la BD:
- Son locales a la aplicación
- No modifican la tabla `clientes`
- Solo afectan el CSV generado

Para crear clientes permanentes:
→ Ir a: Logística > Clientes y Precios > Crear Cliente

---

## 🔧 Solución de Problemas

### Problema: "Guardé mapeos pero siguen apareciendo como no encontrados"

**Causa:** Los mapeos se guardaron pero no se aplicaron

**Solución:**
1. Hacer clic en "🔄 Aplicar Mapeos y Regenerar"
2. El DataFrame se actualizará con los nombres correctos
3. La validación se ejecutará nuevamente

### Problema: "Los mapeos desaparecieron al cerrar Streamlit"

**Causa:** Los mapeos solo se guardan en session_state

**Solución:**
1. Antes de cerrar: Exportar mapeos a JSON
2. Al abrir nuevamente: Importar el JSON
3. Los mapeos vuelven a estar disponibles

### Problema: "Mapeé un cliente pero sigue fallando la validación"

**Causa:** El nombre en el dropdown no coincide con el de BD

**Solución:**
1. Ir a: Logística > Clientes y Precios
2. Copiar el nombre EXACTO del cliente
3. Volver al procesador
4. Verificar que el dropdown tenga ese nombre exacto
5. Si no aparece, refrescar la página

### Problema: "Aparecen muchos clientes sin mapear"

**Causa:** Primera vez o no se importaron mapeos previos

**Solución:**
1. Si tienes archivo `mapeos_clientes.json` → Importarlo
2. Si no existe → Mapear todos manualmente
3. Al terminar → Exportar para no repetir trabajo

### Problema: "El cliente no aparece en el dropdown"

**Causa:** El cliente no existe en BD o está inactivo

**Solución:**
1. Ir a: Logística > Clientes y Precios
2. Verificar si existe el cliente
3. Si existe, verificar que `activo = TRUE`
4. Si no existe, crear el cliente
5. Volver y refrescar

---

## ✅ Mejores Prácticas

### 1. Exportar Regularmente

Después de cada sesión donde mapees nuevos clientes:
```
→ Exportar mapeos a JSON
→ Guardar archivo con fecha: mapeos_clientes_2026-01-08.json
→ Mantener en lugar seguro
```

### 2. Importar al Inicio

Al inicio de cada día:
```
→ Importar último archivo de mapeos
→ Verificar en sidebar: "Mapeos Interactivos: X"
→ Proceder con procesamiento normal
```

### 3. Mantener BD Actualizada

Cuando aparezcan clientes nuevos frecuentemente:
```
→ Crearlos en BD primero
→ Luego procesarlos
→ Evita necesidad de mapeos
```

### 4. Revisar Mapeos Periódicamente

Cada semana:
```
→ Revisar lista de mapeos en Pestaña 2
→ Eliminar mapeos obsoletos
→ Exportar versión limpia
```

### 5. Documentar Mapeos

Mantener lista de mapeos comunes:
```
LEONISA → Leonisa S.A.
BANCO CAJA SOCIAL → Banco Caja Social BCSC
VEHIGROUP SAS → Vehigroup S.A.S
```

---

## 📊 Ejemplo Completo

### Datos Iniciales

**CSV procesado contiene:**
- LEONISA (100 órdenes)
- BANCO CAJA SOCIAL (50 órdenes)
- VEHIGROUP SAS (30 órdenes)
- Distribuidora XYZ (70 órdenes) ✅ Ya existe en BD

**BD contiene:**
- Leonisa S.A.
- Banco Caja Social BCSC
- Vehigroup S.A.S
- Distribuidora XYZ

### Validación Inicial

```
❌ Se encontraron 3 clientes que NO existen en la base de datos
- LEONISA
- BANCO CAJA SOCIAL
- VEHIGROUP SAS
```

### Mapeo Interactivo

```
Cliente CSV              | Cliente BD                    | Estado
-------------------------|-------------------------------|----------
LEONISA                  | [Leonisa S.A.]               | ⏳ Nuevo
BANCO CAJA SOCIAL        | [Banco Caja Social BCSC]     | ⏳ Nuevo
VEHIGROUP SAS            | [Vehigroup S.A.S]            | ⏳ Nuevo
```

### Acciones

1. Seleccionar cada cliente del dropdown
2. Clic "💾 Guardar Mapeos"
   - ✅ Se guardaron 3 mapeos
3. Clic "🔄 Aplicar Mapeos y Regenerar"
   - ✅ Mapeos aplicados correctamente

### Resultado

```
✅ Todos los clientes existen en la base de datos o han sido mapeados correctamente
```

**CSV generado:**
- 100 órdenes → Leonisa S.A.
- 50 órdenes → Banco Caja Social BCSC
- 30 órdenes → Vehigroup S.A.S
- 70 órdenes → Distribuidora XYZ

**Total:** 250 órdenes, todas con nombres correctos

---

## 📖 Referencia Rápida

### Atajos y Ubicaciones

| Acción | Ubicación |
|--------|-----------|
| Mapear clientes | Pestaña 3 > Validación de Clientes |
| Ver mapeos guardados | Pestaña 2 > Mapeos Interactivos |
| Exportar mapeos | Pestaña 2 > Exportar Mapeos (JSON) |
| Importar mapeos | Pestaña 2 > Importar Mapeos |
| Eliminar mapeo | Pestaña 2 > Expandir > ❌ |
| Limpiar todos | Pestaña 2 > Limpiar Todos |

### Estados Posibles

| Indicador | Significado |
|-----------|-------------|
| ⏳ Nuevo | Cliente no mapeado |
| ✓ Guardado | Cliente ya mapeado |
| ✅ Todos validados | Todos los clientes OK |
| ⚠️ Sin mapear | Algunos clientes faltan |
| ❌ No existe | Cliente no encontrado |

---

**Última actualización:** 2026-01-08
**Responsable:** Sistema WhatsApp/iMile - Agrivision
