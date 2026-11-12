"""Генератор промптов: план заказа из N уникальных и разнообразных промптов.

Разнообразие обеспечивается «колодами»: по каждой оси (сюжет темы, стиль, композиция,
палитра, свет, атмосфера, модель) значения перемешиваются и раздаются по очереди,
колода пополняется только когда закончилась. Поэтому значения распределяются равномерно
и подряд почти не повторяются.
"""
from __future__ import annotations

import json
import random
import re
from dataclasses import asdict, dataclass

import requests

from . import config
from .themes import (ALL_STYLES, COMPOSITIONS, LIGHTING, MOODS, PALETTES, THEMES,
                     WALLPAPER_SUFFIX)


@dataclass
class PromptSpec:
    idx: int
    theme_key: str
    theme_name: str
    subject: str
    style: str
    composition: str
    palette: str
    lighting: str
    mood: str
    seed: int
    prompt: str = ""
    model: str = ""      # заполняет конвейер: какой провайдер/модель сгенерировали

    def to_dict(self) -> dict:
        return asdict(self)


class Deck:
    """Перемешанная колода значений, пополняется после исчерпания."""

    def __init__(self, items: list, rng: random.Random):
        self.items, self.rng, self.pile = list(items), rng, []

    def draw(self):
        if not self.pile:
            self.pile = self.items[:]
            self.rng.shuffle(self.pile)
        return self.pile.pop()


def build_prompt(s: PromptSpec) -> str:
    return (f"{s.subject}. {s.style}. {s.composition}. {s.palette}, {s.lighting}. "
            f"{s.mood} atmosphere. {WALLPAPER_SUFFIX}")


# --------------------------------------------------------------------------
# Пользовательские темы → сюжеты через LLM (Cloudflare, бесплатно)
# --------------------------------------------------------------------------
def expand_custom_theme(theme: str, n: int = 12) -> list[str]:
    """Раскрыть свою тему (на любом языке) в n разных сюжетов на английском.
    Если LLM недоступна — вернуть саму тему как единственный сюжет."""
    sys_msg = (
        "You write subjects for AI-generated phone wallpapers. Given a theme, return a JSON array "
        f"of {n} short, visually distinct scene descriptions in English (8-16 words each). "
        "Vary the scale, objects and point of view, but every description must keep the theme's "
        "key context (place, season, weather, era) clearly recognizable. Describe only what is visible. "
        "No style, color or lighting words. No text in images. Output only the JSON array."
    )
    messages = [{"role": "system", "content": sys_msg}, {"role": "user", "content": f"Theme: {theme}"}]
    for name, call in _llm_backends():
        try:
            text = call(messages)
            m = re.search(r"\[.*\]", text, re.S)
            items = [str(x).strip() for x in json.loads(m.group(0)) if str(x).strip()]
            if items:
                return items[:n]
        except Exception as e:  # noqa: BLE001
            print(f"[prompts] LLM {name} недоступна для темы «{theme}»: {e}")
    return [theme]


def _llm_backends():
    """LLM по приоритету: gen-api (OpenAI-формат, копейки) → Cloudflare (бесплатно, общая квота)."""
    if config.GENAPI_API_KEY:
        def genapi(messages):
            r = requests.post("https://proxy.gen-api.ru/v1/chat/completions",
                              headers={"Authorization": f"Bearer {config.GENAPI_API_KEY}"},
                              json={"model": config.GENAPI_TEXT_MODEL, "messages": messages,
                                    "max_tokens": 1200, "temperature": 0.9}, timeout=90)
            r.raise_for_status()
            return r.json()["choices"][0]["message"]["content"]
        yield "gen-api", genapi
    if config.CF_ACCOUNT_ID and config.CF_API_TOKEN:
        def cloudflare(messages):
            r = requests.post(
                f"https://api.cloudflare.com/client/v4/accounts/{config.CF_ACCOUNT_ID}/ai/run/{config.CF_TEXT_MODEL}",
                headers={"Authorization": f"Bearer {config.CF_API_TOKEN}"},
                json={"messages": messages, "max_tokens": 1200, "temperature": 0.9}, timeout=90)
            r.raise_for_status()
            text = r.json()["result"]["response"]
            return text if isinstance(text, str) else json.dumps(text)
        yield "cloudflare", cloudflare


# --------------------------------------------------------------------------
# План заказа
# --------------------------------------------------------------------------
def plan_order(theme_keys: list[str], custom_themes: list[str], count: int,
               seed: int | None = None) -> list[PromptSpec]:
    rng = random.Random(seed)

    # источники тем: (ключ, название, сюжеты, стили, свет)
    sources: list[tuple[str, str, list[str], list[str], list[str]]] = []
    for k in theme_keys:
        t = THEMES[k]
        sources.append((k, t["name"], t["subjects"], t.get("styles", ALL_STYLES),
                        t.get("lighting", LIGHTING)))
    for i, ct in enumerate(c.strip() for c in custom_themes if c.strip()):
        sources.append((f"custom{i + 1}", ct, expand_custom_theme(ct), ALL_STYLES, LIGHTING))
    if not sources:
        raise ValueError("Не выбрано ни одной темы")

    # равное распределение количества по темам
    per_theme = [count // len(sources)] * len(sources)
    for i in range(count % len(sources)):
        per_theme[i] += 1

    decks = {
        "composition": Deck(COMPOSITIONS, rng), "palette": Deck(PALETTES, rng),
        "mood": Deck(MOODS, rng),
    }
    shared_light = Deck(LIGHTING, rng)
    specs: list[PromptSpec] = []
    for (key, name, subjects, styles, lights), n in zip(sources, per_theme):
        subj_deck, style_deck = Deck(subjects, rng), Deck(styles, rng)
        light_deck = shared_light if lights is LIGHTING else Deck(lights, rng)
        for _ in range(n):
            s = PromptSpec(
                idx=0, theme_key=key, theme_name=name,
                subject=subj_deck.draw(), style=style_deck.draw(),
                composition=decks["composition"].draw(), palette=decks["palette"].draw(),
                lighting=light_deck.draw(), mood=decks["mood"].draw(),
                seed=rng.randrange(1, 2**31),
            )
            s.prompt = build_prompt(s)
            specs.append(s)

    rng.shuffle(specs)  # перемешиваем темы, чтобы галерея была разнообразной
    for i, s in enumerate(specs, 1):
        s.idx = i
    return specs
