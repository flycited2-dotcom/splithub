<?php
declare(strict_types=1);

function failDownload(string $message, int $status = 500): never {
    http_response_code($status);
    header('Content-Type: text/plain; charset=utf-8');
    echo $message;
    exit;
}

function productsJsPath(): string {
    return dirname(__DIR__) . '/products.js';
}

function loadProductsFromJs(string $path): array {
    $raw = @file_get_contents($path);
    if ($raw === false) {
        failDownload('Catalog source is unavailable');
    }

    if (!preg_match('/^\s*var\s+PRODUCTS\s*=\s*(\[.*\])\s*;\s*$/s', $raw, $matches)) {
        failDownload('Catalog source has an unexpected format');
    }

    $products = json_decode($matches[1], true);
    if (!is_array($products)) {
        failDownload('Catalog source cannot be decoded');
    }

    return $products;
}

function textValue(mixed $value): string {
    if (is_array($value)) {
        $value = implode('; ', array_map(static fn($item): string => (string)$item, $value));
    }

    return trim(str_replace(["\r", "\n"], ' ', (string)$value));
}

$products = loadProductsFromJs(productsJsPath());
$date = date('Y-m-d');

header('Content-Type: text/csv; charset=utf-8');
header('Content-Disposition: attachment; filename="splithub-price-' . $date . '.csv"');
header('Cache-Control: no-store, max-age=0');

$out = fopen('php://output', 'wb');
if ($out === false) {
    failDownload('Cannot open output stream');
}

fwrite($out, "\xEF\xBB\xBF");
fputcsv($out, ['ID', 'Бренд', 'Серия', 'Модель', 'Описание', 'BTU', 'Площадь м2', 'Цена ₽', 'Наличие', 'Группа'], ';');

foreach ($products as $product) {
    if (!is_array($product)) {
        continue;
    }

    fputcsv($out, [
        textValue($product['id'] ?? ''),
        textValue($product['brand'] ?? ''),
        textValue($product['series'] ?? ''),
        textValue($product['model'] ?? ''),
        textValue($product['descShort'] ?? ''),
        textValue($product['btu'] ?? ''),
        textValue($product['area'] ?? ''),
        textValue($product['price'] ?? ''),
        textValue($product['stockLabel'] ?? $product['stock'] ?? ''),
        textValue($product['group'] ?? ''),
    ], ';');
}
