<?php
require_once __DIR__ . '/../../db/init.php';

function upsertMobileDevice(int $uid, string $expoToken, string $platform, array $preferences): void {
    if (!preg_match('/^(Exponent|Expo)PushToken\[[^\]]+\]$/', $expoToken)) {
        throw new RuntimeException('INVALID_EXPO_PUSH_TOKEN');
    }
    if (!in_array($platform, ['android', 'ios'], true)) {
        throw new RuntimeException('INVALID_DEVICE_PLATFORM');
    }

    getDB()->prepare("INSERT INTO mobile_devices(
        user_id,expo_token,platform,order_status_enabled,promotions_enabled,manager_messages_enabled,active,updated_at
    ) VALUES(?,?,?,?,?,?,1,CURRENT_TIMESTAMP)
    ON CONFLICT(expo_token) DO UPDATE SET user_id=excluded.user_id,platform=excluded.platform,
        order_status_enabled=excluded.order_status_enabled,promotions_enabled=excluded.promotions_enabled,
        manager_messages_enabled=excluded.manager_messages_enabled,active=1,updated_at=CURRENT_TIMESTAMP")
      ->execute([
          $uid,
          $expoToken,
          $platform,
          !empty($preferences['order_status_enabled']) ? 1 : 0,
          !empty($preferences['promotions_enabled']) ? 1 : 0,
          !empty($preferences['manager_messages_enabled']) ? 1 : 0,
      ]);
}

function devicesForUser(int $uid, string $type): array {
    $columns = [
        'order_status' => 'order_status_enabled',
        'promotion' => 'promotions_enabled',
        'manager_message' => 'manager_messages_enabled',
    ];
    if (!isset($columns[$type])) {
        throw new RuntimeException('INVALID_PUSH_TYPE');
    }

    $column = $columns[$type];
    $stmt = getDB()->prepare("SELECT * FROM mobile_devices WHERE user_id=? AND active=1 AND $column=1");
    $stmt->execute([$uid]);
    return $stmt->fetchAll();
}

function buildPushPayload(string $token, string $type, string $title, string $body, array $target): array {
    return [
        'to' => $token,
        'sound' => 'default',
        'title' => $title,
        'body' => $body,
        'data' => ['type' => $type] + $target,
    ];
}

function sendExpoBatch(array $messages): array {
    if (!$messages) {
        return [];
    }

    $ch = curl_init('https://exp.host/--/api/v2/push/send');
    curl_setopt_array($ch, [
        CURLOPT_POST => true,
        CURLOPT_POSTFIELDS => json_encode($messages, JSON_UNESCAPED_UNICODE),
        CURLOPT_HTTPHEADER => ['Content-Type: application/json', 'Accept: application/json'],
        CURLOPT_RETURNTRANSFER => true,
        CURLOPT_TIMEOUT => 15,
    ]);
    $response = curl_exec($ch);
    $status = curl_getinfo($ch, CURLINFO_HTTP_CODE);
    $error = curl_error($ch);
    curl_close($ch);
    if ($response === false || $status < 200 || $status >= 300) {
        throw new RuntimeException('EXPO_PUSH_HTTP_' . $status . ($error ? ': ' . $error : ''));
    }

    $decoded = json_decode((string)$response, true);
    return is_array($decoded['data'] ?? null) ? $decoded['data'] : [];
}

function sendUserPush(int $uid, string $type, string $title, string $body, array $target = []): int {
    $db = getDB();
    $db->prepare('INSERT INTO push_campaigns(type,title,body,target_json,user_id) VALUES(?,?,?,?,?)')
       ->execute([$type, $title, $body, json_encode($target, JSON_UNESCAPED_UNICODE), $uid]);
    $campaignId = (int)$db->lastInsertId();
    $devices = devicesForUser($uid, $type);
    if (!$devices) {
        return $campaignId;
    }

    $insert = $db->prepare("INSERT INTO push_deliveries(campaign_id,device_id,status) VALUES(?,?,'queued')");
    $deliveryIds = [];
    foreach ($devices as $device) {
        $insert->execute([$campaignId, (int)$device['id']]);
        $deliveryIds[] = (int)$db->lastInsertId();
    }

    try {
        $messages = array_map(
            fn($device) => buildPushPayload($device['expo_token'], $type, $title, $body, $target),
            $devices
        );
        $tickets = sendExpoBatch($messages);
    } catch (Throwable $e) {
        $failed = $db->prepare("UPDATE push_deliveries SET status='error',error=?,updated_at=CURRENT_TIMESTAMP WHERE id=?");
        foreach ($deliveryIds as $deliveryId) {
            $failed->execute([$e->getMessage(), $deliveryId]);
        }
        throw $e;
    }

    $update = $db->prepare('UPDATE push_deliveries SET expo_ticket_id=?,status=?,error=?,updated_at=CURRENT_TIMESTAMP WHERE id=?');
    foreach ($deliveryIds as $index => $deliveryId) {
        $ticket = $tickets[$index] ?? [];
        $update->execute([
            $ticket['id'] ?? null,
            $ticket['status'] ?? 'error',
            $ticket['message'] ?? '',
            $deliveryId,
        ]);
    }
    return $campaignId;
}

function fetchExpoReceipts(array $ticketIds): array {
    if (!$ticketIds) {
        return [];
    }

    $ch = curl_init('https://exp.host/--/api/v2/push/getReceipts');
    curl_setopt_array($ch, [
        CURLOPT_POST => true,
        CURLOPT_POSTFIELDS => json_encode(['ids' => $ticketIds]),
        CURLOPT_HTTPHEADER => ['Content-Type: application/json', 'Accept: application/json'],
        CURLOPT_RETURNTRANSFER => true,
        CURLOPT_TIMEOUT => 15,
    ]);
    $response = curl_exec($ch);
    $status = curl_getinfo($ch, CURLINFO_HTTP_CODE);
    curl_close($ch);
    if ($response === false || $status < 200 || $status >= 300) {
        throw new RuntimeException('EXPO_RECEIPTS_HTTP_' . $status);
    }
    $decoded = json_decode((string)$response, true);
    return is_array($decoded['data'] ?? null) ? $decoded['data'] : [];
}

function applyExpoReceipts(array $deliveries, array $receipts): int {
    $db = getDB();
    $update = $db->prepare('UPDATE push_deliveries SET status=?,error=?,updated_at=CURRENT_TIMESTAMP WHERE id=?');
    $disable = $db->prepare('UPDATE mobile_devices SET active=0,updated_at=CURRENT_TIMESTAMP WHERE id=?');
    $processed = 0;
    foreach ($deliveries as $delivery) {
        $receipt = $receipts[$delivery['expo_ticket_id']] ?? null;
        if (!$receipt) {
            continue;
        }
        $error = (string)($receipt['details']['error'] ?? $receipt['message'] ?? '');
        $status = ($receipt['status'] ?? '') === 'ok' ? 'delivered' : 'error';
        $update->execute([$status, $error, (int)$delivery['id']]);
        if ($error === 'DeviceNotRegistered') {
            $disable->execute([(int)$delivery['device_id']]);
        }
        $processed++;
    }
    return $processed;
}

function sendOrderStatusPush(int $orderId, string $status): void {
    $stmt = getDB()->prepare('SELECT user_id FROM orders WHERE id=?');
    $stmt->execute([$orderId]);
    $order = $stmt->fetch();
    if (!$order) {
        return;
    }

    $labels = [
        'new' => 'New',
        'confirmed' => 'Confirmed',
        'in_progress' => 'In progress',
        'shipped' => 'Shipped',
        'completed' => 'Completed',
        'cancelled' => 'Cancelled',
    ];
    try {
        sendUserPush(
            (int)$order['user_id'],
            'order_status',
            'Order status changed',
            $labels[$status] ?? $status,
            ['order_id' => $orderId]
        );
    } catch (Throwable $e) {
        error_log('Order status push failed: ' . $e->getMessage());
    }
}
