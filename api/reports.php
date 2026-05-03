<?php
/**
 * reports.php — Отчётность СплитХаб
 *
 * GET  ?action=weekly&secret=CRON_SECRET   — еженедельный отчёт на почту
 * GET  ?action=sheet&secret=CRON_SECRET    — синхронизация заказов в Google Sheets
 * GET  ?action=status&secret=CRON_SECRET   — проверка конфигурации
 * POST (без action)                        — Telegram webhook: /report, /orders, /week
 *
 * Cron на Спринтхосте (раз в неделю, пн 09:00):
 *   0 9 * * 1  curl -s "https://splithub.ru/api/reports.php?action=weekly&secret=CRON_SECRET"
 */

require_once __DIR__ . '/../db/init.php';

// ── Конфиг (дополнить в config.php) ───────────────────────────────────────────
$botToken   = defined('BOT_TOKEN')          ? BOT_TOKEN          : '';
$chatId     = defined('CHAT_ID')            ? CHAT_ID            : '';
$emailTo    = defined('EMAIL_TO')           ? EMAIL_TO           : '';
$cronSecret = defined('CRON_SECRET')        ? CRON_SECRET        : 'change_me';
$sheetId    = defined('GSHEET_ID')          ? GSHEET_ID          : '';   // ID таблицы Google
$saKeyPath  = defined('GSHEET_KEY_PATH')    ? GSHEET_KEY_PATH    : '';   // путь к service-account JSON
$tgAdminId  = defined('TG_ADMIN_ID')        ? TG_ADMIN_ID        : '';   // ваш Telegram user_id

header('Content-Type: application/json; charset=utf-8');

$method = $_SERVER['REQUEST_METHOD'];
$action = $_GET['action'] ?? '';
$secret = $_GET['secret'] ?? '';

// ── Маршрутизация ──────────────────────────────────────────────────────────────

if ($method === 'POST') {
    // Telegram webhook
    handleTelegramWebhook($botToken, $chatId, $tgAdminId);
    exit;
}

if ($method === 'GET') {
    if ($secret !== $cronSecret) {
        http_response_code(403);
        echo json_encode(['ok' => false, 'error' => 'Forbidden']);
        exit;
    }
    switch ($action) {
        case 'weekly': doWeeklyReport($emailTo, $botToken, $chatId); break;
        case 'daily':  doDailyReport($emailTo, $botToken, $chatId); break;
        case 'sheet':  doSheetSync($sheetId, $saKeyPath);            break;
        case 'status': doStatus($sheetId, $saKeyPath, $emailTo);     break;
        default:
            echo json_encode(['ok' => false, 'error' => 'Unknown action']);
    }
    exit;
}

http_response_code(405);
echo json_encode(['ok' => false, 'error' => 'Method not allowed']);
exit;

// ══════════════════════════════════════════════════════════════════════════════
// TELEGRAM WEBHOOK
// ══════════════════════════════════════════════════════════════════════════════

function handleTelegramWebhook($token, $defaultChat, $adminId) {
    $body   = json_decode(file_get_contents('php://input'), true);
    $msg    = $body['message'] ?? $body['channel_post'] ?? null;
    if (!$msg) { echo json_encode(['ok' => true]); return; }

    $chatId = $msg['chat']['id'] ?? '';
    $fromId = $msg['from']['id'] ?? '';
    $text   = trim($msg['text'] ?? '');

    // Только от админа или в разрешённом чате
    $allowed = ($adminId && (string)$fromId === (string)$adminId)
            || (string)$chatId === (string)$defaultChat;
    if (!$allowed) { echo json_encode(['ok' => true]); return; }

    $cmd = strtolower(explode('@', explode(' ', $text)[0])[0]);

    switch ($cmd) {
        case '/report':
        case '/week':
            $text = buildWeeklyText(7);
            tgReply($token, $chatId, $text);
            break;

        case '/orders':
            // Последние 10 заказов
            $text = buildRecentOrdersText(10);
            tgReply($token, $chatId, $text);
            break;

        case '/today':
            $text = buildWeeklyText(1, 'сегодня');
            tgReply($token, $chatId, $text);
            break;

        case '/month':
            $text = buildWeeklyText(30, 'за 30 дней');
            tgReply($token, $chatId, $text);
            break;

        case '/help':
            tgReply($token, $chatId,
                "📊 *Команды отчётности СплитХаб:*\n"
                . "/report — недельный отчёт\n"
                . "/today  — статистика сегодня\n"
                . "/month  — за 30 дней\n"
                . "/orders — последние 10 заказов\n"
                . "/help   — эта справка"
            );
            break;
    }

    echo json_encode(['ok' => true]);
}

// ══════════════════════════════════════════════════════════════════════════════
// REPORT BUILDERS
// ══════════════════════════════════════════════════════════════════════════════

function buildWeeklyText($days = 7, $label = null) {
    if (!$label) $label = "за {$days} дней";
    try {
        $db   = getDB();
        $from = date('Y-m-d H:i:s', strtotime("-{$days} days"));

        $row = $db->prepare("SELECT COUNT(*) as cnt, COALESCE(SUM(total),0) as sum
                             FROM orders WHERE created_at >= ?");
        $row->execute([$from]);
        $stat = $row->fetch();

        $gRow = $db->prepare("SELECT COUNT(*) as cnt, COALESCE(SUM(total),0) as sum
                              FROM guest_orders WHERE created_at >= ?");
        $gRow->execute([$from]);
        $gStat = $gRow->fetch();

        $total = (int)$stat['sum'] + (int)$gStat['sum'];
        $count = (int)$stat['cnt'] + (int)$gStat['cnt'];
        $avgOrd = $count > 0 ? (int)round($total / $count) : 0;

        // Топ товаров
        $top = $db->prepare("
            SELECT oi.product_name, SUM(oi.qty) as total_qty, SUM(oi.price*oi.qty) as total_sum
            FROM order_items oi
            JOIN orders o ON o.id = oi.order_id
            WHERE o.created_at >= ?
            GROUP BY oi.product_name
            ORDER BY total_sum DESC LIMIT 5
        ");
        $top->execute([$from]);
        $topItems = $top->fetchAll();

        $dt = date('d.m.Y');
        $text  = "📊 *Отчёт СплитХаб — {$label}* (на {$dt})\n";
        $text .= "━━━━━━━━━━━━━━━━━━\n";
        $text .= "📦 Заказов: *{$count}*\n";
        $text .= "💰 Выручка: *" . number_format($total, 0, '.', ' ') . " ₽*\n";
        $text .= "📐 Средний чек: *" . number_format($avgOrd, 0, '.', ' ') . " ₽*\n";

        if ($topItems) {
            $text .= "━━━━━━━━━━━━━━━━━━\n🔥 *Топ позиций:*\n";
            foreach ($topItems as $i => $it) {
                $text .= ($i+1) . ". " . mb_substr($it['product_name'], 0, 35)
                      . " — " . number_format($it['total_sum'], 0, '.', ' ') . " ₽\n";
            }
        }
        return $text;
    } catch (Throwable $e) {
        return "❌ Ошибка формирования отчёта: " . $e->getMessage();
    }
}

function buildRecentOrdersText($limit = 10) {
    try {
        $db    = getDB();
        $orders = $db->prepare("
            SELECT o.id, o.total, o.status, o.created_at, u.name, u.phone
            FROM orders o JOIN users u ON u.id = o.user_id
            ORDER BY o.created_at DESC LIMIT ?
        ");
        $orders->execute([$limit]);
        $list = $orders->fetchAll();

        if (!$list) return "📭 Заказов пока нет.";

        $statusMap = ['new'=>'🆕','confirmed'=>'✅','in_progress'=>'⚙️','shipped'=>'🚚','completed'=>'✔️','cancelled'=>'❌'];
        $text = "📋 *Последние {$limit} заказов:*\n━━━━━━━━━━━━━━━━━━\n";
        foreach ($list as $o) {
            $s   = $statusMap[$o['status']] ?? '❓';
            $dt  = date('d.m H:i', strtotime($o['created_at']));
            $shNum = 'SH-' . str_pad($o['id'], 5, '0', STR_PAD_LEFT);
            $text .= "{$s} *{$shNum}* · {$dt}\n"
                  . "   {$o['name']} · " . number_format($o['total'], 0, '.', ' ') . " ₽\n";
        }
        return $text;
    } catch (Throwable $e) {
        return "❌ Ошибка: " . $e->getMessage();
    }
}

// ══════════════════════════════════════════════════════════════════════════════
// WEEKLY EMAIL REPORT
// ══════════════════════════════════════════════════════════════════════════════

function doWeeklyReport($emailTo, $botToken, $chatId) {
    $tgText = buildWeeklyText(7);

    // Email
    $emailSent = false;
    if ($emailTo) {
        $subject = 'Недельный отчёт СплитХаб — ' . date('d.m.Y');
        $body    = nl2br(htmlspecialchars(strip_tags($tgText, '<br>')));
        $headers = "MIME-Version: 1.0\r\nContent-Type: text/html; charset=utf-8\r\nFrom: СплитХаб <noreply@splithub.ru>";
        $emailSent = mail($emailTo, $subject, "<html><body style='font-family:Arial,sans-serif'>{$body}</body></html>", $headers);
    }

    // Telegram
    $tgSent = false;
    if ($botToken && $chatId) {
        $tgSent = tgSend($botToken, $chatId, $tgText);
    }

    echo json_encode(['ok' => true, 'email' => $emailSent, 'telegram' => $tgSent,
                      'report_preview' => mb_substr($tgText, 0, 200)]);
}

// ══════════════════════════════════════════════════════════════════════════════
// DAILY DIGEST
// ══════════════════════════════════════════════════════════════════════════════

function buildDailyText() {
    try {
        $db   = getDB();
        $from = date('Y-m-d') . ' 00:00:00';

        $row = $db->prepare("SELECT COUNT(*) as cnt, COALESCE(SUM(total),0) as sum FROM orders WHERE created_at >= ?");
        $row->execute([$from]);
        $stat = $row->fetch();

        $gRow = $db->prepare("SELECT COUNT(*) as cnt, COALESCE(SUM(total),0) as sum FROM guest_orders WHERE created_at >= ?");
        $gRow->execute([$from]);
        $gStat = $gRow->fetch();

        $total      = (int)$stat['sum'] + (int)$gStat['sum'];
        $orderCount = (int)$stat['cnt'] + (int)$gStat['cnt'];

        $clients = $db->prepare("SELECT COUNT(DISTINCT user_id) as cnt FROM orders WHERE created_at >= ?");
        $clients->execute([$from]);
        $clientCount = (int)$clients->fetch()['cnt'];

        $dt    = date('d.m.Y');
        $text  = "📅 *Дайджест СплитХаб — {$dt}*\n";
        $text .= "━━━━━━━━━━━━━━━━━━\n";
        $text .= "📦 Заказов за день: *{$orderCount}*\n";
        $text .= "💰 Выручка: *" . number_format($total, 0, '.', ' ') . " ₽*\n";
        $text .= "👤 Клиентов: *{$clientCount}*\n";

        if ($orderCount === 0) {
            $text .= "\n_Заказов сегодня не было._";
        }

        return $text;
    } catch (Throwable $e) {
        return "❌ Ошибка дайджеста: " . $e->getMessage();
    }
}

function doDailyReport($emailTo, $botToken, $chatId) {
    $tgText = buildDailyText();

    $tgSent = false;
    if ($botToken && $chatId) {
        $tgSent = tgSend($botToken, $chatId, $tgText);
    }

    $emailSent = false;
    if ($emailTo) {
        $subject = 'Дайджест СплитХаб — ' . date('d.m.Y');
        $body    = str_replace(['*', '_'], '', $tgText);
        $body    = nl2br(htmlspecialchars($body));
        $headers = "MIME-Version: 1.0\r\nContent-Type: text/html; charset=utf-8\r\n"
                 . "From: =?UTF-8?B?" . base64_encode('СплитХаб') . "?= <noreply@splithub.ru>";
        $emailSent = mail($emailTo, '=?UTF-8?B?' . base64_encode($subject) . '?=',
            "<html><body style='font-family:Arial,sans-serif;line-height:1.8;padding:20px'>{$body}</body></html>",
            $headers);
    }

    echo json_encode(['ok' => true, 'telegram' => $tgSent, 'email' => $emailSent,
                      'preview' => mb_substr($tgText, 0, 200)], JSON_UNESCAPED_UNICODE);
}

// ══════════════════════════════════════════════════════════════════════════════
// GOOGLE SHEETS SYNC
// ══════════════════════════════════════════════════════════════════════════════

function doSheetSync($sheetId, $saKeyPath) {
    if (!$sheetId || !$saKeyPath || !file_exists($saKeyPath)) {
        echo json_encode(['ok' => false, 'error' => 'Google Sheets не настроен. Укажите GSHEET_ID и GSHEET_KEY_PATH в config.php']);
        return;
    }

    try {
        $db = getDB();

        // Берём заказы, которые ещё не синхронизированы (нет записи в sheets_log)
        $db->exec('CREATE TABLE IF NOT EXISTS sheets_log (order_id INTEGER PRIMARY KEY, synced_at TEXT)');

        $orders = $db->query("
            SELECT o.id, o.total, o.status, o.created_at, u.name, u.phone, u.telegram
            FROM orders o JOIN users u ON u.id = o.user_id
            WHERE o.id NOT IN (SELECT order_id FROM sheets_log)
            ORDER BY o.id ASC LIMIT 100
        ")->fetchAll();

        if (!$orders) {
            echo json_encode(['ok' => true, 'synced' => 0, 'message' => 'Нет новых заказов для синхронизации']);
            return;
        }

        $token  = getGoogleAccessToken($saKeyPath);
        $synced = 0;

        foreach ($orders as $o) {
            // Получаем позиции
            $items = $db->prepare('SELECT product_name, qty, price FROM order_items WHERE order_id = ?');
            $items->execute([$o['id']]);
            $itemsList = $items->fetchAll();
            $itemsStr  = implode('; ', array_map(function($it){
                return $it['product_name'] . ' ×' . $it['qty'];
            }, $itemsList));

            $shNum = 'SH-' . str_pad($o['id'], 5, '0', STR_PAD_LEFT);
            $row   = [
                [$shNum, $o['created_at'], $o['name'], $o['phone'], $o['telegram'],
                 $itemsStr, (int)$o['total'], $o['status']]
            ];

            $appended = appendToSheet($token, $sheetId, $row);
            if ($appended) {
                $db->prepare('INSERT OR IGNORE INTO sheets_log (order_id, synced_at) VALUES (?, ?)')
                   ->execute([$o['id'], date('Y-m-d H:i:s')]);
                $synced++;
            }
        }

        echo json_encode(['ok' => true, 'synced' => $synced]);

    } catch (Throwable $e) {
        echo json_encode(['ok' => false, 'error' => $e->getMessage()]);
    }
}

function getGoogleAccessToken($keyPath) {
    $key = json_decode(file_get_contents($keyPath), true);
    if (!$key) throw new \Exception('Ошибка чтения service account JSON');

    $now = time();
    $header  = base64url_encode(json_encode(['alg' => 'RS256', 'typ' => 'JWT']));
    $payload = base64url_encode(json_encode([
        'iss'   => $key['client_email'],
        'scope' => 'https://www.googleapis.com/auth/spreadsheets',
        'aud'   => 'https://oauth2.googleapis.com/token',
        'iat'   => $now,
        'exp'   => $now + 3600,
    ]));

    $toSign = $header . '.' . $payload;
    openssl_sign($toSign, $sig, $key['private_key'], 'SHA256');
    $jwt = $toSign . '.' . base64url_encode($sig);

    $ch = curl_init('https://oauth2.googleapis.com/token');
    curl_setopt_array($ch, [
        CURLOPT_POST           => true,
        CURLOPT_POSTFIELDS     => http_build_query(['grant_type' => 'urn:ietf:params:oauth:grant-type:jwt-bearer', 'assertion' => $jwt]),
        CURLOPT_RETURNTRANSFER => true,
        CURLOPT_SSL_VERIFYPEER => false,
    ]);
    $resp   = json_decode(curl_exec($ch), true);
    curl_close($ch);

    if (empty($resp['access_token'])) throw new \Exception('Не удалось получить Google токен: ' . json_encode($resp));
    return $resp['access_token'];
}

function appendToSheet($token, $sheetId, $rows) {
    $url = "https://sheets.googleapis.com/v4/spreadsheets/{$sheetId}/values/A1:append?valueInputOption=USER_ENTERED&insertDataOption=INSERT_ROWS";
    $ch  = curl_init($url);
    curl_setopt_array($ch, [
        CURLOPT_POST           => true,
        CURLOPT_POSTFIELDS     => json_encode(['values' => $rows]),
        CURLOPT_HTTPHEADER     => ["Authorization: Bearer {$token}", 'Content-Type: application/json'],
        CURLOPT_RETURNTRANSFER => true,
        CURLOPT_SSL_VERIFYPEER => false,
    ]);
    $resp = json_decode(curl_exec($ch), true);
    curl_close($ch);
    return isset($resp['updates']);
}

function base64url_encode($data) {
    return rtrim(strtr(base64_encode($data), '+/', '-_'), '=');
}

// ══════════════════════════════════════════════════════════════════════════════
// STATUS CHECK
// ══════════════════════════════════════════════════════════════════════════════

function doStatus($sheetId, $saKeyPath, $emailTo) {
    echo json_encode([
        'ok'            => true,
        'email_to'      => $emailTo ?: '❌ не настроен (EMAIL_TO)',
        'gsheet_id'     => $sheetId ?: '❌ не настроен (GSHEET_ID)',
        'gsheet_key'    => ($saKeyPath && file_exists($saKeyPath)) ? '✅ найден' : '❌ не найден (GSHEET_KEY_PATH)',
        'telegram_bot'  => defined('BOT_TOKEN') ? '✅ ' . substr(BOT_TOKEN, 0, 10) . '...' : '❌',
        'webhook_url'   => 'https://splithub.ru/api/reports.php',
        'cron_example'  => '0 9 * * 1 curl -s "https://splithub.ru/api/reports.php?action=weekly&secret=' . CRON_SECRET . '"',
    ]);
}

// ══════════════════════════════════════════════════════════════════════════════
// TELEGRAM HELPERS
// ══════════════════════════════════════════════════════════════════════════════

function tgSend($token, $chatId, $text) {
    $ch = curl_init("https://api.telegram.org/bot{$token}/sendMessage");
    curl_setopt_array($ch, [
        CURLOPT_POST           => true,
        CURLOPT_POSTFIELDS     => json_encode(['chat_id' => $chatId, 'text' => $text, 'parse_mode' => 'Markdown']),
        CURLOPT_HTTPHEADER     => ['Content-Type: application/json'],
        CURLOPT_RETURNTRANSFER => true,
        CURLOPT_TIMEOUT        => 10,
        CURLOPT_SSL_VERIFYPEER => false,
    ]);
    $resp = json_decode(curl_exec($ch), true);
    curl_close($ch);
    return $resp['ok'] ?? false;
}

function tgReply($token, $chatId, $text) {
    return tgSend($token, $chatId, $text);
}
