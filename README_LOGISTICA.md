# 📦 Sistema de Gestión Logística - Agrivision

## 🚀 Inicio Rápido

### Opción 1: Ejecutar Sistema de Logística

```bash
# Doble clic en el archivo:
INICIAR_LOGISTICA.bat
```

Esto iniciará el sistema en: **http://localhost:8502**

### Opción 2: Ejecutar Sistema de WhatsApp/iMile

```bash
# Doble clic en el archivo:
INICIAR_WHATSAPP.bat
```

Esto iniciará el sistema en: **http://localhost:8501**

---

## ⚙️ Configuración Inicial de Base de Datos

Si es la primera vez que usas el sistema:

```bash
# Ejecutar SOLO UNA VEZ:
INICIALIZAR_BD_LOGISTICA.bat
```

Esto creará:
- Base de datos: `logistica`
- 20 tablas principales
- 4 vistas para reportes
- 15 ciudades pre-cargadas con costos de flete sugeridos

### Credenciales Base de Datos

- **Host**: `localhost`
- **Usuario**: `root`
- **Password**: `Vale2010`
- **Base de datos**: `logistica`

---

## 📊 Estructura de la Base de Datos

### Módulo de Clientes
- `clientes` - Empresas que contratan el servicio
- `precios_cliente` - Tarifas por cliente (sobres/paquetes, entregas/devoluciones, Bogotá/nacional)

### Módulo de Personal
- `personal` - Mensajeros, alistamiento, conductores, couriers externos, transportadoras
  - **Código único**: 4 dígitos (puede empezar con 0)
- `personal_ciudades` - Asignación de personal a ciudades con tarifas

### Módulo de Órdenes
- `ordenes` - Órdenes con **contadores por estado**:
  - `cantidad_recibido`
  - `cantidad_en_cajoneras`
  - `cantidad_en_lleva`
  - `cantidad_entregados`
  - `cantidad_devolucion`
- `orden_personal` - Asignación de mensajeros a órdenes

### Módulo de Servicios Internos
- `tarifas_servicios` - Tarifas de alistamiento, transporte, pegado
- `registro_horas` - Horas de alistamiento por personal
- `registro_labores` - Labores (pegado de guías, transporte)

### Módulo de Liquidaciones
- `liquidaciones` - Pago a personal interno (día 8 de cada mes)

### Módulo de Facturación
- `facturas_emitidas` - Facturas a clientes
- `detalle_facturas_emitidas` - Detalle por orden
- `facturas_recibidas` - Facturas de couriers/transportadoras
- `detalle_facturas_recibidas` - Detalle de costos

### Módulo de Pagos
- `pagos_recibidos` - Pagos de clientes
- `pagos_realizados` - Pagos a personal/couriers

### Otros
- `ciudades` - Ciudades de operación
- `costos_adicionales` - Fletes, materiales
- `auditoria` - Log de cambios

---

## 🔄 Flujo de Trabajo

### 1. Recepción de Orden
```sql
INSERT INTO ordenes (
    numero_orden, cliente_id, ciudad_destino_id,
    fecha_recepcion, tipo_servicio,
    cantidad_total, cantidad_recibido,
    precio_unitario, valor_total
) VALUES (
    'ORD-2025-001', 1, 1,
    '2025-01-05', 'sobre',
    100, 100,  -- 100 sobres recibidos
    2500, 250000
);
```

### 2. Alistamiento
```sql
-- Registrar horas de alistamiento
INSERT INTO registro_horas (
    personal_id, orden_id, fecha,
    horas_trabajadas, tarifa_hora, tipo_trabajo
) VALUES (
    5, 1, '2025-01-05',
    8, 7960.90, 'alistamiento_sobres'
);

-- Mover a cajoneras
UPDATE ordenes SET
    cantidad_recibido = 0,
    cantidad_en_cajoneras = 100
WHERE id = 1;
```

### 3. Asignación a Mensajeros
```sql
-- Asignar a mensajero
INSERT INTO orden_personal (
    orden_id, personal_id, cantidad_asignada,
    tarifa_unitaria, fecha_asignacion
) VALUES (
    1, 3, 100, 1500, '2025-01-06'
);

-- Mover a en lleva
UPDATE ordenes SET
    cantidad_en_cajoneras = 0,
    cantidad_en_lleva = 100
WHERE id = 1;
```

### 4. Finalización
```sql
-- Registrar resultados
UPDATE orden_personal SET
    cantidad_entregada = 85,
    cantidad_devolucion = 15
WHERE id = 1;

-- Actualizar orden
UPDATE ordenes SET
    cantidad_en_lleva = 0,
    cantidad_entregados = 85,
    cantidad_devolucion = 15,
    estado = 'finalizada',
    fecha_finalizacion = '2025-01-08'
WHERE id = 1;
```

### 5. Facturación al Cliente
```sql
-- Crear factura
INSERT INTO facturas_emitidas (
    numero_factura, cliente_id,
    fecha_emision, fecha_vencimiento,
    periodo_mes, periodo_anio,
    cantidad_items, subtotal, total, saldo_pendiente
) VALUES (
    'FACT-2025-001', 1,
    '2025-02-01', '2025-03-03',  -- 30 días plazo
    1, 2025,
    100, 250000, 250000, 250000
);

-- Agregar detalle
INSERT INTO detalle_facturas_emitidas (
    factura_id, orden_id, descripcion,
    cantidad, precio_unitario, subtotal
) VALUES (
    1, 1, 'Distribución sobres - Enero 2025',
    100, 2500, 250000
);
```

### 6. Liquidación a Personal
```sql
-- Generar liquidación (día 8)
INSERT INTO liquidaciones (
    numero_liquidacion, personal_id,
    periodo_mes, periodo_anio,
    fecha_generacion, fecha_pago_programada,
    total_entregas, cantidad_entregas,
    total_horas, cantidad_horas,
    total_a_pagar, estado
) VALUES (
    'LIQ-2025-001-0003', 3,  -- Mensajero código 0003
    1, 2025,
    '2025-02-08', '2025-02-08',
    127500, 85,  -- 85 entregas x 1500
    0, 0,
    127500, 'generada'
);
```

---

## 📈 Vistas de Reportes

### Estado de Órdenes
```sql
SELECT * FROM vista_estado_ordenes
WHERE estado = 'activa';
```

### Rentabilidad por Cliente
```sql
SELECT *
FROM vista_rentabilidad_cliente
ORDER BY utilidad_total DESC;
```

### Cuentas por Cobrar
```sql
SELECT *
FROM vista_cuentas_por_cobrar
WHERE clasificacion = 'VENCIDA';
```

### Cuentas por Pagar
```sql
SELECT *
FROM vista_cuentas_por_pagar
WHERE clasificacion = 'POR VENCER';
```

### Flujo de Caja (60 días)
```sql
SELECT
    periodo,
    tipo,
    SUM(monto) AS total
FROM vista_flujo_caja_60dias
GROUP BY periodo, tipo
ORDER BY
    CASE periodo
        WHEN 'VENCIDO' THEN 1
        WHEN 'ESTA SEMANA' THEN 2
        WHEN 'ESTE MES' THEN 3
        ELSE 4
    END,
    tipo DESC;
```

---

## 💰 Tarifas 2025

| Servicio | Tarifa |
|----------|--------|
| Hora de alistamiento | $7,960.90 |
| Transporte completo | $8,333.33 |
| Medio transporte | $4,166.67 |
| Pegado de guía | $11.54 |

---

## 🔐 Roles de Usuario

1. **Administrador**: Acceso completo
2. **Contabilidad**: Facturación, pagos, reportes financieros
3. **Operaciones**: Órdenes, asignaciones, tracking
4. **Ventas**: Clientes, precios, órdenes

---

## 📞 Próximos Pasos

1. ✅ Base de datos inicializada
2. ⏳ Crear módulos Streamlit para:
   - Gestión de clientes y precios
   - Gestión de personal
   - Registro de órdenes
   - Asignación y tracking
   - Facturación
   - Liquidaciones
   - Dashboards de rentabilidad
   - Flujo de caja

---

## 🛠️ Mantenimiento

### Backup
```bash
mysqldump -u root -p logistica > backup_logistica_$(date +%Y%m%d).sql
```

### Restaurar
```bash
mysql -u root -p logistica < backup_logistica_20250105.sql
```

---

**Desarrollado para Carvajal - Enero 2025**
