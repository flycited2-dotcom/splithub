<?php
/**
 * send.php — СплитХаб
 * База: рабочий Desktop send.php (идентичная логика TG).
 * Вторичные функции (DB, email, bonus) изолированы в try/catch.
 */

// ── Credentials (идентично Desktop send.php) ──
define('BOT_TOKEN', '8366074996:AAGe0oEpkQ4foTlcJ0zqNFxUv5w1i1Xay78');
define('CHAT_ID',   '-1003727076862');
define('EMAIL_TO',  'flycited@gmail.com');

header('Content-Type: application/json; charset=utf-8');
header('Access-Control-Allow-Origin: *');
header('Access-Control-Allow-Methods: POST');
header('Access-Control-Allow-Headers: Content-Type');
if ($_SERVER['REQUEST_METHOD'] === 'OPTIONS') { http_response_code(200); exit; }
if ($_SERVER['REQUEST_METHOD'] !== 'POST')    { http_response_code(405); exit; }

$raw  = file_get_contents('php://input');
$data = json_decode($raw, true);
if (!$data) { http_response_code(400); echo json_encode(['ok' => false, 'error' => 'Bad JSON']); exit; }

$name     = trim($data['name']     ?? '');
$phone    = trim($data['phone']    ?? '');
$comment  = trim($data['comment']  ?? '');
$clientTg = trim($data['client_tg'] ?? '');
$items    = $data['items'] ?? [];

if (!$name || !$phone || empty($items)) {
    http_response_code(422);
    echo json_encode(['ok' => false, 'error' => 'Заполните все поля']);
    exit;
}

$date  = date('d.m.Y H:i', time() + 3 * 3600);
$total = 0;
$num   = 1;
$tgLines  = '';
$htmlRows = '';

foreach ($items as $item) {
    $n   = htmlspecialchars($item['name'] ?? '—');
    $p   = intval($item['price'] ?? 0);
    $qty = intval($item['qty']   ?? 1);
    $sub = $p * $qty;
    $total += $sub;
    $pf  = number_format($p,   0, '.', ' ');
    $sf  = number_format($sub, 0, '.', ' ');
    $itemBrand = trim($item['brand'] ?? '');
    $itemName  = trim($item['name']  ?? '—');
    $displayName = ($itemBrand !== '' && mb_strpos($itemName, $itemBrand) === false)
        ? $itemBrand . ' ' . $itemName
        : $itemName;
    $tgLines  .= "  {$num}. {$displayName} — {$pf} ₽ × {$qty} шт. = {$sf} ₽\n";
    $htmlRows .= "<tr>"
        . "<td style='padding:8px 12px;border-bottom:1px solid #eee'>{$num}</td>"
        . "<td style='padding:8px 12px;border-bottom:1px solid #eee'>{$n}</td>"
        . "<td style='padding:8px 12px;border-bottom:1px solid #eee;text-align:right'>{$pf} ₽</td>"
        . "<td style='padding:8px 12px;border-bottom:1px solid #eee;text-align:center'>{$qty}</td>"
        . "<td style='padding:8px 12px;border-bottom:1px solid #eee;font-weight:700;color:#D97706;text-align:right'>{$sf} ₽</td>"
        . "</tr>";
    $num++;
}
$totalf = number_format($total, 0, '.', ' ');
$cnt    = count($items);

// ── Telegram (идентично Desktop send.php) ──
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
    curl_close($ch);
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

// ── Вторичные функции (сбой не влияет на ответ) ──

$orderId     = null;
$bonusEarned = 0;
$bonusSpent  = 0;
$guestSaved  = false;

try {
    $dbFile = __DIR__ . '/db/init.php';
    if (file_exists($dbFile)) {
        require_once $dbFile;
        $userId = authCheck();

        if ($userId) {
            $db         = getDB();
            $bonusSpent = max(0, intval($data['bonus_spend'] ?? 0));
            if ($bonusSpent > 0) {
                $s = $db->prepare('SELECT COALESCE(SUM(amount),0) as b FROM bonus_log WHERE user_id=?');
                $s->execute([$userId]);
                $bal = (int)$s->fetch()['b'];
                if ($bonusSpent > $bal)   $bonusSpent = $bal;
                if ($bonusSpent > $total) $bonusSpent = $total;
            }
            $dbItems = array_map(function($i) {
                return ['id' => strval($i['id'] ?? ''), 'name' => $i['name'] ?? '—',
                        'price' => intval($i['price'] ?? 0),
                        'qty'  => max(1, intval($i['qty'] ?? 1)), 'group' => $i['group'] ?? ''];
            }, $items);
            // Начисление бонусов временно отключено
            $bonusEarned = 0;

            $ins = $db->prepare('INSERT INTO orders (user_id,total,bonus_earned,bonus_spent,status,comment,client_tg) VALUES (?,?,?,?,"new",?,?)');
            $ins->execute([$userId, $total, $bonusEarned, $bonusSpent, $comment, $clientTg]);
            $orderId = (int)$db->lastInsertId();

            $ii = $db->prepare('INSERT INTO order_items (order_id,product_name,price,qty,product_id) VALUES (?,?,?,?,?)');
            foreach ($dbItems as $di) $ii->execute([$orderId, $di['name'], $di['price'], $di['qty'], $di['id']]);

            if ($bonusEarned > 0)
                $db->prepare('INSERT INTO bonus_log (user_id,order_id,amount,type,description) VALUES (?,?,?,"earn",?)')->execute([$userId, $orderId, $bonusEarned, 'Заказ #'.$orderId]);
            if ($bonusSpent > 0)
                $db->prepare('INSERT INTO bonus_log (user_id,order_id,amount,type,description) VALUES (?,?,?,"spend",?)')->execute([$userId, $orderId, -$bonusSpent, 'Списано на заказ #'.$orderId]);
        } else {
            // Гостевой заказ
            $db = getDB();
            $db->exec('CREATE TABLE IF NOT EXISTS guest_orders (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL, phone TEXT NOT NULL, total INTEGER NOT NULL DEFAULT 0, items_json TEXT NOT NULL DEFAULT "[]", comment TEXT DEFAULT "", client_tg TEXT DEFAULT "", created_at TEXT DEFAULT CURRENT_TIMESTAMP)');
            $db->prepare('INSERT INTO guest_orders (name,phone,total,items_json,comment,client_tg) VALUES (?,?,?,?,?,?)')->execute([$name, $phone, $total, json_encode($items, JSON_UNESCAPED_UNICODE), $comment, $clientTg]);
            $guestSaved = true;
        }
    }
} catch (Throwable $e) {
    error_log('[SplitHub DB] ' . $e->getMessage());
}

// ── Email (мобильно-адаптивная версия) ──
// Строки товаров — мобильно-адаптивная карточка
$emailItems = '';
foreach ($items as $eit) {
    $en   = htmlspecialchars(trim($eit['name'] ?? '—'));
    $eb   = htmlspecialchars(trim($eit['brand'] ?? ''));
    $ep   = intval($eit['price'] ?? 0);
    $eq   = max(1, intval($eit['qty'] ?? 1));
    $es   = $ep * $eq;
    $epf  = number_format($ep, 0, '.', ' ');
    $esf  = number_format($es, 0, '.', ' ');
    $fullName = ($eb && mb_strpos($en, $eb) === false) ? $eb . ' ' . $en : $en;
    $emailItems .= '<tr>'
        . '<td style="padding:10px 12px;border-bottom:1px solid #f0f0f0;vertical-align:top">'
        . '<div style="font-size:0.84rem;font-weight:600;color:#1f2937;line-height:1.4;word-break:break-word">' . $fullName . '</div>'
        . '<div style="font-size:0.78rem;color:#6b7280;margin-top:3px">' . $epf . '&nbsp;₽&nbsp;&times;&nbsp;' . $eq . '&nbsp;шт.</div>'
        . '</td>'
        . '<td style="padding:10px 12px;border-bottom:1px solid #f0f0f0;vertical-align:top;text-align:right;white-space:nowrap;font-weight:700;color:#D97706;font-size:0.88rem">' . $esf . '&nbsp;₽</td>'
        . '</tr>';
}
$commentBlock = $comment !== ''
    ? '<tr><td colspan="2" style="padding:10px 12px;background:#fffbeb;border-top:2px solid #F59E0B;font-size:0.82rem"><strong style="color:#92400E">Комментарий:</strong> ' . htmlspecialchars($comment) . '</td></tr>'
    : '';

$emailHtml = '<!DOCTYPE html><html lang="ru"><head>'
    . '<meta charset="UTF-8">'
    . '<meta name="viewport" content="width=device-width,initial-scale=1">'
    . '<style>'
    . 'body{margin:0;padding:0;background:#f3f4f6;font-family:Arial,Helvetica,sans-serif;-webkit-text-size-adjust:100%}'
    . '.wrap{max-width:600px;margin:16px auto;background:#fff;border-radius:12px;overflow:hidden}'
    . '.hdr{background:#F59E0B;padding:16px 18px}'
    . '.hdr h2{margin:0;color:#fff;font-size:1rem;font-weight:700}'
    . '.meta{padding:14px 18px}'
    . '.meta table{width:100%;border-collapse:collapse}'
    . '.meta td{padding:4px 0;font-size:0.82rem;vertical-align:top}'
    . '.meta .lbl{color:#6b7280;width:80px}'
    . '.meta .val{font-weight:700;color:#1f2937}'
    . '.items{padding:0 18px 14px}'
    . '.items h3{margin:0 0 8px;font-size:0.85rem;color:#374151}'
    . '.items table{width:100%;border-collapse:collapse}'
    . '.items thead tr{background:#F59E0B}'
    . '.items thead th{padding:7px 12px;color:#fff;font-size:0.78rem;font-weight:600;text-align:left}'
    . '.items thead th:last-child{text-align:right}'
    . '.tot td{padding:9px 12px;font-weight:700;background:#FEF3C7}'
    . '.tot .sum{text-align:right;color:#D97706;font-size:0.95rem}'
    . '.ftr{padding:10px 18px;background:#f9fafb;color:#9ca3af;font-size:0.72rem}'
    . '@media(max-width:480px){'
    . '.wrap{margin:0;border-radius:0}'
    . '.hdr{padding:12px 14px}'
    . '.meta{padding:10px 14px}'
    . '.items{padding:0 14px 12px}'
    . '.ftr{padding:8px 14px}'
    . '}'
    . '</style></head>'
    . '<body><div class="wrap">'
    . '<div class="hdr"><h2>🛒 Новая заявка — СплитХаб</h2></div>'
    . '<div class="meta"><table>'
    . '<tr><td class="lbl">Клиент</td><td class="val">' . htmlspecialchars($name) . '</td></tr>'
    . '<tr><td class="lbl">Телефон</td><td class="val">' . htmlspecialchars($phone) . '</td></tr>'
    . ($clientTg !== '' ? '<tr><td class="lbl">Telegram</td><td class="val">' . htmlspecialchars($clientTg) . '</td></tr>' : '')
    . '<tr><td class="lbl">Время</td><td class="val" style="font-weight:400">' . $date . '</td></tr>'
    . '</table></div>'
    . '<div class="items"><h3>Состав заказа (' . $cnt . ' поз.)</h3>'
    . '<table>'
    . '<thead><tr><th>Наименование</th><th>Сумма</th></tr></thead>'
    . '<tbody>' . $emailItems . $commentBlock . '</tbody>'
    . '<tfoot><tr class="tot"><td>Итого</td><td class="sum">' . $totalf . '&nbsp;₽</td></tr></tfoot>'
    . '</table></div>'
    . '<div class="ftr">СплитХаб · splithub.ru · Симферополь</div>'
    . '</div></body></html>';

$headers   = "From: =?UTF-8?B?" . base64_encode("СплитХаб") . "?= <zakaz@splithub.ru>\r\n";
$headers  .= "MIME-Version: 1.0\r\n";
$headers  .= "Content-Type: text/html; charset=UTF-8\r\n";
$emailSubj = "=?UTF-8?B?" . base64_encode("Новая заявка СплитХаб — {$name} — {$totalf} руб") . "?=";
$mailOk    = @mail(EMAIL_TO, $emailSubj, $emailHtml, $headers);

error_log('[SplitHub] tg=' . ($tgOk?'ok':'FAIL:'.($tgResult['resp']??'')) . ' mail=' . ($mailOk?'ok':'fail') . ' order=' . ($orderId??'null') . ' guest=' . ($guestSaved?'yes':'no'));

// ── Ответ ──
if ($tgOk || $orderId || $guestSaved) {
    $resp = ['ok' => true, 'email' => $mailOk ? 'sent' : 'failed', 'tg' => $tgOk ? 'sent' : 'failed'];
    if ($orderId)     $resp['order_id']     = $orderId;
    if ($bonusEarned) $resp['bonus_earned'] = $bonusEarned;
    if ($bonusSpent)  $resp['bonus_spent']  = $bonusSpent;
    echo json_encode($resp);
} else {
    error_log('[SplitHub] TG error: ' . ($tgResult['resp'] ?? ''));
    http_response_code(500);
    echo json_encode(['ok' => false, 'error' => 'Ошибка отправки. Позвоните: +7 978 599-13-69']);
}
