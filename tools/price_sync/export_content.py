#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Выгрузка наполнения карточек из базы SplitHome: описание, фото, характеристики.

База живёт в докере на VPS и наружу не смотрит, поэтому запрос выполняется НА
СЕРВЕРЕ (как и export_oasis.ps1): пароли базы никуда не уезжают. Только чтение.

    python -m tools.price_sync.export_content НС-1696913 df090358-08ea-11f1-...
    python -m tools.price_sync.export_content --from-file codes.txt

Результат — out/content_export.json: {nc_code: {title, brand, series, description,
images: [...], specs: {название: значение}}}. Уже выгруженные коды дописываются.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import paramiko

from tools.price_sync.sync import DEFAULT_OUT

SSH_HOST = "212.116.115.150"
SSH_PORT = 2222
SSH_USER = "root"
SSH_KEY = str(Path.home() / ".ssh" / "id_ritualb2b_admin")
PSQL = ('docker exec -i oasis-db-1 sh -c '
        '"psql -U \\$POSTGRES_USER -d \\$POSTGRES_DB -At -f -"')

TARGET = DEFAULT_OUT / "content_export.json"

QUERY = """
SELECT json_build_object(
  'nc_code', p.nc_code, 'source', p.source, 'title', p.title,
  'brand', coalesce(b.title, ''), 'series', coalesce(p.series, ''),
  'kind', p.kind, 'btu_calc', p.btu_calc, 'heating_min_temp', p.heating_min_temp,
  'is_heat_pump', p.is_heat_pump, 'description', coalesce(p.description, ''),
  'images', coalesce((SELECT json_agg(i.url ORDER BY i."order", i.id)
                      FROM catalog_productimage i WHERE i.product_id = p.id), '[]'::json),
  'specs', coalesce((SELECT json_object_agg(s.title, trim(t.value || ' ' || coalesce(s.unit, '')))
                     FROM catalog_producttech t JOIN catalog_techspec s ON s.id = t.spec_id
                     WHERE t.product_id = p.id), '{}'::json))
FROM catalog_product p LEFT JOIN catalog_brand b ON b.id = p.brand_id
WHERE p.nc_code IN (%s);
"""


def _quote(code: str) -> str:
    return "'" + code.replace("'", "''") + "'"


def fetch(codes: list[str]) -> dict[str, dict]:
    if not codes:
        return {}
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(SSH_HOST, port=SSH_PORT, username=SSH_USER, key_filename=SSH_KEY, timeout=20)
    try:
        stdin, stdout, stderr = ssh.exec_command(PSQL)
        stdin.write(QUERY % ", ".join(_quote(code) for code in codes))
        stdin.channel.shutdown_write()
        out = stdout.read().decode("utf-8")
        error = stderr.read().decode("utf-8").strip()
    finally:
        ssh.close()
    if error:
        raise RuntimeError(error)
    result = {}
    for line in out.splitlines():
        if line.strip():
            item = json.loads(line)
            result[item["nc_code"]] = item
    return result


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Наполнение карточек из базы SplitHome")
    parser.add_argument("codes", nargs="*", help="nc_code товаров")
    parser.add_argument("--from-file", help="файл с nc_code, по одному в строке")
    args = parser.parse_args(argv)
    codes = list(args.codes)
    if args.from_file:
        codes += [line.strip() for line in Path(args.from_file).read_text(encoding="utf-8").splitlines()
                  if line.strip()]
    known = json.loads(TARGET.read_text(encoding="utf-8")) if TARGET.exists() else {}
    fresh = fetch(sorted(set(codes)))
    known.update(fresh)
    TARGET.write_text(json.dumps(known, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    missing = sorted(set(codes) - set(fresh))
    sys.stdout.buffer.write(("выгружено: %d, не найдено: %d %s\n%s\n" % (
        len(fresh), len(missing), missing[:10], TARGET)).encode("utf-8"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
