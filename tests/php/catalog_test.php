<?php
require_once __DIR__ . '/bootstrap.php';

$catalog = json_decode(file_get_contents(projectPath('products.json')), true);
assertTrue(is_array($catalog), 'products.json is valid JSON');
assertTrue(count($catalog) > 0, 'products.json contains products');
assertTrue(isset($catalog[0]['id'], $catalog[0]['price'], $catalog[0]['stock']), 'catalog fields exist');

require_once projectPath('api/lib/catalog.php');

$result = validateCatalogItems([
    ['id' => '1001', 'name' => 'Old name', 'price' => 1, 'qty' => 2],
]);
assertSame(false, $result['ok'], 'changed price requires confirmation');
assertSame('CATALOG_CHANGED', $result['code'], 'changed price code');

$result = validateCatalogItems([['id' => 'missing', 'price' => 1, 'qty' => 1]]);
assertSame('PRODUCT_UNAVAILABLE', $result['code'], 'unknown product rejected');

assertSame('EMPTY_CART', validateCatalogItems([])['code'], 'empty cart rejected');
assertSame(
    'INVALID_QUANTITY',
    validateCatalogItems([['id' => '1001', 'price' => 24900, 'qty' => 0]])['code'],
    'invalid quantity rejected'
);

$valid = validateCatalogItems([['id' => '1001', 'price' => 24900, 'qty' => 2]]);
assertSame(true, $valid['ok'], 'unchanged catalog item accepted');
assertSame(49800, $valid['items'][0]['price'] * $valid['items'][0]['qty'], 'server values calculate total');
