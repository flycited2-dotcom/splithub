<?php
function catalogPath(): string {
    return getenv('SPLITHUB_PRODUCTS_PATH') ?: dirname(__DIR__, 2) . '/products.json';
}

function loadCatalog(): array {
    $raw = @file_get_contents(catalogPath());
    $items = $raw === false ? null : json_decode($raw, true);
    if (!is_array($items)) {
        throw new RuntimeException('CATALOG_UNAVAILABLE');
    }
    return $items;
}

function catalogById(): array {
    $catalog = [];
    foreach (loadCatalog() as $item) {
        $catalog[(string)$item['id']] = $item;
    }
    return $catalog;
}

function validateCatalogItems(array $requested): array {
    if (!$requested) {
        return ['ok' => false, 'code' => 'EMPTY_CART'];
    }

    $catalog = catalogById();
    $items = [];
    $changes = [];
    foreach ($requested as $row) {
        if (!is_array($row)) {
            return ['ok' => false, 'code' => 'INVALID_ITEM'];
        }

        $id = (string)($row['id'] ?? '');
        $qty = (int)($row['qty'] ?? 0);
        if ($qty < 1 || $qty > 999) {
            return ['ok' => false, 'code' => 'INVALID_QUANTITY', 'product_id' => $id];
        }

        $product = $catalog[$id] ?? null;
        if (!$product || ($product['stock'] ?? '') === 'out') {
            return ['ok' => false, 'code' => 'PRODUCT_UNAVAILABLE', 'product_id' => $id];
        }

        $clientPrice = (int)($row['price'] ?? 0);
        $serverPrice = (int)$product['price'];
        if ($clientPrice !== $serverPrice) {
            $changes[] = ['id' => $id, 'old_price' => $clientPrice, 'new_price' => $serverPrice];
        }

        $items[] = [
            'id' => $id,
            'name' => (string)$product['model'],
            'brand' => (string)$product['brand'],
            'price' => $serverPrice,
            'qty' => $qty,
            'group' => (string)$product['group'],
        ];
    }

    if ($changes) {
        return ['ok' => false, 'code' => 'CATALOG_CHANGED', 'changes' => $changes, 'items' => $items];
    }
    return ['ok' => true, 'items' => $items];
}
