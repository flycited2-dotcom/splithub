#!/usr/bin/env python3
"""Generate and validate the server catalog from the storefront catalog."""

import argparse
import json
import re
from pathlib import Path
from typing import Any


PRODUCTS_ASSIGNMENT = re.compile(r'^\s*(?:var|let|const)\s+PRODUCTS\s*=\s*', re.DOTALL)


def parse_products_js(source: str) -> list[dict[str, Any]]:
    """Parse the JSON array assigned to the storefront PRODUCTS variable."""
    assignment = PRODUCTS_ASSIGNMENT.match(source)
    if not assignment:
        raise ValueError('products.js must start with a PRODUCTS assignment')

    payload = source[assignment.end():].strip()
    if payload.endswith(';'):
        payload = payload[:-1].rstrip()

    try:
        products = json.loads(payload)
    except json.JSONDecodeError as error:
        raise ValueError('products.js does not contain valid JSON') from error

    if not isinstance(products, list) or not all(isinstance(product, dict) for product in products):
        raise ValueError('products.js must contain an array of product objects')
    return products


def read_products_json(path: Path) -> list[dict[str, Any]]:
    try:
        products = json.loads(path.read_text(encoding='utf-8'))
    except json.JSONDecodeError as error:
        raise ValueError(f'{path} does not contain valid JSON') from error

    if not isinstance(products, list) or not all(isinstance(product, dict) for product in products):
        raise ValueError(f'{path} must contain an array of product objects')
    return products


def catalog_by_id(products: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    indexed: dict[str, dict[str, Any]] = {}
    for product in products:
        product_id = str(product.get('id', '')).strip()
        if not product_id:
            raise ValueError('catalog contains a product without id')
        if product_id in indexed:
            raise ValueError(f'catalog contains duplicate product id {product_id}')
        indexed[product_id] = product
    return indexed


def assert_catalogs_match(
    storefront_products: list[dict[str, Any]],
    server_products: list[dict[str, Any]],
) -> None:
    """Raise when the server catalog differs in products or prices."""
    storefront_by_id = catalog_by_id(storefront_products)
    server_by_id = catalog_by_id(server_products)

    missing_on_server = sorted(set(storefront_by_id) - set(server_by_id))
    if missing_on_server:
        raise ValueError(f'missing product ids in products.json: {", ".join(missing_on_server)}')

    unexpected_on_server = sorted(set(server_by_id) - set(storefront_by_id))
    if unexpected_on_server:
        raise ValueError(f'unexpected product ids in products.json: {", ".join(unexpected_on_server)}')

    for product_id, storefront_product in storefront_by_id.items():
        storefront_price = storefront_product.get('price')
        server_price = server_by_id[product_id].get('price')
        if storefront_price != server_price:
            raise ValueError(
                f'price mismatch for product {product_id}: '
                f'products.js={storefront_price}, products.json={server_price}'
            )


def write_products_json(products_js_path: Path, products_json_path: Path) -> list[dict[str, Any]]:
    products = parse_products_js(products_js_path.read_text(encoding='utf-8'))
    products_json_path.write_text(
        json.dumps(products, ensure_ascii=False, indent=2) + '\n',
        encoding='utf-8',
    )
    return products


def main() -> None:
    parser = argparse.ArgumentParser(
        description='Generate products.json from the source-of-truth products.js and verify the pair.',
    )
    parser.add_argument('--products-js', type=Path, required=True)
    parser.add_argument('--products-json', type=Path, required=True)
    args = parser.parse_args()

    storefront_products = write_products_json(args.products_js, args.products_json)
    assert_catalogs_match(storefront_products, read_products_json(args.products_json))
    print(f'Synchronized {len(storefront_products)} products from {args.products_js} to {args.products_json}')


if __name__ == '__main__':
    main()
