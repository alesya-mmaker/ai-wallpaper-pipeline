"""Настройки проекта (из .env + константы)."""
import os
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / ".env")

CF_ACCOUNT_ID = os.environ.get("CF_ACCOUNT_ID", "").strip()
CF_API_TOKEN = os.environ.get("CF_API_TOKEN", "").strip()
GENAPI_API_KEY = os.environ.get("GENAPI_API_KEY", "").strip()

# Провайдер генерации по умолчанию — меняется одной строкой (или PROVIDER=... в .env).
# Варианты: genapi:seedream-v4, genapi:seedream-v4-5, cloudflare:flux-2-klein-4b, ...
PROVIDER = os.environ.get("PROVIDER", "genapi:seedream-v4").strip()

# Название приложения
APP_NAME = os.environ.get("APP_NAME", "WallGen")

# Итоговые обои
TARGET_W, TARGET_H = 1870, 4063
JPEG_QUALITY = 95

# Папки
OUTPUT_DIR = ROOT / "output" / "orders"
REALESRGAN_EXE = ROOT / "tools" / "realesrgan" / "realesrgan-ncnn-vulkan.exe"

# Google Drive: корневая папка для всех заказов (создаётся приложением)
DRIVE_ROOT_FOLDER = os.environ.get("DRIVE_ROOT_FOLDER", "WallGen")
# Открывать папку заказа «Просмотр по ссылке», чтобы ссылкой можно было поделиться
SHARE_ORDER_FOLDER = os.environ.get("SHARE_ORDER_FOLDER", "1") != "0"

# Параллельность запросов к облаку
# 12 — проверено на прогоне 100 шт. (очереди на стороне gen-api не было); 24 — по умолчанию,
# при ответе «слишком много запросов» конвейер сам делает паузы и повторы
GEN_CONCURRENCY = int(os.environ.get("GEN_CONCURRENCY", "24"))
# Опрос готовности gen-api: Seedream работает ~13 с, поэтому первый опрос не раньше 10 с —
# так вдвое меньше запросов к API и запас под лимит ~300 запросов/мин
GENAPI_FIRST_POLL = float(os.environ.get("GENAPI_FIRST_POLL", "10"))
GENAPI_POLL_INTERVAL = float(os.environ.get("GENAPI_POLL_INTERVAL", "3"))

# Автоконтроль качества (vision-модель через gen-api) и число перегенераций при браке
QC_ENABLED = os.environ.get("QC_ENABLED", "1") != "0"
QC_MODEL = os.environ.get("QC_MODEL", "gpt-4o-mini")
QC_MAX_RETRIES = int(os.environ.get("QC_MAX_RETRIES", "2"))

# LLM для раскрытия пользовательских тем (сначала gen-api, если есть ключ, иначе Cloudflare)
GENAPI_TEXT_MODEL = "gpt-4o-mini"
CF_TEXT_MODEL = "@cf/meta/llama-3.3-70b-instruct-fp8-fast"
