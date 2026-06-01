#!/usr/bin/env python3
import re
import subprocess
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
ACTIVE_PHP_FILES = [
    ROOT / "send.php",
    ROOT / "api" / "auth.php",
    ROOT / "api" / "admin.php",
    ROOT / "api" / "price-send.php",
    ROOT / "api" / "tg_poll.php",
    ROOT / "api" / "reports.php",
]
BOT_TOKEN_PATTERN = re.compile(r"\b\d{8,}:[A-Za-z0-9_-]{20,}\b")


class ConfigExternalizationTest(unittest.TestCase):
    def test_runtime_config_loader_and_placeholder_template_exist(self):
        loader = ROOT / "api" / "lib" / "app_config.php"
        template = ROOT / "config.example.php"

        self.assertTrue(loader.is_file(), "secure runtime config loader is missing")
        self.assertTrue(template.is_file(), "placeholder config template is missing")
        self.assertIsNone(
            BOT_TOKEN_PATTERN.search(template.read_text(encoding="utf-8")),
            "config template must not contain a real-looking Telegram token",
        )

    def test_active_php_entrypoints_do_not_read_config_from_webroot(self):
        forbidden = re.compile(r"__DIR__\s*\.\s*['\"]/(?:\.\./)?config\.php['\"]")

        for path in ACTIVE_PHP_FILES:
            with self.subTest(path=path.relative_to(ROOT)):
                source = path.read_text(encoding="utf-8")
                self.assertIn(
                    "app_config.php",
                    source,
                    f"{path.relative_to(ROOT)} does not use the secure config loader",
                )
                self.assertIsNone(
                    forbidden.search(source),
                    f"{path.relative_to(ROOT)} still reads config.php from webroot",
                )

    def test_real_config_file_remains_gitignored(self):
        result = subprocess.run(
            ["git", "check-ignore", "-q", "config.php"],
            cwd=ROOT,
            check=False,
        )
        self.assertEqual(0, result.returncode, "config.php must stay ignored")


if __name__ == "__main__":
    unittest.main()
