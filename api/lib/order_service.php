<?php
require_once __DIR__ . '/../../db/init.php';

function createRegisteredOrder(int $uid, array $items, string $comment = '', string $clientTg = ''): array {
    if (!$items) {
        throw new RuntimeException('EMPTY_CART');
    }

    $db = getDB();
    $total = array_sum(array_map(
        fn($item) => (int)$item['price'] * (int)$item['qty'],
        $items
    ));

    $db->beginTransaction();
    try {
        $db->prepare('INSERT INTO orders(user_id,total,bonus_earned,bonus_spent,status,comment,client_tg)
                      VALUES(?,?,0,0,"new",?,?)')
           ->execute([$uid, $total, $comment, $clientTg]);
        $orderId = (int)$db->lastInsertId();
        $insert = $db->prepare('INSERT INTO order_items(order_id,product_name,price,qty,product_id)
                                VALUES(?,?,?,?,?)');
        foreach ($items as $item) {
            $insert->execute([
                $orderId,
                $item['name'],
                (int)$item['price'],
                (int)$item['qty'],
                (string)$item['id'],
            ]);
        }
        $db->commit();
        return ['order_id' => $orderId, 'total' => $total];
    } catch (Throwable $e) {
        $db->rollBack();
        throw $e;
    }
}
