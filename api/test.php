<?php
/**
 * Diagnostic endpoint — open in browser to check server compatibility.
 * URL: https://splithub.ru/api/test.php
 *
 * DELETE THIS FILE after debugging is done!
 */
header('Content-Type: application/json; charset=utf-8');
header('Access-Control-Allow-Origin: *');

$report = [];

// PHP version
$report['php_version'] = PHP_VERSION;

// PDO drivers
$report['pdo_drivers'] = PDO::getAvailableDrivers();
$report['pdo_sqlite']  = in_array('sqlite', PDO::getAvailableDrivers());

// SQLite3 extension
$report['sqlite3_ext'] = extension_loaded('sqlite3');

// Writable paths
$dbDir  = __DIR__ . '/../db';
$report['db_dir_exists']   = is_dir($dbDir);
$report['db_dir_writable'] = is_writable($dbDir);

$tmpDir = sys_get_temp_dir();
$report['temp_dir']          = $tmpDir;
$report['temp_dir_writable'] = is_writable($tmpDir);

$sessDir = $tmpDir . '/splithub_sess';
@mkdir($sessDir, 0700, true);
$report['sess_dir_writable'] = is_writable($sessDir);

$splithubDbDir = $tmpDir . '/splithub_db';
@mkdir($splithubDbDir, 0700, true);
$report['splithub_db_dir_writable'] = is_writable($splithubDbDir);

// Session start test
if (session_status() === PHP_SESSION_NONE) {
    if (is_writable($sessDir)) session_save_path($sessDir);
    $startOk = @session_start();
    $report['session_start'] = $startOk ? 'OK' : 'FAILED';
    $report['session_id']    = session_id();
}

// SQLite create test
if ($report['pdo_sqlite']) {
    try {
        $testPath = $splithubDbDir . '/test_' . time() . '.sqlite';
        $pdo = new PDO('sqlite:' . $testPath);
        $pdo->exec('CREATE TABLE t (x INTEGER)');
        $pdo->exec('INSERT INTO t VALUES (1)');
        $val = $pdo->query('SELECT x FROM t')->fetchColumn();
        $pdo = null;
        @unlink($testPath);
        $report['sqlite_write_test'] = ($val == 1) ? 'OK' : 'FAILED';
    } catch (Exception $e) {
        $report['sqlite_write_test'] = 'ERROR: ' . $e->getMessage();
    }
} else {
    $report['sqlite_write_test'] = 'SKIPPED (no pdo_sqlite driver)';
}

// Files check
$report['auth_php_exists']   = file_exists(__DIR__ . '/auth.php');
$report['init_php_exists']   = file_exists(__DIR__ . '/../db/init.php');
$report['index_html_exists'] = file_exists(__DIR__ . '/../index.html');

echo json_encode($report, JSON_UNESCAPED_UNICODE | JSON_PRETTY_PRINT);
