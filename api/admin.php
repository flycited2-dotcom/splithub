<?php
/**
 * Admin API
 */

require __DIR__ . '/../db/init.php';

header('Content-Type: application/json; charset=utf-8');
header('Access-Control-Allow-Origin: *');
header('Access-Control-Allow-Methods: GET, POST, OPTIONS');
header('Access-Control-Allow-Headers: Content-Type');
if ($_SERVER['REQUEST_METHOD'] === 'OPTIONS') { http_response_code(200); exit; }

// Public product overrides — no auth required
$action = $_GET['action'] ?? '';
if ($action === 'products_overrides_public') {
    $db = getDB();
    $rows = $db->query("SELECT sku, description, badge, badge_label FROM product_overrides WHERE badge != '' OR description != ''")->fetchAll();
    $map = [];
    foreach ($rows as $r) { $map[$r['sku']] = $r; }
    jsonResponse(['ok' => true, 'overrides' => $map]);
    exit;
}

// CSV export — override Content-Type before auth check output
if ($action === 'export_orders_csv') {
    adminRequire();
    exportOrdersCsv(getDB());
    exit;
}

adminRequire();

$method = $_SERVER['REQUEST_METHOD'];
$db = getDB();

switch ($action) {

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
            SELECT u.id, u.name, u.phone, u.telegram, u.role, u.created_at,
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
        $total  = (int)$db->query('SELECT COUNT(*) FROM guest_orders')->fetchColumn();
        $rows   = $db->prepare('SELECT * FROM guest_orders ORDER BY created_at DESC LIMIT ? OFFSET ?');
        $rows->execute([$limit, $offset]);
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
        $db->prepare('UPDATE users SET role = ? WHERE id = ?')->execute([$role, $uid]);
        jsonResponse(['ok' => true]);
        break;

    // ── Send Telegram report on demand ──
    case 'send_report':
        if ($method !== 'POST') jsonResponse(['ok' => false, 'error' => 'POST only'], 405);
        $cfgFile = __DIR__ . '/../config.php';
        if (file_exists($cfgFile)) require_once $cfgFile;
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
        curl_setopt_array($ch,[CURLOPT_POST=>true,CURLOPT_POSTFIELDS=>json_encode(['chat_id'=>$chatId,'text'=>$msg,'parse_mode'=>'Markdown']),CURLOPT_HTTPHEADER=>['Content-Type: application/json'],CURLOPT_RETURNTRANSFER=>true,CURLOPT_TIMEOUT=>10,CURLOPT_SSL_VERIFYPEER=>false]);
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
        $cfgFile = __DIR__ . '/../config.php';
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
        $raw = json_decode(file_get_contents('php://input'), true);
        $allowed_keys = ['BOT_TOKEN','CHAT_ID','TG_ADMIN_ID','EMAIL_TO','CRON_SECRET','ALLOWED_ORIGIN'];
        $cfgFile = __DIR__ . '/../config.php';

        $content = "<?php\n";
        foreach ($allowed_keys as $key) {
            if (isset($raw[$key])) {
                $val = addslashes(trim($raw[$key]));
                $content .= "define('{$key}', '{$val}');\n";
            }
        }
        $content .= "define('RATE_LIMIT_SEC', 30);\n";

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

    // ── List products + overrides ──
    case 'products_list':
        $jsFile = __DIR__ . '/../products.js';
        $products = [];
        if (file_exists($jsFile)) {
            $js = file_get_contents($jsFile);
            $js = preg_replace('/^\s*var\s+PRODUCTS\s*=\s*/', '', trim($js));
            $js = rtrim($js, ";\r\n ");
            $products = json_decode($js, true) ?: [];
        }
        $ovRows = $db->query("SELECT sku, description, badge, badge_label FROM product_overrides")->fetchAll();
        $ovMap = [];
        foreach ($ovRows as $r) { $ovMap[$r['sku']] = $r; }
        foreach ($products as &$p) {
            if (isset($ovMap[$p['sku']])) { $p['_override'] = $ovMap[$p['sku']]; }
        }
        $search = trim($_GET['search'] ?? '');
        if ($search !== '') {
            $sl = mb_strtolower($search);
            $products = array_values(array_filter($products, function($p) use ($sl) {
                return mb_strpos(mb_strtolower($p['model'] ?? ''), $sl) !== false
                    || mb_strpos(mb_strtolower($p['brand'] ?? ''), $sl) !== false
                    || mb_strpos(mb_strtolower($p['sku'] ?? ''), $sl) !== false
                    || mb_strpos(mb_strtolower($p['series'] ?? ''), $sl) !== false;
            }));
        }
        jsonResponse(['ok' => true, 'products' => array_slice($products, 0, 200), 'total' => count($products)]);
        break;

    // ── Save product override ──
    case 'product_save_override':
        if ($method !== 'POST') jsonResponse(['ok' => false, 'error' => 'POST only'], 405);
        $raw = json_decode(file_get_contents('php://input'), true);
        $sku    = trim($raw['sku'] ?? '');
        $desc   = trim($raw['description'] ?? '');
        $badge  = trim($raw['badge'] ?? '');
        $blabel = trim($raw['badge_label'] ?? '');
        if (!$sku) jsonResponse(['ok' => false, 'error' => 'sku required'], 422);
        if (!in_array($badge, ['', 'new', 'sale', 'clearance'])) jsonResponse(['ok' => false, 'error' => 'Invalid badge'], 422);
        $db->prepare("INSERT OR REPLACE INTO product_overrides (sku, description, badge, badge_label, updated_at) VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)")
            ->execute([$sku, $desc, $badge, $blabel]);
        jsonResponse(['ok' => true]);
        break;

    default:
        jsonResponse(['ok' => false, 'error' => 'Unknown action'], 400);
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
