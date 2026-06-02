<?php
require_once __DIR__ . '/../../db/init.php';

function bearerToken(?array $server = null, ?array $headers = null): string {
    $server ??= $_SERVER;
    $header = (string)($server['HTTP_AUTHORIZATION'] ?? '');
    if ($header === '') {
        $headers ??= function_exists('getallheaders') ? getallheaders() : [];
        foreach ($headers as $name => $value) {
            if (strcasecmp((string)$name, 'Authorization') === 0) {
                $header = (string)$value;
                break;
            }
        }
    }
    return preg_match('/^Bearer\s+(.+)$/i', $header, $matches) ? trim($matches[1]) : '';
}

function issueMobileToken(string $phone, string $password): array {
    $db = getDB();
    $normalized = normalizePhone($phone) ?: trim($phone);
    $stmt = $db->prepare('SELECT id,name,phone,telegram,role,password_hash FROM users WHERE phone=?');
    $stmt->execute([$normalized]);
    $user = $stmt->fetch();
    if (!$user || !password_verify($password, $user['password_hash'])) {
        throw new RuntimeException('INVALID_CREDENTIALS');
    }

    $token = bin2hex(random_bytes(32));
    $db->prepare("INSERT INTO mobile_sessions(user_id,token_hash,expires_at)
                  VALUES(?,?,datetime('now','+90 days'))")
       ->execute([(int)$user['id'], hash('sha256', $token)]);
    unset($user['password_hash']);
    return ['token' => $token, 'user' => $user];
}

function findMobileUser(string $token): ?int {
    if ($token === '') {
        return null;
    }
    $stmt = getDB()->prepare("SELECT user_id FROM mobile_sessions
                              WHERE token_hash=? AND expires_at > datetime('now')");
    $stmt->execute([hash('sha256', $token)]);
    $row = $stmt->fetch();
    return $row ? (int)$row['user_id'] : null;
}

function requireMobileUser(?string $token = null): int {
    $uid = findMobileUser($token ?? bearerToken());
    if (!$uid) {
        throw new RuntimeException('AUTH_REQUIRED');
    }
    return $uid;
}

function revokeMobileToken(string $token): void {
    getDB()->prepare('DELETE FROM mobile_sessions WHERE token_hash=?')
           ->execute([hash('sha256', $token)]);
}
