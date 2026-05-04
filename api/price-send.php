<?php
/**
 * price-send.php — Отправка прайса в Telegram и Email
 */

header('Content-Type: application/json; charset=utf-8');
header('Access-Control-Allow-Origin: *');
header('Access-Control-Allow-Methods: POST');
header('Access-Control-Allow-Headers: Content-Type');

if ($_SERVER['REQUEST_METHOD'] === 'OPTIONS') {
    http_response_code(200);
    exit;
}

if ($_SERVER['REQUEST_METHOD'] !== 'POST') {
    http_response_code(405);
    exit;
}

require_once __DIR__ . '/../config.php';

$raw  = file_get_contents('php://input');
$data = json_decode($raw, true);

if (!$data) {
    http_response_code(400);
    echo json_encode(['ok' => false, 'error' => 'Bad JSON']);
    exit;
}

$method   = trim($data['method'] ?? ''); // 'tg', 'email'
$email    = trim($data['email'] ?? '');
$itemsCount = intval($data['items_count'] ?? 0);

if (!$method || !in_array($method, ['tg', 'email'])) {
    http_response_code(422);
    echo json_encode(['ok' => false, 'error' => 'Invalid method']);
    exit;
}

$date = date('d.m.Y H:i', time() + 3 * 3600);

if ($method === 'tg') {
    $msg = "📥 *Запрос на прайс*\n";
    $msg .= "━━━━━━━━━━━━━━━━━━\n";
    $msg .= "📅 *Дата:* {$date}\n";
    $msg .= "📦 *Товаров в прайсе:* {$itemsCount} шт.\n";
    $msg .= "━━━━━━━━━━━━━━━━━━\n";
    $msg .= "_Прайс-лист доступен на сайте СплитХаб_";

    $ch = curl_init("https://api.telegram.org/bot" . BOT_TOKEN . "/sendMessage");
    curl_setopt_array($ch, [
        CURLOPT_POST           => true,
        CURLOPT_POSTFIELDS     => json_encode([
            'chat_id'    => CHAT_ID,
            'text'       => $msg,
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

    $result = json_decode($resp, true);
    $ok = $result['ok'] ?? false;

    if ($ok) {
        echo json_encode(['ok' => true, 'message' => 'Отправлено в Telegram']);
    } else {
        http_response_code(500);
        echo json_encode(['ok' => false, 'error' => 'Telegram error']);
    }
}
elseif ($method === 'email') {
    if (!filter_var($email, FILTER_VALIDATE_EMAIL)) {
        http_response_code(422);
        echo json_encode(['ok' => false, 'error' => 'Invalid email']);
        exit;
    }

    $headers   = "From: =?UTF-8?B?" . base64_encode("СплитХаб") . "?= <zakaz@splithub.ru>\r\n";
    $headers  .= "MIME-Version: 1.0\r\n";
    $headers  .= "Content-Type: text/html; charset=UTF-8\r\n";
    $subject   = "=?UTF-8?B?" . base64_encode("Прайс-лист СплитХаб") . "?=";

    $htmlBody = "<!DOCTYPE html><html lang=\"ru\"><head>"
        . "<meta charset=\"UTF-8\">"
        . "<style>body { font-family: Arial; background: #f3f4f6; }"
        . ".wrap { max-width: 600px; margin: 16px auto; background: #fff; border-radius: 12px; padding: 20px; }"
        . ".title { color: #F59E0B; font-size: 20px; margin-bottom: 10px; }"
        . ".text { color: #666; font-size: 14px; line-height: 1.6; }"
        . "a { color: #2563eb; text-decoration: none; }"
        . "</style></head><body>"
        . "<div class=\"wrap\">"
        . "<h1 class=\"title\">📥 Прайс-лист СплитХаб</h1>"
        . "<p class=\"text\">Здравствуйте!</p>"
        . "<p class=\"text\">Спасибо за интерес к нашему каталогу. Прайс-лист содержит <strong>{$itemsCount} товаров</strong> с актуальными ценами и статусом наличия на <strong>{$date}</strong>.</p>"
        . "<p class=\"text\"><a href=\"https://splithub.ru\">Откройте полный прайс на сайте</a></p>"
        . "<p class=\"text\">При возникновении вопросов свяжитесь с менеджерами:<br>"
        . "📞 +7 978 599-13-69<br>"
        . "💬 @Byttehnikaopt</p>"
        . "<p class=\"text\" style=\"color: #999; font-size: 12px; margin-top: 20px;\">СплитХаб · splithub.ru · Симферополь</p>"
        . "</div></body></html>";

    $mailOk = @mail($email, $subject, $htmlBody, $headers);

    if ($mailOk) {
        echo json_encode(['ok' => true, 'message' => 'Письмо отправлено']);
    } else {
        http_response_code(500);
        echo json_encode(['ok' => false, 'error' => 'Email send failed']);
    }
}
