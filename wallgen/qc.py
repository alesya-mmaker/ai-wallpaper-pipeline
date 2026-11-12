"""Автоконтроль качества: отбраковка явного брака перед сохранением.

Два уровня:
1. Локальные проверки (бесплатно, мгновенно): точный размер, «пустая» картинка.
2. Vision-модель (gpt-4o-mini через gen-api, ~копейки): рамка устройства/мокап, декоративная
   рамка-паспарту, заметный текст/логотип/водяной знак, сломанная или искажённая картинка.
Если брак — конвейер перегенерирует картинку с новым seed (до QC_MAX_RETRIES раз).
"""
from __future__ import annotations

import base64
import io
import json
import re
from dataclasses import dataclass

import requests
from PIL import Image, ImageStat

from . import config

QC_PROMPT = """You are a strict quality inspector for AI-generated phone wallpapers.
Look at the image and detect ONLY these defects:
- "device_frame": the artwork is shown inside a phone/tablet/screen mockup, device bezel, notch or dynamic island.
- "border": an artificial frame AROUND the artwork: a flat/ornamental strip, passe-partout, card edge or poster
  margin running along the image edges — including a THIN 1–5 px outline/keyline or a colored stroke hugging
  the image edge, and ornamental art-nouveau style frames or arches. Scene objects near the edges (buildings,
  trees, cliffs, walls, window frames inside the scene) are NOT a border.
- "mockup": the artwork is presented as a physical object — a framed print or canvas hanging on a wall,
  a poster, a card, a book cover, a table-top miniature model, a picture inside a picture.
- "text": prominent readable text, captions, letters, logos, signatures or watermarks that are a noticeable part of the image.
  Small blurry background signage that blends into a scene is acceptable.
- "broken": glitched or corrupted image, collage of mismatched panels (e.g. a rectangle of a different sky/time
  pasted into the scene), duplicated halves, heavily distorted or melted subjects, obvious anatomy horrors,
  and SPLIT PANELS: one or more straight vertical/horizontal bands or rectangles of a different tone,
  sky or scene that cut through the image like a pasted strip or inset window.
- "empty": more than 90% of the image is a blank or flat gradient AND there is no clear subject at all.
  Dark, night, neon, foggy or minimalist scenes that have a recognizable subject are NOT empty.
- "rotated": the scene is sideways or upside down — e.g. the horizon or water surface runs vertically,
  trees/mountains/buildings grow from the left or right edge, gravity points sideways.
  A correct wallpaper is upright: sky at the top, ground at the bottom (abstract art is exempt).
Be practical: stylized art, minimalism and abstract art are fine if they look intentional.
Answer ONLY with JSON: {"ok": true|false, "defects": [..codes..], "comment": "<10 words>"}"""


@dataclass
class QCResult:
    ok: bool
    defects: list[str]
    comment: str = ""
    checked: bool = True   # False — vision-проверка не выполнялась (выключена или недоступна)

    @property
    def label(self) -> str:
        if not self.checked:
            return "— не проверено (" + self.comment[:60] + ")"
        return "✓" if self.ok else "✗ " + ", ".join(self.defects)


def _local_checks(img: Image.Image) -> QCResult | None:
    if img.size != (config.TARGET_W, config.TARGET_H):
        return QCResult(False, ["size"], f"size {img.size}")
    # «пустая» картинка: почти нет вариации яркости
    stat = ImageStat.Stat(img.convert("L").resize((200, 434)))
    if stat.stddev[0] < 6:
        return QCResult(False, ["empty"], "almost uniform image")
    return None


def _to_data_url(img: Image.Image, width: int = 512) -> str:
    small = img.resize((width, round(width * img.height / img.width)), Image.LANCZOS)
    buf = io.BytesIO()
    small.save(buf, "JPEG", quality=85)
    return "data:image/jpeg;base64," + base64.b64encode(buf.getvalue()).decode()


def check(img: Image.Image) -> QCResult:
    local = _local_checks(img)
    if local:
        return local
    if not (config.QC_ENABLED and config.GENAPI_API_KEY):
        return QCResult(True, [], "проверка выключена", checked=False)
    try:
        r = requests.post(
            "https://proxy.gen-api.ru/v1/chat/completions",
            headers={"Authorization": f"Bearer {config.GENAPI_API_KEY}"},
            json={"model": config.QC_MODEL, "max_tokens": 120, "temperature": 0,
                  "messages": [{"role": "user", "content": [
                      {"type": "text", "text": QC_PROMPT},
                      {"type": "image_url", "image_url": {"url": _to_data_url(img), "detail": "low"}},
                  ]}]},
            timeout=60,
        )
        r.raise_for_status()
        text = r.json()["choices"][0]["message"]["content"]
        data = json.loads(re.search(r"\{.*\}", text, re.S).group(0))
        defects = [d for d in data.get("defects", []) if d]
        return QCResult(bool(data.get("ok", not defects)) and not defects, defects, data.get("comment", ""))
    except Exception as e:  # noqa: BLE001 — если проверка недоступна, не блокируем заказ, но честно помечаем
        return QCResult(True, [], f"сервис проверки недоступен: {e}"[:120], checked=False)
