<?php
require_once __DIR__ . '/bootstrap.php';
require_once projectPath('api/lib/mobile_auth.php');

$db = getDB();
$db->prepare('INSERT INTO users(name,phone,password_hash) VALUES(?,?,?)')
   ->execute(['Mobile User', '79780000001', password_hash('pass123', PASSWORD_BCRYPT)]);

$login = issueMobileToken('79780000001', 'pass123');
assertTrue(isset($login['token']), 'login returns bearer token');
assertSame(1, requireMobileUser($login['token']), 'token authorizes user');
assertSame(
    'springhost-token',
    bearerToken([], ['Authorization' => 'Bearer springhost-token']),
    'bearer token falls back to web server headers'
);
revokeMobileToken($login['token']);
assertSame(null, findMobileUser($login['token']), 'logout revokes token');

try {
    issueMobileToken('79780000001', 'wrong');
    throw new RuntimeException('FAIL: invalid password accepted');
} catch (RuntimeException $e) {
    assertSame('INVALID_CREDENTIALS', $e->getMessage(), 'invalid password rejected');
}
