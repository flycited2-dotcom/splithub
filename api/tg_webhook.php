<?php
/**
 * tg_webhook.php — Telegram-пульт управления статусами заказов.
 *
 * Telegram присылает сюда callback_query, когда владелец жмёт inline-кнопку
 * под уведомлением о заказе ([Подтвердить]/[Выполнен]/[Отменить]).
 * Меняем orders.status → видно в админке и в ЛК клиента (единый источник правды).
 *
 * Безопасность: секретный заголовок (setWebhook secret_token) + chat_id нашей группы.
 * Смену статуса делает сам владелец — никуда не дублируем (по принципу проекта).
 */

// Всегда отвечаем Telegram 200, иначе он будет ретраить
ignore_user_abort(true);
http_response_code(200);

$cfgFile = __DIR__ . '/../config.php';
if (file_exists($cfgFile)) require_once $cfgFile;

$TOKEN  = defined('BOT_TOKEN') ? BOT_TOKEN : '';
$CHAT   = defined('CHAT_ID')   ? (string)CHAT_ID : '';
$SECRET = defined('WEBHOOK_SECRET') ? WEBHOOK_SECRET : '';

// 1) Проверка секрета (Telegram шлёт его в заголовке при setWebhook secret_token)
$gotSecret = $_SERVER['HTTP_X_TELEGRAM_BOT_API_SECRET_TOKEN'] ?? '';
if ($SECRET === '' || !hash_equals($SECRET, $gotSecret)) {
    error_log('[SplitHub webhook] bad secret');
    echo 'ok'; exit;
}

$raw    = file_get_contents('php://input');
$update = json_decode($raw, true);
if (!is_array($update)) { echo 'ok'; exit; }

// Обрабатываем только нажатия кнопок
$cq = $update['callback_query'] ?? null;
if (!$cq) { echo 'ok'; exit; }

$data    = $cq['data'] ?? '';
$cqId    = $cq['id'] ?? '';
$fromId  = $cq['from']['id'] ?? '';
$msg     = $cq['message'] ?? [];
$msgId   = $msg['message_id'] ?? 0;
$chatId  = (string)($msg['chat']['id'] ?? '');

// 2) Кнопки действуют только в нашей группе
if ($CHAT === '' || $chatId !== $CHAT) {
    error_log('[SplitHub webhook] chat mismatch from='.$fromId.' chat='.$chatId);
    tgApi($TOKEN, 'answerCallbackQuery', ['callback_query_id' => $cqId, 'text' => 'Недоступно']);
    echo 'ok'; exit;
}
error_log('[SplitHub webhook] callback from='.$fromId.' data='.$data);

// 3) Разбор callback_data: st:<status>:<orderId>
$parts   = explode(':', $data);
$allowed = ['confirmed', 'completed', 'cancelled'];
if (count($parts) !== 3 || $parts[0] !== 'st' || !in_array($parts[1], $allowed)) {
    tgApi($TOKEN, 'answerCallbackQuery', ['callback_query_id' => $cqId]);
    echo 'ok'; exit;
}
$newStatus = $parts[1];
$orderId   = (int)$parts[2];

$labels = ['confirmed' => 'Подтверждён', 'completed' => 'Выполнен', 'cancelled' => 'Отменён'];

// 4) Меняем статус
try {
    require_once __DIR__ . '/../db/init.php';
    $db = getDB();
    $st = $db->prepare('SELECT id FROM orders WHERE id = ?');
    $st->execute([$orderId]);
    if (!$st->fetch()) {
        tgApi($TOKEN, 'answerCallbackQuery', ['callback_query_id' => $cqId, 'text' => 'Заказ не найден']);
        echo 'ok'; exit;
    }
    $db->prepare('UPDATE orders SET status = ? WHERE id = ?')->execute([$newStatus, $orderId]);
} catch (Throwable $e) {
    error_log('[SplitHub webhook] DB error: ' . $e->getMessage());
    tgApi($TOKEN, 'answerCallbackQuery', ['callback_query_id' => $cqId, 'text' => 'Ошибка БД']);
    echo 'ok'; exit;
}

// 5) Всплывашка + обновляем кнопки на следующий шаг
tgApi($TOKEN, 'answerCallbackQuery', ['callback_query_id' => $cqId, 'text' => 'Статус: ' . $labels[$newStatus]]);

$shNum  = 'SH-' . str_pad((string)$orderId, 5, '0', STR_PAD_LEFT);
$markup = nextMarkup($newStatus, $orderId);
tgApi($TOKEN, 'editMessageReplyMarkup', [
    'chat_id'      => $chatId,
    'message_id'   => $msgId,
    'reply_markup' => json_encode($markup),
]);
// Допишем строку статуса под сообщением (короткое уведомление в группе)
tgApi($TOKEN, 'sendMessage', [
    'chat_id'             => $chatId,
    'text'                => $shNum . ' → ' . $labels[$newStatus],
    'reply_to_message_id' => $msgId,
]);

echo 'ok';

// ── helpers ──────────────────────────────────────────────
function nextMarkup($status, $orderId) {
    if ($status === 'confirmed') {
        return ['inline_keyboard' => [[
            ['text' => '📦 Выполнен',  'callback_data' => 'st:completed:' . $orderId],
            ['text' => '❌ Отменить',  'callback_data' => 'st:cancelled:' . $orderId],
        ]]];
    }
    // completed / cancelled — терминальные, кнопок больше нет
    return ['inline_keyboard' => []];
}

function tgApi($token, $method, $params) {
    if (!$token) return null;
    $ch = curl_init("https://api.telegram.org/bot{$token}/{$method}");
    curl_setopt_array($ch, [
        CURLOPT_POST           => true,
        CURLOPT_POSTFIELDS     => $params,
        CURLOPT_RETURNTRANSFER => true,
        CURLOPT_TIMEOUT        => 10,
        CURLOPT_SSL_VERIFYPEER => false,
    ]);
    $resp = curl_exec($ch);
    curl_close($ch);
    return $resp;
}
