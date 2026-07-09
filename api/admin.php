<?php
/**
 * Admin API
 */

require __DIR__ . '/../db/init.php';
require_once __DIR__ . '/lib/push.php';

header('Content-Type: application/json; charset=utf-8');
header('Access-Control-Allow-Origin: *');
header('Access-Control-Allow-Methods: GET, POST, OPTIONS');
header('Access-Control-Allow-Headers: Content-Type');
if ($_SERVER['REQUEST_METHOD'] === 'OPTIONS') { http_response_code(200); exit; }

// Public product overrides — no auth required
$action = $_GET['action'] ?? '';
if ($action === 'products_overrides_public') {
    $db = getDB();
    $rows = $db->query("SELECT sku, description, badge, badge_label, active, data_json, updated_at FROM product_overrides")->fetchAll();
    $map = [];
    foreach ($rows as $r) {
        $ov = adminDecodeOverrideRow($r);
        if (adminOverrideHasPublicChanges($ov)) $map[$r['sku']] = $ov;
    }
    $customRows = $db->query("SELECT id, sku, data_json, active, updated_at, created_at FROM custom_products WHERE active = 1 ORDER BY created_at DESC")->fetchAll();
    $custom = [];
    foreach ($customRows as $r) {
        $custom[] = adminDecodeCustomProductRow($r);
    }
    jsonResponse(['ok' => true, 'overrides' => $map, 'custom_products' => $custom]);
    exit;
}

// CSV export — override Content-Type before auth check output
if ($action === 'export_orders_csv') {
    adminRequire();
    exportOrdersCsv(getDB());
    exit;
}

if ($action === 'export_xlsx') {
    adminRequire();
    require_once __DIR__ . '/lib/xlsx_writer.php';
    exportXlsx(getDB());
    exit;
}

$currentAdminId = adminRequire();

$method = $_SERVER['REQUEST_METHOD'];
$db = getDB();

switch ($action) {

    // ── Список посетителей (постранично) ──
    case 'visitors_list':
        $page  = max(1, (int)($_GET['page'] ?? 1));
        $limit = 50;
        $off   = ($page - 1) * $limit;
        $total = (int)$db->query('SELECT COUNT(*) FROM visitors')->fetchColumn();
        $stmt  = $db->prepare('SELECT vid, first_seen, last_seen, visits_count, first_referrer, first_utm_source, first_utm_medium, first_utm_campaign, device, last_ip, linked_name, linked_phone FROM visitors ORDER BY last_seen DESC LIMIT ? OFFSET ?');
        $stmt->bindValue(1, $limit, PDO::PARAM_INT);
        $stmt->bindValue(2, $off, PDO::PARAM_INT);
        $stmt->execute();
        jsonResponse(['ok' => true, 'visitors' => $stmt->fetchAll(), 'total' => $total, 'page' => $page, 'pages' => (int)ceil($total / $limit)]);
        break;

    // ── List promo rules ──
    case 'promo_list':
        $rules = $db->query('SELECT * FROM promo_rules ORDER BY created_at DESC')->fetchAll();
        jsonResponse(['ok' => true, 'rules' => $rules]);
        break;

    // ── Create promo rule ──
    case 'promo_create':
        if ($method !== 'POST') jsonResponse(['ok' => false, 'error' => 'POST only'], 405);
        $raw = json_decode(file_get_contents('php://input'), true);
        $name     = trim($raw['name'] ?? '');
        $percent  = floatval($raw['bonus_percent'] ?? 3.0);
        $group    = isset($raw['product_group']) && $raw['product_group'] !== '' ? trim($raw['product_group']) : null;
        $minOrder = intval($raw['min_order'] ?? 0);
        $active   = intval($raw['active'] ?? 1);
        if (!$name) jsonResponse(['ok' => false, 'error' => 'Укажите название правила'], 422);
        $ins = $db->prepare('INSERT INTO promo_rules (name, active, bonus_percent, product_group, min_order) VALUES (?, ?, ?, ?, ?)');
        $ins->execute([$name, $active, $percent, $group, $minOrder]);
        jsonResponse(['ok' => true, 'id' => (int)$db->lastInsertId()]);
        break;

    // ── Toggle promo rule ──
    case 'promo_toggle':
        if ($method !== 'POST') jsonResponse(['ok' => false, 'error' => 'POST only'], 405);
        $raw = json_decode(file_get_contents('php://input'), true);
        $id = intval($raw['id'] ?? 0); $active = intval($raw['active'] ?? 0);
        if (!$id) jsonResponse(['ok' => false, 'error' => 'id required'], 422);
        $db->prepare('UPDATE promo_rules SET active = ? WHERE id = ?')->execute([$active, $id]);
        jsonResponse(['ok' => true]);
        break;

    // ── Update promo rule ──
    case 'promo_update':
        if ($method !== 'POST') jsonResponse(['ok' => false, 'error' => 'POST only'], 405);
        $raw = json_decode(file_get_contents('php://input'), true);
        $id = intval($raw['id'] ?? 0);
        if (!$id) jsonResponse(['ok' => false, 'error' => 'id required'], 422);
        $fields = []; $vals = [];
        if (isset($raw['name']))          { $fields[] = 'name = ?';          $vals[] = trim($raw['name']); }
        if (isset($raw['bonus_percent'])) { $fields[] = 'bonus_percent = ?'; $vals[] = floatval($raw['bonus_percent']); }
        if (array_key_exists('product_group', $raw)) {
            $fields[] = 'product_group = ?';
            $vals[] = ($raw['product_group'] !== '' && $raw['product_group'] !== null) ? trim($raw['product_group']) : null;
        }
        if (isset($raw['min_order'])) { $fields[] = 'min_order = ?'; $vals[] = intval($raw['min_order']); }
        if (isset($raw['active']))    { $fields[] = 'active = ?';    $vals[] = intval($raw['active']); }
        if (empty($fields)) jsonResponse(['ok' => false, 'error' => 'Нет полей для обновления'], 422);
        $vals[] = $id;
        $db->prepare('UPDATE promo_rules SET ' . implode(', ', $fields) . ' WHERE id = ?')->execute($vals);
        jsonResponse(['ok' => true]);
        break;

    // ── Delete promo rule ──
    case 'promo_delete':
        if ($method !== 'POST') jsonResponse(['ok' => false, 'error' => 'POST only'], 405);
        $raw = json_decode(file_get_contents('php://input'), true);
        $id = intval($raw['id'] ?? 0);
        if (!$id) jsonResponse(['ok' => false, 'error' => 'id required'], 422);
        $db->prepare('DELETE FROM promo_rules WHERE id = ?')->execute([$id]);
        jsonResponse(['ok' => true]);
        break;

    // ── Manual bonus adjustment ──
    case 'bonus_adjust':
        if ($method !== 'POST') jsonResponse(['ok' => false, 'error' => 'POST only'], 405);
        $raw = json_decode(file_get_contents('php://input'), true);
        $targetUserId = intval($raw['user_id'] ?? 0);
        $amount       = intval($raw['amount'] ?? 0);
        $desc         = trim($raw['description'] ?? 'Ручная корректировка');
        if (!$targetUserId || $amount === 0) jsonResponse(['ok' => false, 'error' => 'user_id и amount обязательны'], 422);
        $check = $db->prepare('SELECT id FROM users WHERE id = ?');
        $check->execute([$targetUserId]);
        if (!$check->fetch()) jsonResponse(['ok' => false, 'error' => 'Пользователь не найден'], 404);
        $type = $amount > 0 ? 'manual_earn' : 'manual_spend';
        $db->prepare('INSERT INTO bonus_log (user_id, order_id, amount, type, description) VALUES (?, NULL, ?, ?, ?)')->execute([$targetUserId, $amount, $type, $desc]);
        $bal = $db->prepare('SELECT COALESCE(SUM(amount), 0) as balance FROM bonus_log WHERE user_id = ?');
        $bal->execute([$targetUserId]);
        jsonResponse(['ok' => true, 'new_balance' => (int)$bal->fetch()['balance']]);
        break;

    // ── List users ──
    case 'users':
        $users = $db->query('
            SELECT u.id, u.name, u.phone, u.telegram, u.role, u.email, u.created_at,
                   COALESCE(u.company_name,"") as company_name,
                   COALESCE(u.inn,"") as inn,
                   COALESCE(u.kpp,"") as kpp,
                   COALESCE(u.legal_address,"") as legal_address,
                   COALESCE((SELECT SUM(amount) FROM bonus_log WHERE user_id = u.id), 0) as bonus_balance,
                   (SELECT COUNT(*) FROM orders WHERE user_id = u.id) as order_count,
                   (SELECT COALESCE(SUM(total), 0) FROM orders WHERE user_id = u.id) as total_spent
            FROM users u ORDER BY u.created_at DESC
        ')->fetchAll();
        jsonResponse(['ok' => true, 'users' => $users]);
        break;

    // ── User detail (orders + bonus log) ──
    case 'user_detail':
        $uid = intval($_GET['user_id'] ?? 0);
        if (!$uid) jsonResponse(['ok' => false, 'error' => 'user_id required'], 422);

        $user = $db->prepare('SELECT id, name, phone, telegram, role, created_at FROM users WHERE id = ?');
        $user->execute([$uid]);
        $u = $user->fetch();
        if (!$u) jsonResponse(['ok' => false, 'error' => 'Пользователь не найден'], 404);

        $orders = $db->prepare('SELECT id, total, status, bonus_earned, bonus_spent, comment, created_at FROM orders WHERE user_id = ? ORDER BY created_at DESC LIMIT 20');
        $orders->execute([$uid]);
        $orderList = $orders->fetchAll();

        $bonus = $db->prepare('SELECT amount, type, description, created_at FROM bonus_log WHERE user_id = ? ORDER BY created_at DESC LIMIT 30');
        $bonus->execute([$uid]);
        $bonusLog = $bonus->fetchAll();

        $bal = $db->prepare('SELECT COALESCE(SUM(amount),0) as b FROM bonus_log WHERE user_id = ?');
        $bal->execute([$uid]);
        $balance = (int)$bal->fetch()['b'];

        jsonResponse(['ok' => true, 'user' => $u, 'orders' => $orderList, 'bonus_log' => $bonusLog, 'bonus_balance' => $balance]);
        break;

    // ── List orders (all) with filters ──
    case 'orders':
        $page      = max(1, intval($_GET['page'] ?? 1));
        $limit     = 50;
        $offset    = ($page - 1) * $limit;
        $search    = trim($_GET['search'] ?? '');
        $status    = trim($_GET['status'] ?? '');
        $dateFrom  = trim($_GET['date_from'] ?? '');
        $dateTo    = trim($_GET['date_to'] ?? '');

        $where = []; $params = [];
        if ($status !== '')   { $where[] = 'o.status = ?';                     $params[] = $status; }
        if ($dateFrom !== '') { $where[] = "date(o.created_at) >= ?";           $params[] = $dateFrom; }
        if ($dateTo !== '')   { $where[] = "date(o.created_at) <= ?";           $params[] = $dateTo; }
        if ($search !== '') {
            $num = preg_replace('/^(SH-?|#)/i', '', $search);
            if (ctype_digit($num)) { $where[] = 'o.id = ?'; $params[] = (int)$num; }
            else                   { $where[] = 'u.name LIKE ?'; $params[] = '%'.$search.'%'; }
        }
        $whereSQL = $where ? 'WHERE '.implode(' AND ', $where) : '';

        $cntStmt = $db->prepare("SELECT COUNT(*) FROM orders o JOIN users u ON o.user_id=u.id $whereSQL");
        $cntStmt->execute($params);
        $total = (int)$cntStmt->fetchColumn();

        $orders = $db->prepare("SELECT o.*, u.name as user_name, u.phone as user_phone FROM orders o JOIN users u ON o.user_id=u.id $whereSQL ORDER BY o.created_at DESC LIMIT ? OFFSET ?");
        $orders->execute(array_merge($params, [$limit, $offset]));
        $list = $orders->fetchAll();
        foreach ($list as &$order) {
            $items = $db->prepare('SELECT product_name, price, qty FROM order_items WHERE order_id = ?');
            $items->execute([$order['id']]);
            $order['items'] = $items->fetchAll();
        }
        jsonResponse(['ok' => true, 'orders' => $list, 'total' => $total, 'page' => $page]);
        break;

    // ── Update order status ──
    case 'order_status':
        if ($method !== 'POST') jsonResponse(['ok' => false, 'error' => 'POST only'], 405);
        $raw = json_decode(file_get_contents('php://input'), true);
        $orderId = intval($raw['order_id'] ?? 0);
        $status  = trim($raw['status'] ?? '');
        $allowed = ['new','confirmed','in_progress','shipped','completed','cancelled'];
        if (!$orderId || !in_array($status, $allowed)) jsonResponse(['ok' => false, 'error' => 'Некорректные данные'], 422);
        $db->prepare('UPDATE orders SET status = ? WHERE id = ?')->execute([$status, $orderId]);
        sendOrderStatusPush($orderId, $status);
        jsonResponse(['ok' => true]);
        break;

    // ── Bulk status update ──
    case 'bulk_status':
        if ($method !== 'POST') jsonResponse(['ok' => false, 'error' => 'POST only'], 405);
        $raw      = json_decode(file_get_contents('php://input'), true);
        $ids      = array_map('intval', $raw['order_ids'] ?? []);
        $status   = trim($raw['status'] ?? '');
        $allowed  = ['new','confirmed','in_progress','shipped','completed','cancelled'];
        if (empty($ids) || !in_array($status, $allowed)) jsonResponse(['ok' => false, 'error' => 'order_ids и status обязательны'], 422);
        $ph = implode(',', array_fill(0, count($ids), '?'));
        $db->prepare("UPDATE orders SET status = ? WHERE id IN ($ph)")->execute(array_merge([$status], $ids));
        foreach ($ids as $orderId) sendOrderStatusPush($orderId, $status);
        jsonResponse(['ok' => true, 'updated' => count($ids)]);
        break;

    // ── Save admin note on order ──
    case 'admin_note':
        if ($method !== 'POST') jsonResponse(['ok' => false, 'error' => 'POST only'], 405);
        $raw     = json_decode(file_get_contents('php://input'), true);
        $orderId = intval($raw['order_id'] ?? 0);
        $note    = trim($raw['note'] ?? '');
        if (!$orderId) jsonResponse(['ok' => false, 'error' => 'order_id required'], 422);
        $db->prepare('UPDATE orders SET admin_note = ? WHERE id = ?')->execute([$note, $orderId]);
        jsonResponse(['ok' => true]);
        break;

    // ── Stats summary ──
    case 'stats':
        $stats = [
            'orders_count'   => (int)$db->query('SELECT COUNT(*) FROM orders')->fetchColumn(),
            'orders_new'     => (int)$db->query("SELECT COUNT(*) FROM orders WHERE status='new'")->fetchColumn(),
            'orders_today'   => (int)$db->query("SELECT COUNT(*) FROM orders WHERE date(created_at)=date('now')")->fetchColumn(),
            'orders_revenue' => (int)$db->query("SELECT COALESCE(SUM(total),0) FROM orders WHERE status!='cancelled'")->fetchColumn(),
            'users_count'    => (int)$db->query('SELECT COUNT(*) FROM users')->fetchColumn(),
            'guests_count'   => (int)$db->query('SELECT COUNT(*) FROM guest_orders')->fetchColumn(),
        ];
        jsonResponse(['ok' => true, 'stats' => $stats]);
        break;

    // ── Guest orders ──
    case 'guest_orders':
        $page   = max(1, intval($_GET['page'] ?? 1));
        $limit  = 50; $offset = ($page - 1) * $limit;
        $search = trim($_GET['search'] ?? '');
        $where = []; $params = [];
        if ($search !== '') {
            $num = preg_replace('/^(SH-?|#)/i', '', $search);
            if (ctype_digit($num)) {
                $where[] = 'id = ?';
                $params[] = (int)$num;
            } else {
                $where[] = '(name LIKE ? OR phone LIKE ? OR comment LIKE ?)';
                $like = '%'.$search.'%';
                array_push($params, $like, $like, $like);
            }
        }
        $whereSQL = $where ? 'WHERE '.implode(' AND ', $where) : '';
        $cntStmt = $db->prepare("SELECT COUNT(*) FROM guest_orders $whereSQL");
        $cntStmt->execute($params);
        $total = (int)$cntStmt->fetchColumn();
        $rows = $db->prepare("SELECT * FROM guest_orders $whereSQL ORDER BY created_at DESC LIMIT ? OFFSET ?");
        $rows->execute(array_merge($params, [$limit, $offset]));
        $list = $rows->fetchAll();
        foreach ($list as &$go) { $go['items'] = json_decode($go['items_json'] ?? '[]', true) ?: []; }
        jsonResponse(['ok' => true, 'orders' => $list, 'total' => $total, 'page' => $page]);
        break;

    // ── Set user role ──
    case 'set_role':
        if ($method !== 'POST') jsonResponse(['ok' => false, 'error' => 'POST only'], 405);
        $raw  = json_decode(file_get_contents('php://input'), true);
        $uid  = intval($raw['user_id'] ?? 0);
        $role = trim($raw['role'] ?? '');
        if (!$uid || !in_array($role, ['client','admin'])) jsonResponse(['ok' => false, 'error' => 'Некорректные данные'], 422);
        $targetStmt = $db->prepare('SELECT id, role FROM users WHERE id = ?');
        $targetStmt->execute([$uid]);
        $target = $targetStmt->fetch();
        if (!$target) jsonResponse(['ok' => false, 'error' => 'Пользователь не найден'], 404);
        if ($uid === (int)$currentAdminId && $role !== 'admin') jsonResponse(['ok' => false, 'error' => 'Нельзя снять роль администратора с себя'], 422);
        if ($target['role'] === 'admin' && $role !== 'admin') {
            $adminCount = (int)$db->query("SELECT COUNT(*) FROM users WHERE role='admin'")->fetchColumn();
            if ($adminCount <= 1) jsonResponse(['ok' => false, 'error' => 'Нельзя оставить систему без администратора'], 422);
        }
        $db->prepare('UPDATE users SET role = ? WHERE id = ?')->execute([$role, $uid]);
        jsonResponse(['ok' => true]);
        break;

    // ── Reset client password (+ optionally attach email) ──
    case 'reset_client_password':
        if ($method !== 'POST') jsonResponse(['ok' => false, 'error' => 'POST only'], 405);
        $raw     = json_decode(file_get_contents('php://input'), true);
        $uid     = intval($raw['user_id'] ?? 0);
        $newPass = (string)($raw['password'] ?? '');
        $email   = trim((string)($raw['email'] ?? ''));
        if (!$uid || strlen($newPass) < 4) jsonResponse(['ok' => false, 'error' => 'Нужен клиент и пароль от 4 символов'], 422);
        if ($email !== '' && !filter_var($email, FILTER_VALIDATE_EMAIL)) jsonResponse(['ok' => false, 'error' => 'Некорректный email'], 422);
        if ($email !== '') {
            $db->prepare('UPDATE users SET password_hash = ?, email = ? WHERE id = ?')
               ->execute([password_hash($newPass, PASSWORD_BCRYPT), $email, $uid]);
        } else {
            $db->prepare('UPDATE users SET password_hash = ? WHERE id = ?')
               ->execute([password_hash($newPass, PASSWORD_BCRYPT), $uid]);
        }
        try { $db->prepare('DELETE FROM mobile_sessions WHERE user_id = ?')->execute([$uid]); } catch (Throwable $e) {}
        jsonResponse(['ok' => true]);
        break;

    // ── Send Telegram report on demand ──
    case 'send_report':
        if ($method !== 'POST') jsonResponse(['ok' => false, 'error' => 'POST only'], 405);
        require_once __DIR__ . '/lib/app_config.php';
        $token  = defined('BOT_TOKEN') ? BOT_TOKEN : '';
        $chatId = defined('CHAT_ID')   ? CHAT_ID   : '';
        if (!$token || !$chatId) jsonResponse(['ok' => false, 'error' => 'Bot not configured'], 500);

        $cnt    = (int)$db->query('SELECT COUNT(*) FROM orders')->fetchColumn();
        $newCnt = (int)$db->query("SELECT COUNT(*) FROM orders WHERE status='new'")->fetchColumn();
        $today  = (int)$db->query("SELECT COUNT(*) FROM orders WHERE date(created_at)=date('now')")->fetchColumn();
        $rev    = (int)$db->query("SELECT COALESCE(SUM(total),0) FROM orders WHERE status!='cancelled'")->fetchColumn();
        $guests = (int)$db->query('SELECT COUNT(*) FROM guest_orders')->fetchColumn();
        $recent = $db->query("SELECT o.id,o.total,o.status,o.created_at,u.name FROM orders o JOIN users u ON o.user_id=u.id ORDER BY o.created_at DESC LIMIT 7")->fetchAll();

        $sIco = ['new'=>'🆕','confirmed'=>'✅','in_progress'=>'⚙️','shipped'=>'📦','completed'=>'✔️','cancelled'=>'❌'];
        $msg  = "📊 *Отчёт СплитХаб* (по запросу)\n━━━━━━━━━━━━━━━━\n";
        $msg .= "📦 Всего: *{$cnt}*  |  🆕 Новых: *{$newCnt}*\n";
        $msg .= "📅 Сегодня: *{$today}*  |  👥 Гостевых: *{$guests}*\n";
        $msg .= "💰 Выручка: *".number_format($rev,0,'.',' ')." ₽*\n";
        if ($recent) {
            $msg .= "━━━━━━━━━━━━━━━━\n🕐 Последние:\n";
            foreach ($recent as $r) {
                $ico = $sIco[$r['status']] ?? '•';
                $msg .= "{$ico} SH-".str_pad($r['id'],5,'0',STR_PAD_LEFT)." · {$r['name']} · ".number_format($r['total'],0,'.',' ')." ₽\n";
            }
        }
        $ch = curl_init("https://api.telegram.org/bot{$token}/sendMessage");
        curl_setopt_array($ch,[CURLOPT_POST=>true,CURLOPT_POSTFIELDS=>json_encode(['chat_id'=>$chatId,'text'=>$msg,'parse_mode'=>'Markdown']),CURLOPT_HTTPHEADER=>['Content-Type: application/json'],CURLOPT_RETURNTRANSFER=>true,CURLOPT_TIMEOUT=>5,CURLOPT_SSL_VERIFYPEER=>false,CURLOPT_RESOLVE=>['api.telegram.org:443:'.(defined('TG_FORCE_IP')?TG_FORCE_IP:'149.154.167.220')]]);
        $res = curl_exec($ch); curl_close($ch);
        $ok  = (bool)(json_decode($res,true)['ok'] ?? false);
        jsonResponse(['ok' => $ok]);
        break;

    // ── Analytics ──
    case 'analytics':
        $days = max(1, min(30, (int)($_GET['days'] ?? 7)));
        $from = date('Y-m-d H:i:s', strtotime("-{$days} days"));
        $byDay = $db->prepare("SELECT date(created_at) as day, COUNT(*) as cnt, COALESCE(SUM(total),0) as rev FROM orders WHERE created_at >= ? GROUP BY day ORDER BY day ASC");
        $byDay->execute([$from]); $dailyData = $byDay->fetchAll();
        $byStatus = $db->query("SELECT status, COUNT(*) as cnt FROM orders GROUP BY status")->fetchAll();
        $topP = $db->prepare("SELECT oi.product_name, SUM(oi.qty) as qty, SUM(oi.price*oi.qty) as rev FROM order_items oi JOIN orders o ON o.id=oi.order_id WHERE o.created_at >= ? GROUP BY oi.product_name ORDER BY rev DESC LIMIT 5");
        $topP->execute([$from]); $topProducts = $topP->fetchAll();
        jsonResponse(['ok'=>true,'daily'=>$dailyData,'by_status'=>$byStatus,'top_products'=>$topProducts]);
        break;

    // ── Settings get ──
    case 'settings_get':
        require_once __DIR__ . '/lib/app_config.php';
        $cfgFile = appConfigPath();
        $cfg = [];
        if (file_exists($cfgFile)) {
            $lines = file($cfgFile, FILE_IGNORE_NEW_LINES);
            foreach ($lines as $line) {
                if (preg_match("/define\('([^']+)',\s*'([^']*)'\)/", $line, $m)) {
                    $cfg[$m[1]] = $m[2];
                } elseif (preg_match('/define\(\'([^\']+)\',\s*(\d+)\)/', $line, $m)) {
                    $cfg[$m[1]] = $m[2];
                }
            }
        }
        // Merge app_settings (bonuses_enabled etc.)
        try {
            $appRows = $db->query("SELECT key, value FROM app_settings")->fetchAll();
            foreach ($appRows as $r) { $cfg[$r['key']] = $r['value']; }
        } catch (Throwable $e) {}
        jsonResponse(['ok' => true, 'settings' => $cfg]);
        break;

    // ── Settings save ──
    case 'settings_save':
        if ($method !== 'POST') jsonResponse(['ok' => false, 'error' => 'POST only'], 405);
        require_once __DIR__ . '/lib/app_config.php';
        $raw = json_decode(file_get_contents('php://input'), true);
        if (!is_array($raw)) $raw = [];
        $allowed_keys = ['BOT_TOKEN','CHAT_ID','TG_ADMIN_ID','EMAIL_TO','CRON_SECRET','ALLOWED_ORIGIN','TG_FORCE_IP'];
        $cfgFile = appConfigPath();

        $content = "<?php\n";
        foreach ($allowed_keys as $key) {
            if (array_key_exists($key, $raw)) {
                $val = trim($raw[$key]);
            } elseif (defined($key)) {
                $val = (string)constant($key);
            } else {
                continue;
            }
            $val = addslashes($val);
            $content .= "define('{$key}', '{$val}');\n";
        }
        $rateLimit = defined('RATE_LIMIT_SEC') ? (int)RATE_LIMIT_SEC : 30;
        $content .= "define('RATE_LIMIT_SEC', {$rateLimit});\n";

        file_put_contents($cfgFile, $content);

        // Save app_settings (bonuses_enabled)
        if (isset($raw['bonuses_enabled'])) {
            $bval = ($raw['bonuses_enabled'] === true || $raw['bonuses_enabled'] === '1' || $raw['bonuses_enabled'] === 1) ? '1' : '0';
            try {
                $db->prepare("INSERT OR REPLACE INTO app_settings (key, value) VALUES ('bonuses_enabled', ?)")->execute([$bval]);
            } catch (Throwable $e) {}
        }
        jsonResponse(['ok' => true]);
        break;

    // ── Upload product photo ──
    case 'upload_photo':
        if ($method !== 'POST') jsonResponse(['ok' => false, 'error' => 'POST only'], 405);
        if (empty($_FILES['photo']) || !is_uploaded_file($_FILES['photo']['tmp_name'])) {
            jsonResponse(['ok' => false, 'error' => 'photo required'], 422);
        }
        if (($_FILES['photo']['size'] ?? 0) > 8 * 1024 * 1024) {
            jsonResponse(['ok' => false, 'error' => 'Файл больше 8 МБ'], 422);
        }
        $original = $_FILES['photo']['name'] ?? 'photo';
        $ext = strtolower(pathinfo($original, PATHINFO_EXTENSION));
        $allowed = ['jpg','jpeg','png','webp','gif'];
        if (!in_array($ext, $allowed, true)) jsonResponse(['ok' => false, 'error' => 'Поддерживаются JPG, PNG, WEBP, GIF'], 422);
        $dir = __DIR__ . '/../assets/img/products';
        if (!is_dir($dir) && !mkdir($dir, 0775, true)) {
            jsonResponse(['ok' => false, 'error' => 'Не удалось создать папку изображений'], 500);
        }
        $filename = 'custom_' . date('Ymd_His') . '_' . bin2hex(random_bytes(4)) . '.' . $ext;
        $target = $dir . '/' . $filename;
        if (!move_uploaded_file($_FILES['photo']['tmp_name'], $target)) {
            jsonResponse(['ok' => false, 'error' => 'Не удалось сохранить файл'], 500);
        }
        jsonResponse(['ok' => true, 'filename' => $filename, 'path' => 'assets/img/products/' . $filename]);
        break;

    // ── List products + overrides ──
    case 'products_list':
        $products = adminReadProductsJs();
        $ovRows = $db->query("SELECT sku, description, badge, badge_label, active, data_json, updated_at FROM product_overrides")->fetchAll();
        $ovMap = [];
        foreach ($ovRows as $r) { $ovMap[$r['sku']] = adminDecodeOverrideRow($r); }

        foreach ($products as &$p) {
            $sku = $p['sku'] ?? '';
            $ov = $sku && isset($ovMap[$sku]) ? $ovMap[$sku] : null;
            $p = adminApplyProductOverride($p, $ov);
            $p['_source'] = 'base';
            $p['_is_custom'] = false;
            $p['_override'] = $ov;
            $p['_base'] = $p['_base'] ?? null;
        }
        unset($p);

        $customRows = $db->query("SELECT id, sku, data_json, active, updated_at, created_at FROM custom_products ORDER BY created_at DESC")->fetchAll();
        foreach ($customRows as $r) {
            $products[] = adminDecodeCustomProductRow($r);
        }

        $search = trim($_GET['search'] ?? '');
        $group = trim($_GET['group'] ?? '');
        $status = trim($_GET['status'] ?? 'all');
        if ($search !== '') {
            $sl = mb_strtolower($search);
            $products = array_values(array_filter($products, function($p) use ($sl) {
                return mb_strpos(mb_strtolower($p['model'] ?? ''), $sl) !== false
                    || mb_strpos(mb_strtolower($p['brand'] ?? ''), $sl) !== false
                    || mb_strpos(mb_strtolower($p['sku'] ?? ''), $sl) !== false
                    || mb_strpos(mb_strtolower($p['series'] ?? ''), $sl) !== false;
            }));
        }
        if ($group !== '') {
            $products = array_values(array_filter($products, function($p) use ($group) {
                return ($p['group'] ?? '') === $group;
            }));
        }
        if ($status === 'active') {
            $products = array_values(array_filter($products, function($p) {
                return (int)($p['_active'] ?? 1) === 1;
            }));
        } elseif ($status === 'hidden') {
            $products = array_values(array_filter($products, function($p) {
                return (int)($p['_active'] ?? 1) === 0;
            }));
        }
        $limit = max(20, min(500, (int)($_GET['limit'] ?? 300)));
        $page = max(1, (int)($_GET['page'] ?? 1));
        $offset = ($page - 1) * $limit;
        jsonResponse([
            'ok' => true,
            'products' => array_slice($products, $offset, $limit),
            'total' => count($products),
            'page' => $page,
            'limit' => $limit
        ]);
        break;

    // ── Save product override ──
    case 'product_save_override':
        if ($method !== 'POST') jsonResponse(['ok' => false, 'error' => 'POST only'], 405);
        $raw = json_decode(file_get_contents('php://input'), true);
        if (!is_array($raw)) $raw = [];
        $sku    = trim($raw['sku'] ?? '');
        if (!$sku) jsonResponse(['ok' => false, 'error' => 'sku required'], 422);
        $data = adminNormalizeProductPayload($raw, false);
        $desc   = trim($raw['description'] ?? ($data['description'] ?? ''));
        $badge  = trim($raw['badge'] ?? ($data['badge'] ?? ''));
        $blabel = trim($raw['badge_label'] ?? ($data['badge_label'] ?? ''));
        $active = array_key_exists('active', $raw) ? (int)!!$raw['active'] : 1;
        if (!in_array($badge, ['', 'new', 'sale', 'clearance'])) jsonResponse(['ok' => false, 'error' => 'Invalid badge'], 422);
        unset($data['id'], $data['sku'], $data['active'], $data['is_custom'], $data['_source'], $data['_is_custom']);
        $db->prepare("INSERT INTO product_overrides (sku, description, badge, badge_label, active, data_json, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(sku) DO UPDATE SET
                description = excluded.description,
                badge = excluded.badge,
                badge_label = excluded.badge_label,
                active = excluded.active,
                data_json = excluded.data_json,
                updated_at = CURRENT_TIMESTAMP")
            ->execute([$sku, $desc, $badge, $blabel, $active, json_encode($data, JSON_UNESCAPED_UNICODE | JSON_UNESCAPED_SLASHES)]);
        jsonResponse(['ok' => true]);
        break;

    // ── Delete product override ──
    case 'product_override_delete':
        if ($method !== 'POST') jsonResponse(['ok' => false, 'error' => 'POST only'], 405);
        $raw = json_decode(file_get_contents('php://input'), true);
        $sku = trim($raw['sku'] ?? '');
        if (!$sku) jsonResponse(['ok' => false, 'error' => 'sku required'], 422);
        $db->prepare('DELETE FROM product_overrides WHERE sku = ?')->execute([$sku]);
        jsonResponse(['ok' => true]);
        break;

    // ── Save custom product ──
    case 'custom_product_save':
        if ($method !== 'POST') jsonResponse(['ok' => false, 'error' => 'POST only'], 405);
        $raw = json_decode(file_get_contents('php://input'), true);
        $data = adminNormalizeProductPayload($raw, true);
        $sku = trim($data['sku'] ?? ($raw['sku'] ?? ''));
        if ($sku === '') jsonResponse(['ok' => false, 'error' => 'sku required'], 422);
        if (trim($data['model'] ?? '') === '') jsonResponse(['ok' => false, 'error' => 'model required'], 422);
        $active = array_key_exists('active', $raw) ? (int)!!$raw['active'] : (int)($data['active'] ?? 1);
        $id = trim($data['id'] ?? ($raw['id'] ?? ''));
        if ($id === '') $id = adminProductIdFromSku($sku);
        $data['id'] = $id;
        $data['sku'] = $sku;
        $data['active'] = $active;
        $db->prepare("INSERT INTO custom_products (id, sku, data_json, active, updated_at, created_at)
            VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
            ON CONFLICT(sku) DO UPDATE SET
                id = excluded.id,
                data_json = excluded.data_json,
                active = excluded.active,
                updated_at = CURRENT_TIMESTAMP")
            ->execute([$id, $sku, json_encode($data, JSON_UNESCAPED_UNICODE | JSON_UNESCAPED_SLASHES), $active]);
        jsonResponse(['ok' => true, 'product' => $data]);
        break;

    // ── Delete custom product ──
    case 'custom_product_delete':
        if ($method !== 'POST') jsonResponse(['ok' => false, 'error' => 'POST only'], 405);
        $raw = json_decode(file_get_contents('php://input'), true);
        $sku = trim($raw['sku'] ?? '');
        $id = trim($raw['id'] ?? '');
        if ($sku === '' && $id === '') jsonResponse(['ok' => false, 'error' => 'sku or id required'], 422);
        $stmt = $db->prepare('DELETE FROM custom_products WHERE sku = ? OR id = ?');
        $stmt->execute([$sku, $id]);
        jsonResponse(['ok' => true, 'deleted' => $stmt->rowCount()]);
        break;

    // ── Send generated price list to TG or email ──
    case 'send_pricelist':
        if ($method !== 'POST') jsonResponse(['ok' => false, 'error' => 'POST only'], 405);
        $raw      = json_decode(file_get_contents('php://input'), true);
        $b64data  = $raw['data'] ?? '';
        $filename = preg_replace('/[^a-z0-9_\-\.]/i', '_', $raw['filename'] ?? 'pricelist.xlsx');
        $channel  = trim($raw['channel'] ?? 'tg');
        if (!$b64data) jsonResponse(['ok' => false, 'error' => 'data required'], 422);

        $fileContent = base64_decode($b64data);
        if (!$fileContent) jsonResponse(['ok' => false, 'error' => 'Invalid base64 data'], 422);
        $ext = strtolower(pathinfo($filename, PATHINFO_EXTENSION));
        $mime = $ext === 'pdf'
            ? 'application/pdf'
            : 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet';

        $tmpPath = sys_get_temp_dir() . '/' . uniqid('price_', true) . '_' . $filename;
        file_put_contents($tmpPath, $fileContent);

        $cfgFile = __DIR__ . '/../config.php';
        if (file_exists($cfgFile)) require_once $cfgFile;
        $errors = [];

        if ($channel === 'tg' || $channel === 'both') {
            $token  = defined('BOT_TOKEN') ? BOT_TOKEN : '';
            $chatId = defined('CHAT_ID') ? CHAT_ID : '';
            if (!$token || !$chatId) {
                $errors[] = 'Telegram не настроен';
            } else {
                $ch = curl_init("https://api.telegram.org/bot{$token}/sendDocument");
                curl_setopt_array($ch, [
                    CURLOPT_POST => true,
                    CURLOPT_POSTFIELDS => [
                        'chat_id' => $chatId,
                        'document' => new CURLFile($tmpPath, $mime, $filename),
                        'caption' => 'Прайс-лист СплитХаб',
                    ],
                    CURLOPT_RETURNTRANSFER => true,
                    CURLOPT_TIMEOUT => 30,
                    CURLOPT_SSL_VERIFYPEER => false,
                    CURLOPT_RESOLVE => ['api.telegram.org:443:'.(defined('TG_FORCE_IP') ? TG_FORCE_IP : '149.154.167.220')],
                ]);
                $res = curl_exec($ch); curl_close($ch);
                $tgResult = json_decode($res, true);
                if (!($tgResult['ok'] ?? false)) $errors[] = 'TG: ' . ($tgResult['description'] ?? 'Ошибка');
            }
        }

        if ($channel === 'email' || $channel === 'both') {
            $emailTo = defined('EMAIL_TO') ? EMAIL_TO : '';
            if (!$emailTo) {
                $errors[] = 'Email не настроен';
            } else {
                $boundary = md5(uniqid('', true));
                $headers  = "From: noreply@splithub.ru\r\nMIME-Version: 1.0\r\nContent-Type: multipart/mixed; boundary=\"{$boundary}\"";
                $body  = "--{$boundary}\r\nContent-Type: text/plain; charset=utf-8\r\n\r\nПрайс-лист СплитХаб во вложении.\r\n";
                $body .= "--{$boundary}\r\nContent-Type: {$mime}\r\n";
                $body .= "Content-Transfer-Encoding: base64\r\nContent-Disposition: attachment; filename=\"{$filename}\"\r\n\r\n";
                $body .= chunk_split($b64data) . "\r\n--{$boundary}--";
                if (!mail($emailTo, 'Прайс-лист СплитХаб', $body, $headers)) $errors[] = 'Email: ошибка отправки';
            }
        }

        @unlink($tmpPath);
        if ($errors) jsonResponse(['ok' => false, 'error' => implode('; ', $errors)]);
        jsonResponse(['ok' => true]);
        break;

    // ── Guest orders: bulk status ──
    case 'bulk_status_guest':
        if ($method !== 'POST') jsonResponse(['ok' => false, 'error' => 'POST only'], 405);
        try { $db->exec("ALTER TABLE guest_orders ADD COLUMN status TEXT DEFAULT 'new'"); } catch (Throwable $e) {}
        $raw    = json_decode(file_get_contents('php://input'), true);
        $ids    = array_map('intval', $raw['order_ids'] ?? []);
        $status = trim($raw['status'] ?? '');
        $allowed = ['new','confirmed','in_progress','completed','cancelled'];
        if (empty($ids) || !in_array($status, $allowed)) jsonResponse(['ok' => false, 'error' => 'order_ids и status обязательны'], 422);
        $ph = implode(',', array_fill(0, count($ids), '?'));
        $db->prepare("UPDATE guest_orders SET status = ? WHERE id IN ($ph)")->execute(array_merge([$status], $ids));
        jsonResponse(['ok' => true, 'updated' => count($ids)]);
        break;

    // ── Guest orders: bulk delete ──
    case 'bulk_delete_guest_orders':
        if ($method !== 'POST') jsonResponse(['ok' => false, 'error' => 'POST only'], 405);
        $raw = json_decode(file_get_contents('php://input'), true);
        $ids = array_map('intval', $raw['order_ids'] ?? []);
        if (empty($ids)) jsonResponse(['ok' => false, 'error' => 'order_ids required'], 422);
        $ph = implode(',', array_fill(0, count($ids), '?'));
        $db->prepare("DELETE FROM guest_orders WHERE id IN ($ph)")->execute($ids);
        jsonResponse(['ok' => true, 'deleted' => count($ids)]);
        break;

    // ── Delete order ──
    case 'delete_order':
        if ($method !== 'POST') jsonResponse(['ok' => false, 'error' => 'POST only'], 405);
        $raw = json_decode(file_get_contents('php://input'), true);
        $orderId = intval($raw['order_id'] ?? 0);
        if (!$orderId) jsonResponse(['ok' => false, 'error' => 'order_id required'], 422);
        $db->prepare('DELETE FROM order_items WHERE order_id = ?')->execute([$orderId]);
        $db->prepare('UPDATE bonus_log SET order_id = NULL WHERE order_id = ?')->execute([$orderId]);
        $db->prepare('DELETE FROM orders WHERE id = ?')->execute([$orderId]);
        jsonResponse(['ok' => true]);
        break;

    // ── Bulk delete orders ──
    case 'bulk_delete_orders':
        if ($method !== 'POST') jsonResponse(['ok' => false, 'error' => 'POST only'], 405);
        $raw = json_decode(file_get_contents('php://input'), true);
        $ids = array_map('intval', $raw['order_ids'] ?? []);
        if (empty($ids)) jsonResponse(['ok' => false, 'error' => 'order_ids required'], 422);
        $ph = implode(',', array_fill(0, count($ids), '?'));
        $db->prepare("DELETE FROM order_items WHERE order_id IN ($ph)")->execute($ids);
        $db->prepare("UPDATE bonus_log SET order_id = NULL WHERE order_id IN ($ph)")->execute($ids);
        $db->prepare("DELETE FROM orders WHERE id IN ($ph)")->execute($ids);
        jsonResponse(['ok' => true, 'deleted' => count($ids)]);
        break;

    // ── Delete user ──
    case 'delete_user':
        if ($method !== 'POST') jsonResponse(['ok' => false, 'error' => 'POST only'], 405);
        $raw = json_decode(file_get_contents('php://input'), true);
        $uid = intval($raw['user_id'] ?? 0);
        if (!$uid) jsonResponse(['ok' => false, 'error' => 'user_id required'], 422);
        if ($uid === (int)$currentAdminId) jsonResponse(['ok' => false, 'error' => 'Нельзя удалить себя'], 422);
        $targetStmt = $db->prepare('SELECT id, role FROM users WHERE id = ?');
        $targetStmt->execute([$uid]);
        $target = $targetStmt->fetch();
        if (!$target) jsonResponse(['ok' => false, 'error' => 'Пользователь не найден'], 404);
        if (($target['role'] ?? '') === 'admin') {
            $adminCount = (int)$db->query("SELECT COUNT(*) FROM users WHERE role='admin'")->fetchColumn();
            if ($adminCount <= 1) jsonResponse(['ok' => false, 'error' => 'Нельзя удалить последнего администратора'], 422);
        }
        $userOrders = $db->prepare('SELECT id FROM orders WHERE user_id = ?');
        $userOrders->execute([$uid]);
        $orderIds = array_column($userOrders->fetchAll(), 'id');
        if ($orderIds) {
            $ph = implode(',', array_fill(0, count($orderIds), '?'));
            $db->prepare("DELETE FROM order_items WHERE order_id IN ($ph)")->execute($orderIds);
        }
        $db->prepare('DELETE FROM bonus_log WHERE user_id = ?')->execute([$uid]);
        $db->prepare('DELETE FROM orders WHERE user_id = ?')->execute([$uid]);
        try {
            $devStmt = $db->prepare('SELECT id FROM mobile_devices WHERE user_id = ?');
            $devStmt->execute([$uid]);
            $deviceIds = array_column($devStmt->fetchAll(), 'id');
            if ($deviceIds) {
                $dph = implode(',', array_fill(0, count($deviceIds), '?'));
                $db->prepare("DELETE FROM push_deliveries WHERE device_id IN ($dph)")->execute($deviceIds);
            }
            $db->prepare('DELETE FROM mobile_sessions WHERE user_id = ?')->execute([$uid]);
            $db->prepare('DELETE FROM mobile_devices WHERE user_id = ?')->execute([$uid]);
            $db->prepare('UPDATE push_campaigns SET user_id = NULL WHERE user_id = ?')->execute([$uid]);
        } catch (Throwable $e) {}
        $db->prepare('DELETE FROM users WHERE id = ?')->execute([$uid]);
        jsonResponse(['ok' => true]);
        break;

    // ── Edit user ──
    case 'edit_user':
        if ($method !== 'POST') jsonResponse(['ok' => false, 'error' => 'POST only'], 405);
        $raw = json_decode(file_get_contents('php://input'), true);
        $uid = intval($raw['user_id'] ?? 0);
        if (!$uid) jsonResponse(['ok' => false, 'error' => 'user_id required'], 422);
        $allowed = ['name','phone','telegram','company_name','inn','kpp','legal_address'];
        $fields = []; $vals = [];
        foreach ($allowed as $f) {
            if (array_key_exists($f, $raw)) {
                $fields[] = "$f = ?";
                $val = trim($raw[$f] ?? '');
                if ($f === 'phone') $val = normalizePhone($val);
                $vals[] = $val;
            }
        }
        if (empty($fields)) jsonResponse(['ok' => false, 'error' => 'No fields to update'], 422);
        $vals[] = $uid;
        $db->prepare('UPDATE users SET ' . implode(', ', $fields) . ' WHERE id = ?')->execute($vals);
        jsonResponse(['ok' => true]);
        break;

    // ── Month close ──
    case 'month_close':
        if ($method !== 'POST') jsonResponse(['ok' => false, 'error' => 'POST only'], 405);
        $raw    = json_decode(file_get_contents('php://input'), true);
        $period = trim($raw['period'] ?? '');
        $notes  = trim($raw['notes'] ?? '');
        if (!preg_match('/^\d{4}-\d{2}$/', $period)) jsonResponse(['ok' => false, 'error' => 'period format: YYYY-MM'], 422);
        $pStart = $period . '-01';
        $pEnd   = date('Y-m-t', strtotime($pStart));
        $stats  = $db->prepare("SELECT COUNT(*) as orders_count, COALESCE(SUM(total),0) as revenue, SUM(CASE WHEN status='completed' THEN 1 ELSE 0 END) as completed_count, SUM(CASE WHEN status='cancelled' THEN 1 ELSE 0 END) as cancelled_count, COALESCE(AVG(CASE WHEN status!='cancelled' THEN total END),0) as avg_order FROM orders WHERE date(created_at) BETWEEN ? AND ?");
        $stats->execute([$pStart, $pEnd]);
        $s = $stats->fetch();
        $ncStmt = $db->prepare("SELECT COUNT(*) FROM users WHERE date(created_at) BETWEEN ? AND ?");
        $ncStmt->execute([$pStart, $pEnd]);
        $newClients = (int)$ncStmt->fetchColumn();
        $db->prepare("INSERT OR REPLACE INTO monthly_reports (period, orders_count, revenue, new_clients, completed_count, cancelled_count, avg_order, notes, closed_at) VALUES (?,?,?,?,?,?,?,?,CURRENT_TIMESTAMP)")
            ->execute([$period, (int)$s['orders_count'], (int)$s['revenue'], $newClients, (int)$s['completed_count'], (int)$s['cancelled_count'], (int)$s['avg_order'], $notes]);
        jsonResponse(['ok' => true, 'period' => $period, 'stats' => $s, 'new_clients' => $newClients]);
        break;

    // ── Month report list ──
    case 'month_report_list':
        $reports = $db->query('SELECT * FROM monthly_reports ORDER BY period DESC LIMIT 24')->fetchAll();
        jsonResponse(['ok' => true, 'reports' => $reports]);
        break;

    // ── Change password ──
    case 'change_password':
        if ($method !== 'POST') jsonResponse(['ok' => false, 'error' => 'POST only'], 405);
        $raw = json_decode(file_get_contents('php://input'), true);
        $targetUid = intval($raw['user_id'] ?? 0);
        $newPass   = $raw['new_password'] ?? '';
        if (!$targetUid || strlen($newPass) < 4) jsonResponse(['ok' => false, 'error' => 'user_id и пароль (мин. 4 символа) обязательны'], 422);
        $hash = password_hash($newPass, PASSWORD_DEFAULT);
        $db->prepare('UPDATE users SET password_hash = ? WHERE id = ?')->execute([$hash, $targetUid]);
        jsonResponse(['ok' => true]);
        break;

    // ── Toggle product active ──
    case 'product_toggle_active':
        if ($method !== 'POST') jsonResponse(['ok' => false, 'error' => 'POST only'], 405);
        $raw    = json_decode(file_get_contents('php://input'), true);
        $sku    = trim($raw['sku'] ?? '');
        $active = intval($raw['active'] ?? 1);
        if (!$sku) jsonResponse(['ok' => false, 'error' => 'sku required'], 422);
        $custom = $db->prepare('SELECT id FROM custom_products WHERE sku = ? OR id = ?');
        $custom->execute([$sku, $sku]);
        if ($custom->fetch()) {
            $db->prepare('UPDATE custom_products SET active = ?, updated_at = CURRENT_TIMESTAMP WHERE sku = ? OR id = ?')
                ->execute([$active, $sku, $sku]);
        } else {
            $db->prepare("INSERT INTO product_overrides (sku, active) VALUES (?, ?) ON CONFLICT(sku) DO UPDATE SET active=excluded.active, updated_at=CURRENT_TIMESTAMP")
                ->execute([$sku, $active]);
        }
        jsonResponse(['ok' => true]);
        break;

    // ── Bulk toggle products active ──
    case 'product_bulk_toggle_active':
        if ($method !== 'POST') jsonResponse(['ok' => false, 'error' => 'POST only'], 405);
        $raw    = json_decode(file_get_contents('php://input'), true);
        $skus   = array_filter(array_map('trim', $raw['skus'] ?? []), 'strlen');
        $active = intval($raw['active'] ?? 1);
        if (empty($skus)) jsonResponse(['ok' => false, 'error' => 'skus required'], 422);
        foreach ($skus as $sku) {
            $custom = $db->prepare('SELECT id FROM custom_products WHERE sku = ? OR id = ?');
            $custom->execute([$sku, $sku]);
            if ($custom->fetch()) {
                $db->prepare('UPDATE custom_products SET active = ?, updated_at = CURRENT_TIMESTAMP WHERE sku = ? OR id = ?')
                    ->execute([$active, $sku, $sku]);
            } else {
                $db->prepare("INSERT INTO product_overrides (sku, active) VALUES (?, ?) ON CONFLICT(sku) DO UPDATE SET active=excluded.active, updated_at=CURRENT_TIMESTAMP")
                    ->execute([$sku, $active]);
            }
        }
        jsonResponse(['ok' => true, 'updated' => count($skus)]);
        break;

    // ── Send order to TG or email ──
    case 'order_send':
        if ($method !== 'POST') jsonResponse(['ok' => false, 'error' => 'POST only'], 405);
        $raw     = json_decode(file_get_contents('php://input'), true);
        $orderId = intval($raw['order_id'] ?? 0);
        $channel = trim($raw['channel'] ?? 'tg');
        if (!$orderId) jsonResponse(['ok' => false, 'error' => 'order_id required'], 422);

        $ord = $db->prepare('SELECT o.*, u.name as uname, u.phone as uphone, u.telegram as utg FROM orders o JOIN users u ON o.user_id=u.id WHERE o.id=?');
        $ord->execute([$orderId]);
        $o = $ord->fetch();
        if (!$o) jsonResponse(['ok' => false, 'error' => 'Заказ не найден'], 404);
        $items = $db->prepare('SELECT product_name, price, qty FROM order_items WHERE order_id=?');
        $items->execute([$orderId]);
        $itemList = $items->fetchAll();

        $shNum = 'SH-' . str_pad($orderId, 5, '0', STR_PAD_LEFT);
        $sNames = ['new'=>'Новый','confirmed'=>'Подтверждён','in_progress'=>'В работе','shipped'=>'Отгружен','completed'=>'Выполнен','cancelled'=>'Отменён'];
        $cfgFile = __DIR__ . '/../config.php';
        if (file_exists($cfgFile)) require_once $cfgFile;

        if ($channel === 'tg') {
            $token  = defined('BOT_TOKEN') ? BOT_TOKEN : '';
            $chatId = defined('TG_ADMIN_ID') ? TG_ADMIN_ID : (defined('CHAT_ID') ? CHAT_ID : '');
            if (!$token || !$chatId) jsonResponse(['ok' => false, 'error' => 'Telegram не настроен'], 500);

            $msg = "*{$shNum}*\n";
            $msg .= "━━━━━━━━━━━━━━\n";
            $msg .= "Клиент: {$o['uname']} / +{$o['uphone']}\n";
            if ($o['utg']) $msg .= "Telegram: @{$o['utg']}\n";
            $msg .= "Дата: {$o['created_at']}\n";
            $msg .= "Статус: " . ($sNames[$o['status']] ?? $o['status']) . "\n";
            $msg .= "━━━━━━━━━━━━━━\n";
            foreach ($itemList as $it) {
                $msg .= "• {$it['product_name']} x{$it['qty']} — " . number_format($it['price'] * $it['qty'], 0, '.', ' ') . " ₽\n";
            }
            $msg .= "━━━━━━━━━━━━━━\n";
            $msg .= "Итого: *" . number_format($o['total'], 0, '.', ' ') . " ₽*\n";
            if ($o['bonus_earned'] > 0) $msg .= "Бонусов начислено: +{$o['bonus_earned']}\n";
            if ($o['bonus_spent']  > 0) $msg .= "Бонусов списано: -{$o['bonus_spent']}\n";
            if ($o['comment'])    $msg .= "Комментарий: {$o['comment']}\n";
            if ($o['admin_note']) $msg .= "Заметка: {$o['admin_note']}\n";

            $ch = curl_init("https://api.telegram.org/bot{$token}/sendMessage");
            curl_setopt_array($ch, [
                CURLOPT_POST => true,
                CURLOPT_RETURNTRANSFER => true,
                CURLOPT_TIMEOUT => 10,
                CURLOPT_SSL_VERIFYPEER => false,
                CURLOPT_HTTPHEADER => ['Content-Type: application/json'],
                CURLOPT_POSTFIELDS => json_encode(['chat_id'=>$chatId,'text'=>$msg,'parse_mode'=>'Markdown']),
                CURLOPT_RESOLVE => ['api.telegram.org:443:'.(defined('TG_FORCE_IP') ? TG_FORCE_IP : '149.154.167.220')],
            ]);
            $res = curl_exec($ch); curl_close($ch);
            $ok2 = (bool)(json_decode($res, true)['ok'] ?? false);
            jsonResponse(['ok' => $ok2, 'error' => $ok2 ? null : 'Ошибка Telegram']);
        } else {
            $to = defined('EMAIL_TO') ? EMAIL_TO : '';
            if (!$to) jsonResponse(['ok' => false, 'error' => 'Email не настроен'], 500);
            $subject = "Заказ {$shNum} — " . ($sNames[$o['status']] ?? $o['status']);
            $body = "Заказ: {$shNum}\r\nКлиент: {$o['uname']} / +{$o['uphone']}\r\n";
            $body .= "Статус: " . ($sNames[$o['status']] ?? $o['status']) . "\r\n";
            $body .= "Дата: {$o['created_at']}\r\n\r\nТовары:\r\n";
            foreach ($itemList as $it) {
                $body .= "  {$it['product_name']} x{$it['qty']} — " . ($it['price'] * $it['qty']) . " ₽\r\n";
            }
            $body .= "\r\nИтого: {$o['total']} ₽";
            if ($o['comment']) $body .= "\r\nКомментарий: {$o['comment']}";
            $headers = "From: noreply@splithub.ru\r\nContent-Type: text/plain; charset=UTF-8";
            $sent = mail($to, $subject, $body, $headers);
            jsonResponse(['ok' => $sent, 'error' => $sent ? null : 'Ошибка mail()']);
        }
        break;

    // ── Reset order counter ──
    case 'reset_counter':
        if ($method !== 'POST') jsonResponse(['ok' => false, 'error' => 'POST only'], 405);
        $raw  = json_decode(file_get_contents('php://input'), true);
        $type = trim($raw['type'] ?? 'orders');
        $tables = [];
        if ($type === 'orders' || $type === 'all') $tables[] = 'orders';
        if ($type === 'guest_orders' || $type === 'all') $tables[] = 'guest_orders';
        if (!$tables) jsonResponse(['ok' => false, 'error' => 'Некорректный тип'], 422);
        foreach ($tables as $tbl) {
            try { $db->exec("DELETE FROM sqlite_sequence WHERE name='{$tbl}'"); } catch (Throwable $e) {}
        }
        jsonResponse(['ok' => true, 'reset' => $tables]);
        break;

    // ── Mobile push notifications ──
    case 'push_promotion':
        if ($method !== 'POST') jsonResponse(['ok' => false, 'error' => 'POST only'], 405);
        $raw = json_decode(file_get_contents('php://input'), true) ?: [];
        $title = trim($raw['title'] ?? '');
        $body = trim($raw['body'] ?? '');
        if ($title === '' || $body === '') jsonResponse(['ok' => false, 'error' => 'title and body required'], 422);
        $target = ['category' => trim($raw['category'] ?? '')];
        $users = $db->query('SELECT DISTINCT user_id FROM mobile_devices WHERE active=1 AND promotions_enabled=1')->fetchAll();
        foreach ($users as $user) sendUserPush((int)$user['user_id'], 'promotion', $title, $body, $target);
        jsonResponse(['ok' => true, 'users' => count($users)]);
        break;

    case 'push_manager_message':
        if ($method !== 'POST') jsonResponse(['ok' => false, 'error' => 'POST only'], 405);
        $raw = json_decode(file_get_contents('php://input'), true) ?: [];
        $uid = (int)($raw['user_id'] ?? 0);
        $body = trim($raw['body'] ?? '');
        if (!$uid || $body === '') jsonResponse(['ok' => false, 'error' => 'user_id and body required'], 422);
        $exists = $db->prepare('SELECT id FROM users WHERE id=?');
        $exists->execute([$uid]);
        if (!$exists->fetch()) jsonResponse(['ok' => false, 'error' => 'user not found'], 404);
        sendUserPush($uid, 'manager_message', 'Message from SplitHub manager', $body, ['telegram_url' => 'https://t.me/Byttehnikaopt']);
        jsonResponse(['ok' => true]);
        break;

    case 'push_log':
        $rows = $db->query('SELECT * FROM push_campaigns ORDER BY id DESC LIMIT 100')->fetchAll();
        jsonResponse(['ok' => true, 'campaigns' => $rows]);
        break;

    default:
        jsonResponse(['ok' => false, 'error' => 'Unknown action'], 400);
}

function adminReadProductsJs() {
    $jsFile = __DIR__ . '/../products.js';
    if (!file_exists($jsFile)) return [];
    $js = trim(file_get_contents($jsFile));
    if (preg_match('/var\s+PRODUCTS\s*=\s*(\[.*\])\s*;?\s*$/s', $js, $m)) {
        $products = json_decode($m[1], true);
        return is_array($products) ? $products : [];
    }
    $js = preg_replace('/^\s*var\s+PRODUCTS\s*=\s*/', '', $js);
    $js = rtrim($js, ";\r\n ");
    $products = json_decode($js, true);
    return is_array($products) ? $products : [];
}

function adminProductFields() {
    return [
        'id','sku','brandCode','brand','series','model','group','type','factory','color',
        'btu','area','price','stock','stockLabel','descShort','cardBenef','benefits',
        'compressor','freon','photo','photos','description','badge','badge_label','active'
    ];
}

function adminNormalizeImageName($value) {
    $value = trim((string)$value);
    if ($value === '') return '';
    $value = str_replace('\\', '/', $value);
    if (preg_match('#^https?://#i', $value)) return $value;
    $value = preg_replace('#^/?assets/img/products/#i', '', $value);
    $value = basename($value);
    return preg_replace('/[^a-zA-Z0-9._-]/', '_', $value);
}

function adminNormalizeImageList($value) {
    if (is_string($value)) {
        $value = preg_split('/[\r\n,;]+/', $value);
    }
    if (!is_array($value)) return [];
    $out = [];
    foreach ($value as $item) {
        $name = adminNormalizeImageName($item);
        if ($name !== '' && !in_array($name, $out, true)) $out[] = $name;
        if (count($out) >= 12) break;
    }
    return $out;
}

function adminNormalizeBenefits($value) {
    if (is_string($value)) {
        $value = preg_split('/[\r\n;]+/', $value);
    }
    if (!is_array($value)) return [];
    $out = [];
    foreach ($value as $item) {
        $text = trim((string)$item);
        if ($text !== '') $out[] = $text;
    }
    return $out;
}

function adminNormalizeProductPayload($raw, $isCustom = false) {
    $raw = is_array($raw) ? $raw : [];
    $source = (isset($raw['data']) && is_array($raw['data'])) ? $raw['data'] : $raw;
    $data = [];
    foreach (adminProductFields() as $field) {
        if (!array_key_exists($field, $source)) continue;
        $value = $source[$field];
        if (in_array($field, ['price','area'], true)) {
            $data[$field] = ($value === '' || $value === null) ? 0 : (int)$value;
        } elseif ($field === 'benefits') {
            $data[$field] = adminNormalizeBenefits($value);
        } elseif ($field === 'photos') {
            $data[$field] = adminNormalizeImageList($value);
        } elseif ($field === 'photo') {
            $data[$field] = adminNormalizeImageName($value);
        } elseif ($field === 'active') {
            $data[$field] = (int)!!$value;
        } else {
            $data[$field] = is_array($value) ? $value : trim((string)$value);
        }
    }
    if (!empty($data['photos']) && empty($data['photo'])) $data['photo'] = $data['photos'][0];
    if (!isset($data['benefits'])) $data['benefits'] = [];
    if ($isCustom) {
        $data['id'] = trim((string)($data['id'] ?? ''));
        $data['sku'] = trim((string)($data['sku'] ?? ''));
        $data['brandCode'] = $data['brandCode'] ?? 'custom';
        $data['brand'] = $data['brand'] ?? 'SplitHub';
        $data['series'] = $data['series'] ?? 'Каталог';
        $data['group'] = $data['group'] ?? 'inv';
        $data['type'] = $data['type'] ?? 'split';
        $data['factory'] = $data['factory'] ?? '';
        $data['color'] = $data['color'] ?? 'white';
        $data['stock'] = $data['stock'] ?? 'in_stock';
        $data['stockLabel'] = $data['stockLabel'] ?? 'В наличии';
        $data['descShort'] = $data['descShort'] ?? '';
        $data['cardBenef'] = $data['cardBenef'] ?? '';
        $data['compressor'] = $data['compressor'] ?? '';
        $data['freon'] = $data['freon'] ?? '';
        $data['price'] = (int)($data['price'] ?? 0);
        $data['area'] = (int)($data['area'] ?? 0);
        $data['active'] = (int)($data['active'] ?? 1);
    }
    return $data;
}

function adminDecodeJsonObject($json) {
    $data = json_decode((string)$json, true);
    return is_array($data) ? $data : [];
}

function adminDecodeOverrideRow($row) {
    $row = is_array($row) ? $row : [];
    $data = adminDecodeJsonObject($row['data_json'] ?? '{}');
    foreach (['description','badge','badge_label'] as $field) {
        if (array_key_exists($field, $row) && trim((string)$row[$field]) !== '') {
            $data[$field] = trim((string)$row[$field]);
        }
    }
    if (!empty($data['photos'])) $data['photos'] = adminNormalizeImageList($data['photos']);
    if (!empty($data['photo'])) $data['photo'] = adminNormalizeImageName($data['photo']);
    if (!empty($data['benefits'])) $data['benefits'] = adminNormalizeBenefits($data['benefits']);
    $data['sku'] = (string)($row['sku'] ?? ($data['sku'] ?? ''));
    $data['active'] = (int)($row['active'] ?? ($data['active'] ?? 1));
    $data['updated_at'] = $row['updated_at'] ?? '';
    return $data;
}

function adminOverrideHasPublicChanges($override) {
    if ((int)($override['active'] ?? 1) === 0) return true;
    $skip = ['sku','active','updated_at','id','_source','_is_custom','created_at'];
    foreach ($override as $key => $value) {
        if (in_array($key, $skip, true)) continue;
        if (is_array($value) && count($value) > 0) return true;
        if (!is_array($value) && trim((string)$value) !== '') return true;
    }
    return false;
}

function adminApplyProductOverride($product, $override) {
    $base = is_array($product) ? $product : [];
    $merged = $base;
    $merged['_base'] = $base;
    $active = 1;
    if (is_array($override)) {
        $active = (int)($override['active'] ?? 1);
        foreach (adminProductFields() as $field) {
            if (in_array($field, ['id','sku','active'], true)) continue;
            if (array_key_exists($field, $override)) {
                $merged[$field] = $override[$field];
            }
        }
    }
    if (!isset($merged['benefits']) || !is_array($merged['benefits'])) $merged['benefits'] = [];
    if (!empty($merged['photos']) && empty($merged['photo'])) $merged['photo'] = $merged['photos'][0];
    $merged['_active'] = $active;
    return $merged;
}

function adminDecodeCustomProductRow($row) {
    $row = is_array($row) ? $row : [];
    $data = adminNormalizeProductPayload(adminDecodeJsonObject($row['data_json'] ?? '{}'), true);
    $data['id'] = $data['id'] ?: (string)($row['id'] ?? adminProductIdFromSku($row['sku'] ?? 'custom'));
    $data['sku'] = $data['sku'] ?: (string)($row['sku'] ?? '');
    $data['active'] = (int)($row['active'] ?? ($data['active'] ?? 1));
    $data['_active'] = $data['active'];
    $data['_source'] = 'custom';
    $data['_is_custom'] = true;
    $data['updated_at'] = $row['updated_at'] ?? '';
    $data['created_at'] = $row['created_at'] ?? '';
    return $data;
}

function adminProductIdFromSku($sku) {
    $id = strtolower(trim((string)$sku));
    $id = preg_replace('/[^a-z0-9_-]+/', '-', $id);
    $id = trim($id, '-_');
    if ($id === '') $id = bin2hex(random_bytes(4));
    if (strpos($id, 'custom-') !== 0) $id = 'custom-' . $id;
    return $id;
}

// ── Export CSV helper ──────────────────────────────────────────────────────
function exportOrdersCsv($db) {
    $status   = trim($_GET['status'] ?? '');
    $dateFrom = trim($_GET['date_from'] ?? '');
    $dateTo   = trim($_GET['date_to'] ?? '');
    $search   = trim($_GET['search'] ?? '');

    $where = []; $params = [];
    if ($status !== '')   { $where[] = 'o.status = ?';           $params[] = $status; }
    if ($dateFrom !== '') { $where[] = 'date(o.created_at) >= ?'; $params[] = $dateFrom; }
    if ($dateTo !== '')   { $where[] = 'date(o.created_at) <= ?'; $params[] = $dateTo; }
    if ($search !== '') {
        $num = preg_replace('/^(SH-?|#)/i', '', $search);
        if (ctype_digit($num)) { $where[] = 'o.id = ?'; $params[] = (int)$num; }
        else                   { $where[] = 'u.name LIKE ?'; $params[] = '%'.$search.'%'; }
    }
    $whereSQL = $where ? 'WHERE '.implode(' AND ', $where) : '';

    $rows = $db->prepare("SELECT o.id, o.created_at, u.name, u.phone, u.telegram, o.total, o.status, o.bonus_earned, o.bonus_spent, o.admin_note, o.comment FROM orders o JOIN users u ON o.user_id=u.id $whereSQL ORDER BY o.created_at DESC LIMIT 5000");
    $rows->execute($params);
    $list = $rows->fetchAll();

    header('Content-Type: text/csv; charset=utf-8');
    header('Content-Disposition: attachment; filename="orders_'.date('Y-m-d').'.csv"');
    echo "\xEF\xBB\xBF"; // UTF-8 BOM для Excel
    $out = fopen('php://output', 'w');
    fputcsv($out, ['№','Дата','Клиент','Телефон','Telegram','Сумма ₽','Статус','Бонусов начислено','Бонусов списано','Заметка','Комментарий'], ';');
    $smap = ['new'=>'Новый','confirmed'=>'Подтверждён','in_progress'=>'В работе','shipped'=>'Отгружен','completed'=>'Выполнен','cancelled'=>'Отменён'];
    foreach ($list as $r) {
        fputcsv($out, [
            'SH-'.str_pad($r['id'],5,'0',STR_PAD_LEFT),
            $r['created_at'], $r['name'], $r['phone'], $r['telegram'],
            $r['total'], $smap[$r['status']] ?? $r['status'],
            $r['bonus_earned'], $r['bonus_spent'], $r['admin_note'], $r['comment']
        ], ';');
    }
    fclose($out);
}

function exportXlsx($db) {
    $smap = ['new'=>'Новый','confirmed'=>'Подтверждён','in_progress'=>'В работе','shipped'=>'Отгружен','completed'=>'Выполнен','cancelled'=>'Отменён'];

    // ── Лист «Клиенты» ──
    $clients = [[
        'ID','Тип','Имя','Телефон','Telegram','Компания','ИНН','КПП','Юр.адрес',
        'Дата регистрации','Кол-во заказов','Сумма заказов ₽'
    ]];
    $urows = $db->query("
        SELECT u.id, u.name, u.phone, u.telegram,
               COALESCE(u.company_name,'') company_name, COALESCE(u.inn,'') inn,
               COALESCE(u.kpp,'') kpp, COALESCE(u.legal_address,'') legal_address,
               u.created_at,
               (SELECT COUNT(*) FROM orders WHERE user_id=u.id) oc,
               (SELECT COALESCE(SUM(total),0) FROM orders WHERE user_id=u.id) os
        FROM users u ORDER BY u.created_at DESC
    ")->fetchAll();
    foreach ($urows as $r) {
        $clients[] = [
            (int)$r['id'], 'Зарегистрирован', $r['name'], $r['phone'], $r['telegram'],
            $r['company_name'], $r['inn'], $r['kpp'], $r['legal_address'],
            $r['created_at'], (int)$r['oc'], (int)$r['os']
        ];
    }
    $grows = $db->query("
        SELECT name, phone, COUNT(*) cnt, COALESCE(SUM(total),0) sm, MIN(created_at) first_at
        FROM guest_orders GROUP BY phone ORDER BY first_at DESC
    ")->fetchAll();
    foreach ($grows as $r) {
        $clients[] = [
            '', 'Гость', $r['name'], $r['phone'], '', '', '', '', '',
            $r['first_at'], (int)$r['cnt'], (int)$r['sm']
        ];
    }

    // ── Лист «Заказы» ──
    $orders = [[
        '№','Тип','Дата','Клиент','Телефон','Telegram','Сумма ₽','Статус',
        'Бонусов начислено','Бонусов списано','Заметка','Комментарий','Источник'
    ]];
    $orows = $db->query("
        SELECT o.id, o.created_at, u.name, u.phone, u.telegram, o.total, o.status,
               o.bonus_earned, o.bonus_spent, COALESCE(o.admin_note,'') admin_note, o.comment
        FROM orders o JOIN users u ON o.user_id=u.id ORDER BY o.created_at DESC LIMIT 10000
    ")->fetchAll();
    $srcByPhone = [];
    try {
        foreach ($db->query("SELECT linked_phone, first_utm_source, first_referrer FROM visitors WHERE linked_phone!=''")->fetchAll() as $v) {
            $src = $v['first_utm_source'] !== '' ? $v['first_utm_source'] : ($v['first_referrer'] !== '' ? $v['first_referrer'] : '');
            if ($src !== '') $srcByPhone[$v['linked_phone']] = $src;
        }
    } catch (Throwable $e) {}
    foreach ($orows as $r) {
        $orders[] = [
            'SH-'.str_pad($r['id'],5,'0',STR_PAD_LEFT), 'Клиент', $r['created_at'],
            $r['name'], $r['phone'], $r['telegram'], (int)$r['total'],
            $smap[$r['status']] ?? $r['status'], (int)$r['bonus_earned'], (int)$r['bonus_spent'],
            $r['admin_note'], $r['comment'], $srcByPhone[$r['phone']] ?? ''
        ];
    }
    $gord = $db->query("SELECT id, created_at, name, phone, total, COALESCE(comment,'') comment FROM guest_orders ORDER BY created_at DESC LIMIT 10000")->fetchAll();
    foreach ($gord as $r) {
        $orders[] = [
            'G-'.str_pad($r['id'],5,'0',STR_PAD_LEFT), 'Гость', $r['created_at'],
            $r['name'], $r['phone'], '', (int)$r['total'], '—', 0, 0, '', $r['comment'],
            $srcByPhone[$r['phone']] ?? ''
        ];
    }

    // ── Лист «Посетители» ──
    $visitors = [[
        'ID посетителя','Первый визит','Последний визит','Кол-во визитов','Источник (referrer)',
        'UTM source','UTM medium','UTM campaign','Устройство','IP','Привязанный клиент'
    ]];
    try {
        $vrows = $db->query("SELECT * FROM visitors ORDER BY last_seen DESC LIMIT 20000")->fetchAll();
        foreach ($vrows as $r) {
            $linked = trim(($r['linked_name'] ?? '') . ' ' . ($r['linked_phone'] ?? ''));
            $visitors[] = [
                $r['vid'], $r['first_seen'], $r['last_seen'], (int)$r['visits_count'],
                $r['first_referrer'], $r['first_utm_source'], $r['first_utm_medium'],
                $r['first_utm_campaign'], $r['device'], $r['last_ip'], $linked
            ];
        }
    } catch (Throwable $e) {}

    $w = new SimpleXlsxWriter();
    $w->addSheet('Клиенты', $clients);
    $w->addSheet('Заказы', $orders);
    $w->addSheet('Посетители', $visitors);
    $w->download('splithub_export_' . date('Y-m-d') . '.xlsx');
}
