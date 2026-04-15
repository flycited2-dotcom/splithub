<?php
/**
 * Telegram bot diagnostic — DELETE after use!
 * Open: https://splithub.ru/api/tg-test.php
 */
header('Content-Type: application/json; charset=utf-8');
if (!file_exists(__DIR__ . '/../config.php')) {
    echo json_encode(['error' => 'config.php not found']); exit;
}
require __DIR__ . '/../config.php';

$result = [];

// Test 1: getMe
$ch = curl_init("https://api.telegram.org/bot" . BOT_TOKEN . "/getMe");
curl_setopt_array($ch, [CURLOPT_RETURNTRANSFER => true, CURLOPT_TIMEOUT => 10, CURLOPT_SSL_VERIFYPEER => true]);
$resp = curl_exec($ch);
$result['getMe'] = json_decode($resp, true);
$result['getMe_raw'] = $resp;
curl_close($ch);

// Test 2: sendMessage
$ch = curl_init("https://api.telegram.org/bot" . BOT_TOKEN . "/sendMessage");
curl_setopt_array($ch, [
    CURLOPT_POST => true,
    CURLOPT_POSTFIELDS => json_encode(['chat_id' => CHAT_ID, 'text' => '🔧 Тест СплитХаб — ' . date('d.m.Y H:i:s'), 'parse_mode' => 'Markdown']),
    CURLOPT_HTTPHEADER => ['Content-Type: application/json'],
    CURLOPT_RETURNTRANSFER => true,
    CURLOPT_TIMEOUT => 10,
]);
$resp = curl_exec($ch);
$result['sendMessage'] = json_decode($resp, true);
$result['sendMessage_raw'] = $resp;
curl_close($ch);

$result['chat_id_used'] = CHAT_ID;
$result['token_prefix'] = substr(BOT_TOKEN, 0, 10) . '...';

echo json_encode($result, JSON_UNESCAPED_UNICODE | JSON_PRETTY_PRINT);
