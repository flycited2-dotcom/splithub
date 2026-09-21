# -*- coding: utf-8 -*-
"""PowerShell-скрипты обязаны открываться в Windows PowerShell 5.1.

Планировщик запускает `powershell.exe`, а это 5.1: файл без BOM он читает в cp1251.
Кириллица превращается в кашу, а тире «—» (в UTF-8 это байты E2 80 94) даёт 0x94 —
в cp1251 это закрывающая кавычка, она рвёт строковый литерал, и скрипт падает на
разборе ещё до первой строки. Так прогон цен молча падал с кодом 1 каждые три дня.
"""
import shutil
import subprocess
from pathlib import Path

import pytest

SCRIPTS = sorted((Path(__file__).resolve().parents[1]).glob("*.ps1"))
UTF8_BOM = b"\xef\xbb\xbf"


@pytest.mark.parametrize("script", SCRIPTS, ids=lambda p: p.name)
def test_ps1_s_bom(script):
    """С BOM 5.1 читает файл как UTF-8 — и кириллица, и тире остаются собой."""
    assert script.read_bytes().startswith(UTF8_BOM), (
        "%s сохранён без UTF-8 BOM — Windows PowerShell 5.1 его не разберёт" % script.name)


@pytest.mark.skipif(shutil.which("powershell.exe") is None, reason="нет Windows PowerShell 5.1")
@pytest.mark.parametrize("script", SCRIPTS, ids=lambda p: p.name)
def test_ps1_razbiraetsya_v_powershell_5(script):
    """Разбор тем самым движком, которым запускает планировщик, а не PowerShell 7."""
    check = (
        "$e=$null; [System.Management.Automation.Language.Parser]::ParseFile("
        "'%s',[ref]$null,[ref]$e)|Out-Null; if($e.Count){$e[0].Message; exit 1}" % script
    )
    result = subprocess.run(["powershell.exe", "-NoProfile", "-Command", check],
                            capture_output=True, text=True, timeout=60)
    assert result.returncode == 0, result.stdout + result.stderr
