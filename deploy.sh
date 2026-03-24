#!/bin/bash
# Uso: ./deploy.sh "mensaje del commit"
MSG="${1:-update}"
git add -A
git commit -m "$MSG" 2>/dev/null || true
git push origin main
echo "Push listo. El VPS se actualizará en menos de 1 minuto."
