<?php
require_once __DIR__ . '/bootstrap.php';
require_once projectPath('api/lib/push.php');

$db = getDB();
$db->prepare('INSERT INTO users(name,phone,password_hash) VALUES(?,?,?)')
   ->execute(['Push User', '79780000004', password_hash('pass123', PASSWORD_BCRYPT)]);
$uid = (int)$db->lastInsertId();

upsertMobileDevice($uid, 'ExponentPushToken[test-token]', 'android', [
    'order_status_enabled' => true,
    'promotions_enabled' => false,
    'manager_messages_enabled' => true,
]);
upsertMobileDevice($uid, 'ExpoPushToken[test-token-2]', 'ios', [
    'order_status_enabled' => true,
    'promotions_enabled' => true,
    'manager_messages_enabled' => false,
]);

assertSame(2, count(devicesForUser($uid, 'order_status')), 'both Expo token formats accepted');
assertSame(1, count(devicesForUser($uid, 'promotion')), 'promotion preference respected');
assertSame(1, count(devicesForUser($uid, 'manager_message')), 'manager-message preference respected');

try {
    upsertMobileDevice($uid, 'not-an-expo-token', 'android', []);
    throw new RuntimeException('FAIL: invalid Expo token accepted');
} catch (RuntimeException $e) {
    assertSame('INVALID_EXPO_PUSH_TOKEN', $e->getMessage(), 'invalid Expo token rejected');
}
