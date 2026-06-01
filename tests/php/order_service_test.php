<?php
require_once __DIR__ . '/bootstrap.php';
require_once projectPath('api/lib/order_service.php');

$db = getDB();
$db->prepare('INSERT INTO users(name,phone,password_hash) VALUES(?,?,?)')
   ->execute(['Buyer', '79780000002', password_hash('pass123', PASSWORD_BCRYPT)]);
$uid = (int)$db->lastInsertId();

$created = createRegisteredOrder($uid, [
    ['id' => '1001', 'name' => 'ELYSIUM', 'price' => 24900, 'qty' => 2, 'group' => 'inv'],
], 'mobile test', '@buyer');

assertTrue($created['order_id'] > 0, 'order created');
assertSame(49800, $created['total'], 'server calculates total');

$stored = $db->query('SELECT product_id,product_name,price,qty FROM order_items')->fetch();
assertSame('1001', $stored['product_id'], 'product id stored');
assertSame(2, (int)$stored['qty'], 'quantity stored');

try {
    createRegisteredOrder($uid, []);
    throw new RuntimeException('FAIL: empty order accepted');
} catch (RuntimeException $e) {
    assertSame('EMPTY_CART', $e->getMessage(), 'empty order rejected');
}
