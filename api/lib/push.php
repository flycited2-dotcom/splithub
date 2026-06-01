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
