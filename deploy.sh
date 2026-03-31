#!/bin/bash
# deploy.sh — Actualización de producción BLMP
# Uso: bash deploy.sh [--skip-pip] [--restart-nginx]

set -euo pipefail

# ── Configuración ──────────────────────────────────────────────
PROJECT_ROOT="$HOME/proyectos/catalogacion-musical"
APP_DIR="$PROJECT_ROOT"
VENV="$HOME/.virtualenvs/blmp_env"
PYTHON="$VENV/bin/python"
PIP="$VENV/bin/pip"
SERVICE="blmp_web"
BRANCH="main"

# ── Colores ────────────────────────────────────────────────────
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

log()     { echo -e "${GREEN}[deploy]${NC} $1"; }
warn()    { echo -e "${YELLOW}[warn]${NC}   $1"; }
error()   { echo -e "${RED}[error]${NC}  $1"; exit 1; }

# ── Opciones ───────────────────────────────────────────────────
SKIP_PIP=false
RESTART_NGINX=false

for arg in "$@"; do
  case $arg in
    --skip-pip)        SKIP_PIP=true ;;
    --restart-nginx)   RESTART_NGINX=true ;;
    *) warn "Argumento desconocido: $arg" ;;
  esac
done

# ── Verificaciones previas ─────────────────────────────────────
[[ -d "$PROJECT_ROOT" ]] || error "Directorio del proyecto no encontrado: $PROJECT_ROOT"
[[ -d "$VENV" ]]         || error "Entorno virtual no encontrado: $VENV"
[[ -f "$APP_DIR/manage.py" ]] || error "manage.py no encontrado en $APP_DIR"

# ── 1. Git pull ────────────────────────────────────────────────
log "Actualizando código desde $BRANCH..."
cd "$PROJECT_ROOT"
git fetch origin
LOCAL=$(git rev-parse HEAD)
REMOTE=$(git rev-parse "origin/$BRANCH")

if [[ "$LOCAL" == "$REMOTE" ]]; then
  warn "Sin cambios nuevos en $BRANCH. Continuando de todas formas..."
else
  git pull origin "$BRANCH"
  log "Código actualizado: $(git log -1 --oneline)"
fi

# ── 2. Dependencias ────────────────────────────────────────────
cd "$APP_DIR"

if [[ "$SKIP_PIP" == false ]]; then
  log "Instalando dependencias Python..."
  $PIP install -r requirements.txt --quiet
else
  warn "Saltando pip install (--skip-pip)"
fi

# ── 3. Migraciones ─────────────────────────────────────────────
log "Aplicando migraciones..."
$PYTHON manage.py migrate --noinput

# ── 4. Archivos estáticos ──────────────────────────────────────
log "Recolectando archivos estáticos..."
$PYTHON manage.py collectstatic --noinput --clear

# ── 5. Verificar configuración Django ─────────────────────────
log "Verificando configuración..."
$PYTHON manage.py check --deploy 2>&1 || true

# ── 6. Reiniciar servicio ──────────────────────────────────────
# Restart completo para que todos los workers carguen el nuevo manifest
# de ManifestStaticFilesStorage y sirvan los hashes nuevos de los estáticos.
log "Reiniciando servicio $SERVICE..."
if sudo systemctl restart "$SERVICE" 2>/dev/null; then
  log "Gunicorn reiniciado (systemctl sudo)."
elif systemctl --user restart "$SERVICE" 2>/dev/null; then
  log "Gunicorn reiniciado (systemctl --user)."
else
  warn "systemctl falló — intentando con HUP como último recurso..."
  kill -HUP $(pgrep -f blmp_web_gunicorn) 2>/dev/null || true
fi
sleep 5

# Verificar que levantó correctamente
if systemctl --user is-active --quiet "$SERVICE" 2>/dev/null || pgrep -f blmp_web_gunicorn > /dev/null; then
  log "Gunicorn activo."
else
  error "Gunicorn no está corriendo. Ver: tail -50 /var/log/blmp/gunicorn_web_error.log"
fi

# ── Resumen ────────────────────────────────────────────────────
echo ""
log "Deploy completado exitosamente."
log "Commit activo: $(git -C $PROJECT_ROOT log -1 --oneline)"
log "Sitio: https://blmp.unl.edu.ec/"
