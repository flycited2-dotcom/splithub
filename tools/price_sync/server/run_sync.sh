#!/bin/bash
# Ночная сверка цен и наличия СплитХаб на сервере (cron, 04:00 МСК) — то же, что делал
# run_sync.ps1 на компьютере владельца, но без него: компьютер ночью спит, сервер — нет.
# Остатки JAC, выгрузки SplitHome и Бриза, пересчёт каталога, заливка на сайт через
# предохранитель, итог в Telegram. Упал шаг — повтор; не вышло — сообщение о сбое,
# сайт при этом не трогаем.
#
#     /opt/splithub-price-sync/app/tools/price_sync/server/run_sync.sh
#     ... run_sync.sh --dry-run     # всё посчитать, но не заливать и не слать
#
# Раскладка на сервере (её создаёт push_to_server.ps1 с компьютера):
#   app/      — нужная часть репозитория splithub (tools/, products.js, converter/config)
#   jac/data/ — остатки JAC: их собирает компьютер владельца и присылает сюда готовым
#               файлом (run_sync.ps1 -JacOnly) — портал JAC серверам отдаёт неполные данные
#   venv/     — python-зависимости, logs/ — логи прогонов
set -u

BASE=/opt/splithub-price-sync
APP=$BASE/app
JAC=$BASE/jac
PY=$BASE/venv/bin/python
OUT=$APP/tools/price_sync/out
LOG_DIR=$BASE/logs
DRY=""
[ "${1:-}" = "--dry-run" ] && DRY="--dry-run"
# Без доступа к хостингу (его кладёт push_to_server.ps1 -WithSecrets) считаем, но не
# заливаем и не пишем в Telegram — сайт пока обновляет компьютер.
NO_ACCESS=""
if [ ! -f "$APP/converter/config/deploy.json" ]; then
    DRY="--dry-run"
    NO_ACCESS=1
fi

mkdir -p "$LOG_DIR" "$OUT"
LOG=$LOG_DIR/sync_$(date +%Y%m%d_%H%M).log
exec >>"$LOG" 2>&1

export PYTHONIOENCODING=utf-8
# Остатки JAC — файл с компьютера; Telegram — токен и чат бота остатков на этом сервере.
export SPLITHUB_JAC_JSON=$JAC/data/jac_stock_latest.json
export SPLITHUB_TG_ENV=/opt/splithub_api_telegram/.env

log() { echo "$(date '+%H:%M:%S') $*"; }

notify() {
    [ -n "$DRY" ] && return 0
    (cd "$APP" && "$PY" -m tools.price_sync.notify "$1") || true
}

# Один прогон за раз: ручной запуск не наложится на ночной.
exec 9>/run/lock/splithub-price-sync.lock
if ! flock -n 9; then
    log "прошлый прогон ещё идёт — выхожу"
    exit 0
fi

log "=== Сверка цен $(date '+%d.%m.%Y %H:%M') ${DRY} ==="
[ -n "$NO_ACCESS" ] && log "нет доступа к хостингу (converter/config/deploy.json) — считаю без заливки"

# ── 1. Остатки JAC ────────────────────────────────────────────────────────────
# Их присылает компьютер владельца (вечерний сбор). Не включали несколько дней —
# JAC-позиции остаются как были, а владелец получает напоминание.
jac_hours=$(( ($(date +%s) - $(stat -c %Y "$SPLITHUB_JAC_JSON" 2>/dev/null || echo 0)) / 3600 ))
log "Остатки JAC: срез от $(date -r "$SPLITHUB_JAC_JSON" '+%d.%m %H:%M' 2>/dev/null || echo '—')"
if [ "$jac_hours" -ge 72 ]; then
    notify "ℹ️ СплитХаб: остатки JAC (MDV, THAICON, Mitsubishi) не обновлялись $(( jac_hours / 24 )) дн. — их собирает компьютер, включите его хотя бы на вечер."
fi

# ── 2. Каталог SplitHome (Русклимат / Daichi / Бриз) ──────────────────────────
# Запрос только на чтение, прямо в контейнере базы: пароли никуда не уезжают.
log "Выгружаю каталог SplitHome..."
part=$OUT/oasis_stock.csv.part
if docker exec -i oasis-db-1 sh -c 'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -At -F"|" -f -' \
        < "$APP/tools/price_sync/oasis_export.sql" > "$part" && [ -s "$part" ]; then
    mv -f "$part" "$OUT/oasis_stock.csv"
    log "SplitHome: $(wc -l < "$OUT/oasis_stock.csv") строк"
else
    rm -f "$part"
    log "SplitHome: выгрузка не удалась, беру прошлую"
fi

# ── 3. Опт Бриза ──────────────────────────────────────────────────────────────
# В базе SplitHome у Бриза розница, опт — только в его API. Ключ лежит на сервере.
# .env не «сорсим»: в значении ключа пробел («Basic xxx») — читаем sed-ом.
log "Запрашиваю опт-цены Бриза..."
H=$(sed -n 's/^BREEZ_AUTH_HEADER=//p' /opt/oasis/.env)
U=$(sed -n 's/^BREEZ_BASE_URL=//p' /opt/oasis/.env)
part=$OUT/breez_base.json.part
if curl -sS --max-time 120 -H "Authorization: $H" -H "Accept: application/json" \
        "${U%/}/leftoversnew/" -o "$part" \
        && [ "$(stat -c %s "$part" 2>/dev/null || echo 0)" -ge 100000 ] \
        && [ "$(head -c 1 "$part")" = "{" ]; then
    mv -f "$part" "$OUT/breez_base.json"
    log "Бриз: $(( $(stat -c %s "$OUT/breez_base.json") / 1024 )) КБ"
else
    rm -f "$part"
    log "Бриз: ответ пустой или не JSON, прошлые цены оставлены"
fi
unset H U

# ── 3а. Техносистемс: их Telegram-канал и прайс-таблица ──────────────────────
# Канал читает личный Telegram владельца — сессия живёт в контейнере telegram-personal-mcp
# и наружу не выходит, скрипт подаём ему на stdin. Свежий текстовый прайс из канала
# перебивает их Google-таблицу; таблица (цены + склад) — основа. Не вышло — прайс прежний.
log "Техносистемс: канал и прайс-таблица..."
last=$(cd "$APP" && "$PY" -m tools.price_sync.techno_live --last-id 2>/dev/null || echo 0)
part=$OUT/techno_tg.json.part
if docker exec -i -w /app -e LAST_ID="$last" telegram-personal-mcp-telegram-mcp-1 python -         < "$APP/tools/price_sync/server/techno_tg_fetch.py" > "$part" 2>/dev/null         && [ "$(head -c 1 "$part")" = "[" ]; then
    mv -f "$part" "$OUT/techno_tg.json"
else
    rm -f "$part"
    echo "[]" > "$OUT/techno_tg.json"
    log "Техносистемс: канал прочитать не удалось — беру только таблицу"
fi
techno_args=""
[ -n "$DRY" ] && techno_args="--dry-run"
(cd "$APP" && "$PY" -m tools.price_sync.techno_live $techno_args)     || log "Техносистемс: таблица не прочиталась — прайс прежний"

# ── 4–7. Пересчёт, карточки, сборка, заливка ─────────────────────────────────
step() {  # step "название" попыток модуль [аргументы...]
    local title=$1 attempts=$2 i
    shift 2
    for ((i = 1; i <= attempts; i++)); do
        (cd "$APP" && "$PY" -m "$@") && return 0
        log "$title — попытка $i не удалась"
        # Сеть до поставщиков иногда рвётся на минуту-другую.
        [ "$i" -lt "$attempts" ] && sleep 300
    done
    return 1
}

fail() {
    local text="⚠️ СплитХаб $(date '+%d.%m %H:%M'): ночная сверка на сервере упала на шаге «$1». Сайт не тронут. Лог: $(basename "$LOG")"
    log "$text"
    notify "$text"
    exit 1
}

log "Пересчитываю каталог по прайсам..."
step "Пересчёт цен" 2 tools.price_sync.sync || fail "пересчёт цен"
log "Карточки новых товаров..."
step "Карточки" 1 tools.price_sync.new_cards || fail "карточки новых товаров"
# Фото новой карточки должно уже лежать на сайте — проверяем прямо там.
step "Сборка каталога" 1 tools.price_sync.merge --assets https://splithub.ru/assets/img/products/ \
    || fail "сборка каталога"
log "Заливаю на сайт через предохранитель..."
step "Заливка" 2 tools.price_sync.publish $DRY || exit 1   # publish сам сообщает причину

log "Готово."
find "$LOG_DIR" -name 'sync_*.log' -mtime +60 -delete
