import json
import tempfile
import unittest
from pathlib import Path

from tools.catalog_sync import assert_catalogs_match, parse_products_js, write_products_json


class CatalogSyncTests(unittest.TestCase):
    def test_generates_json_with_the_same_ids_and_prices_as_products_js(self):
        source = '''var PRODUCTS = [
  {"id": "100", "model": "Split 07", "price": 21990},
  {"id": "101", "model": "Split 09", "price": 23490}
];
'''
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            js_path = root / 'products.js'
            json_path = root / 'products.json'
            js_path.write_text(source, encoding='utf-8')

            write_products_json(js_path, json_path)

            generated = json.loads(json_path.read_text(encoding='utf-8'))
            expected = parse_products_js(source)
            self.assertEqual(generated, expected)
            assert_catalogs_match(expected, generated)

    def test_rejects_price_mismatch_before_deployment(self):
        source = parse_products_js('''var PRODUCTS = [
  {"id": "100", "model": "Split 07", "price": 21990}
];
''')

        with self.assertRaisesRegex(ValueError, 'price mismatch for product 100'):
            assert_catalogs_match(source, [{"id": "100", "model": "Split 07", "price": 22390}])


if __name__ == '__main__':
    unittest.main()
