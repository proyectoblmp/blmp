#!/bin/bash
# deploy.sh — Actualización de producción BLMP
# Uso: bash deploy.sh [--skip-pip] [--restart-nginx] [--migrate]

set -euo pipefail

# ── Colores ───────────────────────────────────────────────────────────────────
BOLD='\033[1m'
RESET='\033[0m'
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
RED='\033[0;31m'
CYAN='\033[0;36m'
DIM='\033[2m'

ok()   { echo -e "${GREEN}${BOLD}  ✓${RESET}  $*"; }
warn() { echo -e "${YELLOW}${BOLD}  ⚠${RESET}  $*"; }
fail() { echo -e "${RED}${BOLD}  ✗${RESET}  $*" >&2; exit 1; }
step() { echo -e "\n${BOLD}${CYAN}▶ $*${RESET}"; }
dim()  { echo -e "${DIM}    $*${RESET}"; }

# ── Configuración ─────────────────────────────────────────────────────────────
PROJECT_ROOT="$HOME/proyectos/catalogacion-musical"
APP_DIR="$PROJECT_ROOT"
VENV="$HOME/.virtualenvs/blmp_env"
PYTHON="$VENV/bin/python"
PIP="$VENV/bin/pip"
SERVICE="blmp_web"
BRANCH="main"

# ── Opciones ──────────────────────────────────────────────────────────────────
SKIP_PIP=false
RESTART_NGINX=false
MIGRATE=false

for arg in "$@"; do
  case $arg in
    --skip-pip)      SKIP_PIP=true ;;
    --restart-nginx) RESTART_NGINX=true ;;
    --migrate)       MIGRATE=true ;;
    *) warn "Argumento desconocido: $arg" ;;
  esac
done

# Variables para el resumen final
SUMMARY_GIT=""
SUMMARY_COMMIT=""
SUMMARY_MIGRATE=""
SUMMARY_STATIC=""

# ── Verificaciones previas ────────────────────────────────────────────────────
[[ -d "$PROJECT_ROOT" ]] || fail "Directorio del proyecto no encontrado: $PROJECT_ROOT"
[[ -d "$VENV" ]]         || fail "Entorno virtual no encontrado: $VENV"
[[ -f "$APP_DIR/manage.py" ]] || fail "manage.py no encontrado en $APP_DIR"

DEPLOY_START=$(date '+%Y-%m-%d %H:%M:%S')
echo -e "\n${BOLD}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${RESET}"
echo -e "${BOLD}   BLMP — Despliegue  ${DEPLOY_START}${RESET}"
echo -e "${BOLD}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${RESET}"

cd "$PROJECT_ROOT"

# ── 1. Git ────────────────────────────────────────────────────────────────────
step "Actualizando código"
git fetch origin --quiet
BEFORE=$(git rev-parse HEAD)
REMOTE=$(git rev-parse "origin/$BRANCH")

if [[ "$BEFORE" == "$REMOTE" ]]; then
  SUMMARY_GIT="Sin cambios nuevos"
else
  git pull origin "$BRANCH" --quiet
  N=$(git rev-list --count "$BEFORE"..HEAD)
  SUMMARY_GIT="${N} commit(s) nuevos"
fi

LAST_MSG=$(git log -1 --pretty=format:"%s")
LAST_AUTHOR=$(git log -1 --pretty=format:"%an")
LAST_DATE=$(git log -1 --pretty=format:"%cd" --date=format:'%Y-%m-%d %H:%M')
SUMMARY_COMMIT="${LAST_MSG} ${DIM}($(git rev-parse --short HEAD) · ${LAST_AUTHOR} · ${LAST_DATE})${RESET}"
ok "Código listo"

# ── 2. Dependencias ───────────────────────────────────────────────────────────
step "Dependencias"
if [[ "$SKIP_PIP" == false ]]; then
  cd "$APP_DIR"
  $PIP install -r requirements.txt --quiet
  ok "Dependencias OK"
else
  warn "Saltadas (--skip-pip)"
fi

# ── 3. Migraciones ───────────────────────────────────────────────────────────
step "Migraciones"
cd "$APP_DIR"
if $MIGRATE; then
  MIGRATE_OUT=$($PYTHON manage.py migrate --noinput 2>&1)
  APPLIED=$(echo "$MIGRATE_OUT" | grep -c "Applying" || true)
  if [[ "$APPLIED" -gt 0 ]]; then
    SUMMARY_MIGRATE="${APPLIED} migración(es) aplicada(s)"
  else
    SUMMARY_MIGRATE="Sin migraciones pendientes"
  fi
  ok "Migraciones OK"
else
  SUMMARY_MIGRATE="Omitidas (usa --migrate para ejecutarlas)"
  warn "Omitidas — pasa --migrate para ejecutarlas"
fi

# ── 4. Estáticos ──────────────────────────────────────────────────────────────
step "Colectando estáticos"
STATIC_OUT=$($PYTHON manage.py collectstatic --noinput --clear 2>&1)
SUMMARY_STATIC=$(echo "$STATIC_OUT" | grep -E "^[0-9]+ static" | head -1 || echo "OK")
ok "Estáticos listos"

# ── 5. Verificar configuración ────────────────────────────────────────────────
step "Verificando configuración Django"
$PYTHON manage.py check --deploy 2>&1 | grep -E "^System check|ERROR|WARNING" || true
ok "Check OK"

# ── 6. Reiniciar servicio ─────────────────────────────────────────────────────
step "Reiniciando servicio"
if sudo systemctl restart "$SERVICE" 2>/dev/null; then
  dim "Reiniciado vía systemctl sudo"
elif systemctl --user restart "$SERVICE" 2>/dev/null; then
  dim "Reiniciado vía systemctl --user"
else
  warn "systemctl falló — intentando HUP como último recurso..."
  kill -HUP "$(pgrep -f blmp_web_gunicorn)" 2>/dev/null || fail "No se pudo reiniciar el servicio."
fi
sleep 3

if systemctl --user is-active --quiet "$SERVICE" 2>/dev/null || pgrep -f blmp_web_gunicorn > /dev/null; then
  ok "Servicio activo"
else
  fail "Gunicorn no está corriendo. Ver: tail -50 /var/log/blmp/gunicorn_web_error.log"
fi

# ── 7. Nginx (opcional) ───────────────────────────────────────────────────────
if $RESTART_NGINX; then
  step "Reiniciando Nginx"
  sudo systemctl reload nginx || fail "No pude recargar nginx."
  ok "Nginx recargado"
fi

# ── Resumen final ─────────────────────────────────────────────────────────────
echo -e "\n${GREEN}${BOLD}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${RESET}"
echo -e "${GREEN}${BOLD}   ✓ Despliegue completado${RESET}"
echo -e "${GREEN}${BOLD}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${RESET}"
echo -e ""
echo -e "  ${BOLD}Commit   ${RESET} ${SUMMARY_COMMIT}"
echo -e "  ${BOLD}Git      ${RESET} ${SUMMARY_GIT}"
echo -e "  ${BOLD}Migracs  ${RESET} ${SUMMARY_MIGRATE}"
echo -e "  ${BOLD}Estáticos${RESET} ${SUMMARY_STATIC}"
echo -e "  ${BOLD}Sitio    ${RESET} https://blmp.unl.edu.ec/"
echo -e "  ${BOLD}Hora     ${RESET} ${DEPLOY_START} → $(date '+%H:%M:%S')"
echo -e ""
