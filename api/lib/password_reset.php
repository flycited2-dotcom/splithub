<?php
require_once __DIR__ . '/../../db/init.php';

// Поэтапный выкат: обязателен ли email при регистрации (флаг app_settings.email_required).
function pr_emailRequired(): bool {
    try {
        $s = getDB()->prepare("SELECT value FROM app_settings WHERE key='email_required'");
        $s->execute();
        return $s->fetchColumn() === '1';
    } catch (Throwable $e) {
        return false;
    }
}

function pr_generateCode(): string {
    return str_pad((string)random_int(0, 999999), 6, '0', STR_PAD_LEFT);
}

function pr_maskEmail(string $email): string {
    $at = strpos($email, '@');
    if ($at === false) return '***';
    $name = substr($email, 0, $at);
    $domain = substr($email, $at + 1);
    $dot = strrpos($domain, '.');
    $tld = $dot !== false ? substr($domain, $dot) : '';
    $maskedName = ($name === '' ? '' : $name[0]) . '***';
    $maskedDomain = ($domain === '' ? '' : $domain[0]) . '***' . $tld;
    return $maskedName . '@' . $maskedDomain;
}

function pr_findUser(string $identifier): ?array {
    $db = getDB();
    $phone = normalizePhone($identifier);
    if (strlen($phone) >= 10) {
        $s = $db->prepare('SELECT * FROM users WHERE phone=?');
        $s->execute([$phone]);
        $u = $s->fetch();
        if ($u) return $u;
    }
    if (strpos($identifier, '@') !== false) {
        $s = $db->prepare('SELECT * FROM users WHERE email=? AND email != ""');
        $s->execute([trim($identifier)]);
        $u = $s->fetch();
        if ($u) return $u;
    }
    return null;
}

function pr_lastTestCode(): string { return (string)getenv('PR_LAST_TEST_CODE'); }

function pr_sendResetEmail(string $toEmail, string $code): bool {
    if (getenv('PR_DISABLE_EMAIL')) { putenv('PR_LAST_TEST_CODE=' . $code); return true; }
    $subject = '=?UTF-8?B?' . base64_encode('Код восстановления СплитХаб') . '?=';
    $body = "Ваш код для сброса пароля: $code\nКод действует 15 минут.\nЕсли вы не запрашивали сброс — игнорируйте письмо.\n\nСплитХаб · splithub.ru";
    $headers = "From: SplitHub <info@splithub.ru>\r\nContent-Type: text/plain; charset=UTF-8\r\n";
    return @mail($toEmail, $subject, $body, $headers);
}

function requestPasswordReset(string $identifier): array {
    $db = getDB();
    $user = pr_findUser($identifier);
    if (!$user) return ['state' => 'not_found', 'email_masked' => null];
    if (empty($user['email'])) return ['state' => 'no_email', 'email_masked' => null];

    // rate-limit: не более 5 запросов за час
    $cnt = $db->prepare("SELECT COUNT(*) FROM password_resets WHERE user_id=? AND created_at > datetime('now','-1 hour')");
    $cnt->execute([(int)$user['id']]);
    if ((int)$cnt->fetchColumn() >= 5) return ['state' => 'rate_limited', 'email_masked' => pr_maskEmail($user['email'])];

    // гасим прошлые неиспользованные коды
    $db->prepare("UPDATE password_resets SET used=1 WHERE user_id=? AND used=0")->execute([(int)$user['id']]);
    $code = pr_generateCode();
    $db->prepare("INSERT INTO password_resets(user_id,code_hash,expires_at) VALUES(?,?,datetime('now','+15 minutes'))")
       ->execute([(int)$user['id'], hash('sha256', $code)]);
    pr_sendResetEmail($user['email'], $code);
    return ['state' => 'sent', 'email_masked' => pr_maskEmail($user['email'])];
}

function confirmPasswordReset(string $identifier, string $code, string $newPassword): array {
    $db = getDB();
    if (strlen($newPassword) < 4) return ['ok' => false, 'code' => 'INVALID_PASSWORD'];
    $user = pr_findUser($identifier);
    if (!$user) return ['ok' => false, 'code' => 'CODE_EXPIRED'];

    $s = $db->prepare("SELECT * FROM password_resets WHERE user_id=? AND used=0 AND expires_at > datetime('now') ORDER BY id DESC LIMIT 1");
    $s->execute([(int)$user['id']]);
    $row = $s->fetch();
    if (!$row) return ['ok' => false, 'code' => 'CODE_EXPIRED'];

    if ((int)$row['attempts'] >= 5) {
        $db->prepare("UPDATE password_resets SET used=1 WHERE id=?")->execute([(int)$row['id']]);
        return ['ok' => false, 'code' => 'TOO_MANY_ATTEMPTS'];
    }
    if (!hash_equals($row['code_hash'], hash('sha256', $code))) {
        $db->prepare("UPDATE password_resets SET attempts=attempts+1 WHERE id=?")->execute([(int)$row['id']]);
        return ['ok' => false, 'code' => 'INVALID_CODE', 'attempts_left' => 5 - ((int)$row['attempts'] + 1)];
    }
    // успех
    $db->prepare("UPDATE users SET password_hash=? WHERE id=?")
       ->execute([password_hash($newPassword, PASSWORD_BCRYPT), (int)$user['id']]);
    $db->prepare("UPDATE password_resets SET used=1 WHERE id=?")->execute([(int)$row['id']]);
    try { $db->prepare("DELETE FROM mobile_sessions WHERE user_id=?")->execute([(int)$user['id']]); } catch (Throwable $e) {}
    unset($user['password_hash']);
    return ['ok' => true, 'user' => $user];
}
