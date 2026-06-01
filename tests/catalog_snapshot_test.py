#!/usr/bin/env python3
import json
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from converter.convert import Converter
from tools.products_js_to_json import convert_products_js


class CatalogSnapshotTest(unittest.TestCase):
    def test_converter_json_omits_internal_sort_order(self):
        converter = Converter()
        converter.products = [
            {"id": "1001", "price": 24900, "stock": "in_stock", "_sortOrder": 1},
        ]

        self.assertEqual(
            [{"id": "1001", "price": 24900, "stock": "in_stock"}],
            json.loads(converter.generate_json()),
        )

    def test_current_javascript_catalog_can_be_migrated_to_json(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "products.js"
            target = Path(tmp) / "products.json"
            source.write_text('var PRODUCTS = [{"id": "1001", "price": 24900}];\n', encoding="utf-8")

            count = convert_products_js(source, target)

            self.assertEqual(1, count)
            self.assertEqual([{"id": "1001", "price": 24900}], json.loads(target.read_text(encoding="utf-8")))

    def test_deploy_uploads_both_catalog_artifacts(self):
        source = (ROOT / "converter" / "deploy.py").read_text(encoding="utf-8")

        self.assertIn('("products.js", "products.json")', source)


if __name__ == "__main__":
    unittest.main()
