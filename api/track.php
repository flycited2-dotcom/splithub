<?php
/**
 * track.php — приём «маячков» от посетителей сайта.
 * Пишет визит в visits и агрегат в visitors. Без авторизации.
 * Любой сбой не должен мешать посетителю — всегда быстрый ответ.
 */

header('Content-Type: application/json; charset=utf-8');
header('Access-Control-Allow-Origin: *');
header('Access-Control-Allow-Methods: POST, OPTIONS');
header('Access-Control-Allow-Headers: Content-Type');
if ($_SERVER['REQUEST_METHOD'] === 'OPTIONS') { http_response_code(200); exit; }
if ($_SERVER['REQUEST_METHOD'] !== 'POST')    { http_response_code(405); echo '{"ok":false}'; exit; }

function track_clip($s, $max = 500) {
    $s = is_string($s) ? trim($s) : '';
    if (mb_strlen($s) > $max) $s = mb_substr($s, 0, $max);
    return $s;
}

function track_client_ip() {
    $xff = $_SERVER['HTTP_X_FORWARDED_FOR'] ?? '';
    if ($xff !== '') {
        $parts = explode(',', $xff);
        $ip = trim($parts[0]);
        if (filter_var($ip, FILTER_VALIDATE_IP)) return $ip;
    }
    $ip = $_SERVER['REMOTE_ADDR'] ?? '';
    return filter_var($ip, FILTER_VALIDATE_IP) ? $ip : '';
}

try {
    $raw  = file_get_contents('php://input');
    $data = json_decode($raw, true);
    if (!is_array($data)) $data = [];

    // vid из cookie, иначе генерируем и ставим
    $vid = $_COOKIE['sh_vid'] ?? '';
    if (!preg_match('/^[a-f0-9\-]{8,40}$/i', $vid)) {
        $vid = bin2hex(random_bytes(16));
        setcookie('sh_vid', $vid, [
            'expires'  => time() + 365 * 24 * 3600,
            'path'     => '/',
            'samesite' => 'Lax',
            'secure'   => (!empty($_SERVER['HTTPS']) && $_SERVER['HTTPS'] !== 'off'),
        ]);
    }

    $page     = track_clip($data['page'] ?? '');
    $referrer = track_clip($data['referrer'] ?? '');
    $utmS     = track_clip($data['utm_source'] ?? '', 100);
    $utmM     = track_clip($data['utm_medium'] ?? '', 100);
    $utmC     = track_clip($data['utm_campaign'] ?? '', 100);
    $device   = track_clip($data['device'] ?? '', 20);
    $ua       = track_clip($_SERVER['HTTP_USER_AGENT'] ?? '', 300);
    $ip       = track_client_ip();

    require_once __DIR__ . '/../db/init.php';
    $db = getDB();

    $ins = $db->prepare('INSERT INTO visits (vid,page,referrer,utm_source,utm_medium,utm_campaign,device,ip) VALUES (?,?,?,?,?,?,?,?)');
    $ins->execute([$vid, $page, $referrer, $utmS, $utmM, $utmC, $device, $ip]);

    $exists = $db->prepare('SELECT vid FROM visitors WHERE vid = ?');
    $exists->execute([$vid]);
    if ($exists->fetch()) {
        $db->prepare("UPDATE visitors SET last_seen=CURRENT_TIMESTAMP, visits_count=visits_count+1, last_ip=?, device=?, user_agent=? WHERE vid=?")
           ->execute([$ip, $device, $ua, $vid]);
    } else {
        $db->prepare("INSERT INTO visitors (vid,visits_count,first_referrer,first_utm_source,first_utm_medium,first_utm_campaign,device,user_agent,last_ip) VALUES (?,?,?,?,?,?,?,?,?)")
           ->execute([$vid, 1, $referrer, $utmS, $utmM, $utmC, $device, $ua, $ip]);
    }

    echo json_encode(['ok' => true, 'vid' => $vid]);
} catch (Throwable $e) {
    error_log('[SplitHub track] ' . $e->getMessage());
    echo json_encode(['ok' => false]);
}
