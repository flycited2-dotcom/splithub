<?php
/**
 * SQLite database initialization and connection.
 * Database file is auto-created on first request.
 *
 * Falls back to sys_get_temp_dir() if db/ directory is not writable.
 * Throws a clear RuntimeException if PDO SQLite driver is missing.
 */

function setupPromoRules($db) {
    // Count current distinct rule names
    $distinct = (int)$db->query('SELECT COUNT(DISTINCT COALESCE(product_group,"_all")) FROM promo_rules')->fetchColumn();
    $total    = (int)$db->query('SELECT COUNT(*) FROM promo_rules')->fetchColumn();
    // If duplicates exist OR rules are not the expected 6 per-group rules, reset
    if ($total !== 6 || $distinct !== 6) {
        $db->exec('DELETE FROM promo_rules');
        $db->exec('
            INSERT INTO promo_rules (name, active, bonus_percent, product_group, min_order) VALUES
            ("Ретробонус инв 2%",       1, 2.0, "inv",      0),
            ("Ретробонус он/офф 2%",    1, 2.0, "onoff",    0),
            ("Ретробонус мульти 3%",    1, 3.0, "multi",    0),
            ("Ретробонус полупром 3%",  1, 3.0, "poluprom", 0),
            ("Ретробонус расходка 1%",  1, 1.0, "rashod",   0),
            ("Ретробонус труба 2%",     1, 2.0, "truba",    0)
        ');
    }
}

function getDB() {
    static $db = null;
    if ($db) return $db;

    // ── Check PDO SQLite availability ─────────────────────────────────────────
    if (!extension_loaded('pdo_sqlite') && !in_array('sqlite', PDO::getAvailableDrivers())) {
        throw new RuntimeException(
            'PDO SQLite driver is not enabled on this server. ' .
            'Please contact your hosting provider to enable php-pdo-sqlite / php8.x-sqlite3.'
        );
    }

    // ── Determine writable path for the database file ─────────────────────────
    $dbDir  = __DIR__;
    $dbPath = $dbDir . '/splithub.sqlite';

    // If db/ is not writable, fall back to system temp directory
    if (!is_writable($dbDir)) {
        $tmpDir = sys_get_temp_dir() . '/splithub_db';
        if (!is_dir($tmpDir)) @mkdir($tmpDir, 0700, true);
        $dbPath = $tmpDir . '/splithub.sqlite';
    }

    try {
        $db = new PDO('sqlite:' . $dbPath);
    } catch (PDOException $e) {
        throw new RuntimeException(
            'Cannot open database: ' . $e->getMessage() .
            ' (path: ' . $dbPath . ')'
        );
    }

    $db->setAttribute(PDO::ATTR_ERRMODE, PDO::ERRMODE_EXCEPTION);
    $db->setAttribute(PDO::ATTR_DEFAULT_FETCH_MODE, PDO::FETCH_ASSOC);
    $db->exec('PRAGMA journal_mode=WAL');
    $db->exec('PRAGMA foreign_keys=ON');

    // Always run migrate — all statements use IF NOT EXISTS, so it's safe to call every time.
    // This also fixes the case where the DB file was created empty by a previous failed attempt.
    migrate($db);
    setupPromoRules($db);

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
    ');
}

/**
 * JSON response helper.
 */
function jsonResponse($data, $code = 200) {
    if (ob_get_level()) ob_clean();
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
        if (!is_dir($sessDir)) @mkdir($sessDir, 0700, true);
        if (is_writable($sessDir)) session_save_path($sessDir);
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
    $db  = getDB();
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
    $db    = getDB();
    $rules = $db->query('SELECT * FROM promo_rules WHERE active = 1')->fetchAll();

    $totalBonus   = 0;
    $appliedRules = [];

    foreach ($rules as $rule) {
        if ($rule['min_order'] > 0 && $total < $rule['min_order']) continue;

        $pg = $rule['product_group'] ?? '';
        if ($pg === null || $pg === '') {
            // Global rule — apply to whole order
            $bonus = (int)floor($total * $rule['bonus_percent'] / 100);
            if ($bonus > 0) {
                $totalBonus += $bonus;
                $appliedRules[] = $rule['name'] . ': +' . $bonus . ' ₽';
            }
        } else {
            // Group rule — sum all matching items first, then calculate once
            $groupTotal = 0;
            foreach ($items as $item) {
                if (($item['group'] ?? '') === $pg) {
                    $groupTotal += ($item['price'] ?? 0) * ($item['qty'] ?? 1);
                }
            }
            if ($groupTotal > 0) {
                $bonus = (int)floor($groupTotal * $rule['bonus_percent'] / 100);
                if ($bonus > 0) {
                    $totalBonus += $bonus;
                    $appliedRules[] = $rule['name'] . ': +' . $bonus . ' ₽';
                }
            }
        }
    }

    return ['bonus' => $totalBonus, 'rules' => $appliedRules];
}
