"""Адаптеры провайдеров генерации изображений.

Единый интерфейс: provider.generate(prompt, seed) -> PIL.Image.
Провайдер выбирается строкой из конфига, например:
    "genapi:seedream-v4"                 — gen-api.ru, Seedream 4.0 (сразу ~1872×4064)
    "cloudflare:flux-2-klein-4b"         — Cloudflare Workers AI, бесплатный режим
Чтобы добавить новый сервис (Replicate, fal.ai, локальная модель), достаточно
написать класс с методом generate() и зарегистрировать его в PROVIDERS.
"""
from __future__ import annotations

import base64
import io
import time
from dataclasses import dataclass

import requests
from PIL import Image

from . import config


class ProviderError(RuntimeError):
    """Ошибка генерации; retryable=False — повторять бессмысленно (нет денег/квоты)."""

    def __init__(self, msg: str, retryable: bool = True, retry_after: float | None = None):
        super().__init__(msg)
        self.retryable = retryable
        self.retry_after = retry_after  # подсказка сервиса «повторите через N с» (429)


@dataclass
class ModelSpec:
    name: str            # человекочитаемое имя для реестра и отчёта
    width: int           # размер, в котором генерируем
    height: int
    price_note: str = ""


class Provider:
    key: str = ""
    model: ModelSpec

    def generate(self, prompt: str, seed: int) -> Image.Image:  # pragma: no cover
        raise NotImplementedError

    @property
    def label(self) -> str:
        return f"{self.key}:{self.model.name}"


# --------------------------------------------------------------------------
# gen-api.ru (агрегатор, оплата в рублях)
# --------------------------------------------------------------------------
class GenApiProvider(Provider):
    key = "genapi"
    BASE = "https://api.gen-api.ru/api/v1"
    MODELS = {
        # Seedream: цена за картинку не зависит от разрешения → генерируем сразу в нужном размере
        "seedream-v4": ModelSpec("Seedream 4.0", 1872, 4064, "7.5 ₽/шт"),
        "seedream-v4-5": ModelSpec("Seedream 4.5", 1872, 4064, "10 ₽/шт"),
    }

    def __init__(self, model: str):
        if not config.GENAPI_API_KEY:
            raise ProviderError("Не задан GENAPI_API_KEY в .env", retryable=False)
        self.model_id, self.model = model, self.MODELS[model]
        self.h = {"Authorization": f"Bearer {config.GENAPI_API_KEY}", "Accept": "application/json"}

    def generate(self, prompt: str, seed: int) -> Image.Image:
        body = {"prompt": prompt, "width": self.model.width, "height": self.model.height,
                "num_images": 1, "seed": seed % 2_147_483_647}
        # 1) постановка задачи. Сеть/таймаут/429/5xx — временные ошибки (повторит конвейер)
        try:
            r = requests.post(f"{self.BASE}/networks/{self.model_id}", headers=self.h, json=body, timeout=60)
        except requests.RequestException as e:
            raise ProviderError(f"gen-api: сеть: {e}") from e
        if r.status_code in (401, 402, 403):
            raise ProviderError(f"gen-api {r.status_code}: {r.text[:300]}", retryable=False)
        if r.status_code >= 400:
            raise ProviderError(f"gen-api {r.status_code}: {r.text[:300]}",
                                retry_after=_retry_after(r) if r.status_code == 429 else None)
        try:
            data = r.json()
        except ValueError as e:
            raise ProviderError(f"gen-api: не JSON: {r.text[:200]}") from e
        req_id = data.get("request_id") or data.get("id")
        if not req_id:
            raise ProviderError(f"gen-api: нет request_id в ответе: {str(data)[:300]}")

        # 2) ожидание результата. Задача уже оплачена — сбои опроса не бросают её, а повторяются
        deadline = time.time() + 300
        time.sleep(max(0.0, config.GENAPI_FIRST_POLL - config.GENAPI_POLL_INTERVAL))
        while time.time() < deadline:
            time.sleep(config.GENAPI_POLL_INTERVAL)
            try:
                s = requests.get(f"{self.BASE}/request/get/{req_id}", headers=self.h, timeout=30)
                if s.status_code >= 400:
                    continue
                res = s.json()
            except (requests.RequestException, ValueError):
                continue
            status = res.get("status")
            if status == "success":
                urls = _find_urls(res.get("result")) or _find_urls(res.get("full_response"))
                if not urls:
                    raise ProviderError(f"gen-api: нет ссылки на картинку: {str(res)[:300]}")
                return _download_image(urls[0])
            if status in ("error", "failed"):
                raise ProviderError(f"gen-api: генерация не удалась: {str(res)[:300]}")
        raise ProviderError("gen-api: таймаут ожидания результата")


def _retry_after(r: requests.Response) -> float | None:
    try:
        return float(r.headers.get("Retry-After", ""))
    except ValueError:
        return None


def _download_image(url: str) -> Image.Image:
    """Скачать готовую картинку (до 3 попыток — она уже оплачена)."""
    for attempt in range(3):
        try:
            resp = requests.get(url, timeout=120)
            resp.raise_for_status()
            return Image.open(io.BytesIO(resp.content)).convert("RGB")
        except (requests.RequestException, OSError) as e:
            if attempt == 2:
                raise ProviderError(f"не удалось скачать результат: {e}") from e
            time.sleep(2 * (attempt + 1))


def _find_urls(obj) -> list[str]:
    """Достать http-ссылки из result / full_response любой вложенности."""
    out: list[str] = []
    if isinstance(obj, str) and obj.startswith("http"):
        out.append(obj)
    elif isinstance(obj, list):
        for x in obj:
            out += _find_urls(x)
    elif isinstance(obj, dict):
        for x in obj.values():
            out += _find_urls(x)
    return out


# --------------------------------------------------------------------------
# Cloudflare Workers AI (бесплатно 10 000 нейронов/сутки)
# --------------------------------------------------------------------------
class CloudflareProvider(Provider):
    key = "cloudflare"
    MODELS = {
        # (id модели, формат запроса)
        "flux-2-klein-4b": (ModelSpec("FLUX.2 klein 4B", 944, 2048, "~48 шт/сутки бесплатно"),
                            "@cf/black-forest-labs/flux-2-klein-4b", "multipart"),
        "flux-2-klein-9b": (ModelSpec("FLUX.2 klein 9B", 944, 2048, "~6 шт/сутки бесплатно"),
                            "@cf/black-forest-labs/flux-2-klein-9b", "multipart"),
        "lucid-origin": (ModelSpec("Leonardo Lucid Origin", 1152, 2496, "~1 шт/сутки бесплатно"),
                         "@cf/leonardo/lucid-origin", "json"),
    }

    def __init__(self, model: str):
        if not (config.CF_ACCOUNT_ID and config.CF_API_TOKEN):
            raise ProviderError("Не заданы CF_ACCOUNT_ID / CF_API_TOKEN в .env", retryable=False)
        self.model, self.model_path, self.fmt = self.MODELS[model]
        self.url = f"https://api.cloudflare.com/client/v4/accounts/{config.CF_ACCOUNT_ID}/ai/run/{self.model_path}"
        self.h = {"Authorization": f"Bearer {config.CF_API_TOKEN}"}

    def generate(self, prompt: str, seed: int) -> Image.Image:
        w, h = str(self.model.width), str(self.model.height)
        try:
            if self.fmt == "multipart":
                r = requests.post(self.url, headers=self.h, timeout=180, files={
                    "prompt": (None, prompt), "width": (None, w), "height": (None, h),
                    "seed": (None, str(seed % 2_147_483_647))})
            else:
                r = requests.post(self.url, headers=self.h, timeout=180, json={
                    "prompt": prompt, "width": int(w), "height": int(h), "seed": seed % 2_147_483_647})
            data = r.json() if r.headers.get("content-type", "").startswith("application/json") else {}
        except (requests.RequestException, ValueError) as e:
            raise ProviderError(f"Cloudflare: сеть: {e}") from e
        if not data.get("success"):
            err = str(data.get("errors") or r.text[:300])
            quota = "4006" in err or "daily free allocation" in err
            raise ProviderError(f"Cloudflare {r.status_code}: {err}", retryable=not quota)
        return Image.open(io.BytesIO(base64.b64decode(data["result"]["image"]))).convert("RGB")


# --------------------------------------------------------------------------
PROVIDERS = {"genapi": GenApiProvider, "cloudflare": CloudflareProvider}


def get_provider(spec: str) -> Provider:
    """'genapi:seedream-v4' → экземпляр провайдера."""
    key, _, model = spec.partition(":")
    if key not in PROVIDERS:
        raise ValueError(f"Неизвестный провайдер: {key}. Доступны: {', '.join(PROVIDERS)}")
    return PROVIDERS[key](model)


def available_models() -> list[str]:
    return [f"{k}:{m}" for k, cls in PROVIDERS.items() for m in cls.MODELS]
