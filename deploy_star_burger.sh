#!/usr/bin/env bash
set -euo pipefail

PROJECT_DIR="/opt/projects/star-burger"
VENV_DIR="$PROJECT_DIR/venv"

SYSTEMD_SERVICES=(
  "star-burger.service"
)

log() {
  echo "[$(date +'%Y-%m-%d %H:%M:%S')] $*"
}

log "==> Переход в папку проекта"
cd "$PROJECT_DIR"

if [ -f "$PROJECT_DIR/star_burger/.env" ]; then
  log "==> Загрузка переменных окружения из .env"
  set -a
  . "$PROJECT_DIR/star_burger/.env"
  set +a
fi

log "==> Обновление кода из git"
git pull

log "==> Активация виртуального окружения"
source "$VENV_DIR/bin/activate"

log "==> Обновление Python-зависимостей"
pip install -r requirements.txt

log "==> Установка зависимостей Node.js"
if command -v npm >/dev/null 2>&1; then
  if [ -f package-lock.json ]; then
    npm ci
  else
    npm install
  fi
else
  echo "npm не найден. Установите Node.js и npm." >&2
  exit 1
fi

log "==> Сборка JS-бандлов (Parcel)"
./node_modules/.bin/parcel build bundles-src/index.js --dist-dir bundles --public-url="./"

log "==> Накатывание миграций Django"
python manage.py migrate --noinput

log "==> Сбор статики Django"
python manage.py collectstatic --noinput

for SERVICE in "${SYSTEMD_SERVICES[@]}"; do
  log "==> Перезапуск systemd-сервиса: ${SERVICE}"
  systemctl restart "$SERVICE"
done

log "==> Отправка информации о деплое в Rollbar"

ROLLBAR_ACCESS_TOKEN="${ROLLBAR_ACCESS_TOKEN:-}"
ROLLBAR_ENV="${ROLLBAR_ENV:-production}"

if [ -n "$ROLLBAR_ACCESS_TOKEN" ]; then
  GIT_COMMIT=$(git rev-parse HEAD)

  curl -s -X POST "https://api.rollbar.com/api/1/deploy" \
    -H "Content-Type: application/json" \
    -d "{
      \"access_token\": \"${ROLLBAR_ACCESS_TOKEN}\",
      \"environment\": \"${ROLLBAR_ENV}\",
      \"revision\": \"${GIT_COMMIT}\",
      \"rollbar_username\": \"deploy-bot\"
    }" >/dev/null || log "Не удалось отправить deploy-нотификацию в Rollbar"
else
  log "ROLLBAR_ACCESS_TOKEN не задан, пропускаю отправку deploy-нотификации"
fi

log "Деплой star-burger завершён успешно"

