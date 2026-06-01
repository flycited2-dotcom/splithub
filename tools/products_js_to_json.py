#!/usr/bin/env python3
import json
from pathlib import Path


def convert_products_js(source: Path, target: Path) -> int:
    text = source.read_text(encoding="utf-8").strip()
    prefix = "var PRODUCTS = "
    if not text.startswith(prefix) or not text.endswith(";"):
        raise ValueError("products.js wrapper is not recognized")
    products = json.loads(text[len(prefix):-1])
    target.write_text(
        json.dumps(products, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return len(products)


if __name__ == "__main__":
    root = Path(__file__).resolve().parents[1]
    count = convert_products_js(root / "products.js", root / "products.json")
    print(f"products.json: {count} products")
