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

// Test 3: getUpdates — show all chats the bot has seen (to find correct chat_id)
$ch = curl_init("https://api.telegram.org/bot" . BOT_TOKEN . "/getUpdates");
curl_setopt_array($ch, [CURLOPT_RETURNTRANSFER => true, CURLOPT_TIMEOUT => 10, CURLOPT_SSL_VERIFYPEER => true]);
$resp = curl_exec($ch);
$updates = json_decode($resp, true);
curl_close($ch);

$chats = [];
if (!empty($updates['result'])) {
    foreach ($updates['result'] as $upd) {
        $msg = $upd['message'] ?? $upd['my_chat_member'] ?? $upd['channel_post'] ?? null;
        if ($msg && isset($msg['chat'])) {
            $c = $msg['chat'];
            $chats[(string)$c['id']] = [
                'id'    => $c['id'],
                'type'  => $c['type'],
                'title' => $c['title'] ?? ($c['first_name'] ?? '?'),
            ];
        }
    }
}
$result['detected_chats'] = array_values($chats);
$result['getUpdates_raw'] = $resp;

$result['chat_id_used'] = CHAT_ID;
$result['token_prefix'] = substr(BOT_TOKEN, 0, 10) . '...';

echo json_encode($result, JSON_UNESCAPED_UNICODE | JSON_PRETTY_PRINT);
