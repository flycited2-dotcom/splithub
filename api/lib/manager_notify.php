<?php
function notifyManagerAboutMobileOrder(int $orderId, string $name, string $phone, array $items, int $total): void {
    try {
        require_once __DIR__ . '/app_config.php';
        if (!defined('BOT_TOKEN') || !defined('CHAT_ID') || !BOT_TOKEN || !CHAT_ID) {
            return;
        }

        $lines = array_map(
            fn($item) => sprintf('%s x %d', $item['name'], (int)$item['qty']),
            $items
        );
        $text = 'New mobile order SH-' . str_pad((string)$orderId, 5, '0', STR_PAD_LEFT)
            . "\nCustomer: $name\nPhone: $phone\n"
            . implode("\n", $lines)
            . "\nTotal: $total RUB";
        $ch = curl_init('https://api.telegram.org/bot' . BOT_TOKEN . '/sendMessage');
        curl_setopt_array($ch, [
            CURLOPT_POST => true,
            CURLOPT_POSTFIELDS => json_encode(['chat_id' => CHAT_ID, 'text' => $text], JSON_UNESCAPED_UNICODE),
            CURLOPT_HTTPHEADER => ['Content-Type: application/json'],
            CURLOPT_RETURNTRANSFER => true,
            CURLOPT_TIMEOUT => 10,
        ]);
        curl_exec($ch);
        curl_close($ch);
    } catch (Throwable $e) {
        error_log('Mobile order manager notification failed: ' . $e->getMessage());
    }
}
