<?php
/**
 * send.php — обработчик заявок СплитХаб
 * Архитектура по ТЗ: TG — первичная функция, всё остальное — вторичное.
 * Потеря заявки недопустима. Сбой DB/email не влияет на отправку в TG.
 */

ob_start();

header('Content-Type: application/json; charset=utf-8');
header('Access-Control-Allow-Origin: *');
header('Access-Control-Allow-Methods: POST, OPTIONS');
header('Access-Control-Allow-Headers: Content-Type');
if ($_SERVER['REQUEST_METHOD'] === 'OPTIONS') { ob_end_clean(); http_response_code(200); exit; }
if ($_SERVER['REQUEST_METHOD'] !== 'POST')    { ob_end_clean(); http_response_code(405); exit; }

// ── Конфиг (с фолбэком если config.php недоступен) ──
if (file_exists(__DIR__ . '/config.php')) {
    require __DIR__ . '/config.php';
}
if (!defined('BOT_TOKEN'))     define('BOT_TOKEN',     '8366074996:AAGe0oEpkQ4foTlcJ0zqNFxUv5w1i1Xay78');
if (!defined('CHAT_ID'))       define('CHAT_ID',       '-1003727076862');
if (!defined('EMAIL_TO'))      define('EMAIL_TO',      'flycited@gmail.com');
if (!defined('RATE_LIMIT_SEC')) define('RATE_LIMIT_SEC', 30);

// ── Shutdown handler — всегда возвращает JSON ──
register_shutdown_function(function() {
    $err = error_get_last();
    if ($err && in_array($err['type'], [E_ERROR, E_PARSE, E_CORE_ERROR, E_COMPILE_ERROR])) {
        ob_clean();
        if (!headers_sent()) header('Content-Type: application/json; charset=utf-8');
        http_response_code(500);
        echo json_encode(['ok' => false, 'error' => 'Ошибка сервера. Позвоните: +7 978 599-13-69'], JSON_UNESCAPED_UNICODE);
        exit;
    }
    ob_end_flush();
});

// ── Вход ──
$raw  = file_get_contents('php://input');
$data = json_decode($raw, true);
if (!$data) {
    http_response_code(400);
    echo json_encode(['ok' => false, 'error' => 'Bad JSON']);
    exit;
}

$name     = trim($data['name']     ?? '');
$phone    = trim($data['phone']    ?? '');
$comment  = trim($data['comment']  ?? '');
$clientTg = trim($data['client_tg'] ?? '');
$items    = $data['items'] ?? [];

if (!$name || !$phone || empty($items)) {
    http_response_code(422);
    echo json_encode(['ok' => false, 'error' => 'Заполните все поля'], JSON_UNESCAPED_UNICODE);
    exit;
}
if (count($items) > 50) {
    http_response_code(422);
    echo json_encode(['ok' => false, 'error' => 'Слишком много позиций'], JSON_UNESCAPED_UNICODE);
    exit;
}

// ── Сборка заказа ──
$date    = date('d.m.Y H:i', time() + 3 * 3600);
$total   = 0;
$num     = 1;
$tgLines = '';
$htmlRows = '';

foreach ($items as $item) {
    $n   = $item['name'] ?? '—';
    $p   = intval($item['price'] ?? 0);
    $qty = max(1, min(999, intval($item['qty'] ?? 1)));
    $sub = $p * $qty;
    $total += $sub;
    $pf  = number_format($p,   0, '.', ' ');
    $sf  = number_format($sub, 0, '.', ' ');
    $ne  = htmlspecialchars($n);
    $tgLines  .= "  {$num}. {$n} — {$pf} ₽ × {$qty} шт. = {$sf} ₽\n";
    $htmlRows .= "<tr>"
        . "<td style='padding:8px 12px;border-bottom:1px solid #eee'>{$num}</td>"
        . "<td style='padding:8px 12px;border-bottom:1px solid #eee'>{$ne}</td>"
        . "<td style='padding:8px 12px;border-bottom:1px solid #eee;text-align:right'>{$pf} ₽</td>"
        . "<td style='padding:8px 12px;border-bottom:1px solid #eee;text-align:center'>{$qty}</td>"
        . "<td style='padding:8px 12px;border-bottom:1px solid #eee;font-weight:700;color:#D97706;text-align:right'>{$sf} ₽</td>"
        . "</tr>";
    $num++;
}
$totalf = number_format($total, 0, '.', ' ');
$cnt    = count($items);

// ══════════════════════════════════════════
// ПЕРВИЧНАЯ ФУНКЦИЯ: отправка в Telegram
// ══════════════════════════════════════════

function sendTg($token, $chatId, $text) {
    $ch = curl_init("https://api.telegram.org/bot{$token}/sendMessage");
    curl_setopt_array($ch, [
        CURLOPT_POST           => true,
        CURLOPT_POSTFIELDS     => json_encode([
            'chat_id'    => $chatId,
            'text'       => $text,
            'parse_mode' => 'Markdown',
        ]),
        CURLOPT_HTTPHEADER     => ['Content-Type: application/json'],
        CURLOPT_RETURNTRANSFER => true,
        CURLOPT_TIMEOUT        => 10,
        CURLOPT_SSL_VERIFYPEER => false,
    ]);
    $resp = curl_exec($ch);
    $code = curl_getinfo($ch, CURLINFO_HTTP_CODE);
    $err  = curl_errno($ch);
    curl_close($ch);
    if ($err) error_log('[SplitHub TG] curl errno=' . $err);
    return ['resp' => $resp, 'code' => $code, 'result' => json_decode($resp, true)];
}

$tgMsg  = "🛒 *Новая заявка — СплитХаб*\n";
$tgMsg .= "━━━━━━━━━━━━━━━━━━\n";
$tgMsg .= "👤 *Имя:* {$name}\n";
$tgMsg .= "📞 *Телефон:* {$phone}\n";
if ($clientTg !== '') $tgMsg .= "💬 *Telegram:* {$clientTg}\n";
$tgMsg .= "📅 *Время:* {$date}\n";
$tgMsg .= "━━━━━━━━━━━━━━━━━━\n";
$tgMsg .= "📦 *Позиции ({$cnt} шт.):*\n{$tgLines}";
$tgMsg .= "━━━━━━━━━━━━━━━━━━\n";
$tgMsg .= "💰 *Итого:* {$totalf} ₽\n";
if ($comment !== '') $tgMsg .= "━━━━━━━━━━━━━━━━━━\n💬 *Комментарий:* {$comment}\n";
$tgMsg .= "\n_Клиент ждёт звонка_";

$tgResult = sendTg(BOT_TOKEN, CHAT_ID, $tgMsg);
$tgOk     = $tgResult['result']['ok'] ?? false;

// Если Markdown отклонён — повтор без форматирования
if (!$tgOk) {
    error_log('[SplitHub TG] Markdown failed (' . ($tgResult['resp'] ?? '') . '), retrying plain');
    $tgPlain  = "Новая заявка — СплитХаб\n";
    $tgPlain .= "Имя: {$name}\nТелефон: {$phone}\n";
    if ($clientTg !== '') $tgPlain .= "Telegram: {$clientTg}\n";
    $tgPlain .= "Время: {$date}\n\nПозиции ({$cnt} шт.):\n{$tgLines}\nИтого: {$totalf} руб\n";
    if ($comment !== '') $tgPlain .= "Комментарий: {$comment}\n";
    $tgResult2 = sendTg(BOT_TOKEN, CHAT_ID, $tgPlain);
    if ($tgResult2['result']['ok'] ?? false) {
        $tgOk     = true;
        $tgResult = $tgResult2;
    }
}

error_log('[SplitHub TG] ok=' . ($tgOk ? 'yes' : 'no') . ' resp=' . ($tgResult['resp'] ?? ''));

// ══════════════════════════════════════════
// ВТОРИЧНЫЕ ФУНКЦИИ: DB, email, rate limit
// Сбой любой из них НЕ влияет на ответ TG
// ══════════════════════════════════════════

$orderId       = null;
$bonusEarned   = 0;
$bonusSpent    = 0;
$guestSaved    = false;
$mailOk        = false;

// ── DB (авторизованный пользователь) ──
try {
    if (file_exists(__DIR__ . '/db/init.php')) {
        require_once __DIR__ . '/db/init.php';
        $userId = authCheck();
        if ($userId) {
            $db         = getDB();
            $bonusSpent = max(0, intval($data['bonus_spend'] ?? 0));
            if ($bonusSpent > 0) {
                $bal = $db->prepare('SELECT COALESCE(SUM(amount),0) as b FROM bonus_log WHERE user_id=?');
                $bal->execute([$userId]);
                $balance = (int)$bal->fetch()['b'];
                if ($bonusSpent > $balance) $bonusSpent = $balance;
                if ($bonusSpent > $total)   $bonusSpent = $total;
            }
            $dbItems = [];
            foreach ($items as $item) {
                $dbItems[] = [
                    'name'  => $item['name'] ?? '—',
                    'price' => intval($item['price'] ?? 0),
                    'qty'   => max(1, min(999, intval($item['qty'] ?? 1))),
                    'group' => $item['group'] ?? '',
                ];
            }
            $bonusResult = calculateBonus($total - $bonusSpent, $dbItems);
            $bonusEarned = $bonusResult['bonus'];

            $ins = $db->prepare('INSERT INTO orders (user_id,total,bonus_earned,bonus_spent,status,comment,client_tg) VALUES (?,?,?,?,"new",?,?)');
            $ins->execute([$userId, $total, $bonusEarned, $bonusSpent, $comment, $clientTg]);
            $orderId = (int)$db->lastInsertId();

            $itemIns = $db->prepare('INSERT INTO order_items (order_id,product_name,price,qty) VALUES (?,?,?,?)');
            foreach ($dbItems as $di) {
                $itemIns->execute([$orderId, $di['name'], $di['price'], $di['qty']]);
            }
            if ($bonusEarned > 0) {
                $db->prepare('INSERT INTO bonus_log (user_id,order_id,amount,type,description) VALUES (?,?,?,"earn",?)')->execute([$userId, $orderId, $bonusEarned, 'Начислено за заказ #' . $orderId]);
            }
            if ($bonusSpent > 0) {
                $db->prepare('INSERT INTO bonus_log (user_id,order_id,amount,type,description) VALUES (?,?,?,"spend",?)')->execute([$userId, $orderId, -$bonusSpent, 'Списано на заказ #' . $orderId]);
            }
        }
    }
} catch (Throwable $e) {
    error_log('[SplitHub DB] ' . $e->getMessage());
}

// ── Guest orders (анонимный пользователь) ──
if (!$orderId) {
    try {
        if (file_exists(__DIR__ . '/db/init.php')) {
            if (!function_exists('getDB')) require_once __DIR__ . '/db/init.php';
            $gdb = getDB();
            $gdb->exec('CREATE TABLE IF NOT EXISTS guest_orders (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL, phone TEXT NOT NULL,
                total INTEGER NOT NULL DEFAULT 0,
                items_json TEXT NOT NULL DEFAULT "[]",
                comment TEXT DEFAULT "", client_tg TEXT DEFAULT "",
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )');
            $gdb->prepare('INSERT INTO guest_orders (name,phone,total,items_json,comment,client_tg) VALUES (?,?,?,?,?,?)')
                ->execute([$name, $phone, $total, json_encode($items, JSON_UNESCAPED_UNICODE), $comment, $clientTg]);
            $guestSaved = true;
        }
    } catch (Throwable $e) {
        error_log('[SplitHub guest] ' . $e->getMessage());
    }
}

// ── Email ──
try {
    $commentHtml = $comment !== ''
        ? "<tr><td colspan='5' style='padding:10px 12px;background:#fffbeb;color:#92400e'><strong>Комментарий:</strong> " . htmlspecialchars($comment) . "</td></tr>"
        : '';
    $emailHtml = '<!DOCTYPE html><html><head><meta charset="UTF-8"></head>'
        . '<body style="margin:0;padding:0;background:#f3f4f6;font-family:Arial,sans-serif">'
        . '<div style="max-width:600px;margin:20px auto;background:#fff;border-radius:12px;overflow:hidden">'
        . '<div style="background:#F59E0B;padding:18px 24px"><h2 style="margin:0;color:#fff;font-size:1.1rem">🛒 Новая заявка — СплитХаб</h2></div>'
        . '<div style="padding:20px 24px">'
        . '<table style="width:100%;border-collapse:collapse;margin-bottom:16px">'
        . "<tr><td style='padding:5px 0;color:#6b7280;width:90px'>Клиент</td><td style='padding:5px 0;font-weight:700'>" . htmlspecialchars($name) . "</td></tr>"
        . "<tr><td style='padding:5px 0;color:#6b7280'>Телефон</td><td style='padding:5px 0;font-weight:700'>" . htmlspecialchars($phone) . "</td></tr>"
        . "<tr><td style='padding:5px 0;color:#6b7280'>Время</td><td style='padding:5px 0'>{$date}</td></tr>"
        . '</table>'
        . "<h3 style='margin:0 0 10px;font-size:.88rem;color:#374151'>Состав заказа ({$cnt} поз.)</h3>"
        . '<table style="width:100%;border-collapse:collapse;font-size:.84rem">'
        . '<thead><tr style="background:#F59E0B">'
        . '<th style="padding:8px 12px;text-align:left;color:#fff">№</th>'
        . '<th style="padding:8px 12px;text-align:left;color:#fff">Наименование</th>'
        . '<th style="padding:8px 12px;text-align:right;color:#fff">Цена</th>'
        . '<th style="padding:8px 12px;text-align:center;color:#fff">Кол.</th>'
        . '<th style="padding:8px 12px;text-align:right;color:#fff">Сумма</th>'
        . '</tr></thead><tbody>' . $htmlRows . $commentHtml . '</tbody>'
        . "<tfoot><tr style='background:#FEF3C7'><td colspan='4' style='padding:10px 12px;font-weight:700'>Итого</td>"
        . "<td style='padding:10px 12px;font-weight:700;color:#D97706;text-align:right'>{$totalf} ₽</td></tr></tfoot>"
        . '</table></div>'
        . '<div style="padding:10px 24px;background:#f9fafb;color:#9ca3af;font-size:.72rem">СплитХаб · splithub.ru · Симферополь</div>'
        . '</div></body></html>';

    $headers   = "From: =?UTF-8?B?" . base64_encode("СплитХаб") . "?= <zakaz@splithub.ru>\r\n";
    $headers  .= "MIME-Version: 1.0\r\n";
    $headers  .= "Content-Type: text/html; charset=UTF-8\r\n";
    $emailSubj = "=?UTF-8?B?" . base64_encode("Новая заявка СплитХаб — {$name} — {$totalf} руб") . "?=";
    $mailOk    = mail(EMAIL_TO, $emailSubj, $emailHtml, $headers);
} catch (Throwable $e) {
    error_log('[SplitHub mail] ' . $e->getMessage());
}

// ── Rate limit (записывается после отправки, не блокирует) ──
try {
    $rateDir  = sys_get_temp_dir() . '/splithub_rate';
    if (!is_dir($rateDir)) @mkdir($rateDir, 0700, true);
    $rateFile = $rateDir . '/' . md5($_SERVER['REMOTE_ADDR'] ?? 'x') . '.txt';
    // Проверка (мягкая — не прерывает, только логирует)
    if (file_exists($rateFile)) {
        $last = (int)file_get_contents($rateFile);
        if (time() - $last < RATE_LIMIT_SEC) {
            error_log('[SplitHub rate] repeated request from ' . ($_SERVER['REMOTE_ADDR'] ?? '?'));
        }
    }
    file_put_contents($rateFile, time());
} catch (Throwable $e) { /* rate limit не блокирует */ }

error_log('[SplitHub] tg=' . ($tgOk?'ok':'fail') . ' mail=' . ($mailOk?'ok':'fail') . ' orderId=' . ($orderId??'null') . ' guest=' . ($guestSaved?'yes':'no'));

// ── Ответ ──
// Успех если TG доставил, или заказ сохранён в БД
$orderOk = $tgOk || ($orderId !== null) || $guestSaved;

if ($orderOk) {
    $resp = [
        'ok'    => true,
        'tg'    => $tgOk   ? 'sent' : 'failed',
        'email' => $mailOk ? 'sent' : 'failed',
    ];
    if ($orderId)      $resp['order_id']     = $orderId;
    if ($bonusEarned)  $resp['bonus_earned'] = $bonusEarned;
    if ($bonusSpent)   $resp['bonus_spent']  = $bonusSpent;
    echo json_encode($resp, JSON_UNESCAPED_UNICODE);
} else {
    http_response_code(500);
    echo json_encode(['ok' => false, 'error' => 'Заявка не отправлена. Позвоните: +7 978 599-13-69'], JSON_UNESCAPED_UNICODE);
}
