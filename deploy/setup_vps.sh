#!/bin/bash
# Script de configuración del VPS Hetzner
# Ejecutar como root: bash setup_vps.sh

set -e

echo "=== 1. Actualizar sistema ==="
apt update && apt upgrade -y
apt install -y git caddy

echo "=== 2. Instalar MySQL ==="
apt install -y mysql-server
systemctl enable mysql
systemctl start mysql

echo "=== 3. Instalar Miniconda ==="
wget -q https://repo.anaconda.com/miniconda/Miniconda3-latest-Linux-x86_64.sh -O /tmp/miniconda.sh
bash /tmp/miniconda.sh -b -p /root/miniconda3
/root/miniconda3/bin/conda init bash
source /root/.bashrc

echo "=== 4. Crear entorno Python ==="
/root/miniconda3/bin/conda create -n carvajal python=3.12 -y
source /root/miniconda3/bin/activate carvajal

echo "=== 5. Instalar dependencias ==="
pip install streamlit pandas mysql-connector-python openpyxl pillow numpy \
    python-dotenv streamlit-authenticator pyyaml bcrypt

echo "=== 6. Copiar código ==="
# Opción A: clonar desde git
# git clone https://github.com/TU_USUARIO/TU_REPO.git /opt/carvajal

# Opción B: ya copiado con scp
# scp -r /ruta/local/dashboard root@IP_VPS:/opt/carvajal

echo "=== 7. Configurar systemd ==="
cp /opt/carvajal/deploy/carvajal.service /etc/systemd/system/
systemctl daemon-reload
systemctl enable carvajal
systemctl start carvajal

echo "=== 8. Configurar Caddy ==="
cp /opt/carvajal/deploy/Caddyfile /etc/caddy/Caddyfile
systemctl reload caddy

echo ""
echo "=== LISTO ==="
echo "Recuerda:"
echo "  1. Apuntar DNS de www.servilla.com.co a esta IP"
echo "  2. Crear /opt/carvajal/.env con las credenciales de MySQL"
echo "  3. Crear /opt/carvajal/auth/users.yaml con los usuarios"
echo "  4. Importar las bases de datos:"
echo "     mysql -u root < imile.sql"
echo "     mysql -u root < logistica.sql"
