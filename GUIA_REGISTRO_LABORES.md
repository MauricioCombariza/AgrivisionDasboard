# Guía de Uso - Registro de Labores

**Página:** 6_Registro_Labores.py
**Ubicación:** Sistema de Logística > Registro de Labores
**Versión:** 1.0 - 2026-01-08

---

## 📋 Descripción General

Nueva página para registrar las horas de alistamiento y labores del personal de manera eficiente y organizada.

---

## 🎯 Funcionalidades Principales

### 1. **⏰ Registro de Horas de Alistamiento**

Permite registrar las horas trabajadas por el personal de alistamiento en diferentes órdenes.

#### Flujo de Uso:

**Paso 1: Identificar al Personal**
- Ingresar el código de 4 dígitos del personal
- El sistema muestra automáticamente:
  - ✅ Nombre completo
  - ✅ Número de cédula
  - ✅ Tipo de personal

**Paso 2: Configurar la Labor**
- Seleccionar fecha de la labor
- Elegir tipo de trabajo:
  - Alistamiento de Sobres
  - Alistamiento de Paquetes

**Paso 3: Registrar Órdenes Trabajadas**
- Seleccionar cuántas órdenes diferentes trabajó (1-5)
- Por cada orden:
  - Seleccionar la orden desde el dropdown
  - Ingresar horas trabajadas (acepta decimales: 8.5 = 8h 30min)
  - El sistema muestra la tarifa por hora vigente
- Agregar observaciones (opcional)

**Paso 4: Guardar**
- Clic en "💾 Guardar Registro de Horas"
- El sistema:
  - ✅ Guarda todos los registros
  - ✅ Muestra los consecutivos generados
  - ✅ Limpia el formulario automáticamente
  - ✅ Muestra el último consecutivo guardado

#### Ejemplo de Uso:

```
Personal: 0025 → Juan Pérez (CC: 123456789)
Fecha: 08/01/2026
Tipo: Alistamiento de Sobres

Órdenes trabajadas:
  Orden #1: 12345 - Cliente A → 4.5 horas ($10,000/hora)
  Orden #2: 12346 - Cliente B → 3.0 horas ($10,000/hora)

Total a pagar: $75,000
Consecutivos generados: #145, #146
```

---

### 2. **🔧 Registro de Labores**

Permite registrar labores específicas como pegado de guías y transportes.

#### Flujo de Uso:

**Paso 1: Identificar al Personal**
- Ingresar el código de 4 dígitos
- Ver información completa del personal

**Paso 2: Configurar la Labor**
- Seleccionar fecha de la labor
- Elegir tipo de labor:
  - **Pegado de Guías** - Por cada guía pegada
  - **Transporte Completo** - Viaje completo
  - **Medio Transporte** - Medio viaje

**Paso 3: Detalles de la Labor**
- Seleccionar la orden trabajada
- Ingresar cantidad ejecutada:
  - Para pegado: Número de guías
  - Para transporte: Número de viajes
- El sistema calcula automáticamente:
  - ✅ Tarifa unitaria vigente
  - ✅ Total a pagar

**Paso 4: Guardar**
- Clic en "💾 Guardar Labor"
- El sistema:
  - ✅ Guarda el registro
  - ✅ Muestra el consecutivo generado
  - ✅ Limpia el formulario automáticamente
  - ✅ Listo para el siguiente registro

#### Ejemplo de Uso:

```
Personal: 0030 → María García (CC: 987654321)
Fecha: 08/01/2026
Tipo: Pegado de Guías

Orden: 12345 - Distribuidora XYZ
Cantidad: 150 guías
Tarifa: $300/guía

Total: $45,000
Consecutivo generado: #89
```

---

### 3. **🏢 Labores Administrativas**

Permite registrar labores generales que no están asociadas a órdenes específicas y que se cargan a costos administrativos internos.

#### Flujo de Uso:

**Paso 1: Identificar al Personal**
- Ingresar el código de 4 dígitos del personal
- El sistema muestra automáticamente:
  - ✅ Nombre completo
  - ✅ Número de cédula
  - ✅ Tipo de personal

**Paso 2: Configurar la Labor Administrativa**
- Seleccionar fecha de la labor
- Elegir tipo de labor administrativa:
  - **Cortar Hojas** - Corte y preparación de papelería
  - **Organización de Zona de Trabajo** - Ordenar y organizar el área
  - **Limpieza del Área** - Limpieza general de espacios
  - **Mantenimiento de Equipos** - Mantenimiento preventivo/correctivo
  - **Archivo de Documentos** - Organización de documentación
  - **Otros Administrativos** - Otras tareas administrativas generales

**Paso 3: Detalles de la Labor**
- Ingresar horas trabajadas (acepta decimales: 2.5 = 2h 30min)
- El sistema muestra la tarifa por hora vigente
- Escribir descripción detallada de la labor (mínimo 10 caracteres)
- El sistema calcula automáticamente:
  - ✅ Tarifa por hora (misma que alistamiento)
  - ✅ Total a pagar

**Paso 4: Guardar**
- Clic en "💾 Guardar Labor Administrativa"
- El sistema:
  - ✅ Guarda el registro
  - ✅ Muestra el consecutivo generado
  - ✅ Limpia el formulario automáticamente
  - ✅ Listo para el siguiente registro

#### Ejemplo de Uso:

```
Personal: 0025 → Juan Pérez (CC: 123456789)
Fecha: 08/01/2026
Tipo: Organización de Zona de Trabajo

Horas trabajadas: 3.5 horas
Tarifa: $10,000/hora
Descripción: Reorganización del área de alistamiento,
             etiquetado de estanterías y separación de
             materiales por tipo de servicio

Total: $35,000
Consecutivo generado: #201
```

#### Características Especiales:

- **No requiere orden asociada**: Estas labores son generales y no se vinculan a órdenes específicas
- **Costos administrativos**: Se registran como costos internos de administración
- **Mismo consecutivo**: Los registros se guardan en la misma tabla de horas pero con identificador [ADMIN]
- **Descripción obligatoria**: Se requiere descripción detallada para auditoría

---

### 4. **📊 Consultar Registros**

Permite consultar y revisar los registros históricos.

#### Opciones de Consulta:

**Filtros Disponibles:**
- Tipo de registro:
  - Horas de Alistamiento
  - Labores
  - Labores Administrativas
- Rango de fechas (desde - hasta)

**Información Mostrada:**

**Para Horas de Alistamiento:**
- Consecutivo
- Código del personal
- Nombre completo
- Número de orden
- Fecha
- Horas trabajadas
- Tarifa por hora
- Total
- Tipo de trabajo
- Estado de aprobación
- Fecha de creación

**Para Labores:**
- Consecutivo
- Código del personal
- Nombre completo
- Número de orden
- Fecha
- Tipo de labor
- Cantidad ejecutada
- Tarifa unitaria
- Total
- Estado de aprobación
- Fecha de creación

**Para Labores Administrativas:**
- Consecutivo
- Código del personal
- Nombre completo
- Fecha
- Horas trabajadas
- Tarifa por hora
- Total
- Tipo de labor (cortar hojas, organización, etc.)
- Descripción de la labor
- Estado de aprobación
- Fecha de creación

**Métricas Resumidas:**
- Total de registros
- Total de horas/cantidad
- Valor total a pagar

---

## 💡 Características Especiales

### ✅ Limpieza Automática de Formularios

Después de cada guardado exitoso:
- ✨ Los campos vuelven a 0/vacío
- ✨ Listo para ingresar el siguiente registro
- ✨ No necesitas refrescar la página

### 🔢 Consecutivos Visibles

- Cada registro genera un **ID único** (autonumérico)
- Se muestra en verde después de guardar
- Útil para seguimiento y auditoría

### 🎨 Interfaz Amigable

- **Búsqueda rápida** por código
- **Información automática** del personal
- **Cálculos automáticos** de totales
- **Validaciones en tiempo real**
- **Mensajes claros** de éxito/error

### 🔐 Seguridad y Validaciones

- ✅ Valida que el personal exista y esté activo
- ✅ Solo permite órdenes activas
- ✅ Valida rangos de horas (0-24)
- ✅ Verifica cantidades mínimas
- ✅ Obtiene tarifas vigentes automáticamente

---

## 📊 Integración con el Sistema

### Relación con Otras Tablas:

**registro_horas:**
- Se vincula a: `personal`, `ordenes`, `tarifas_servicios`
- Alimenta: `liquidaciones` (cuando se aprueba)
- Estado inicial: `aprobado = FALSE`

**registro_labores:**
- Se vincula a: `personal`, `ordenes`, `tarifas_servicios`
- Alimenta: `liquidaciones` (cuando se aprueba)
- Estado inicial: `aprobado = FALSE`

### Flujo de Aprobación:

```
1. Registro → aprobado = FALSE (registro normal)
2. Supervisor revisa → Aprueba
3. Sistema marca → aprobado = TRUE
4. Proceso de liquidación → Incluye en nómina
5. Pago realizado → liquidado = TRUE
```

---

## 🎯 Casos de Uso

### Caso 1: Personal de Alistamiento

**Escenario:** Juan trabajó 8 horas alistando 3 órdenes diferentes

**Proceso:**
1. Ingresar código: 0025
2. Fecha: Hoy
3. Tipo: Alistamiento de Sobres
4. Órdenes trabajadas: 3
   - Orden 12345: 3 horas
   - Orden 12346: 3 horas
   - Orden 12347: 2 horas
5. Guardar → Genera 3 consecutivos (uno por orden)

**Resultado:**
- 3 registros en `registro_horas`
- Total: 8 horas × $10,000 = $80,000
- Consecutivos: #150, #151, #152

### Caso 2: Personal de Pegado

**Escenario:** María pegó 200 guías en una orden

**Proceso:**
1. Ingresar código: 0030
2. Fecha: Hoy
3. Tipo: Pegado de Guías
4. Orden: 12345
5. Cantidad: 200
6. Guardar → Genera 1 consecutivo

**Resultado:**
- 1 registro en `registro_labores`
- Total: 200 × $300 = $60,000
- Consecutivo: #95

### Caso 3: Conductor - Transporte

**Escenario:** Carlos hizo 2 viajes completos

**Proceso:**
1. Ingresar código: 0040
2. Fecha: Hoy
3. Tipo: Transporte Completo
4. Orden: 12345
5. Cantidad: 2
6. Guardar → Genera 1 consecutivo

**Resultado:**
- 1 registro en `registro_labores`
- Total: 2 × $50,000 = $100,000
- Consecutivo: #120

### Caso 4: Labor Administrativa

**Escenario:** Ana dedicó tiempo a organizar el área de trabajo y cortar hojas

**Proceso:**
1. Ingresar código: 0025
2. Fecha: Hoy
3. Ir a pestaña "Labores Administrativas"
4. Tipo: Organización de Zona de Trabajo
5. Horas trabajadas: 2.5
6. Descripción: Reorganización de estanterías, limpieza de área de alistamiento
7. Guardar → Genera 1 consecutivo

**Resultado:**
- 1 registro en `registro_horas` (con orden_id NULL)
- Total: 2.5 × $10,000 = $25,000
- Consecutivo: #201
- Marcado como [ADMIN] para identificación

---

## 📝 Notas Importantes

1. **Tarifas Automáticas:**
   - Las tarifas se obtienen de `tarifas_servicios`
   - Se usa la tarifa vigente más reciente
   - Si no hay tarifa configurada, muestra $0

2. **Múltiples Registros:**
   - En horas: Puede trabajar hasta 5 órdenes diferentes
   - En labores: Un registro por labor (pero puede agregar varios seguidos)

3. **Formato de Horas:**
   - Acepta decimales: 8.5, 4.25, 1.75
   - Máximo 24 horas por registro

4. **Estados de Aprobación:**
   - Todos los registros inician como **NO aprobados**
   - Requieren aprobación de supervisor
   - Solo los aprobados se incluyen en liquidación

5. **Consultas:**
   - Limitadas a 100 registros por consulta
   - Ordenadas por fecha de creación (más recientes primero)
   - Exportables a Excel (función de Streamlit)

6. **Labores Administrativas:**
   - No requieren orden asociada (orden_id = NULL)
   - Se identifican con prefijo [ADMIN] en observaciones
   - Usan la misma tarifa que el alistamiento por hora
   - Requieren descripción detallada obligatoria
   - Se cargan a costos administrativos internos
   - Siguen el mismo flujo de aprobación

---

## 🔧 Mantenimiento

### Configurar Tarifas:

Las tarifas se configuran en la tabla `tarifas_servicios`:

```sql
-- Ejemplos de tarifas
tipo_servicio = 'alistamiento_hora'       → $10,000/hora
tipo_servicio = 'pegado_guia'             → $300/guía
tipo_servicio = 'transporte_completo'     → $50,000/viaje
tipo_servicio = 'medio_transporte'        → $25,000/medio viaje
```

Para actualizar tarifas, usar el sistema de gestión o SQL directo.

---

## ✅ Checklist de Uso Diario

**Registro de Horas:**
- [ ] Código del personal (4 dígitos)
- [ ] Verificar nombre y cédula
- [ ] Fecha de la labor
- [ ] Tipo de trabajo
- [ ] Órdenes trabajadas (1-5)
- [ ] Horas por cada orden
- [ ] Observaciones (opcional)
- [ ] Guardar → Anotar consecutivos

**Registro de Labores:**
- [ ] Código del personal
- [ ] Verificar información
- [ ] Fecha de la labor
- [ ] Tipo de labor
- [ ] Orden trabajada
- [ ] Cantidad ejecutada
- [ ] Verificar total calculado
- [ ] Guardar → Anotar consecutivo

**Labores Administrativas:**
- [ ] Código del personal (4 dígitos)
- [ ] Verificar nombre y cédula
- [ ] Fecha de la labor
- [ ] Tipo de labor administrativa
- [ ] Horas trabajadas
- [ ] Descripción detallada (mínimo 10 caracteres)
- [ ] Verificar tarifa y total
- [ ] Guardar → Anotar consecutivo

---

## 🎓 Preguntas Frecuentes

**P: ¿Puedo registrar horas de días anteriores?**
R: Sí, puedes seleccionar cualquier fecha en el campo "Fecha de la Labor"

**P: ¿Qué pasa si me equivoco en un registro?**
R: Contacta al supervisor para que elimine/edite el registro antes de la aprobación

**P: ¿Dónde veo mi total acumulado del mes?**
R: En la pestaña "Consultar Registros" con el rango del mes

**P: ¿Cuándo se me paga?**
R: Los registros se pagan en la liquidación mensual (día 8) después de ser aprobados

**P: ¿Puedo trabajar en órdenes de diferentes clientes?**
R: Sí, puedes agregar hasta 5 órdenes diferentes en un mismo registro

**P: ¿Qué son las labores administrativas?**
R: Son tareas generales que no están vinculadas a órdenes específicas (cortar hojas, organizar, limpieza, etc.). Se registran en la pestaña "Labores Administrativas" y se cargan a costos internos

**P: ¿Por qué no veo mis labores administrativas en el reporte de horas?**
R: Las labores administrativas tienen su propia categoría en "Consultar Registros". Selecciona "Labores Administrativas" en el tipo de consulta

---

## 🚀 Próximas Mejoras

Funcionalidades planeadas:
- [ ] Exportar registros a Excel
- [ ] Notificaciones de registros pendientes de aprobación
- [ ] Dashboard de productividad personal
- [ ] Firma digital del personal
- [ ] Integración con app móvil

---

**Última actualización:** 2026-01-08
**Responsable:** Sistema de Logística - Agrivision
