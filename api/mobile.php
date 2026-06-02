<?php
require_once __DIR__ . '/lib/catalog.php';
require_once __DIR__ . '/lib/mobile_auth.php';
require_once __DIR__ . '/lib/order_service.php';
require_once __DIR__ . '/lib/manager_notify.php';
require_once __DIR__ . '/lib/push.php';

header('Content-Type: application/json; charset=utf-8');
header('Access-Control-Allow-Headers: Content-Type, Authorization');
header('Access-Control-Allow-Methods: GET, POST, OPTIONS');
if ($_SERVER['REQUEST_METHOD'] === 'OPTIONS') {
    http_response_code(204);
    exit;
}

function body(): array {
    return json_decode(file_get_contents('php://input'), true) ?: [];
}

function ok(array $data = []): never {
    jsonResponse(['ok' => true] + $data);
}

function fail(string $code, int $status, array $data = []): never {
    jsonResponse(['ok' => false, 'code' => $code] + $data, $status);
}

function requirePost(): void {
    if ($_SERVER['REQUEST_METHOD'] !== 'POST') {
        fail('METHOD_NOT_ALLOWED', 405);
    }
}

try {
    $action = $_GET['action'] ?? '';

    if ($action === 'catalog') {
        $items = loadCatalog();
        ok([
            'version' => hash_file('sha256', catalogPath()),
            'updated_at' => gmdate(DATE_ATOM, filemtime(catalogPath())),
            'products' => $items,
        ]);
    }

    if ($action === 'register') {
        requirePost();
        $data = body();
        $name = trim((string)($data['name'] ?? ''));
        $phone = normalizePhone((string)($data['phone'] ?? ''));
        $password = (string)($data['password'] ?? '');
        if ($name === '' || strlen($phone) < 10 || strlen($phone) > 15 || strlen($password) < 4) {
            fail('INVALID_REGISTRATION', 422);
        }
        $db = getDB();
        $exists = $db->prepare('SELECT id FROM users WHERE phone=?');
        $exists->execute([$phone]);
        if ($exists->fetch()) {
            fail('PHONE_ALREADY_REGISTERED', 409);
        }
        $db->prepare('INSERT INTO users(name,phone,telegram,password_hash) VALUES(?,?,?,?)')
           ->execute([$name, $phone, trim((string)($data['telegram'] ?? '')), password_hash($password, PASSWORD_BCRYPT)]);
        ok(issueMobileToken($phone, $password));
    }

    if ($action === 'login') {
        requirePost();
        $data = body();
        ok(issueMobileToken((string)($data['phone'] ?? ''), (string)($data['password'] ?? '')));
    }

    if ($action === 'logout') {
        requirePost();
        requireMobileUser();
        revokeMobileToken(bearerToken());
        ok();
    }

    if ($action === 'profile') {
        $uid = requireMobileUser();
        $stmt = getDB()->prepare('SELECT id,name,phone,telegram,role,created_at FROM users WHERE id=?');
        $stmt->execute([$uid]);
        ok(['user' => $stmt->fetch()]);
    }

    if ($action === 'register_device' || $action === 'notification_preferences') {
        requirePost();
        $uid = requireMobileUser();
        $data = body();
        upsertMobileDevice(
            $uid,
            (string)($data['expo_token'] ?? ''),
            (string)($data['platform'] ?? ''),
            $data
        );
        ok();
    }

    if ($action === 'remove_device') {
        requirePost();
        $uid = requireMobileUser();
        $data = body();
        getDB()->prepare('DELETE FROM mobile_devices WHERE user_id=? AND expo_token=?')
               ->execute([$uid, (string)($data['expo_token'] ?? '')]);
        ok();
    }

    if ($action === 'create_order') {
        requirePost();
        $uid = requireMobileUser();
        $data = body();
        $validation = validateCatalogItems($data['items'] ?? []);
        if (!$validation['ok']) {
            $status = in_array($validation['code'], ['CATALOG_CHANGED', 'PRODUCT_UNAVAILABLE'], true) ? 409 : 422;
            fail($validation['code'], $status, $validation);
        }
        $comment = trim((string)($data['comment'] ?? ''));
        $clientTg = trim((string)($data['client_tg'] ?? ''));
        $created = createRegisteredOrder(
            $uid,
            $validation['items'],
            $comment,
            $clientTg
        );
        $profile = getDB()->prepare('SELECT name,phone FROM users WHERE id=?');
        $profile->execute([$uid]);
        $user = $profile->fetch();
        notifyManagerAboutMobileOrder(
            $created['order_id'],
            (string)$user['name'],
            (string)$user['phone'],
            $validation['items'],
            $created['total'],
            $comment,
            $clientTg
        );
        ok($created);
    }

    if ($action === 'orders') {
        $uid = requireMobileUser();
        $page = max(1, (int)($_GET['page'] ?? 1));
        $perPage = 20;
        $offset = ($page - 1) * $perPage;
        $db = getDB();
        $count = $db->prepare('SELECT COUNT(*) FROM orders WHERE user_id=?');
        $count->execute([$uid]);
        $total = (int)$count->fetchColumn();
        $stmt = $db->prepare("SELECT id,total,status,comment,created_at
                              FROM orders WHERE user_id=? ORDER BY id DESC LIMIT $perPage OFFSET $offset");
        $stmt->execute([$uid]);
        ok(['orders' => $stmt->fetchAll(), 'total' => $total, 'page' => $page]);
    }

    if ($action === 'order') {
        $uid = requireMobileUser();
        $stmt = getDB()->prepare('SELECT id,total,status,comment,created_at FROM orders WHERE id=? AND user_id=?');
        $stmt->execute([(int)($_GET['id'] ?? 0), $uid]);
        $order = $stmt->fetch();
        if (!$order) {
            fail('ORDER_NOT_FOUND', 404);
        }
        $items = getDB()->prepare('SELECT product_id,product_name,price,qty FROM order_items WHERE order_id=?');
        $items->execute([(int)$order['id']]);
        $order['items'] = $items->fetchAll();
        ok(['order' => $order]);
    }

    if ($action === 'repeat_order') {
        requirePost();
        $uid = requireMobileUser();
        $data = body();
        $orderId = (int)($data['order_id'] ?? 0);
        $owned = getDB()->prepare('SELECT id FROM orders WHERE id=? AND user_id=?');
        $owned->execute([$orderId, $uid]);
        if (!$owned->fetch()) {
            fail('ORDER_NOT_FOUND', 404);
        }
        $items = getDB()->prepare('SELECT product_id AS id,qty FROM order_items WHERE order_id=?');
        $items->execute([$orderId]);
        ok(['items' => $items->fetchAll()]);
    }

    if ($action === 'cancel_order') {
        requirePost();
        $uid = requireMobileUser();
        $data = body();
        $reason = trim((string)($data['reason'] ?? ''));
        if ($reason === '') {
            fail('CANCEL_REASON_REQUIRED', 422);
        }
        $stmt = getDB()->prepare("UPDATE orders SET status='cancelled',cancel_reason=?
                                  WHERE id=? AND user_id=? AND status='new'");
        $stmt->execute([$reason, (int)($data['order_id'] ?? 0), $uid]);
        if ($stmt->rowCount() !== 1) {
            fail('ORDER_CANNOT_BE_CANCELLED', 409);
        }
        ok();
    }

    fail('UNKNOWN_ACTION', 404);
} catch (RuntimeException $e) {
    $statuses = [
        'AUTH_REQUIRED' => 401,
        'INVALID_CREDENTIALS' => 401,
        'CATALOG_UNAVAILABLE' => 503,
    ];
    fail($e->getMessage(), $statuses[$e->getMessage()] ?? 422);
} catch (Throwable $e) {
    error_log('Mobile API error: ' . $e->getMessage());
    fail('SERVER_ERROR', 500);
}
