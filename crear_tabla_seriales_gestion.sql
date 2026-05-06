-- Tabla de seriales individuales desde mayo 2026.
-- Enero-abril 2026 permanece en gestiones_mensajero sin cambios.
-- UNIQUE KEY (serial, tipo_gestion) hace imposible pagar dos veces
-- la misma entrega o devolución del mismo serial.

CREATE TABLE IF NOT EXISTS seriales_gestion (
    id                  INT AUTO_INCREMENT PRIMARY KEY,

    -- Identificación del hecho
    serial              VARCHAR(50)     NOT NULL,
    planilla            VARCHAR(50)     NOT NULL,
    fecha_escaner       DATE            NOT NULL,

    -- Quién y para quién
    cod_men             VARCHAR(4)      NOT NULL,
    mensajero_id        INT             NULL,
    cliente             VARCHAR(100)    NOT NULL,
    cliente_id          INT             NULL,

    -- Tipo de operación
    tipo_gestion        ENUM('Entrega', 'Devolucion') NOT NULL,
    tipo_envio          ENUM('sobre', 'paquete')      NOT NULL DEFAULT 'sobre',
    ambito              ENUM('bogota', 'nacional')    NOT NULL DEFAULT 'bogota',

    -- Precios al momento del registro
    precio_cliente      DECIMAL(10,2)   NOT NULL DEFAULT 0,
    precio_mensajero    DECIMAL(10,2)   NOT NULL DEFAULT 0,

    -- Ciclo de vida: pendiente → liquidado → facturado | anulado | en_revision
    estado              ENUM('pendiente','liquidado','facturado','anulado','en_revision')
                        NOT NULL DEFAULT 'pendiente',

    -- Referencias a documentos (se rellenan al liquidar/facturar)
    liquidacion_id      INT             NULL,
    factura_id          INT             NULL,
    fecha_liquidacion   DATE            NULL,
    fecha_facturacion   DATE            NULL,

    -- Trazabilidad
    origen              ENUM('scanner','imile','manual') NOT NULL DEFAULT 'scanner',
    editado_manualmente BOOLEAN         NOT NULL DEFAULT FALSE,
    observaciones       TEXT            NULL,

    -- Auditoría
    fecha_creacion      TIMESTAMP       NOT NULL DEFAULT CURRENT_TIMESTAMP,
    fecha_modificacion  TIMESTAMP       NOT NULL DEFAULT CURRENT_TIMESTAMP
                        ON UPDATE CURRENT_TIMESTAMP,

    -- Un serial solo puede tener UNA gestión (entrega o devolución, nunca las dos)
    UNIQUE KEY uk_serial        (serial),

    KEY idx_planilla            (planilla),
    KEY idx_cod_men             (cod_men),
    KEY idx_fecha_escaner       (fecha_escaner),
    KEY idx_estado              (estado),
    KEY idx_mensajero_id        (mensajero_id),
    KEY idx_liquidacion_id      (liquidacion_id),
    KEY idx_factura_id          (factura_id)
);
