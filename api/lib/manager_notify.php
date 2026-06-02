<?php

function mobileOrderNumber(int $orderId): string {
    return 'SH-' . str_pad((string)$orderId, 5, '0', STR_PAD_LEFT);
}

function mobileOrderMoney(int $amount): string {
    return number_format($amount, 0, '.', ' ');
}

function mobileOrderHtmlMoney(int $amount): string {
    return str_replace(' ', '&nbsp;', mobileOrderMoney($amount));
}

function mobileOrderTelegramEscape(string $value): string {
    return htmlspecialchars($value, ENT_QUOTES | ENT_SUBSTITUTE, 'UTF-8');
}

function mobileOrderItemName(array $item): string {
    $brand = trim((string)($item['brand'] ?? ''));
    $name = trim((string)($item['name'] ?? '—'));
    if ($brand !== '' && mb_strpos($name, $brand) === false) {
        return $brand . ' ' . $name;
    }
    return $name;
}

function mobileOrderTelegramText(
    int $orderId,
    string $name,
    string $phone,
    array $items,
    int $total,
    string $comment = '',
    string $clientTg = '',
    ?string $date = null
): string {
    $date ??= date('d.m.Y H:i', time() + 3 * 3600);
    $lines = '';
    $num = 1;
    foreach ($items as $item) {
        $price = (int)($item['price'] ?? 0);
        $qty = max(1, (int)($item['qty'] ?? 1));
        $subtotal = $price * $qty;
        $lines .= sprintf(
            "  %d. %s — %s ₽ × %d шт. = %s ₽\n",
            $num++,
            mobileOrderTelegramEscape(mobileOrderItemName($item)),
            mobileOrderMoney($price),
            $qty,
            mobileOrderMoney($subtotal)
        );
    }

    $text  = "🛒 <b>Новая заявка — СплитХаб</b>\n";
    $text .= "━━━━━━━━━━━━━━━━━━\n";
    $text .= "🧾 <b>Номер:</b> " . mobileOrderNumber($orderId) . "\n";
    $text .= "👤 <b>Имя:</b> " . mobileOrderTelegramEscape($name) . "\n";
    $text .= "📞 <b>Телефон:</b> " . mobileOrderTelegramEscape($phone) . "\n";
    if ($clientTg !== '') {
        $text .= "💬 <b>Telegram:</b> " . mobileOrderTelegramEscape($clientTg) . "\n";
    }
    $text .= "📅 <b>Время:</b> " . mobileOrderTelegramEscape($date) . "\n";
    $text .= "━━━━━━━━━━━━━━━━━━\n";
    $text .= "📦 <b>Позиции (" . count($items) . " шт.):</b>\n{$lines}";
    $text .= "━━━━━━━━━━━━━━━━━━\n";
    $text .= "💰 <b>Итого:</b> " . mobileOrderMoney($total) . " ₽\n";
    if ($comment !== '') {
        $text .= "━━━━━━━━━━━━━━━━━━\n💬 <b>Комментарий:</b> " . mobileOrderTelegramEscape($comment) . "\n";
    }
    $text .= "\n<i>Клиент ждёт звонка</i>";

    return $text;
}

function mobileOrderReplyMarkup(int $orderId): array {
    return ['inline_keyboard' => [[
        ['text' => '✅ Подтвердить', 'callback_data' => 'st:confirmed:' . $orderId],
        ['text' => '❌ Отменить', 'callback_data' => 'st:cancelled:' . $orderId],
    ]]];
}

function mobileOrderEmailHtml(
    int $orderId,
    string $name,
    string $phone,
    array $items,
    int $total,
    string $comment = '',
    string $clientTg = '',
    ?string $date = null
): string {
    $date ??= date('d.m.Y H:i', time() + 3 * 3600);
    $rows = '';
    foreach ($items as $item) {
        $itemName = htmlspecialchars(mobileOrderItemName($item), ENT_QUOTES, 'UTF-8');
        $price = (int)($item['price'] ?? 0);
        $qty = max(1, (int)($item['qty'] ?? 1));
        $subtotal = $price * $qty;
        $rows .= '<tr>'
            . '<td style="padding:10px 12px;border-bottom:1px solid #f0f0f0">'
            . '<div style="font-weight:700;color:#1f2937">' . $itemName . '</div>'
            . '<div style="font-size:12px;color:#6b7280;margin-top:3px">' . mobileOrderHtmlMoney($price) . '&nbsp;₽ × ' . $qty . '&nbsp;шт.</div>'
            . '</td>'
            . '<td style="padding:10px 12px;border-bottom:1px solid #f0f0f0;text-align:right;font-weight:700;color:#D97706;white-space:nowrap">'
            . mobileOrderHtmlMoney($subtotal) . '&nbsp;₽</td>'
            . '</tr>';
    }
    $commentRow = $comment !== ''
        ? '<tr><td colspan="2" style="padding:10px 12px;background:#fffbeb;border-top:2px solid #F59E0B"><strong>Комментарий:</strong> ' . htmlspecialchars($comment, ENT_QUOTES, 'UTF-8') . '</td></tr>'
        : '';
    $clientTgRow = $clientTg !== ''
        ? '<tr><td style="color:#6b7280">Telegram</td><td style="font-weight:700">' . htmlspecialchars($clientTg, ENT_QUOTES, 'UTF-8') . '</td></tr>'
        : '';

    return '<!DOCTYPE html><html lang="ru"><head><meta charset="UTF-8">'
        . '<meta name="viewport" content="width=device-width,initial-scale=1">'
        . '</head><body style="margin:0;padding:0;background:#f3f4f6;font-family:Arial,Helvetica,sans-serif">'
        . '<div style="max-width:600px;margin:16px auto;background:#fff;border-radius:12px;overflow:hidden">'
        . '<div style="background:#F59E0B;padding:16px 18px;color:#fff;font-weight:700">🛒 Новая заявка — СплитХаб</div>'
        . '<div style="padding:14px 18px"><table style="width:100%;border-collapse:collapse">'
        . '<tr><td style="color:#6b7280">Номер</td><td style="font-weight:700">' . mobileOrderNumber($orderId) . '</td></tr>'
        . '<tr><td style="color:#6b7280">Клиент</td><td style="font-weight:700">' . htmlspecialchars($name, ENT_QUOTES, 'UTF-8') . '</td></tr>'
        . '<tr><td style="color:#6b7280">Телефон</td><td style="font-weight:700">' . htmlspecialchars($phone, ENT_QUOTES, 'UTF-8') . '</td></tr>'
        . $clientTgRow
        . '<tr><td style="color:#6b7280">Время</td><td>' . htmlspecialchars($date, ENT_QUOTES, 'UTF-8') . '</td></tr>'
        . '</table></div>'
        . '<div style="padding:0 18px 14px"><table style="width:100%;border-collapse:collapse">'
        . '<thead><tr style="background:#F59E0B;color:#fff"><th style="padding:8px 12px;text-align:left">Наименование</th><th style="padding:8px 12px;text-align:right">Сумма</th></tr></thead>'
        . '<tbody>' . $rows . $commentRow . '</tbody>'
        . '<tfoot><tr><td style="padding:10px 12px;background:#FEF3C7;font-weight:700">Итого</td>'
        . '<td style="padding:10px 12px;background:#FEF3C7;text-align:right;color:#D97706;font-weight:800">' . mobileOrderHtmlMoney($total) . '&nbsp;₽</td></tr></tfoot>'
        . '</table></div>'
        . '<div style="padding:10px 18px;background:#f9fafb;color:#9ca3af;font-size:12px">СплитХаб · splithub.ru · Симферополь</div>'
        . '</div></body></html>';
}

function sendMobileOrderTelegram(string $text, int $orderId): bool {
    if (!defined('BOT_TOKEN') || !defined('CHAT_ID') || !BOT_TOKEN || !CHAT_ID) {
        return false;
    }

    $ch = curl_init('https://api.telegram.org/bot' . BOT_TOKEN . '/sendMessage');
    curl_setopt_array($ch, [
        CURLOPT_POST => true,
        CURLOPT_POSTFIELDS => json_encode([
            'chat_id' => CHAT_ID,
            'text' => $text,
            'parse_mode' => 'HTML',
            'reply_markup' => mobileOrderReplyMarkup($orderId),
        ], JSON_UNESCAPED_UNICODE),
        CURLOPT_HTTPHEADER => ['Content-Type: application/json'],
        CURLOPT_RETURNTRANSFER => true,
        CURLOPT_TIMEOUT => 10,
        CURLOPT_SSL_VERIFYPEER => false,
        CURLOPT_RESOLVE => ['api.telegram.org:443:' . (defined('TG_FORCE_IP') ? TG_FORCE_IP : '149.154.167.220')],
    ]);
    $response = curl_exec($ch);
    curl_close($ch);
    $data = json_decode((string)$response, true);
    return (bool)($data['ok'] ?? false);
}

function sendMobileOrderEmail(
    int $orderId,
    string $name,
    string $phone,
    array $items,
    int $total,
    string $comment = '',
    string $clientTg = ''
): bool {
    if (!defined('EMAIL_TO') || !EMAIL_TO) {
        return false;
    }

    $subject = '=?UTF-8?B?' . base64_encode('Новая заявка СплитХаб — ' . $name . ' — ' . mobileOrderMoney($total) . ' руб') . '?=';
    $headers = "From: =?UTF-8?B?" . base64_encode('СплитХаб') . "?= <zakaz@splithub.ru>\r\n";
    $headers .= "MIME-Version: 1.0\r\n";
    $headers .= "Content-Type: text/html; charset=UTF-8\r\n";

    return @mail(
        EMAIL_TO,
        $subject,
        mobileOrderEmailHtml($orderId, $name, $phone, $items, $total, $comment, $clientTg),
        $headers
    );
}

function notifyManagerAboutMobileOrder(
    int $orderId,
    string $name,
    string $phone,
    array $items,
    int $total,
    string $comment = '',
    string $clientTg = ''
): array {
    $result = ['tg' => false, 'email' => false];
    try {
        require_once __DIR__ . '/app_config.php';
        $text = mobileOrderTelegramText($orderId, $name, $phone, $items, $total, $comment, $clientTg);
        $result['tg'] = sendMobileOrderTelegram($text, $orderId);
        $result['email'] = sendMobileOrderEmail($orderId, $name, $phone, $items, $total, $comment, $clientTg);
        error_log('[SplitHub mobile order] tg=' . ($result['tg'] ? 'ok' : 'fail') . ' mail=' . ($result['email'] ? 'ok' : 'fail') . ' order=' . mobileOrderNumber($orderId));
    } catch (Throwable $e) {
        error_log('Mobile order manager notification failed: ' . $e->getMessage());
    }
    return $result;
}
