<?php
/**
 * estimate.php — публикация файла сметы (PDF / Excel) по неугадываемой ссылке.
 * Сайт не может прикрепить файл к сообщению в Telegram/WhatsApp/Max/почте,
 * поэтому смета загружается сюда, а клиенту уходит ссылка на файл.
 * Изолировано: заявки (send.php) и БД не трогает.
 *
 * POST multipart: file (PDF или XLSX, до 5 МБ), name (имя файла для скачивания).
 * Ответ: {"ok":true,"url":"https://splithub.ru/estimates/<token>/<name>"}
 */

header('Content-Type: application/json; charset=utf-8');

if ($_SERVER['REQUEST_METHOD'] !== 'POST') {
    http_response_code(405);
    echo json_encode(['ok' => false, 'error' => 'POST only']);
    exit;
}

const EST_MAX_BYTES   = 5 * 1024 * 1024;
const EST_KEEP_DAYS   = 90;
const EST_IP_PER_HOUR = 60;

function est_fail($code, $msg) {
    http_response_code($code);
    echo json_encode(['ok' => false, 'error' => $msg], JSON_UNESCAPED_UNICODE);
    exit;
}

$baseDir = dirname(__DIR__) . '/estimates';
if (!is_dir($baseDir) && !mkdir($baseDir, 0755, true)) est_fail(500, 'storage');

// Простой лимит по IP: не больше EST_IP_PER_HOUR загрузок в час.
$ip = $_SERVER['REMOTE_ADDR'] ?? '';
$rateFile = $baseDir . '/.rate-' . substr(sha1($ip), 0, 16);
$now = time();
$hits = array_filter(array_map('intval', @file($rateFile, FILE_IGNORE_NEW_LINES) ?: []), function ($t) use ($now) {
    return $t > $now - 3600;
});
if (count($hits) >= EST_IP_PER_HOUR) est_fail(429, 'Слишком много смет за час, попробуйте позже');
$hits[] = $now;
@file_put_contents($rateFile, implode("\n", $hits));

$f = $_FILES['file'] ?? null;
if (!$f || $f['error'] !== UPLOAD_ERR_OK || !is_uploaded_file($f['tmp_name'])) est_fail(400, 'Файл не получен');
if ($f['size'] <= 0 || $f['size'] > EST_MAX_BYTES) est_fail(413, 'Файл слишком большой');

// Тип — по содержимому, не по имени: PDF начинается с %PDF-, XLSX — zip (PK\x03\x04).
$head = (string) file_get_contents($f['tmp_name'], false, null, 0, 5);
if (strncmp($head, '%PDF-', 5) === 0) {
    $ext = 'pdf';
} elseif (strncmp($head, "PK\x03\x04", 4) === 0) {
    $ext = 'xlsx';
} else {
    est_fail(415, 'Поддерживаются только PDF и Excel');
}

// Имя для скачивания: только безопасные символы, расширение — по содержимому.
$name = preg_replace('/[^A-Za-z0-9._-]+/', '-', pathinfo((string) ($_POST['name'] ?? ''), PATHINFO_FILENAME));
$name = trim($name, '.-_') ?: 'smeta';
$name = substr($name, 0, 60) . '.' . $ext;

$token = bin2hex(random_bytes(12));
$dir = $baseDir . '/' . $token;
if (!mkdir($dir, 0755) || !move_uploaded_file($f['tmp_name'], $dir . '/' . $name)) est_fail(500, 'storage');
@chmod($dir . '/' . $name, 0644);

// Уборка: папки смет старше EST_KEEP_DAYS и старые счётчики лимита.
foreach (glob($baseDir . '/*', GLOB_ONLYDIR) ?: [] as $old) {
    if (filemtime($old) < $now - EST_KEEP_DAYS * 86400 && preg_match('/^[0-9a-f]{24}$/', basename($old))) {
        array_map('unlink', glob($old . '/*') ?: []);
        @rmdir($old);
    }
}
foreach (glob($baseDir . '/.rate-*') ?: [] as $rf) {
    if (filemtime($rf) < $now - 86400) @unlink($rf);
}

$scheme = (!empty($_SERVER['HTTPS']) && $_SERVER['HTTPS'] !== 'off') ? 'https' : 'http';
$host = $_SERVER['HTTP_HOST'] ?? 'splithub.ru';
echo json_encode(['ok' => true, 'url' => "$scheme://$host/estimates/$token/" . rawurlencode($name)], JSON_UNESCAPED_SLASHES);
