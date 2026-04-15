<?php
/**
 * Auth API — register, login, logout, profile, bonus balance.
 *
 * POST /api/auth.php?action=register  {name, phone, password, telegram?}
 * POST /api/auth.php?action=login     {phone, password}
 * POST /api/auth.php?action=logout
 * GET  /api/auth.php?action=profile
 * GET  /api/auth.php?action=history
 * GET  /api/auth.php?action=bonus
 */

// Always respond with JSON — catch PHP fatal errors
set_error_handler(function($errno, $errstr) {
    header('Content-Type: application/json; charset=utf-8');
    http_response_code(500);
    echo json_encode(['ok' => false, 'error' => 'Server error: ' . $errstr]);
    exit;
});
register_shutdown_function(function() {
    $err = error_get_last();
    if ($err && in_array($err['type'], [E_ERROR, E_PARSE, E_CORE_ERROR, E_COMPILE_ERROR])) {
        if (!headers_sent()) header('Content-Type: application/json; charset=utf-8');
        http_response_code(500);
        echo json_encode(['ok' => false, 'error' => 'Fatal server error']);
        exit;
    }
});

require __DIR__ . '/../db/init.php';

header('Content-Type: application/json; charset=utf-8');
header('Access-Control-Allow-Origin: *');
header('Access-Control-Allow-Methods: GET, POST, OPTIONS');
header('Access-Control-Allow-Headers: Content-Type');
if ($_SERVER['REQUEST_METHOD'] === 'OPTIONS') { http_response_code(200); exit; }

if (session_status() === PHP_SESSION_NONE) {
    // Use writable session path on shared hosting
    $sessDir = sys_get_temp_dir() . '/splithub_sess';
    if (!is_dir($sessDir)) @mkdir($sessDir, 0700, true);
    if (is_writable($sessDir)) session_save_path($sessDir);
    session_start();
}

$action = $_GET['action'] ?? '';
$method = $_SERVER['REQUEST_METHOD'];

try {

switch ($action) {

    // ── Register ──
    case 'register':
        if ($method !== 'POST') jsonResponse(['ok' => false, 'error' => 'POST only'], 405);

        $raw = json_decode(file_get_contents('php://input'), true);
        $name     = trim($raw['name'] ?? '');
        $phone    = normalizePhone($raw['phone'] ?? '');
        $password = $raw['password'] ?? '';
        $telegram = trim($raw['telegram'] ?? '');

        if (!$name || !$phone || !$password) {
            jsonResponse(['ok' => false, 'error' => 'Заполните все обязательные поля'], 422);
        }
        if (strlen($phone) < 10 || strlen($phone) > 15) {
            jsonResponse(['ok' => false, 'error' => 'Некорректный телефон'], 422);
        }
        if (strlen($password) < 4) {
            jsonResponse(['ok' => false, 'error' => 'Пароль минимум 4 символа'], 422);
        }

        $db = getDB();

        // Check duplicate
        $stmt = $db->prepare('SELECT id FROM users WHERE phone = ?');
        $stmt->execute([$phone]);
        if ($stmt->fetch()) {
            jsonResponse(['ok' => false, 'error' => 'Этот телефон уже зарегистрирован'], 409);
        }

        $hash = password_hash($password, PASSWORD_BCRYPT);
        $ins = $db->prepare('INSERT INTO users (name, phone, telegram, password_hash) VALUES (?, ?, ?, ?)');
        $ins->execute([$name, $phone, $telegram, $hash]);

        $userId = (int)$db->lastInsertId();
        $_SESSION['user_id'] = $userId;

        jsonResponse(['ok' => true, 'user' => [
            'id'   => $userId,
            'name' => $name,
            'phone' => $phone,
            'role'  => 'client'
        ]]);
        break;

    // ── Login ──
    case 'login':
        if ($method !== 'POST') jsonResponse(['ok' => false, 'error' => 'POST only'], 405);

        $raw = json_decode(file_get_contents('php://input'), true);
        $phone    = normalizePhone($raw['phone'] ?? '');
        $password = $raw['password'] ?? '';

        if (!$phone || !$password) {
            jsonResponse(['ok' => false, 'error' => 'Введите телефон и пароль'], 422);
        }

        $db = getDB();
        $stmt = $db->prepare('SELECT * FROM users WHERE phone = ?');
        $stmt->execute([$phone]);
        $user = $stmt->fetch();

        if (!$user || !password_verify($password, $user['password_hash'])) {
            jsonResponse(['ok' => false, 'error' => 'Неверный телефон или пароль'], 401);
        }

        $_SESSION['user_id'] = (int)$user['id'];

        jsonResponse(['ok' => true, 'user' => [
            'id'   => (int)$user['id'],
            'name' => $user['name'],
            'phone' => $user['phone'],
            'role'  => $user['role']
        ]]);
        break;

    // ── Logout ──
    case 'logout':
        $_SESSION = [];
        if (ini_get('session.use_cookies')) {
            $p = session_get_cookie_params();
            setcookie(session_name(), '', time() - 42000, $p['path'], $p['domain'], $p['secure'], $p['httponly']);
        }
        session_destroy();
        jsonResponse(['ok' => true]);
        break;

    // ── Profile ──
    case 'profile':
        $uid = authRequire();
        $db = getDB();

        $stmt = $db->prepare('SELECT id, name, phone, telegram, role, created_at FROM users WHERE id = ?');
        $stmt->execute([$uid]);
        $user = $stmt->fetch();

        // Bonus balance
        $bal = $db->prepare('SELECT COALESCE(SUM(amount), 0) as balance FROM bonus_log WHERE user_id = ?');
        $bal->execute([$uid]);
        $balance = (int)$bal->fetch()['balance'];

        jsonResponse(['ok' => true, 'user' => $user, 'bonus_balance' => $balance]);
        break;

    // ── Order history ──
    case 'history':
        $uid = authRequire();
        $db = getDB();

        $orders = $db->prepare('
            SELECT id, total, bonus_earned, bonus_spent, status, comment, created_at
            FROM orders WHERE user_id = ? ORDER BY created_at DESC LIMIT 50
        ');
        $orders->execute([$uid]);
        $list = $orders->fetchAll();

        // Attach items to each order
        foreach ($list as &$order) {
            $items = $db->prepare('SELECT product_name, price, qty FROM order_items WHERE order_id = ?');
            $items->execute([$order['id']]);
            $order['items'] = $items->fetchAll();
        }

        jsonResponse(['ok' => true, 'orders' => $list]);
        break;

    // ── Bonus log ──
    case 'bonus':
        $uid = authRequire();
        $db = getDB();

        $log = $db->prepare('
            SELECT bl.amount, bl.type, bl.description, bl.created_at, o.total as order_total
            FROM bonus_log bl
            LEFT JOIN orders o ON bl.order_id = o.id
            WHERE bl.user_id = ?
            ORDER BY bl.created_at DESC LIMIT 100
        ');
        $log->execute([$uid]);

        $bal = $db->prepare('SELECT COALESCE(SUM(amount), 0) as balance FROM bonus_log WHERE user_id = ?');
        $bal->execute([$uid]);
        $balance = (int)$bal->fetch()['balance'];

        jsonResponse(['ok' => true, 'balance' => $balance, 'log' => $log->fetchAll()]);
        break;

    default:
        jsonResponse(['ok' => false, 'error' => 'Unknown action'], 400);
}

} catch (Exception $e) {
    http_response_code(500);
    echo json_encode(['ok' => false, 'error' => $e->getMessage()], JSON_UNESCAPED_UNICODE);
    exit;
} catch (Throwable $e) {
    http_response_code(500);
    echo json_encode(['ok' => false, 'error' => 'Server error: ' . $e->getMessage()], JSON_UNESCAPED_UNICODE);
    exit;
}
