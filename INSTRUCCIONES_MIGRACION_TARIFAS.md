# Instrucciones de Migración - Sistema de Tarifas Diferenciadas

**Fecha:** 2026-01-07
**Versión:** 1.0

---

## Resumen de Cambios

Se ha ajustado el sistema logístico para implementar la siguiente lógica de negocio:

### Ámbito LOCAL (Bogotá):
- **Lo que paga el mensajero:** Depende del **CLIENTE**
- Cada cliente define cuánto se le paga al mensajero por entrega y por devolución
- Configuración en: **Clientes > Precios** con campos adicionales

### Ámbito NACIONAL:
- **Lo que paga el courier:** Depende del **COURIER** específico
- Cada courier tiene su propia negociación por ciudad destino
- Diferenciación por tipo de servicio (sobre/paquete)
- Configuración en: **Personal > Tarifas por Ciudad**

---

## Paso 1: Ejecutar Migración de Base de Datos

### Opción A: Migración automática (RECOMENDADA)

```bash
cd /mnt/c/Users/mcomb/Desktop/Carvajal/python/dashboard
mysql -u root -p logistica < migracion_tarifas_logistica.sql
```

**Ingrese la contraseña cuando se solicite:** `Vale2010`

### Opción B: Migración manual desde MySQL Workbench

1. Abrir MySQL Workbench
2. Conectar a la base de datos `logistica`
3. Abrir el archivo `migracion_tarifas_logistica.sql`
4. Ejecutar todo el script (clic en el rayo ⚡)

### Verificar que la migración fue exitosa:

```sql
-- Verificar estructura de precios_cliente
DESCRIBE precios_cliente;
-- Debe incluir: costo_mensajero_entrega, costo_mensajero_devolucion

-- Verificar estructura de personal_ciudades
DESCRIBE personal_ciudades;
-- Debe incluir: tipo_servicio

-- Verificar estructura de orden_personal
DESCRIBE orden_personal;
-- Debe incluir: tarifa_entrega, tarifa_devolucion (NO tarifa_unitaria)
```

---

## Paso 2: Configurar Tarifas de Mensajeros (Ámbito Local)

### Navegación: Clientes > Gestión de Precios

1. Seleccionar un cliente
2. Clic en **"Agregar Nuevo Precio"**
3. Configurar:
   - **Tipo Servicio:** sobre / paquete
   - **Ámbito:** **bogota**
   - **Tipo:** entrega / devolucion
   - **Precio al Cliente:** Lo que cobra al cliente
   - **Costo Mensajero:** ⭐ **NUEVO** - Lo que se le paga al mensajero

4. Guardar

### Ejemplo de configuración:

| Cliente | Tipo | Ámbito | Operación | Precio Cliente | Costo Mensajero |
|---------|------|--------|-----------|----------------|----------------|
| Empresa A | sobre | bogota | entrega | $8.000 | $2.500 |
| Empresa A | sobre | bogota | devolucion | $5.000 | $1.500 |
| Empresa A | paquete | bogota | entrega | $12.000 | $4.000 |
| Empresa A | paquete | bogota | devolucion | $8.000 | $3.000 |

---

## Paso 3: Configurar Tarifas de Couriers (Ámbito Nacional)

### Navegación: Personal > Tarifas por Ciudad

1. Seleccionar un courier (tipo: courier_externo o transportadora)
2. Clic en **"Agregar Ciudad"**
3. Configurar:
   - **Ciudad:** Ciudad destino
   - **Tipo Servicio:** ⭐ **NUEVO** - sobre / paquete
   - **Tarifa Entrega:** Lo que se le paga por entrega
   - **Tarifa Devolución:** Lo que se le paga por devolución
   - **Vigencia:** Desde - Hasta

4. Guardar

### Ejemplo de configuración:

**Courier: INTERRAPIDÍSIMO (Nacional)**

| Ciudad | Tipo Servicio | Tarifa Entrega | Tarifa Devolución |
|--------|---------------|----------------|-------------------|
| Medellín | sobre | $8.000 | $6.000 |
| Medellín | paquete | $15.000 | $12.000 |
| Cali | sobre | $9.000 | $7.000 |
| Cali | paquete | $18.000 | $14.000 |

---

## Paso 4: Asignar Personal a Órdenes (MEJORADO)

### Navegación: Órdenes > Asignar Personal

Ahora el sistema **busca automáticamente** las tarifas:

### Caso 1: Asignar Mensajero Local
1. Seleccionar orden
2. Seleccionar mensajero
3. ⭐ **AUTOMÁTICO:** El sistema busca las tarifas del cliente y las pre-carga
4. Revisar y ajustar si es necesario
5. Guardar asignación

### Caso 2: Asignar Courier Nacional
1. Seleccionar orden
2. Seleccionar courier
3. ⭐ **AUTOMÁTICO:** El sistema busca las tarifas del courier según:
   - Ciudad destino de la orden
   - Tipo de servicio (sobre/paquete)
4. Revisar y ajustar si es necesario
5. Guardar asignación

---

## Paso 5: Registrar Entregas y Devoluciones (MEJORADO)

### Navegación: Órdenes > Actualizar Estado > Registrar Entrega/Devolución

Ahora se debe especificar QUÉ personal realizó las entregas:

1. Seleccionar orden
2. Elegir acción: **"Registrar Entrega/Devolución"**
3. ⭐ **NUEVO:** Seleccionar el personal que realizó las entregas
4. Ingresar cantidades:
   - Cantidad Entregados
   - Cantidad Devolución
5. Confirmar

**El sistema actualiza automáticamente:**
- Contadores en la orden (para seguimiento)
- Contadores en `orden_personal` (para cálculo de pago)
- El campo `total_pagar` se calcula automáticamente:
  ```
  total_pagar = (cantidad_entregada * tarifa_entrega) +
                (cantidad_devolucion * tarifa_devolucion)
  ```

---

## Paso 6: Verificar Pagos

### Ver pagos calculados:

**Navegación: Órdenes > Asignar Personal > Ver Personal Asignado**

La tabla muestra:
- Código y nombre del personal
- Cantidad asignada
- **Tarifa Entrega** ⭐
- **Tarifa Devolución** ⭐
- Cantidad entregada
- Cantidad devolución
- **Total a Pagar** (calculado automáticamente)

---

## Flujo Completo de Ejemplo

### Escenario: Orden para Cliente "Distribuidora XYZ"

**Datos de la orden:**
- Cliente: Distribuidora XYZ
- Tipo: Paquete
- Ciudad destino: Medellín
- Cantidad: 100 items

### 1. Configurar Precios del Cliente (solo primera vez)
```
Distribuidora XYZ - Paquete - Bogotá - Entrega
  Precio Cliente: $10.000
  Costo Mensajero: $3.500

Distribuidora XYZ - Paquete - Bogotá - Devolución
  Precio Cliente: $7.000
  Costo Mensajero: $2.500
```

### 2. Crear Orden
- Crear orden #12345 con 100 paquetes
- Precio unitario cliente: $10.000
- Valor total orden: $1.000.000

### 3. Asignar Personal

**Caso A: 60 items para mensajero local (Bogotá)**
- Seleccionar mensajero: 0025 - Juan Pérez
- Cantidad asignada: 60
- **Sistema carga automáticamente:**
  - Tarifa Entrega: $3.500 (desde precios_cliente)
  - Tarifa Devolución: $2.500 (desde precios_cliente)

**Caso B: 40 items para courier nacional (Medellín)**
- Seleccionar courier: 0100 - INTERRAPIDÍSIMO
- Cantidad asignada: 40
- **Sistema carga automáticamente:**
  - Tarifa Entrega: $15.000 (desde personal_ciudades)
  - Tarifa Devolución: $12.000 (desde personal_ciudades)

### 4. Registrar Resultados

**Juan Pérez (mensajero local):**
- Seleccionar: Juan Pérez
- Entregados: 55
- Devolución: 5
- **Pago calculado:** (55 × $3.500) + (5 × $2.500) = $205.000

**INTERRAPIDÍSIMO (courier nacional):**
- Seleccionar: INTERRAPIDÍSIMO
- Entregados: 38
- Devolución: 2
- **Pago calculado:** (38 × $15.000) + (2 × $12.000) = $594.000

**Total costos mensajería:** $205.000 + $594.000 = $799.000
**Ingreso cliente:** $1.000.000
**Margen:** $201.000 (20.1%)

---

## Diferencias con el Sistema Anterior

| Aspecto | ANTES | AHORA |
|---------|-------|-------|
| **Tarifa mensajero local** | Manual por asignación | Automática desde cliente |
| **Tarifa courier nacional** | Manual por asignación | Automática desde courier + ciudad |
| **Diferencia entrega/devolución** | Una sola tarifa | Dos tarifas independientes |
| **Tipo servicio (sobre/paquete)** | Solo en orden | También en courier nacional |
| **Registro entregas** | Solo contadores orden | Orden + Personal para pago |
| **Cálculo pago** | Simplificado | Exacto por tipo operación |

---

## Archivos Modificados

### SQL:
- ✅ `migracion_tarifas_logistica.sql` - Migración de base de datos
- ✅ `actualizar_schema_completo.sql` - Documentación de cambios

### Streamlit:
- ✅ `pages/1_Clientes_Precios.py` - Agregar costos de mensajero
- ✅ `pages/2_Personal.py` - Agregar tipo_servicio en tarifas
- ✅ `pages/3_Ordenes.py` - Asignación automática y registro mejorado

---

## Soporte y Resolución de Problemas

### Error: "Column 'costo_mensajero_entrega' doesn't exist"
**Solución:** Ejecutar el script de migración SQL

### Error: "Duplicate entry for key 'uk_personal_ciudad_servicio'"
**Solución:** Ya existe una tarifa para esa combinación courier + ciudad + tipo_servicio. Eliminar la anterior o editar.

### Las tarifas no se cargan automáticamente
**Verificar:**
1. Que las tarifas estén configuradas (Clientes o Personal según corresponda)
2. Que las fechas de vigencia incluyan la fecha actual
3. Que los registros estén marcados como `activo = TRUE`

### Consulta SQL para verificar tarifas:

```sql
-- Ver tarifas de mensajero por cliente
SELECT c.nombre_empresa, pc.tipo_servicio, pc.ambito, pc.tipo_operacion,
       pc.precio_unitario, pc.costo_mensajero_entrega, pc.costo_mensajero_devolucion
FROM precios_cliente pc
JOIN clientes c ON pc.cliente_id = c.id
WHERE pc.activo = TRUE
  AND pc.ambito = 'bogota'
ORDER BY c.nombre_empresa, pc.tipo_servicio;

-- Ver tarifas de courier por ciudad
SELECT p.nombre_completo, c.nombre as ciudad, pc.tipo_servicio,
       pc.tarifa_entrega, pc.tarifa_devolucion
FROM personal_ciudades pc
JOIN personal p ON pc.personal_id = p.id
JOIN ciudades c ON pc.ciudad_id = c.id
WHERE pc.activo = TRUE
  AND p.tipo_personal IN ('courier_externo', 'transportadora')
ORDER BY p.nombre_completo, c.nombre, pc.tipo_servicio;
```

---

## Próximos Pasos Recomendados

1. ✅ Ejecutar migración SQL
2. ✅ Configurar tarifas de mensajeros para clientes existentes (Ámbito Bogotá)
3. ✅ Configurar tarifas de couriers para ciudades destino frecuentes
4. ✅ Probar flujo completo con una orden de prueba
5. ✅ Capacitar al equipo en el nuevo flujo
6. ✅ Migrar órdenes activas (ajustar asignaciones si es necesario)

---

**¿Dudas o problemas?** Revisa este documento o consulta el código fuente de los archivos modificados.
