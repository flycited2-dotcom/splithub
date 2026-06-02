<?php
require_once __DIR__ . '/../api/lib/manager_notify.php';

function assertContainsText(string $needle, string $haystack): void {
    if (strpos($haystack, $needle) === false) {
        throw new RuntimeException("Expected text to contain: {$needle}");
    }
}

$items = [
    ['brand' => 'MIDEA', 'name' => 'MSAG1-09HRN8-I on/off', 'price' => 28990, 'qty' => 1],
    ['brand' => '', 'name' => 'Медная труба 3/8 · бухта 50 м', 'price' => 8590, 'qty' => 1],
];

$telegram = mobileOrderTelegramText(
    47,
    'Test_mob',
    '79781234567',
    $items,
    37540,
    'Нужен звонок',
    '@test',
    '02.06.2026 23:01'
);

assertContainsText('🛒 *Новая заявка — СплитХаб*', $telegram);
assertContainsText('*Номер:* SH-00047', $telegram);
assertContainsText('*Имя:* Test_mob', $telegram);
assertContainsText('*Телефон:* 79781234567', $telegram);
assertContainsText('*Telegram:* @test', $telegram);
assertContainsText('MIDEA MSAG1-09HRN8-I on/off — 28 990 ₽ × 1 шт. = 28 990 ₽', $telegram);
assertContainsText('*Итого:* 37 540 ₽', $telegram);
assertContainsText('*Комментарий:* Нужен звонок', $telegram);
assertContainsText('Клиент ждёт звонка', $telegram);
if (strpos($telegram, 'New mobile order') !== false || strpos($telegram, 'Total:') !== false) {
    throw new RuntimeException('Telegram text must not use the old English mobile template');
}

$markup = mobileOrderReplyMarkup(47);
if ($markup['inline_keyboard'][0][0]['callback_data'] !== 'st:confirmed:47') {
    throw new RuntimeException('Confirm callback is wrong');
}
if ($markup['inline_keyboard'][0][1]['callback_data'] !== 'st:cancelled:47') {
    throw new RuntimeException('Cancel callback is wrong');
}

$email = mobileOrderEmailHtml(47, 'Test_mob', '79781234567', $items, 37540, 'Нужен звонок', '@test', '02.06.2026 23:01');
assertContainsText('Новая заявка — СплитХаб', $email);
assertContainsText('SH-00047', $email);
assertContainsText('MIDEA MSAG1-09HRN8-I on/off', $email);
assertContainsText('37&nbsp;540', $email);

echo "manager_notify_test passed\n";
