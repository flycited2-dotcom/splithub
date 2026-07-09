<?php
/**
 * SQLite database initialization and connection.
 * Database file is auto-created on first request.
 */

function getDB() {
    static $db = null;
    if ($db) return $db;

    $dbPath = getenv('SPLITHUB_DB_PATH') ?: __DIR__ . '/splithub.sqlite';
    $isNew = !file_exists($dbPath);

    $db = new PDO('sqlite:' . $dbPath);
    $db->setAttribute(PDO::ATTR_ERRMODE, PDO::ERRMODE_EXCEPTION);
    $db->setAttribute(PDO::ATTR_DEFAULT_FETCH_MODE, PDO::FETCH_ASSOC);
    try { $db->exec('PRAGMA journal_mode=WAL'); } catch (Throwable $e) {}
    try { $db->exec('PRAGMA foreign_keys=ON'); } catch (Throwable $e) {}

    if ($isNew) {
        migrate($db);
    } else {
        // Ensure tables exist even if DB file was created but migration failed
        $tables = $db->query("SELECT name FROM sqlite_master WHERE type='table' AND name='users'")->fetch();
        if (!$tables) migrate($db);
    }

    // Incremental migrations — safe to run on every boot
    try {
        $cols = $db->query("PRAGMA table_info(order_items)")->fetchAll(PDO::FETCH_ASSOC);
        $colNames = array_column($cols, 'name');
        if (!in_array('product_id', $colNames)) {
            $db->exec("ALTER TABLE order_items ADD COLUMN product_id TEXT DEFAULT ''");
        }
    } catch (Throwable $e) {}

    // product_overrides table
    try {
        $db->exec("CREATE TABLE IF NOT EXISTS product_overrides (
            sku TEXT PRIMARY KEY,
            description TEXT DEFAULT '',
            badge TEXT DEFAULT '',
            badge_label TEXT DEFAULT '',
            active INTEGER DEFAULT 1,
            data_json TEXT DEFAULT '{}',
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP
        )");
        $pcols = array_column($db->query("PRAGMA table_info(product_overrides)")->fetchAll(PDO::FETCH_ASSOC), 'name');
        if (!in_array('active', $pcols)) {
            $db->exec("ALTER TABLE product_overrides ADD COLUMN active INTEGER DEFAULT 1");
        }
        if (!in_array('data_json', $pcols)) {
            $db->exec("ALTER TABLE product_overrides ADD COLUMN data_json TEXT DEFAULT '{}'");
        }
        $db->exec("CREATE TABLE IF NOT EXISTS custom_products (
            id TEXT PRIMARY KEY,
            sku TEXT NOT NULL UNIQUE,
            data_json TEXT NOT NULL DEFAULT '{}',
            active INTEGER NOT NULL DEFAULT 1,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )");
    } catch (Throwable $e) {}

    // app_settings table
    try {
        $db->exec("CREATE TABLE IF NOT EXISTS app_settings (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL DEFAULT ''
        )");
        $db->exec("INSERT OR IGNORE INTO app_settings (key, value) VALUES ('bonuses_enabled', '1')");
        // Поэтапный выкат: email в регистрации сначала опционален ('0'),
        // флип на обязательный ('1') — после готовности фронтов сайта и приложения.
        $db->exec("INSERT OR IGNORE INTO app_settings (key, value) VALUES ('email_required', '0')");
    } catch (Throwable $e) {}

    // Mobile bearer sessions and push-notification devices
    try {
        $db->exec("CREATE TABLE IF NOT EXISTS mobile_sessions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            token_hash TEXT NOT NULL UNIQUE,
            expires_at TEXT NOT NULL,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id)
        )");
        $db->exec("CREATE TABLE IF NOT EXISTS mobile_devices (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            expo_token TEXT NOT NULL UNIQUE,
            platform TEXT NOT NULL,
            order_status_enabled INTEGER NOT NULL DEFAULT 1,
            promotions_enabled INTEGER NOT NULL DEFAULT 1,
            manager_messages_enabled INTEGER NOT NULL DEFAULT 1,
            active INTEGER NOT NULL DEFAULT 1,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id)
        )");
        $db->exec("CREATE TABLE IF NOT EXISTS push_campaigns (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            type TEXT NOT NULL,
            title TEXT NOT NULL,
            body TEXT NOT NULL,
            target_json TEXT NOT NULL DEFAULT '{}',
            user_id INTEGER,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id)
        )");
        $db->exec("CREATE TABLE IF NOT EXISTS push_deliveries (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            campaign_id INTEGER,
            device_id INTEGER NOT NULL,
            expo_ticket_id TEXT,
            status TEXT NOT NULL DEFAULT 'queued',
            error TEXT DEFAULT '',
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (campaign_id) REFERENCES push_campaigns(id),
            FOREIGN KEY (device_id) REFERENCES mobile_devices(id)
        )");
    } catch (Throwable $e) {}

    // admin_note column on orders
    try {
        $cols2 = $db->query("PRAGMA table_info(orders)")->fetchAll(PDO::FETCH_ASSOC);
        $colNames2 = array_column($cols2, 'name');
        if (!in_array('admin_note', $colNames2)) {
            $db->exec("ALTER TABLE orders ADD COLUMN admin_note TEXT DEFAULT ''");
        }
        if (!in_array('cancel_reason', $colNames2)) {
            $db->exec("ALTER TABLE orders ADD COLUMN cancel_reason TEXT DEFAULT ''");
        }
    } catch (Throwable $e) {}

    // email column on users + password_resets table
    try {
        $ucols = array_column($db->query("PRAGMA table_info(users)")->fetchAll(PDO::FETCH_ASSOC), 'name');
        if (!in_array('email', $ucols)) {
            $db->exec("ALTER TABLE users ADD COLUMN email TEXT DEFAULT ''");
        }
        $db->exec("CREATE TABLE IF NOT EXISTS password_resets (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            code_hash TEXT NOT NULL,
            expires_at TEXT NOT NULL,
            attempts INTEGER NOT NULL DEFAULT 0,
            used INTEGER NOT NULL DEFAULT 0,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id)
        )");
    } catch (Throwable $e) {}

    // Company/legal fields on users (нужны экспорту «Клиенты»)
    try {
        $uc = $db->query("PRAGMA table_info(users)")->fetchAll(PDO::FETCH_ASSOC);
        $ucNames = array_column($uc, 'name');
        foreach (['company_name','inn','kpp','legal_address'] as $col) {
            if (!in_array($col, $ucNames)) {
                $db->exec("ALTER TABLE users ADD COLUMN {$col} TEXT DEFAULT ''");
            }
        }
    } catch (Throwable $e) {}

    // visitors / visits — собственный трекинг посетителей
    try {
        $db->exec("CREATE TABLE IF NOT EXISTS visitors (
            vid TEXT PRIMARY KEY,
            first_seen TEXT DEFAULT CURRENT_TIMESTAMP,
            last_seen  TEXT DEFAULT CURRENT_TIMESTAMP,
            visits_count INTEGER DEFAULT 0,
            first_referrer TEXT DEFAULT '',
            first_utm_source TEXT DEFAULT '',
            first_utm_medium TEXT DEFAULT '',
            first_utm_campaign TEXT DEFAULT '',
            device TEXT DEFAULT '',
            user_agent TEXT DEFAULT '',
            last_ip TEXT DEFAULT '',
            linked_phone TEXT DEFAULT '',
            linked_name  TEXT DEFAULT ''
        )");
        $db->exec("CREATE TABLE IF NOT EXISTS visits (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            vid TEXT NOT NULL,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            page TEXT DEFAULT '',
            referrer TEXT DEFAULT '',
            utm_source TEXT DEFAULT '',
            utm_medium TEXT DEFAULT '',
            utm_campaign TEXT DEFAULT '',
            device TEXT DEFAULT '',
            ip TEXT DEFAULT ''
        )");
        $db->exec("CREATE INDEX IF NOT EXISTS idx_visits_vid ON visits(vid)");
        $db->exec("CREATE INDEX IF NOT EXISTS idx_visits_created ON visits(created_at)");
    } catch (Throwable $e) {}

    // Monthly admin reports
    try {
        $db->exec("CREATE TABLE IF NOT EXISTS monthly_reports (
            period TEXT PRIMARY KEY,
            orders_count INTEGER NOT NULL DEFAULT 0,
            revenue INTEGER NOT NULL DEFAULT 0,
            new_clients INTEGER NOT NULL DEFAULT 0,
            completed_count INTEGER NOT NULL DEFAULT 0,
            cancelled_count INTEGER NOT NULL DEFAULT 0,
            avg_order INTEGER NOT NULL DEFAULT 0,
            notes TEXT DEFAULT '',
            closed_at TEXT DEFAULT CURRENT_TIMESTAMP
        )");
    } catch (Throwable $e) {}

    // Guest orders status for admin bulk workflows
    try {
        $gcols = array_column($db->query("PRAGMA table_info(guest_orders)")->fetchAll(PDO::FETCH_ASSOC), 'name');
        if ($gcols && !in_array('status', $gcols)) {
            $db->exec("ALTER TABLE guest_orders ADD COLUMN status TEXT DEFAULT 'new'");
        }
    } catch (Throwable $e) {}

    return $db;
}

function migrate($db) {
    $db->exec('
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            phone TEXT NOT NULL UNIQUE,
            telegram TEXT DEFAULT "",
            password_hash TEXT NOT NULL,
            role TEXT DEFAULT "client",
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS orders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            total INTEGER NOT NULL DEFAULT 0,
            bonus_earned INTEGER NOT NULL DEFAULT 0,
            bonus_spent INTEGER NOT NULL DEFAULT 0,
            status TEXT DEFAULT "new",
            comment TEXT DEFAULT "",
            client_tg TEXT DEFAULT "",
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id)
        );

        CREATE TABLE IF NOT EXISTS order_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            order_id INTEGER NOT NULL,
            product_name TEXT NOT NULL,
            price INTEGER NOT NULL,
            qty INTEGER NOT NULL DEFAULT 1,
            FOREIGN KEY (order_id) REFERENCES orders(id)
        );

        CREATE TABLE IF NOT EXISTS bonus_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            order_id INTEGER,
            amount INTEGER NOT NULL,
            type TEXT NOT NULL,
            description TEXT DEFAULT "",
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id),
            FOREIGN KEY (order_id) REFERENCES orders(id)
        );

        CREATE TABLE IF NOT EXISTS promo_rules (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            active INTEGER DEFAULT 1,
            bonus_percent REAL DEFAULT 3.0,
            product_group TEXT DEFAULT NULL,
            min_order INTEGER DEFAULT 0,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS product_overrides (
            sku TEXT PRIMARY KEY,
            description TEXT DEFAULT "",
            badge TEXT DEFAULT "",
            badge_label TEXT DEFAULT "",
            active INTEGER DEFAULT 1,
            data_json TEXT DEFAULT "{}",
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS custom_products (
            id TEXT PRIMARY KEY,
            sku TEXT NOT NULL UNIQUE,
            data_json TEXT NOT NULL DEFAULT "{}",
            active INTEGER NOT NULL DEFAULT 1,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS guest_orders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            phone TEXT NOT NULL,
            total INTEGER NOT NULL DEFAULT 0,
            items_json TEXT NOT NULL DEFAULT "[]",
            status TEXT DEFAULT "new",
            comment TEXT DEFAULT "",
            client_tg TEXT DEFAULT "",
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        );

        -- Default promo: 3% retro-bonus on all orders
        INSERT INTO promo_rules (name, active, bonus_percent, product_group, min_order)
        VALUES ("Ретробонус 3%", 1, 3.0, NULL, 0);
    ');
}

/**
 * JSON response helper.
 */
function jsonResponse($data, $code = 200) {
    http_response_code($code);
    header('Content-Type: application/json; charset=utf-8');
    echo json_encode($data, JSON_UNESCAPED_UNICODE);
    exit;
}

/**
 * Start session and return user_id or null.
 */
function authCheck() {
    if (session_status() === PHP_SESSION_NONE) {
        $sessDir = sys_get_temp_dir() . '/splithub_sess';
        if (is_dir($sessDir) && is_writable($sessDir)) session_save_path($sessDir);
        session_start();
    }
    return $_SESSION['user_id'] ?? null;
}

/**
 * Require authentication — 401 if not logged in.
 */
function authRequire() {
    $uid = authCheck();
    if (!$uid) jsonResponse(['ok' => false, 'error' => 'Необходима авторизация'], 401);
    return $uid;
}

/**
 * Require admin role — 403 if not admin.
 */
function adminRequire() {
    $uid = authRequire();
    $db = getDB();
    $user = $db->prepare('SELECT role FROM users WHERE id = ?');
    $user->execute([$uid]);
    $row = $user->fetch();
    if (!$row || $row['role'] !== 'admin') {
        jsonResponse(['ok' => false, 'error' => 'Доступ запрещён'], 403);
    }
    return $uid;
}

/**
 * Normalize phone to digits-only (e.g. "79781234567").
 */
function normalizePhone($phone) {
    $digits = preg_replace('/\D/', '', $phone);
    if (strlen($digits) === 11 && $digits[0] === '8') {
        $digits = '7' . substr($digits, 1);
    }
    return $digits;
}

/**
 * Calculate bonus for an order based on active promo rules.
 */
function calculateBonus($total, $items = []) {
    $db = getDB();

    // Honour global bonuses_enabled flag
    try {
        $bs = $db->prepare("SELECT value FROM app_settings WHERE key = 'bonuses_enabled'");
        $bs->execute();
        $bsRow = $bs->fetch();
        if ($bsRow && $bsRow['value'] === '0') return ['bonus' => 0, 'rules' => []];
    } catch (Throwable $e) {}

    $rules = $db->query('SELECT * FROM promo_rules WHERE active = 1')->fetchAll();

    $totalBonus = 0;
    $appliedRules = [];

    foreach ($rules as $rule) {
        if ($rule['min_order'] > 0 && $total < $rule['min_order']) continue;

        if ($rule['product_group'] === null || $rule['product_group'] === '') {
            // Rule applies to entire order
            $bonus = (int)floor($total * $rule['bonus_percent'] / 100);
            $totalBonus += $bonus;
            $appliedRules[] = $rule['name'] . ': +' . $bonus . ' ₽';
        } else {
            // Rule applies to specific product group — match by group name in item names
            // Items should have 'group' field if available
            foreach ($items as $item) {
                $group = $item['group'] ?? '';
                if ($group === $rule['product_group']) {
                    $itemTotal = ($item['price'] ?? 0) * ($item['qty'] ?? 1);
                    $bonus = (int)floor($itemTotal * $rule['bonus_percent'] / 100);
                    $totalBonus += $bonus;
                    $appliedRules[] = $rule['name'] . ' (' . $group . '): +' . $bonus . ' ₽';
                }
            }
        }
    }

    return ['bonus' => $totalBonus, 'rules' => $appliedRules];
}
