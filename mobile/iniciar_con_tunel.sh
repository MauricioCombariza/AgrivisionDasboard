#!/bin/bash
# ─────────────────────────────────────────────────────────────
# Inicia Streamlit + túnel Cloudflare con un solo comando
# ─────────────────────────────────────────────────────────────
set -e
cd "$(dirname "$0")"

LOG_CF="/tmp/cloudflared_mobile.log"

cleanup() {
    echo ""
    echo "Cerrando servicios…"
    kill "$STREAMLIT_PID" 2>/dev/null
    kill "$CF_PID"        2>/dev/null
    exit 0
}
trap cleanup INT TERM

# ── 1. Inicia Streamlit en segundo plano ──────────────────────
echo "Iniciando Streamlit…"
/home/mauro/miniconda3/bin/streamlit run home.py &
STREAMLIT_PID=$!
sleep 4

# ── 2. Inicia cloudflared y captura la URL ────────────────────
echo "Abriendo túnel Cloudflare…"
cloudflared tunnel --url http://localhost:8502 > "$LOG_CF" 2>&1 &
CF_PID=$!

# Espera hasta encontrar la URL en el log (máx 15 seg)
URL=""
for i in $(seq 1 15); do
    URL=$(grep -oP 'https://[a-z0-9\-]+\.trycloudflare\.com' "$LOG_CF" 2>/dev/null | head -1)
    [ -n "$URL" ] && break
    sleep 1
done

# ── 3. Muestra la URL de forma destacada ─────────────────────
echo ""
echo "╔══════════════════════════════════════════════════════════════╗"
if [ -n "$URL" ]; then
    echo "║  ✅ App lista. Abre esta URL en tu celular:                  ║"
    printf  "║  %-60s  ║\n" "$URL"
else
    echo "║  ⚠️  No se pudo obtener la URL. Revisa la salida de cloudflared ║"
fi
echo "║                                                              ║"
echo "║  Presiona Ctrl+C para apagar el servidor.                    ║"
echo "╚══════════════════════════════════════════════════════════════╝"
echo ""

# Muestra QR si qrencode está disponible
if [ -n "$URL" ] && command -v qrencode &>/dev/null; then
    echo "Escanea el QR con tu celular:"
    qrencode -t ansiutf8 "$URL"
    echo ""
fi

# ── 4. Mantiene vivo hasta Ctrl+C ────────────────────────────
wait "$STREAMLIT_PID"
