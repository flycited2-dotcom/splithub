<?php
/**
 * tg_poll.php — Telegram-пульт через POLLING (getUpdates).
 *
 * Почему polling, а не webhook: серверы Telegram (за рубежом) не достукиваются
 * до российского хостинга (вх. соединения таймаутят), зато ИСХОДЯЩИЕ запросы
 * сервер→Telegram работают. Поэтому сервер сам забирает нажатия кнопок.
 *
 * Запускается по cron раз в минуту:
 *   curl -s "https://splithub.ru/api/tg_poll.php?secret=<WEBHOOK_SECRET>"
 *
 * Обрабатывает callback_query от inline-кнопок ([Подтвердить]/[Выполнен]/[Отменить]),
 * меняет orders.status (виден в админке и ЛК клиента). Offset — в app_settings,
 * сохраняется ВСЕГДА (даже при сбоях отдельных апдейтов), чтобы не зацикливаться.
 */

require_once __DIR__ . '/lib/app_config.php';
require_once __DIR__ . '/../db/init.php';
require_once __DIR__ . '/lib/push.php';
header('Content-Type: text/plain; charset=utf-8');

$TOKEN  = defined('BOT_TOKEN') ? BOT_TOKEN : '';
$CHAT   = defined('CHAT_ID')   ? (string)CHAT_ID : '';
$SECRET = defined('WEBHOOK_SECRET') ? WEBHOOK_SECRET : '';
$LOG    = __DIR__ . '/tg_poll.log';

if ($SECRET === '' || ($_GET['secret'] ?? '') !== $SECRET) {
    http_response_code(403); echo 'forbidden'; exit;
}

function plog($file, $m) { @error_log('[' . date('Y-m-d H:i:s') . '] ' . $m . "\n", 3, $file); }

function getSetting($db, $k, $def = '') {
    $s = $db->prepare('SELECT value FROM app_settings WHERE key = ?');
    $s->execute([$k]); $r = $s->fetch();
    return $r ? $r['value'] : $def;
}
function setSetting($db, $k, $v) {
    $db->prepare('INSERT OR REPLACE INTO app_settings(key,value) VALUES(?,?)')->execute([$k, $v]);
}

function tgApi($token, $method, $params) {
    if (!$token) return null;
    $ch = curl_init("https://api.telegram.org/bot{$token}/{$method}");
    curl_setopt_array($ch, [
        CURLOPT_POST => true, CURLOPT_POSTFIELDS => $params,
        CURLOPT_RETURNTRANSFER => true, CURLOPT_TIMEOUT => 25, CURLOPT_SSL_VERIFYPEER => false,
        CURLOPT_RESOLVE => ['api.telegram.org:443:' . (defined('TG_FORCE_IP') ? TG_FORCE_IP : '149.154.167.220')],
    ]);
    $r = curl_exec($ch); curl_close($ch);
    return $r;
}

$labels  = ['confirmed' => 'Подтверждён', 'completed' => 'Выполнен', 'cancelled' => 'Отменён'];
$allowed = ['confirmed', 'completed', 'cancelled'];
$processed = 0; $errors = 0;

try {
    $db = getDB();
    $offset = (int)getSetting($db, 'tg_offset', '0');

    $resp = tgApi($TOKEN, 'getUpdates', [
        'offset' => $offset, 'timeout' => 0, 'allowed_updates' => json_encode(['callback_query']),
    ]);
    $j = json_decode($resp, true);
    if (!is_array($j) || empty($j['ok'])) {
        plog($LOG, 'getUpdates fail: ' . substr((string)$resp, 0, 300));
        http_response_code(502); echo 'getUpdates fail'; exit;
    }

    $maxId = $offset - 1;
    foreach ($j['result'] as $u) {
        $maxId = max($maxId, (int)$u['update_id']);
        try {
            $cq = $u['callback_query'] ?? null;
            if (!$cq) continue;
            $data   = $cq['data'] ?? '';
            $cqId   = $cq['id'] ?? '';
            $msg    = $cq['message'] ?? [];
            $msgId  = $msg['message_id'] ?? 0;
            $chatId = (string)($msg['chat']['id'] ?? '');

            if ($chatId !== $CHAT) {
                tgApi($TOKEN, 'answerCallbackQuery', ['callback_query_id' => $cqId, 'text' => 'Недоступно']);
                continue;
            }
            $p = explode(':', $data);
            if (count($p) !== 3 || $p[0] !== 'st' || !in_array($p[1], $allowed)) {
                tgApi($TOKEN, 'answerCallbackQuery', ['callback_query_id' => $cqId]);
                continue;
            }
            $status = $p[1]; $oid = (int)$p[2];

            $chk = $db->prepare('SELECT status FROM orders WHERE id = ?');
            $chk->execute([$oid]); $row = $chk->fetch();
            if (!$row) {
                tgApi($TOKEN, 'answerCallbackQuery', ['callback_query_id' => $cqId, 'text' => 'Заказ не найден']);
                continue;
            }
            $sh = 'SH-' . str_pad((string)$oid, 5, '0', STR_PAD_LEFT);

            // Уже в этом статусе (напр. переобработка) — только всплывашка, без дублей
            if ($row['status'] === $status) {
                tgApi($TOKEN, 'answerCallbackQuery', ['callback_query_id' => $cqId, 'text' => 'Статус: ' . $labels[$status]]);
                $processed++;
                continue;
            }

            $db->prepare('UPDATE orders SET status = ? WHERE id = ?')->execute([$status, $oid]);
            sendOrderStatusPush($oid, $status);
            tgApi($TOKEN, 'answerCallbackQuery', ['callback_query_id' => $cqId, 'text' => 'Статус: ' . $labels[$status]]);
            $mk = ($status === 'confirmed')
                ? ['inline_keyboard' => [[
                    ['text' => '📦 Выполнен', 'callback_data' => 'st:completed:' . $oid],
                    ['text' => '❌ Отменить', 'callback_data' => 'st:cancelled:' . $oid],
                  ]]]
                : ['inline_keyboard' => []];
            tgApi($TOKEN, 'editMessageReplyMarkup', ['chat_id' => $chatId, 'message_id' => $msgId, 'reply_markup' => json_encode($mk)]);
            tgApi($TOKEN, 'sendMessage', ['chat_id' => $chatId, 'text' => $sh . ' → ' . $labels[$status], 'reply_to_message_id' => $msgId]);
            $processed++;
        } catch (Throwable $e) {
            $errors++;
            plog($LOG, 'update ' . ($u['update_id'] ?? '?') . ' error: ' . $e->getMessage() . ' @ ' . $e->getFile() . ':' . $e->getLine());
        }
    }

    // offset сохраняем ВСЕГДА — чтобы не переобрабатывать одни и те же нажатия
    if ($maxId >= $offset) setSetting($db, 'tg_offset', (string)($maxId + 1));

    echo "ok processed={$processed} errors={$errors} offset=" . ($maxId + 1);
} catch (Throwable $e) {
    plog($LOG, 'FATAL: ' . $e->getMessage() . ' @ ' . $e->getFile() . ':' . $e->getLine());
    http_response_code(500); echo 'error';
}
