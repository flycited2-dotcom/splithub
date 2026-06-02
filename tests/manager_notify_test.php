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
    'Test_mob <client>',
    '79781234567',
    $items,
    37540,
    'Нужен звонок & счёт',
    '@test',
    '02.06.2026 23:01'
);

assertContainsText('🛒 <b>Новая заявка — СплитХаб</b>', $telegram);
assertContainsText('<b>Номер:</b> SH-00047', $telegram);
assertContainsText('<b>Имя:</b> Test_mob &lt;client&gt;', $telegram);
assertContainsText('<b>Телефон:</b> 79781234567', $telegram);
assertContainsText('<b>Telegram:</b> @test', $telegram);
assertContainsText('MIDEA MSAG1-09HRN8-I on/off — 28 990 ₽ × 1 шт. = 28 990 ₽', $telegram);
assertContainsText('<b>Итого:</b> 37 540 ₽', $telegram);
assertContainsText('<b>Комментарий:</b> Нужен звонок &amp; счёт', $telegram);
assertContainsText('Клиент ждёт звонка', $telegram);
if (strpos($telegram, 'New mobile order') !== false || strpos($telegram, 'Total:') !== false) {
    throw new RuntimeException('Telegram text must not use the old English mobile template');
}
if (strpos($telegram, '*Номер:*') !== false || strpos($telegram, '_Клиент ждёт звонка_') !== false) {
    throw new RuntimeException('Telegram text must not use Markdown formatting');
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
