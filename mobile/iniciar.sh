#!/bin/bash
# ─────────────────────────────────────────────────────────────
# Inicia la app móvil (misma WiFi)
# Accede desde el celular en:  http://<IP-de-la-PC>:8502
# ─────────────────────────────────────────────────────────────
set -e
cd "$(dirname "$0")"

# Muestra la IP local
IP=$(ip route get 1 2>/dev/null | awk '{print $7; exit}' || hostname -I | awk '{print $1}')
echo ""
echo "  ╔══════════════════════════════════════════════╗"
echo "  ║  Servidor móvil iniciado                     ║"
echo "  ║                                              ║"
echo "  ║  Misma WiFi:  http://${IP}:8502         ║"
echo "  ╚══════════════════════════════════════════════╝"
echo ""

/home/mauro/miniconda3/bin/streamlit run home.py --server.address=0.0.0.0 --server.port=8502
