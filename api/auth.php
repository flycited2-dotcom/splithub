<?php
ob_start();
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
        error_log('[SplitHub auth] Fatal: '.($err['message']??'').' in '.($err['file']??'?').':'.($err['line']??'0'));
        ob_clean();
        echo json_encode(['ok' => false, 'error' => 'Ошибка: '.($err['message'] ?? 'Fatal server error')], JSON_UNESCAPED_UNICODE);
        exit;
    }
});

header('Content-Type: application/json; charset=utf-8');
header('Access-Control-Allow-Origin: *');
header('Access-Control-Allow-Methods: GET, POST, OPTIONS');
header('Access-Control-Allow-Headers: Content-Type');
if ($_SERVER['REQUEST_METHOD'] === 'OPTIONS') { ob_end_clean(); http_response_code(200); exit; }

$action = $_GET['action'] ?? '';
$method = $_SERVER['REQUEST_METHOD'];

try {

require __DIR__ . '/../db/init.php';

if (session_status() === PHP_SESSION_NONE) {
    $sessDir = sys_get_temp_dir() . '/splithub_sess';
    if (!is_dir($sessDir)) @mkdir($sessDir, 0700, true);
    if (is_writable($sessDir)) session_save_path($sessDir);
    @session_start();
}

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

    // ── Order history (with pagination + filters) ──
    case 'history':
        $uid = authRequire();
        $db  = getDB();

        $page    = max(1, (int)($_GET['page']   ?? 1));
        $perPage = 10;
        $status  = trim($_GET['status'] ?? '');
        $period  = trim($_GET['period'] ?? '');
        $search  = trim($_GET['search'] ?? '');

        $where  = ['user_id = ?'];
        $params = [$uid];

        if ($status !== '') { $where[] = 'status = ?'; $params[] = $status; }

        if ($period === '30d')     { $where[] = "created_at >= datetime('now','-30 days')"; }
        elseif ($period === '3m')  { $where[] = "created_at >= datetime('now','-3 months')"; }
        elseif ($period === '1y')  { $where[] = "created_at >= datetime('now','-1 year')"; }

        if ($search !== '') {
            // strip SH- prefix if present, search by numeric id
            $numSearch = preg_replace('/^(SH-?|#)/i', '', $search);
            if (ctype_digit($numSearch)) {
                $where[] = 'id = ?';
                $params[] = (int)$numSearch;
            }
        }

        $whereSQL = 'WHERE ' . implode(' AND ', $where);

        $cnt = $db->prepare("SELECT COUNT(*) AS cnt FROM orders $whereSQL");
        $cnt->execute($params);
        $total  = (int)$cnt->fetch()['cnt'];
        $pages  = max(1, (int)ceil($total / $perPage));
        $offset = ($page - 1) * $perPage;

        $stmt = $db->prepare("SELECT id, total, bonus_earned, bonus_spent, status, comment, created_at
                               FROM orders $whereSQL ORDER BY created_at DESC LIMIT $perPage OFFSET $offset");
        $stmt->execute($params);
        $list = $stmt->fetchAll();

        foreach ($list as &$order) {
            $it = $db->prepare('SELECT product_name, price, qty FROM order_items WHERE order_id = ?');
            $it->execute([$order['id']]);
            $order['items'] = $it->fetchAll();
        }
        unset($order);

        jsonResponse(['ok' => true, 'orders' => $list, 'total' => $total, 'pages' => $pages, 'page' => $page]);
        break;

    // ── Repeat order — returns items for client-side cart merge ──
    case 'repeat_order':
        if ($method !== 'POST') jsonResponse(['ok' => false, 'error' => 'POST only'], 405);
        $uid = authRequire();
        $db  = getDB();

        $raw     = json_decode(file_get_contents('php://input'), true);
        $orderId = (int)($raw['orderId'] ?? 0);
        if (!$orderId) jsonResponse(['ok' => false, 'error' => 'orderId required'], 422);

        $chk = $db->prepare('SELECT id FROM orders WHERE id = ? AND user_id = ?');
        $chk->execute([$orderId, $uid]);
        if (!$chk->fetch()) jsonResponse(['ok' => false, 'error' => 'Заказ не найден'], 404);

        $it = $db->prepare('SELECT product_name, price, qty FROM order_items WHERE order_id = ?');
        $it->execute([$orderId]);
        jsonResponse(['ok' => true, 'items' => $it->fetchAll()]);
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
