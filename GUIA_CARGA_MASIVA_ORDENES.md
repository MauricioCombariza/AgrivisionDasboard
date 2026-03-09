# Guía de Carga Masiva de Órdenes desde CSV

**Página:** 3_Ordenes.py > Pestaña "Carga Masiva CSV"
**Ubicación:** Sistema de Logística > Órdenes > Carga Masiva CSV
**Versión:** 1.0 - 2026-01-08

---

## 📋 Descripción General

Funcionalidad para cargar múltiples órdenes simultáneamente desde un archivo CSV, agilizando el ingreso de grandes volúmenes de órdenes.

---

## 🎯 Ventajas de la Carga Masiva

✅ **Ahorro de tiempo**: Carga cientos de órdenes en segundos
✅ **Menos errores**: Reduce errores de digitación manual
✅ **Validación automática**: Verifica todos los datos antes de crear las órdenes
✅ **Precios automáticos**: Calcula precios basándose en configuración de clientes
✅ **Reporte detallado**: Muestra qué órdenes se crearon y cuáles fallaron

---

## 📄 Formato del Archivo CSV

### Columnas Requeridas

El archivo CSV debe contener exactamente estas 6 columnas:

| Columna | Descripción | Valores Válidos | Ejemplo |
|---------|-------------|-----------------|---------|
| **orden** | Número de orden | Texto/número único | 12345 |
| **destino** | Ámbito de la orden | `local` o `nacional` | local |
| **fecha_recepcion** | Fecha de recepción | YYYY-MM-DD o DD/MM/YYYY | 2026-01-08 |
| **nombre_cliente** | Nombre del cliente | Debe existir en sistema | Distribuidora XYZ |
| **tipo_servicio** | Tipo de servicio | `sobres` o `paquetes` | sobres |
| **cantidad** | Cantidad total | Número entero positivo | 500 |

### Importante sobre Columnas

- ✅ Los nombres de columnas deben ser **exactamente** como se muestra arriba
- ✅ El orden de las columnas no importa
- ⚠️ No agregar columnas adicionales (el sistema las ignorará)
- ⚠️ **No incluir** columna de precio - se calcula automáticamente

---

## 🔧 Cómo Funciona el Cálculo de Precios

El sistema calcula automáticamente el precio unitario basándose en:

1. **Cliente**: Se busca el cliente por nombre exacto
2. **Tipo de servicio**: sobres o paquetes
3. **Ámbito**: local (Bogotá) o nacional

**Ejemplo de búsqueda:**
```
Cliente: Distribuidora XYZ
Tipo: sobres
Ámbito: local (bogota)
→ Sistema busca en precios_cliente el precio configurado
→ Si encuentra: Aplica ese precio
→ Si NO encuentra: Marca la orden como fallida
```

⚠️ **Importante**: Todos los clientes deben tener precios configurados previamente en la página "Clientes y Precios" para ambos tipos de servicio y ámbitos que se usarán.

---

## 📝 Paso a Paso - Carga de Órdenes

### Paso 1: Preparar el Archivo CSV

**Opción A: Descargar Plantilla**
1. Ir a pestaña "Carga Masiva CSV"
2. Hacer clic en "📥 Descargar Plantilla CSV"
3. Abrir el archivo en Excel o editor de texto
4. Completar con los datos de las órdenes

**Opción B: Crear Desde Cero**
1. Crear archivo con las 6 columnas requeridas
2. Asegurar que los nombres coincidan exactamente

**Ejemplo de archivo CSV:**
```csv
orden,destino,fecha_recepcion,nombre_cliente,tipo_servicio,cantidad
12345,local,2026-01-08,Distribuidora XYZ,sobres,500
12346,nacional,2026-01-08,Empresa ABC,paquetes,250
12347,local,2026-01-09,Distribuidora XYZ,paquetes,100
12348,nacional,2026-01-09,Corporación DEF,sobres,300
```

### Paso 2: Validar Datos Antes de Subir

**Verificar clientes:**
- Los nombres deben coincidir **exactamente** con los registrados en el sistema
- Revisar en "Clientes y Precios" > "Listar Clientes"

**Verificar precios:**
- Cada cliente debe tener precios configurados para:
  - Tipo de servicio que se usará (sobres/paquetes)
  - Ámbito que se usará (local/nacional)

**Verificar fechas:**
- Formato recomendado: YYYY-MM-DD (ej: 2026-01-08)
- También acepta: DD/MM/YYYY (ej: 08/01/2026)

### Paso 3: Cargar el Archivo

1. Ir a página "Órdenes"
2. Seleccionar pestaña "📤 Carga Masiva CSV"
3. Hacer clic en "Seleccione el archivo CSV"
4. Elegir el archivo preparado
5. El sistema mostrará una **vista previa** del archivo

### Paso 4: Revisar Validación

El sistema valida automáticamente:

✅ **Columnas requeridas**: Verifica que existan las 6 columnas
✅ **Destinos**: Solo acepta 'local' o 'nacional'
✅ **Tipo de servicio**: Solo acepta 'sobres' o 'paquetes' (normaliza variaciones)
✅ **Cantidades**: Deben ser números positivos
✅ **Fechas**: Formato válido
✅ **Clientes**: Deben existir en el sistema

**Si hay errores:**
- ❌ Se muestran en rojo
- ❌ No se permite continuar
- 📝 Corregir el CSV y volver a cargar

**Si todo está bien:**
- ✅ Mensaje verde "Validación exitosa"
- 📊 Se muestran métricas: Total órdenes, Total items, Clientes únicos
- 🚀 Aparece botón "Procesar y Crear Órdenes"

### Paso 5: Procesar Órdenes

1. Revisar métricas mostradas
2. Hacer clic en "🚀 Procesar y Crear Órdenes"
3. El sistema:
   - Muestra barra de progreso
   - Procesa orden por orden
   - Busca precio para cada combinación cliente/servicio/ámbito
   - Crea las órdenes en la base de datos

### Paso 6: Revisar Resultados

El sistema muestra un reporte completo:

**Órdenes Creadas Exitosamente:**
- ✅ Número de orden
- ✅ Cliente
- ✅ Cantidad
- ✅ Valor calculado

**Órdenes Fallidas:**
- ❌ Número de orden
- ❌ Razón del error

**Errores Comunes:**
- "No se encontró precio configurado..." → Falta configurar precio para ese cliente/servicio/ámbito
- "Duplicate entry..." → La orden ya existe en el sistema
- Error de fecha → Formato incorrecto

---

## 💡 Ejemplos Prácticos

### Ejemplo 1: Carga Simple - Un Cliente

**Escenario:** Distribuidora XYZ envía 3 órdenes locales

**CSV:**
```csv
orden,destino,fecha_recepcion,nombre_cliente,tipo_servicio,cantidad
ORD-001,local,2026-01-08,Distribuidora XYZ,sobres,500
ORD-002,local,2026-01-08,Distribuidora XYZ,sobres,300
ORD-003,local,2026-01-08,Distribuidora XYZ,paquetes,150
```

**Resultado:**
- 3 órdenes creadas
- Precios aplicados desde configuración de Distribuidora XYZ
- Todas marcadas como 'activa'

### Ejemplo 2: Carga Mixta - Varios Clientes

**Escenario:** Múltiples clientes con diferentes destinos

**CSV:**
```csv
orden,destino,fecha_recepcion,nombre_cliente,tipo_servicio,cantidad
12345,local,2026-01-08,Distribuidora XYZ,sobres,500
12346,nacional,2026-01-08,Empresa ABC,paquetes,250
12347,local,2026-01-09,Corporación DEF,sobres,400
12348,nacional,2026-01-09,Distribuidora XYZ,paquetes,180
```

**Proceso:**
- Orden 12345: Busca precio local+sobres para Distribuidora XYZ
- Orden 12346: Busca precio nacional+paquetes para Empresa ABC
- Orden 12347: Busca precio local+sobres para Corporación DEF
- Orden 12348: Busca precio nacional+paquetes para Distribuidora XYZ

### Ejemplo 3: Error de Validación

**Escenario:** CSV con errores

**CSV Incorrecto:**
```csv
orden,destino,fecha_recepcion,nombre_cliente,tipo_servicio,cantidad
12345,LOCAL,2026-01-08,Cliente Inexistente,sobres,500
12346,regional,2026-01-08,Empresa ABC,sobre,-100
```

**Errores Detectados:**
- ❌ Cliente "Cliente Inexistente" no está registrado
- ❌ Destino "regional" inválido (debe ser 'local' o 'nacional')
- ❌ Cantidad -100 es negativa

**Solución:** Corregir el CSV:
```csv
orden,destino,fecha_recepcion,nombre_cliente,tipo_servicio,cantidad
12345,local,2026-01-08,Empresa ABC,sobres,500
12346,nacional,2026-01-08,Empresa ABC,sobres,100
```

---

## 🔍 Validaciones Detalladas

### 1. Validación de Destino

**Valores aceptados:**
- `local` → Se interpreta como ámbito 'bogota'
- `nacional` → Se interpreta como ámbito 'nacional'

**No se distinguen mayúsculas/minúsculas**: "LOCAL", "Local", "local" son equivalentes

### 2. Validación de Tipo de Servicio

**Variaciones aceptadas:**
- `sobre`, `sobres` → Se normaliza a 'sobre'
- `paquete`, `paquetes` → Se normaliza a 'paquete'

**No se distinguen mayúsculas/minúsculas**

### 3. Validación de Clientes

**Requisitos:**
- Cliente debe existir en tabla `clientes`
- Cliente debe estar **activo** (activo = TRUE)
- El nombre debe coincidir exactamente (ignora mayúsculas/minúsculas)

**Tip:** Si tienes clientes con nombres similares:
- "Distribuidora XYZ"
- "Distribuidora XYZ S.A."

Son considerados diferentes. Usa el nombre exacto registrado.

### 4. Validación de Fechas

**Formatos aceptados:**
- ISO: `2026-01-08`
- Europeo: `08/01/2026`
- Americano: `01/08/2026`

**Recomendación:** Usar formato ISO (YYYY-MM-DD) para evitar ambigüedades.

---

## ⚠️ Notas Importantes

1. **Precios Obligatorios:**
   - TODOS los clientes deben tener precios configurados
   - Para TODOS los tipos de servicio que usarán
   - Para TODOS los ámbitos que usarán
   - Sin esto, las órdenes fallarán

2. **Órdenes Duplicadas:**
   - El número de orden debe ser único
   - Si ya existe, la creación fallará
   - Revisar en "Listar Órdenes" antes de cargar

3. **Límite de Órdenes:**
   - No hay límite técnico
   - Recomendado: Máximo 1000 órdenes por carga
   - Para cargas muy grandes, dividir en varios archivos

4. **Ciudad Destino:**
   - No se puede especificar en el CSV
   - Se crea como NULL (sin ciudad asignada)
   - Asignar manualmente después si es necesario

5. **Estado Inicial:**
   - Todas las órdenes se crean como 'activa'
   - Para anular/finalizar, usar pestaña "Actualizar Estado"

6. **Observaciones:**
   - Se agrega automáticamente: "Carga masiva CSV - [destino]"
   - No se pueden personalizar en carga masiva
   - Editar individualmente después si es necesario

---

## 🎓 Preguntas Frecuentes

**P: ¿Puedo agregar columnas adicionales al CSV?**
R: Sí, el sistema las ignorará. Solo procesará las 6 columnas requeridas.

**P: ¿Qué pasa si una orden falla?**
R: El proceso continúa con las demás. Al final se muestra un reporte de exitosas y fallidas.

**P: ¿Puedo cargar órdenes de fechas pasadas?**
R: Sí, la fecha puede ser cualquier día (pasado, presente o futuro).

**P: ¿Cómo sé qué precio se aplicará?**
R: El sistema busca en "Clientes y Precios" la tarifa vigente para ese cliente/servicio/ámbito.

**P: ¿Puedo modificar una orden después de crearla?**
R: Sí, ir a pestaña "Crear/Editar Orden" en modo "Editar Existente".

**P: ¿Se pueden cargar órdenes para clientes inactivos?**
R: No, solo clientes con estado activo = TRUE.

**P: ¿Qué pasa si el CSV tiene errores de formato?**
R: El sistema los detecta en la validación y no permite procesar hasta corregirlos.

---

## 📊 Casos de Uso Reales

### Caso 1: Distribuidora Diaria

**Situación:** Distribuidora XYZ recibe 50 órdenes diarias

**Proceso:**
1. Exportar órdenes del sistema interno a CSV
2. Ajustar nombres de columnas a formato requerido
3. Cargar a sistema de logística
4. Revisar que todas se crearon correctamente
5. Asignar personal en pestaña correspondiente

**Tiempo:** 5 minutos vs 2 horas manual

### Caso 2: Migración de Datos

**Situación:** Migrar 500 órdenes de sistema antiguo

**Proceso:**
1. Exportar datos de sistema antiguo
2. Transformar a formato CSV requerido
3. Dividir en lotes de 100 órdenes
4. Cargar lote por lote
5. Verificar totales

**Ventaja:** Validación automática detecta inconsistencias

### Caso 3: Cliente Corporativo

**Situación:** Empresa ABC envía archivo semanal con todas sus órdenes

**Proceso:**
1. Recibir archivo de cliente por correo
2. Verificar formato (puede requerir ajustes)
3. Validar que cliente tenga precios configurados
4. Cargar archivo completo
5. Notificar a cliente las órdenes creadas

---

## 🔧 Solución de Problemas

### Problema: "Faltan columnas en el CSV"

**Causa:** Nombres de columnas incorrectos

**Solución:**
- Verificar nombres exactos (case-sensitive)
- Descargar plantilla y copiar nombres de columnas
- No usar espacios adicionales

### Problema: "Cliente no encontrado"

**Causa:** Nombre no coincide con registro

**Solución:**
1. Ir a "Clientes y Precios" > "Listar Clientes"
2. Copiar nombre EXACTO del cliente
3. Pegar en CSV
4. Volver a cargar

### Problema: "No se encontró precio configurado"

**Causa:** Falta precio para esa combinación

**Solución:**
1. Ir a "Clientes y Precios"
2. Buscar el cliente
3. Agregar precio para el tipo_servicio y ámbito faltante
4. Volver a intentar carga

### Problema: "Duplicate entry"

**Causa:** Número de orden ya existe

**Solución:**
- Revisar en "Listar Órdenes" si ya fue creada
- Cambiar número de orden si es una nueva
- Omitir si ya estaba registrada

---

## ✅ Checklist de Carga Masiva

**Antes de cargar:**
- [ ] Archivo CSV con 6 columnas correctas
- [ ] Nombres de clientes verificados
- [ ] Precios configurados para todos los clientes
- [ ] Fechas en formato válido
- [ ] Números de orden únicos
- [ ] Destinos como 'local' o 'nacional'
- [ ] Tipo de servicio como 'sobres' o 'paquetes'
- [ ] Cantidades positivas

**Durante la carga:**
- [ ] Revisar vista previa del archivo
- [ ] Verificar validación exitosa
- [ ] Revisar métricas mostradas
- [ ] Confirmar procesamiento

**Después de cargar:**
- [ ] Revisar órdenes creadas exitosamente
- [ ] Anotar órdenes fallidas (si hay)
- [ ] Corregir y recargar fallidas
- [ ] Verificar en "Listar Órdenes"
- [ ] Asignar personal si es necesario

---

## 🚀 Mejores Prácticas

1. **Configurar precios primero**: Antes de cualquier carga masiva, asegurar que todos los clientes tengan precios configurados.

2. **Usar plantilla**: Siempre descargar y usar la plantilla proporcionada para evitar errores.

3. **Probar con pocas órdenes**: Primera vez, cargar 2-3 órdenes para verificar que todo funciona.

4. **Dividir cargas grandes**: Para más de 500 órdenes, dividir en múltiples archivos.

5. **Mantener backups**: Guardar copias de los CSV cargados por si se necesita referenciarlos.

6. **Documentar errores**: Si órdenes fallan repetidamente, documentar para ajustar precios o datos.

---

**Última actualización:** 2026-01-08
**Responsable:** Sistema de Logística - Agrivision
