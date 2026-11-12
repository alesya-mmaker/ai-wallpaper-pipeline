"""Запуск заказа из командной строки.

Примеры:
  python run_order.py --themes space mountains anime --count 8
  python run_order.py --themes ocean --custom "японские храмы осенью" --count 10 --provider cloudflare:flux-2-klein-4b
  python run_order.py --list
"""
import argparse
import sys

sys.stdout.reconfigure(encoding="utf-8")

from wallgen import config  # noqa: E402
from wallgen.pipeline import run_order  # noqa: E402
from wallgen.providers import available_models  # noqa: E402
from wallgen.themes import THEMES  # noqa: E402

p = argparse.ArgumentParser(description="Генерация обоев для телефона")
p.add_argument("--themes", nargs="*", default=[], help="ключи тем (см. --list)")
p.add_argument("--custom", nargs="*", default=[], help="свои темы, любым языком")
p.add_argument("--count", type=int, default=10)
p.add_argument("--provider", default=config.PROVIDER, help="например genapi:seedream-v4")
p.add_argument("--no-upload", action="store_true", help="не загружать в Google Drive")
p.add_argument("--list", action="store_true", help="показать темы и модели")
a = p.parse_args()

if a.list:
    print("Темы:")
    for k, t in THEMES.items():
        print(f"  {k:12} {t['name']}")
    print("Модели:", ", ".join(available_models()))
    sys.exit()

r = run_order(a.themes, a.custom, a.count, a.provider, upload=not a.no_upload)
print("\nПапка:", r.folder_link or r.local_dir)
if r.sheet_link:
    print("Таблица промптов:", r.sheet_link)
