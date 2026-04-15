<?php
require __DIR__ . '/config.php';
require __DIR__ . '/db/init.php';

// ── CORS ──
$origin = $_SERVER['HTTP_ORIGIN'] ?? '';
if ($origin === ALLOWED_ORIGIN) {
    header('Access-Control-Allow-Origin: ' . ALLOWED_ORIGIN);
} else {
    header('Access-Control-Allow-Origin: ' . ALLOWED_ORIGIN);
}
header('Content-Type: application/json; charset=utf-8');
header('Access-Control-Allow-Methods: POST');
header('Access-Control-Allow-Headers: Content-Type');
if ($_SERVER['REQUEST_METHOD'] === 'OPTIONS') { http_response_code(200); exit; }
if ($_SERVER['REQUEST_METHOD'] !== 'POST')    { http_response_code(405); exit; }

// ── Rate Limiting (файловый, по IP) ──
$ip = $_SERVER['REMOTE_ADDR'] ?? 'unknown';
$rateDir = sys_get_temp_dir() . '/splithub_rate';
if (!is_dir($rateDir)) @mkdir($rateDir, 0700, true);
$rateFile = $rateDir . '/' . md5($ip) . '.txt';
if (file_exists($rateFile)) {
    $lastTime = (int)file_get_contents($rateFile);
    if (time() - $lastTime < RATE_LIMIT_SEC) {
        http_response_code(429);
        echo json_encode(['ok' => false, 'error' => 'Подождите перед повторной отправкой']);
        exit;
    }
}

// ── Input ──
$raw = file_get_contents('php://input');
$data = json_decode($raw, true);
if (!$data) { http_response_code(400); echo json_encode(['ok' => false, 'error' => 'Bad JSON']); exit; }

$name    = trim($data['name'] ?? '');
$phone   = trim($data['phone'] ?? '');
$comment = trim($data['comment'] ?? '');
$clientTg = trim($data['client_tg'] ?? '');
$items   = $data['items'] ?? [];

// Валидация
if (!$name || !$phone || empty($items)) {
    http_response_code(422);
    echo json_encode(['ok' => false, 'error' => 'Заполните все поля']);
    exit;
}
if (!preg_match('/^\+?[0-9\s\-\(\)]{7,20}$/', $phone)) {
    http_response_code(422);
    echo json_encode(['ok' => false, 'error' => 'Некорректный телефон']);
    exit;
}
if (count($items) > 50) {
    http_response_code(422);
    echo json_encode(['ok' => false, 'error' => 'Слишком много позиций']);
    exit;
}

// ── Сборка заказа ──
$date = date('d.m.Y H:i', time() + 3 * 3600);
$total = 0; $num = 1; $tgLines = ''; $htmlRows = '';

foreach ($items as $item) {
    $n   = htmlspecialchars($item['name'] ?? '—');
    $p   = intval($item['price'] ?? 0);
    $qty = max(1, min(999, intval($item['qty'] ?? 1)));
    $sub = $p * $qty; $total += $sub;
    $pf  = number_format($p, 0, '.', ' ');
    $sf  = number_format($sub, 0, '.', ' ');
    $tgLines .= "  {$num}. {$n} — {$pf} ₽ × {$qty} шт. = {$sf} ₽\n";
    $htmlRows .= "<tr><td style='padding:10px 8px;border-bottom:1px solid #f0f0f0;vertical-align:top;width:24px;color:#9ca3af;font-size:.75rem'>{$num}</td><td style='padding:10px 8px;border-bottom:1px solid #f0f0f0;vertical-align:top'><div style='font-size:.82rem;font-weight:600;color:#1f2937;line-height:1.4'>{$n}</div><div style='font-size:.75rem;color:#6b7280;margin-top:3px'>{$pf}&nbsp;₽&nbsp;&times;&nbsp;{$qty}&nbsp;шт.</div></td><td style='padding:10px 8px;border-bottom:1px solid #f0f0f0;vertical-align:top;text-align:right;white-space:nowrap;font-weight:700;color:#D97706;font-size:.85rem'>{$sf}&nbsp;₽</td></tr>";
    $num++;
}
$totalf = number_format($total, 0, '.', ' ');
$cnt = count($items);

// ── Save to DB (if user is logged in) ──
$orderId = null;
$bonusEarned = 0;
$bonusSpent = 0;
$userId = authCheck();

if ($userId) {
    $db = getDB();

    // Check bonus redemption request
    $bonusSpent = max(0, intval($data['bonus_spend'] ?? 0));
    if ($bonusSpent > 0) {
        $bal = $db->prepare('SELECT COALESCE(SUM(amount), 0) as balance FROM bonus_log WHERE user_id = ?');
        $bal->execute([$userId]);
        $balance = (int)$bal->fetch()['balance'];
        if ($bonusSpent > $balance) $bonusSpent = $balance;
        if ($bonusSpent > $total)   $bonusSpent = $total;
    }

    // Calculate bonus earned
    $dbItems = [];
    foreach ($items as $item) {
        $dbItems[] = [
            'name'  => $item['name'] ?? '—',
            'price' => intval($item['price'] ?? 0),
            'qty'   => max(1, min(999, intval($item['qty'] ?? 1))),
            'group' => $item['group'] ?? ''
        ];
    }
    $bonusResult = calculateBonus($total - $bonusSpent, $dbItems);
    $bonusEarned = $bonusResult['bonus'];

    // Insert order
    $ins = $db->prepare('INSERT INTO orders (user_id, total, bonus_earned, bonus_spent, status, comment, client_tg) VALUES (?, ?, ?, ?, "new", ?, ?)');
    $ins->execute([$userId, $total, $bonusEarned, $bonusSpent, $comment, $clientTg]);
    $orderId = (int)$db->lastInsertId();

    // Insert order items
    $itemIns = $db->prepare('INSERT INTO order_items (order_id, product_name, price, qty) VALUES (?, ?, ?, ?)');
    foreach ($dbItems as $di) {
        $itemIns->execute([$orderId, $di['name'], $di['price'], $di['qty']]);
    }

    // Bonus log: earned
    if ($bonusEarned > 0) {
        $logIns = $db->prepare('INSERT INTO bonus_log (user_id, order_id, amount, type, description) VALUES (?, ?, ?, "earn", ?)');
        $logIns->execute([$userId, $orderId, $bonusEarned, 'Начислено за заказ #' . $orderId . ': ' . implode(', ', $bonusResult['rules'])]);
    }

    // Bonus log: spent (negative amount)
    if ($bonusSpent > 0) {
        $logIns = $db->prepare('INSERT INTO bonus_log (user_id, order_id, amount, type, description) VALUES (?, ?, ?, "spend", ?)');
        $logIns->execute([$userId, $orderId, -$bonusSpent, 'Списано на заказ #' . $orderId]);
    }
}

// ── Telegram ──
function sendTg($token, $chatId, $text) {
    $ch = curl_init("https://api.telegram.org/bot{$token}/sendMessage");
    curl_setopt_array($ch, [
        CURLOPT_POST => true,
        CURLOPT_POSTFIELDS => json_encode(['chat_id' => $chatId, 'text' => $text, 'parse_mode' => 'Markdown']),
        CURLOPT_HTTPHEADER => ['Content-Type: application/json'],
        CURLOPT_RETURNTRANSFER => true,
        CURLOPT_TIMEOUT => 10,
        CURLOPT_SSL_VERIFYPEER => true
    ]);
    $resp = curl_exec($ch);
    $code = curl_getinfo($ch, CURLINFO_HTTP_CODE);
    curl_close($ch);
    return ['resp' => $resp, 'code' => $code, 'result' => json_decode($resp, true)];
}

$tgMsg  = "🛒 *Новая заявка — СплитХаб*\n━━━━━━━━━━━━━━━━━━\n";
$tgMsg .= "👤 *Имя:* {$name}\n📞 *Телефон:* {$phone}\n";
if ($clientTg !== '') $tgMsg .= "💬 *Telegram:* {$clientTg}\n";
$tgMsg .= "📅 *Время:* {$date}\n━━━━━━━━━━━━━━━━━━\n";
$tgMsg .= "📦 *Позиции ({$cnt} шт.):*\n{$tgLines}━━━━━━━━━━━━━━━━━━\n💰 *Итого:* {$totalf} ₽\n";
if ($bonusSpent > 0) $tgMsg .= "🎁 *Списано бонусов:* −" . number_format($bonusSpent, 0, '.', ' ') . " ₽\n";
if ($bonusEarned > 0) $tgMsg .= "⭐ *Начислено бонусов:* +" . number_format($bonusEarned, 0, '.', ' ') . " ₽\n";
if ($orderId) $tgMsg .= "🆔 *Заказ:* #{$orderId}\n";
if ($comment !== '') $tgMsg .= "━━━━━━━━━━━━━━━━━━\n💬 *Комментарий:* " . htmlspecialchars($comment) . "\n";
$tgMsg .= "\n_Клиент ждёт звонка_";

$tgResult = sendTg(BOT_TOKEN, CHAT_ID, $tgMsg);

// ── Email ──
$commentHtml = $comment !== ''
    ? "<div style='padding:14px 24px;background:#fffbeb;border-top:2px solid #F59E0B;'><strong style='color:#92400E;'>💬 Комментарий:</strong><br>" . htmlspecialchars($comment) . "</div>"
    : '';
$emailHtml = '<!DOCTYPE html><html lang="ru"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1"><style>body{margin:0;padding:0;background:#f3f4f6;font-family:Arial,Helvetica,sans-serif}table{border-collapse:collapse}@media(max-width:600px){.wrap{width:100%!important;border-radius:0!important}.pad{padding:14px 12px!important}.hpad{padding:14px 16px!important}}</style></head><body><center><table width="100%" cellpadding="0" cellspacing="0" style="background:#f3f4f6;padding:16px 8px"><tr><td align="center"><table class="wrap" width="600" cellpadding="0" cellspacing="0" style="background:#fff;border-radius:12px;overflow:hidden;max-width:600px;width:100%"><tr><td style="background:#F59E0B;padding:16px 20px"><h2 style="margin:0;color:#fff;font-size:1.1rem">🛒 Новая заявка — СплитХаб</h2></td></tr><tr><td class="pad" style="padding:16px 20px"><table width="100%" cellpadding="0" cellspacing="0" style="margin-bottom:16px"><tr><td style="padding:4px 0;color:#6b7280;font-size:.8rem;width:80px">Клиент</td><td style="padding:4px 0;font-weight:700;font-size:.85rem">' . htmlspecialchars($name) . '</td></tr><tr><td style="padding:4px 0;color:#6b7280;font-size:.8rem">Телефон</td><td style="padding:4px 0;font-weight:700;font-size:.85rem">' . htmlspecialchars($phone) . '</td></tr><tr><td style="padding:4px 0;color:#6b7280;font-size:.8rem">Время</td><td style="padding:4px 0;font-size:.8rem">' . $date . '</td></tr></table><p style="margin:0 0 10px;font-weight:700;color:#374151;font-size:.88rem">Состав заказа (' . $cnt . ' поз.)</p><table width="100%" cellpadding="0" cellspacing="0"><thead><tr style="background:#F59E0B"><th style="padding:8px;text-align:left;color:#fff;font-size:.78rem;font-weight:600;width:24px">#</th><th style="padding:8px;text-align:left;color:#fff;font-size:.78rem;font-weight:600">Наименование</th><th style="padding:8px;text-align:right;color:#fff;font-size:.78rem;font-weight:600;white-space:nowrap">Сумма</th></tr></thead><tbody>' . $htmlRows . '</tbody><tfoot><tr style="background:#FEF3C7"><td colspan="2" style="padding:10px 8px;font-weight:700;font-size:.85rem">Итого</td><td style="padding:10px 8px;font-weight:700;font-size:1rem;color:#D97706;text-align:right;white-space:nowrap">' . $totalf . ' ₽</td></tr></tfoot></table></td></tr>' . ($commentHtml ? '<tr><td style="padding:12px 20px;background:#fffbeb;border-top:2px solid #F59E0B;font-size:.82rem"><strong style="color:#92400E">💬 Комментарий:</strong><br>' . htmlspecialchars($comment) . '</td></tr>' : '') . '<tr><td style="padding:10px 20px;background:#f9fafb;color:#9ca3af;font-size:.72rem">СплитХаб · splithub.ru · Симферополь</td></tr></table></td></tr></table></center></body></html>';
$headers = "From: =?UTF-8?B?" . base64_encode("СплитХаб") . "?= <zakaz@splithub.ru>\r\nMIME-Version: 1.0\r\nContent-Type: text/html; charset=UTF-8\r\n";
$emailSubj = "=?UTF-8?B?" . base64_encode("Новая заявка СплитХаб — {$name} — {$totalf} руб") . "?=";
$mailOk = mail(EMAIL_TO, $emailSubj, $emailHtml, $headers);

// ── Записать rate limit ──
file_put_contents($rateFile, time());

// ── Ответ ──
if ($tgResult['result']['ok'] ?? false) {
    $resp = ['ok' => true, 'email' => $mailOk ? 'sent' : 'failed'];
    if ($orderId) {
        $resp['order_id'] = $orderId;
        $resp['bonus_earned'] = $bonusEarned;
        $resp['bonus_spent'] = $bonusSpent;
    }
    echo json_encode($resp);
} else {
    error_log("[SplitHub] TG error: " . ($tgResult['resp'] ?? ''));
    http_response_code(500);
    echo json_encode(['ok' => false, 'error' => 'Ошибка отправки']);
}
