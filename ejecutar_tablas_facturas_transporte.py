"""
Script para crear las tablas de facturas de transporte
Ejecutar una sola vez
"""
import mysql.connector
import os
from dotenv import load_dotenv

load_dotenv()

def crear_tablas():
    try:
        conn = mysql.connector.connect(
            host=os.environ.get("DB_HOST", "localhost"),
            user=os.environ.get("DB_USER", "root"),
            password=os.environ.get("DB_PASSWORD", ""),
            database=os.environ.get("DB_NAME_LOGISTICA", "logistica")
        )
        cursor = conn.cursor()

        # Crear tabla facturas_transporte
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS facturas_transporte (
                id INT AUTO_INCREMENT PRIMARY KEY,
                numero_factura VARCHAR(50) NOT NULL COMMENT 'Numero alfanumerico de la factura',
                fecha_factura DATE NOT NULL,
                courrier_id INT NOT NULL COMMENT 'ID del courrier/transportadora en tabla personal',
                monto_total DECIMAL(12, 2) NOT NULL COMMENT 'Monto total de la factura',
                total_sobres INT DEFAULT 0 COMMENT 'Total de sobres en la factura',
                estado ENUM('pendiente', 'pagada', 'anulada') DEFAULT 'pendiente',
                observaciones TEXT,
                fecha_creacion TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                fecha_modificacion TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,

                FOREIGN KEY (courrier_id) REFERENCES personal(id),
                UNIQUE KEY uk_factura_courrier (numero_factura, courrier_id),
                INDEX idx_fecha (fecha_factura),
                INDEX idx_courrier (courrier_id),
                INDEX idx_estado (estado)
            ) ENGINE=InnoDB
        """)
        print("Tabla facturas_transporte creada")

        # Crear tabla detalle_facturas_transporte
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS detalle_facturas_transporte (
                id INT AUTO_INCREMENT PRIMARY KEY,
                factura_id INT NOT NULL,
                orden_id INT NOT NULL COMMENT 'Orden asociada',
                cantidad_sobres INT NOT NULL COMMENT 'Cantidad de sobres de esta orden',
                costo_asignado DECIMAL(12, 2) NOT NULL COMMENT 'Costo proporcional asignado',
                fecha_creacion TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

                FOREIGN KEY (factura_id) REFERENCES facturas_transporte(id) ON DELETE CASCADE,
                FOREIGN KEY (orden_id) REFERENCES ordenes(id),
                UNIQUE KEY uk_factura_orden (factura_id, orden_id),
                INDEX idx_orden (orden_id)
            ) ENGINE=InnoDB
        """)
        print("Tabla detalle_facturas_transporte creada")

        conn.commit()
        print("\nTablas creadas exitosamente!")

    except Exception as e:
        print(f"Error: {e}")
    finally:
        if conn.is_connected():
            cursor.close()
            conn.close()

if __name__ == "__main__":
    crear_tablas()
