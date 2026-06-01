<?php
require_once __DIR__ . '/../../db/init.php';

$db = getDB();
$db->prepare('INSERT INTO users(name,phone,password_hash,role) VALUES(?,?,?,?)')
   ->execute(['Admin', 'admin', password_hash('pass123', PASSWORD_BCRYPT), 'admin']);
$db->prepare('INSERT INTO users(name,phone,password_hash) VALUES(?,?,?)')
   ->execute(['Push Customer', '79780000006', password_hash('pass123', PASSWORD_BCRYPT)]);
echo $db->lastInsertId();
