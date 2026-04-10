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
LAST_HASH=$(git rev-parse --short HEAD)

# Construir resumen del commit actual (siempre mostrar el último)
if [[ "$BEFORE" == "$REMOTE" ]]; then
  # Sin cambios nuevos — hacer más explícito que se despliega el último commit
  SUMMARY_COMMIT="${LAST_MSG} ${DIM}(${LAST_HASH} · ${LAST_AUTHOR} · ${LAST_DATE} · sin cambios nuevos)${RESET}"
else
  SUMMARY_COMMIT="${LAST_MSG} ${DIM}(${LAST_HASH} · ${LAST_AUTHOR} · ${LAST_DATE})${RESET}"
fi

ok "Código listo — HEAD: $LAST_HASH"

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
CHECK_OUT=$($PYTHON manage.py check --deploy 2>&1 || true)
ERRORS=$(echo "$CHECK_OUT" | grep -c "^.*: (security\." || true)
if echo "$CHECK_OUT" | grep -q "^System check identified 0"; then
  ok "Check OK (sin issues)"
elif echo "$CHECK_OUT" | grep -q "ERROR"; then
  echo "$CHECK_OUT" | grep -E "ERROR|WARNINGS|^System check" >&2
  fail "Django check encontró ERRORES — despliegue abortado."
else
  # Solo warnings — mostrarlos pero continuar
  echo "$CHECK_OUT" | grep -v "^$" | sed 's/^/    /'
  warn "Check con warnings (ver arriba) — continuando de todas formas"
fi

# ── 6. Reiniciar servicio ─────────────────────────────────────────────────────
# Gunicorn corre directamente (sin systemd). El master process recibe HUP
# para recargar workers sin perder conexiones activas.
step "Reiniciando servicio"

# El master es el proceso gunicorn con PPID=1 (arrancado como daemon)
GUNICORN_MASTER=$(pgrep -f "gunicorn.*${SERVICE}" 2>/dev/null | head -1)
if [[ -z "$GUNICORN_MASTER" ]]; then
  # Fallback: cualquier gunicorn corriendo
  GUNICORN_MASTER=$(pgrep -f "gunicorn" 2>/dev/null | head -1)
fi

if [[ -z "$GUNICORN_MASTER" ]]; then
  fail "No se encontró proceso gunicorn. El servicio no está corriendo."
fi

kill -HUP "$GUNICORN_MASTER"
dim "HUP enviado a master gunicorn PID $GUNICORN_MASTER"
sleep 3

if pgrep -f "gunicorn" > /dev/null 2>&1; then
  ok "Servicio activo (PID $GUNICORN_MASTER)"
else
  fail "Gunicorn no está corriendo tras el HUP."
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
echo -e "  ${BOLD}Última versión${RESET}"
echo -e "    ${SUMMARY_COMMIT}"
echo -e ""
echo -e "  ${BOLD}Cambios      ${RESET} ${SUMMARY_GIT}"
echo -e "  ${BOLD}Migraciones  ${RESET} ${SUMMARY_MIGRATE}"
echo -e "  ${BOLD}Estáticos    ${RESET} ${SUMMARY_STATIC}"
echo -e ""
echo -e "  ${BOLD}Sitio        ${RESET} https://blmp.unl.edu.ec/"
echo -e "  ${BOLD}Duración     ${RESET} ${DEPLOY_START} → $(date '+%H:%M:%S')"
echo -e ""
