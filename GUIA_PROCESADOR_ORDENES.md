# Guía del Procesador de Órdenes Históricas

**Página:** Procesador_Ordenes.py
**Ubicación:** Sistema WhatsApp/iMile > Procesador de Órdenes
**Versión:** 1.0 - 2026-01-08

---

## 📋 Descripción General

Herramienta especializada para procesar archivos históricos de órdenes y prepararlos para carga masiva en el sistema de logística. Automatiza la clasificación, normalización y validación de datos.

---

## 🎯 Funcionalidades Principales

### 1. **Procesamiento Automático**
- Lee archivo CSV histórico (basesHisto.csv)
- Filtra órdenes por número mínimo
- Clasifica destinos automáticamente (local/nacional)
- Agrupa y cuenta cantidades por orden
- Genera formato compatible con carga masiva

### 2. **Mapeo de Clientes**
- Normaliza nombres de clientes
- Evita duplicados por errores tipográficos
- Configurable y editable

### 3. **Validación Inteligente**
- Detecta órdenes duplicadas en BD
- Permite mismo número de orden con destino diferente
- Valida existencia de clientes
- Genera reporte detallado

### 4. **Exportación Lista**
- CSV listo para carga masiva
- Compatible con sistema de logística
- Incluye solo órdenes nuevas

---

## 🔧 Cómo Funciona

### Clasificación de Destinos

El sistema clasifica automáticamente los destinos basándose en la ciudad:

```python
Si ciudad contiene "bog" → destino = "local"
Si NO contiene "bog" → destino = "nacional"
```

**Ejemplos:**
- "Bogotá" → local
- "Bogota D.C." → local
- "Medellín" → nacional
- "Cali" → nacional

### Procesamiento de Datos

1. **Carga**: Lee archivo CSV desde ruta especificada
2. **Filtrado**: Solo órdenes >= número mínimo especificado
3. **Conversión**: Parsea fechas y convierte tipos de datos
4. **Agrupación**: Agrupa por (orden, destino) y cuenta items
5. **Normalización**: Aplica mapeo de nombres de clientes
6. **Validación**: Compara contra BD para eliminar duplicados
7. **Exportación**: Genera CSV con formato requerido

### Detección de Duplicados

Una orden se considera **duplicada** si:
- Existe en BD con el **mismo número** Y **mismo destino**

Una orden se considera **nueva** si:
- No existe en BD, O
- Existe pero con **destino diferente**

**Ejemplo:**
```
Orden 12345 - local → Ya existe en BD
Orden 12345 - nacional → NO existe en BD → Se incluye

Resultado: Se puede tener orden 12345 dos veces (una local, una nacional)
```

---

## 📝 Uso Paso a Paso

### Pestaña 1: Procesar Archivo

#### Paso 1: Configurar Parámetros

**Ruta del Archivo CSV:**
- Ruta completa al archivo basesHisto.csv
- Default: `/mnt/c/Users/mcomb/Desktop/Carvajal/python/basesHisto.csv`

**Orden Mínima a Procesar:**
- Solo se procesarán órdenes con número >= a este valor
- Default: 123273
- Útil para procesar solo órdenes recientes

#### Paso 2: Procesar

1. Hacer clic en "🚀 Procesar Archivo"
2. El sistema:
   - Lee el archivo CSV
   - Filtra por orden mínima
   - Clasifica destinos
   - Agrupa por orden y destino
   - Cuenta cantidades
   - Muestra preview

#### Paso 3: Revisar Resultado

**Vista Previa:**
- Muestra últimas 50 órdenes procesadas
- Formato: orden, destino, fecha_recepcion, nombre_cliente, tipo_servicio, cantidad

**Estadísticas:**
- Total de órdenes procesadas
- Órdenes locales vs nacionales
- Total de items
- Clientes únicos identificados

**Lista de Clientes:**
- Expandible
- Muestra todos los nombres de clientes encontrados
- Útil para configurar mapeo

---

### Pestaña 2: Mapeo de Clientes

#### ¿Por Qué es Necesario?

Los nombres de clientes pueden variar en el archivo histórico:
- "DISTRIBUIDORA XYZ"
- "Distribuidora XYZ S.A."
- "Dist XYZ"

Sin mapeo → Se crearían 3 clientes diferentes
Con mapeo → Se normaliza a un solo nombre correcto

#### Configuración de Mapeo

**Ver Mapeo Actual:**
- Lista de todos los mapeos configurados
- Expandir para ver variaciones de cada cliente

**Agregar Nuevo Mapeo:**

1. **Nombre Correcto del Cliente:**
   - El nombre que debe aparecer en el CSV final
   - Debe coincidir exactamente con el cliente en BD

2. **Variaciones (una por línea):**
   ```
   DISTRIBUIDORA XYZ
   Distribuidora XYZ S.A.
   Dist XYZ
   DIST. XYZ
   ```

3. Hacer clic en "💾 Agregar Mapeo"

**Eliminar Mapeo:**
- Seleccionar cliente de la lista
- Clic en "🗑️ Eliminar"

#### Ejemplo de Configuración

```
Nombre Correcto: Distribuidora XYZ

Variaciones:
DISTRIBUIDORA XYZ
Distribuidora XYZ S.A.
Dist XYZ
DIST. XYZ
Distribuidora XYZ LTDA
```

Resultado: Todas estas variaciones se convertirán a "Distribuidora XYZ" en el CSV final.

---

### Pestaña 3: Resultado

#### Paso 1: Normalización de Nombres

- Aplica las reglas de mapeo configuradas
- Convierte todas las variaciones al nombre correcto
- Muestra cantidad de reglas aplicadas

#### Paso 2: Verificación contra BD

- Consulta todas las órdenes existentes en BD
- Identifica duplicados (mismo número + mismo destino)
- Separa órdenes nuevas de duplicadas

#### Paso 3: Resultados

**Órdenes Nuevas:**
- Total de órdenes que se pueden crear
- Total de items
- Datos expandibles

**Órdenes Duplicadas (Excluidas):**
- Total de órdenes que ya existen
- No se incluirán en el CSV
- Datos expandibles para revisión

#### Paso 4: Validación de Clientes

El sistema verifica que todos los clientes del CSV existan en la BD:

✅ **Todos existen** → Puede proceder con la descarga
❌ **Algunos no existen** → Lista los clientes faltantes

**Si hay clientes faltantes:**
- Opción 1: Crear los clientes en "Clientes y Precios"
- Opción 2: Ajustar el mapeo de nombres
- Opción 3: Descargar CSV de todas formas (órdenes fallarán al cargar)

#### Paso 5: Descargar CSV

1. Hacer clic en "📥 Descargar CSV de Órdenes Nuevas"
2. Se descarga archivo: `ordenes_procesadas_YYYYMMDD_HHMMSS.csv`
3. Contiene solo las órdenes nuevas (sin duplicados)
4. Formato listo para carga masiva

#### Paso 6: Cargar en Sistema

1. Ir a: **Logística** > **Órdenes** > **Carga Masiva CSV**
2. Subir el archivo descargado
3. Seguir proceso de carga masiva normal

---

## 📊 Formato del Archivo de Entrada

### Estructura Esperada (basesHisto.csv)

El archivo debe contener estas columnas:

| Columna | Descripción | Ejemplo |
|---------|-------------|---------|
| orden | Número de orden | 123273 |
| f_emi | Fecha de emisión | 2026-01-08 |
| ciudad1 | Ciudad destino | Bogotá |
| no_entidad | Nombre del cliente | Distribuidora XYZ |
| serial | Serial del item | ABC123 |

**Nota:** El sistema cuenta los seriales por orden para obtener la cantidad total.

---

## 📤 Formato del Archivo de Salida

### CSV Generado para Carga Masiva

| Columna | Descripción | Ejemplo |
|---------|-------------|---------|
| orden | Número de orden | 123273 |
| destino | local o nacional | local |
| fecha_recepcion | Fecha primera emisión | 2026-01-08 |
| nombre_cliente | Nombre normalizado | Distribuidora XYZ |
| tipo_servicio | Siempre "sobre" | sobre |
| cantidad | Count de seriales | 500 |

Este formato es compatible con la funcionalidad de **Carga Masiva CSV** del sistema de logística.

---

## 💡 Casos de Uso

### Caso 1: Procesamiento Diario

**Escenario:** Procesar órdenes del día anterior

**Proceso:**
1. Actualizar basesHisto.csv con datos del día
2. Ir a "Procesar Archivo"
3. Establecer orden mínima al último número procesado
4. Procesar → Normalizar → Descargar
5. Cargar en sistema de logística

**Frecuencia:** Diario

### Caso 2: Migración Histórica

**Escenario:** Migrar todas las órdenes desde orden 123273

**Proceso:**
1. Configurar mapeo de clientes (importante para datos históricos)
2. Establecer orden mínima: 123273
3. Procesar archivo completo
4. Revisar clientes faltantes
5. Crear clientes faltantes
6. Re-procesar si es necesario
7. Descargar CSV
8. Cargar en lotes (recomendado: 500 órdenes por lote)

### Caso 3: Actualización Incremental

**Escenario:** Solo agregar órdenes nuevas, evitando duplicados

**Proceso:**
1. Procesar archivo con orden mínima actual
2. El sistema automáticamente:
   - Detecta duplicados
   - Excluye órdenes existentes
   - Genera CSV solo con nuevas
3. Descargar y cargar

**Ventaja:** No necesitas llevar control manual de qué órdenes ya existen.

---

## ⚠️ Consideraciones Importantes

### 1. Duplicados con Destinos Diferentes

El sistema **permite** tener la misma orden dos veces si los destinos son diferentes:

```
Orden 12345 - local → Permitido
Orden 12345 - nacional → También permitido
```

Esto es intencional porque una orden puede tener entregas tanto locales como nacionales.

### 2. Normalización de Nombres

**Crítico:** El nombre normalizado debe coincidir **exactamente** con el nombre en la BD.

❌ Incorrecto:
```
Mapeo: "Distribuidora XYZ"
BD: "Distribuidora XYZ S.A."
→ No coincide → Error al cargar
```

✅ Correcto:
```
Mapeo: "Distribuidora XYZ S.A."
BD: "Distribuidora XYZ S.A."
→ Coincide → Carga exitosa
```

### 3. Tipo de Servicio

Actualmente, el sistema asigna **"sobre"** a todas las órdenes del archivo histórico.

Si necesitas diferenciar sobres vs paquetes:
- Opción 1: Modificar manualmente el CSV antes de cargar
- Opción 2: Solicitar ajuste al script de procesamiento

### 4. Fechas

Se toma la **primera fecha de emisión** (f_emi) encontrada para cada orden/destino.

### 5. Cantidades

Se cuentan los **seriales únicos** para cada orden/destino.

---

## 🔍 Validaciones Realizadas

### Durante Procesamiento

✅ Número de orden válido (numérico)
✅ Fechas parseables
✅ Ciudad disponible para clasificar destino
✅ Nombre de cliente no vacío

### Antes de Generar CSV

✅ Normalización de nombres aplicada
✅ Duplicados detectados y eliminados
✅ Clientes existen en BD
✅ Formato compatible con carga masiva

---

## 📈 Métricas y Estadísticas

### Durante Procesamiento

- **Total Órdenes**: Procesadas del archivo
- **Locales**: Órdenes clasificadas como local
- **Nacionales**: Órdenes clasificadas como nacional
- **Total Items**: Suma de cantidades
- **Clientes Únicos**: Diferentes nombres encontrados

### En Resultado

- **Órdenes Procesadas**: Total leído del archivo
- **Órdenes Nuevas**: Que se incluirán en CSV
- **Órdenes Duplicadas**: Que se excluyeron
- **% Nuevas**: Efectividad del procesamiento

---

## 🎓 Preguntas Frecuentes

**P: ¿Qué pasa si el archivo basesHisto.csv no existe?**
R: Se mostrará un error. Verifica la ruta del archivo.

**P: ¿Puedo cambiar la ruta del archivo?**
R: Sí, edita el campo "Ruta del Archivo CSV" antes de procesar.

**P: ¿El mapeo de clientes se guarda?**
R: Sí, se guarda en session_state durante la sesión. Para hacerlo permanente, se debería guardar en BD (mejora futura).

**P: ¿Qué pasa si no configuro mapeo de clientes?**
R: Los nombres se usarán tal cual están en el archivo. Puede resultar en clientes duplicados.

**P: ¿Por qué algunas órdenes se marcan como duplicadas?**
R: Porque ya existen en la BD con el mismo número de orden y mismo destino.

**P: ¿Puedo incluir órdenes duplicadas de todas formas?**
R: No directamente. Si las necesitas, debes eliminarlas de la BD primero.

**P: ¿Qué significa "orden mínima"?**
R: Solo se procesarán órdenes con número >= a este valor. Útil para procesar solo las recientes.

**P: ¿El CSV generado tiene límite de tamaño?**
R: No hay límite técnico, pero se recomienda cargar en lotes de 500-1000 órdenes.

**P: ¿Qué pasa si hay clientes que no existen?**
R: Se muestra advertencia. Puedes crear los clientes primero o descargar el CSV de todas formas (algunas órdenes fallarán al cargar).

---

## 🔧 Solución de Problemas

### Problema: "Error al procesar archivo"

**Posibles causas:**
- Archivo no existe en la ruta especificada
- Formato de CSV incorrecto
- Columnas faltantes

**Solución:**
1. Verificar que el archivo existe
2. Verificar columnas: orden, f_emi, ciudad1, no_entidad, serial
3. Verificar formato UTF-8

### Problema: "Todos los clientes no encontrados"

**Causa:** Los nombres normalizados no coinciden con los de BD

**Solución:**
1. Ir a "Clientes y Precios" > "Listar Clientes"
2. Copiar nombres exactos
3. Configurar mapeo con esos nombres
4. Re-procesar

### Problema: "No hay órdenes nuevas"

**Causa:** Todas las órdenes ya existen en BD

**Solución:**
- Esto es normal si ya se procesó el archivo
- Verificar orden mínima (aumentarla)
- Verificar que basesHisto.csv tiene datos nuevos

### Problema: "El CSV descargado está vacío"

**Causa:** Todas las órdenes fueron marcadas como duplicadas

**Solución:**
- Normal si no hay órdenes nuevas
- Aumentar orden mínima para incluir órdenes más recientes

---

## 🚀 Flujo Completo Recomendado

### Primera Vez (Migración Histórica)

1. **Preparación:**
   - [ ] Revisar archivo basesHisto.csv
   - [ ] Identificar clientes únicos
   - [ ] Crear clientes faltantes en BD

2. **Configuración:**
   - [ ] Ir a "Mapeo de Clientes"
   - [ ] Configurar variaciones de nombres
   - [ ] Verificar coincidencia con BD

3. **Procesamiento:**
   - [ ] Establecer orden mínima
   - [ ] Procesar archivo
   - [ ] Revisar estadísticas

4. **Validación:**
   - [ ] Revisar órdenes nuevas vs duplicadas
   - [ ] Verificar clientes existen
   - [ ] Corregir mapeo si es necesario

5. **Exportación:**
   - [ ] Descargar CSV
   - [ ] Dividir en lotes si es muy grande

6. **Carga:**
   - [ ] Ir a sistema de logística
   - [ ] Carga masiva CSV
   - [ ] Verificar resultados

### Uso Diario

1. Actualizar basesHisto.csv
2. Procesar con orden mínima actualizada
3. Descargar CSV (solo nuevas)
4. Cargar en sistema
5. Listo

---

## 📊 Ejemplo Completo

### Datos de Entrada (basesHisto.csv)

```csv
orden,f_emi,ciudad1,no_entidad,serial
123273,2026-01-05,Bogotá,DISTRIBUIDORA XYZ,SER001
123273,2026-01-05,Bogotá,DISTRIBUIDORA XYZ,SER002
123273,2026-01-05,Bogotá,Distribuidora XYZ S.A.,SER003
123274,2026-01-06,Medellín,Empresa ABC,SER004
123274,2026-01-06,Medellín,EMPRESA ABC LTDA,SER005
```

### Mapeo Configurado

```
Distribuidora XYZ:
  - DISTRIBUIDORA XYZ
  - Distribuidora XYZ S.A.
  - Dist XYZ

Empresa ABC:
  - Empresa ABC
  - EMPRESA ABC LTDA
```

### Resultado Procesado

```csv
orden,destino,fecha_recepcion,nombre_cliente,tipo_servicio,cantidad
123273,local,2026-01-05,Distribuidora XYZ,sobre,3
123274,nacional,2026-01-06,Empresa ABC,sobre,2
```

**Explicación:**
- Orden 123273: 3 seriales con nombres diferentes → Normalizados a "Distribuidora XYZ"
- Ciudad "Bogotá" → destino "local"
- Orden 123274: 2 seriales con nombres diferentes → Normalizados a "Empresa ABC"
- Ciudad "Medellín" → destino "nacional"

---

## ✅ Checklist de Uso

**Preparación:**
- [ ] Archivo basesHisto.csv actualizado
- [ ] Clientes creados en BD
- [ ] Mapeo de clientes configurado

**Procesamiento:**
- [ ] Ruta de archivo correcta
- [ ] Orden mínima establecida
- [ ] Archivo procesado exitosamente
- [ ] Estadísticas revisadas

**Resultado:**
- [ ] Nombres normalizados
- [ ] Duplicados excluidos
- [ ] Clientes validados
- [ ] CSV descargado
- [ ] Cargado en sistema de logística

---

**Última actualización:** 2026-01-08
**Responsable:** Sistema WhatsApp/iMile - Agrivision
