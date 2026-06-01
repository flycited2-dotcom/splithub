<?php
function projectPath(string $path): string {
    return dirname(__DIR__, 2) . '/' . $path;
}

function assertTrue(bool $value, string $message): void {
    if (!$value) {
        throw new RuntimeException('FAIL: ' . $message);
    }
    echo "PASS: $message\n";
}

function assertSame(mixed $expected, mixed $actual, string $message): void {
    assertTrue($expected === $actual, $message);
}

$tmpDb = sys_get_temp_dir() . '/splithub_mobile_tests_' . getmypid() . '.sqlite';
foreach ([$tmpDb, $tmpDb . '-wal', $tmpDb . '-shm'] as $path) {
    @unlink($path);
}
putenv('SPLITHUB_DB_PATH=' . $tmpDb);
putenv('SPLITHUB_PRODUCTS_PATH=' . projectPath('products.json'));
register_shutdown_function(function () use ($tmpDb): void {
    foreach ([$tmpDb, $tmpDb . '-wal', $tmpDb . '-shm'] as $path) {
        @unlink($path);
    }
});
require_once projectPath('db/init.php');
