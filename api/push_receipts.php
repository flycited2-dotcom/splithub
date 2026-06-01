<?php
require_once __DIR__ . '/lib/app_config.php';
require_once __DIR__ . '/lib/push.php';

header('Content-Type: application/json; charset=utf-8');
$provided = (string)($_GET['secret'] ?? '');
if (!defined('CRON_SECRET') || CRON_SECRET === '' || !hash_equals((string)CRON_SECRET, $provided)) {
    jsonResponse(['ok' => false, 'error' => 'forbidden'], 403);
}

try {
    $db = getDB();
    $deliveries = $db->query("SELECT id,device_id,expo_ticket_id FROM push_deliveries
                              WHERE status='ok' AND expo_ticket_id IS NOT NULL LIMIT 100")
                     ->fetchAll();
    if (!$deliveries) {
        jsonResponse(['ok' => true, 'processed' => 0]);
    }
    $receipts = fetchExpoReceipts(array_column($deliveries, 'expo_ticket_id'));
    jsonResponse(['ok' => true, 'processed' => applyExpoReceipts($deliveries, $receipts)]);
} catch (Throwable $e) {
    error_log('Expo receipt reconciliation failed: ' . $e->getMessage());
    jsonResponse(['ok' => false, 'error' => 'receipt reconciliation failed'], 502);
}
