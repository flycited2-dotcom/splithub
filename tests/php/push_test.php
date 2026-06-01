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

$payload = buildPushPayload(
    'ExponentPushToken[test-token]',
    'order_status',
    'Order updated',
    'SH-00001',
    ['order_id' => 1]
);
assertSame('ExponentPushToken[test-token]', $payload['to'], 'push token mapped');
assertSame('order_status', $payload['data']['type'], 'push type mapped');
assertSame(1, $payload['data']['order_id'], 'push target mapped');

$db->prepare('INSERT INTO push_campaigns(type,title,body,target_json,user_id) VALUES(?,?,?,?,?)')
   ->execute(['order_status', 'Order updated', 'SH-00001', '{}', $uid]);
$campaignId = (int)$db->lastInsertId();
$device = $db->query("SELECT id FROM mobile_devices WHERE expo_token='ExponentPushToken[test-token]'")->fetch();
$db->prepare("INSERT INTO push_deliveries(campaign_id,device_id,expo_ticket_id,status) VALUES(?,?,?,'ok')")
   ->execute([$campaignId, (int)$device['id'], 'ticket-1']);
$delivery = $db->query("SELECT id,device_id,expo_ticket_id FROM push_deliveries WHERE expo_ticket_id='ticket-1'")->fetch();

$processed = applyExpoReceipts([$delivery], [
    'ticket-1' => ['status' => 'error', 'details' => ['error' => 'DeviceNotRegistered']],
]);
assertSame(1, $processed, 'receipt processed');
$active = $db->query("SELECT active FROM mobile_devices WHERE expo_token='ExponentPushToken[test-token]'")->fetchColumn();
assertSame(0, (int)$active, 'unregistered device deactivated');

$db->prepare('INSERT INTO users(name,phone,password_hash) VALUES(?,?,?)')
   ->execute(['Status User', '79780000005', password_hash('pass123', PASSWORD_BCRYPT)]);
$statusUid = (int)$db->lastInsertId();
$db->prepare('INSERT INTO orders(user_id,total,status) VALUES(?,?,?)')
   ->execute([$statusUid, 24900, 'confirmed']);
$orderId = (int)$db->lastInsertId();

sendOrderStatusPush($orderId, 'confirmed');
$campaign = $db->query("SELECT type,target_json FROM push_campaigns WHERE user_id=$statusUid ORDER BY id DESC LIMIT 1")->fetch();
assertSame('order_status', $campaign['type'], 'status helper creates order-status campaign');
assertSame($orderId, json_decode($campaign['target_json'], true)['order_id'], 'status helper targets order details');
