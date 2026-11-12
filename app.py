"""Веб-интерфейс генератора обоев (Gradio).

Запуск: start.bat  или  .venv\\Scripts\\python app.py
Откроется страница в браузере: выбрать темы → количество → «Сгенерировать».
"""
from __future__ import annotations

import os
import queue
import random
import re
import sys
import threading
import time

import gradio as gr

from wallgen import config
from wallgen.pipeline import run_order
from wallgen.themes import THEMES

sys.stdout.reconfigure(encoding="utf-8")

APP_NAME = config.APP_NAME

ICONS = {
    "space": "🌌", "mountains": "⛰️", "ocean": "🌊", "forest": "🌲", "cyberpunk": "🌃",
    "city": "🏙️", "anime": "🌸", "fantasy": "🐉", "abstract": "🌀", "minimal": "◐",
    "animals": "🦊", "flowers": "🌷", "sky": "⛈️", "desert": "🏜️", "winter": "❄️",
    "scifi": "🚀", "retro": "🌴", "cozy": "☕", "japan": "⛩️", "underwater": "🐠",
}
THEME_CHOICES = [(f"{ICONS.get(k, '•')} {t['name']}", k) for k, t in THEMES.items()]
DEFAULT_THEMES = ["space", "mountains", "anime", "cyberpunk", "fantasy"]


# ---------------------------------------------------------------------------
# Вспомогательное
# ---------------------------------------------------------------------------
def parse_custom(text: str) -> list[str]:
    """Одна тема — одна строка (или через «;»). Запятые остаются внутри темы:
    «японские храмы, осень» — это одна тема, а не две."""
    return [p.strip() for p in re.split(r"[\n;]+", text or "") if p.strip()]


def fmt_time(sec: float) -> str:
    sec = int(max(sec, 0))
    return f"{sec // 60} мин {sec % 60:02d} с" if sec >= 60 else f"{sec} с"


def progress_html(done: int, total: int, note: str = "") -> str:
    pct = 0 if not total else round(100 * done / total)
    return (f'<div class="ws-progress"><div class="ws-bar"><div class="ws-fill" style="width:{pct}%"></div></div>'
            f'<div class="ws-progress-text"><b>{done}</b> / {total}<span>{note}</span></div></div>')


def button_label(count: int) -> str:
    return f"✦  Сгенерировать обои · {int(count)} шт."


# ---------------------------------------------------------------------------
# Запуск заказа: конвейер работает в фоне, интерфейс обновляется по событиям
# ---------------------------------------------------------------------------
def generate(themes: list[str], custom_text: str, count: float):
    count = int(count)
    custom = parse_custom(custom_text)
    hidden = gr.update(visible=False)
    if not themes and not custom:
        yield (gr.update(value="", visible=False), "⚠️ Выберите хотя бы одну тему или впишите свою.",
               gr.update(value=None, visible=False), hidden, gr.update(interactive=True))
        return

    events: queue.Queue = queue.Queue()

    def on_progress(msg, item=None):
        events.put(("item" if item else "msg", msg, item))

    def worker():
        try:
            events.put(("done", run_order(themes, custom, count, on_progress=on_progress), None))
        except Exception as e:  # noqa: BLE001
            events.put(("error", str(e), None))

    threading.Thread(target=worker, daemon=True).start()
    t0, done, failed = time.time(), 0, 0
    yield (gr.update(value=progress_html(0, count, " · подготовка…"), visible=True),
           "Готовлю заказ: подбираю сюжеты и стили…",
           gr.update(value=None, visible=False), hidden, gr.update(interactive=False, value="Генерация…"))

    while True:
        kind, msg, item = events.get()
        if kind == "item":
            done += 1
            elapsed = time.time() - t0
            left = elapsed / done * (count - done)
            note = f" · осталось ~{fmt_time(left)}" if done < count else ""
            yield (gr.update(value=progress_html(done, count, note)), "Генерирую обои…",
                   gr.update(), hidden, gr.update())
        elif kind == "msg":
            if msg.startswith("[ошибка]"):
                failed += 1
            if msg.startswith("Генерация"):
                yield (gr.update(), "Генерирую обои…", gr.update(), hidden, gr.update())
        elif kind == "done":
            r = msg
            ok = len(r.done)
            pool = [it for it in r.done if it.get("qc_ok")] or r.done
            picks = random.sample(pool, min(8, len(pool))) if pool else []
            gallery = [(it["path"], None) for it in sorted(picks, key=lambda x: x["idx"])]
            if r.fatal or not ok:
                summary = f"### ⚠️ Остановлено: сделано {ok} из {count} шт."
            else:
                summary = f"### ✓ Готово: {ok} шт. за {fmt_time(r.seconds)}"
            if r.fatal:
                summary += (f"\n\n⚠️ Генерация остановлена: сервис отказал в доступе "
                            f"(проверьте баланс или ключ). Не сделано: {len(r.failed)} шт.")
            elif r.failed:
                summary += f"\n\nНе удалось даже после повторов: {len(r.failed)} шт."
            for w in r.warnings:
                summary += f"\n\n⚠️ {w[0].upper() + w[1:]}"
            link = r.folder_link or str(r.local_dir)
            yield (gr.update(value=progress_html(ok, count, " · готово")), summary,
                   gr.update(value=gallery, visible=bool(gallery)),
                   gr.update(visible=bool(r.folder_link), link=link),
                   gr.update(interactive=True, value=button_label(count)))
            return
        elif kind == "error":
            yield (gr.update(), f"⚠️ Не получилось запустить генерацию: {msg}",
                   gr.update(), hidden, gr.update(interactive=True, value=button_label(count)))
            return


# ---------------------------------------------------------------------------
# Внешний вид
# ---------------------------------------------------------------------------
ACCENT = "#ff7a45"
CSS = f"""
:root, .dark {{
  --ws-bg: #0b0c10; --ws-surface: #14161c; --ws-surface-2: #1b1e26; --ws-border: #262a34;
  --ws-text: #ecedf1; --ws-muted: #8b90a0; --ws-accent: {ACCENT};
}}
html, body, gradio-app, .gradio-container, .main, .wrap.app {{ background: var(--ws-bg) !important; color: var(--ws-text); }}
.ws-links {{ align-items: center !important; }}
.html-container {{ padding-left: 0 !important; padding-right: 0 !important; }}
#ws-none {{ padding-right: 0 !important; }}
.ws-links .ws-label {{ margin: 0 !important; }}
#ws-all, #ws-none {{ flex: 0 0 auto !important; min-width: max-content !important; width: auto !important;
                     white-space: nowrap !important; }}
.gradio-container {{ max-width: 980px !important; margin: 0 auto !important; padding: 24px 16px 48px !important; }}
footer {{ display: none !important; }}

.ws-header {{ display:flex; align-items:baseline; gap:12px; margin: 8px 0 20px; }}
.ws-header h1 {{ font-size: 28px; font-weight: 800; letter-spacing: -0.02em; margin:0; }}
.ws-header h1 span {{ color: var(--ws-accent); }}
.ws-header p {{ color: var(--ws-muted); margin:0; font-size: 14px; }}

.ws-card {{ background: var(--ws-surface) !important; border: 1px solid var(--ws-border) !important;
            border-radius: 16px !important; padding: 20px !important; }}
.ws-label {{ font-size: 13px; text-transform: uppercase; letter-spacing: .08em; color: var(--ws-muted);
             margin: 0 0 10px; font-weight: 600; }}

/* темы-плитки */
#ws-themes .wrap {{ gap: 8px !important; }}
#ws-themes label {{ background: var(--ws-surface-2) !important; border: 1px solid var(--ws-border) !important;
   border-radius: 999px !important; padding: 8px 14px !important; cursor: pointer; transition: all .15s;
   color: var(--ws-text) !important; font-size: 14px !important; }}
#ws-themes label:hover {{ border-color: var(--ws-accent) !important; }}
#ws-themes label.selected, #ws-themes label:has(input:checked) {{ background: color-mix(in srgb, var(--ws-accent) 18%, var(--ws-surface-2)) !important;
   border-color: var(--ws-accent) !important; }}
#ws-themes input[type=checkbox] {{ display: none !important; }}
.ws-links button {{ background: none !important; border: none !important; color: var(--ws-muted) !important;
   padding: 2px 6px !important; min-width: 0 !important; font-size: 13px !important; box-shadow:none !important; }}
.ws-links button:hover {{ color: var(--ws-accent) !important; }}

textarea, input[type=number] {{ background: var(--ws-surface-2) !important; border-color: var(--ws-border) !important; }}
input[type=range] {{ accent-color: var(--ws-accent); }}

#ws-run {{ background: var(--ws-accent) !important; color: #140a05 !important; font-weight: 800 !important;
   font-size: 17px !important; border: none !important; border-radius: 14px !important; padding: 16px !important;
   box-shadow: 0 8px 30px color-mix(in srgb, var(--ws-accent) 35%, transparent) !important; }}
#ws-run:hover {{ filter: brightness(1.08); }}
#ws-run:disabled {{ opacity: .6; }}

.ws-progress {{ margin: 6px 0 2px; }}
.ws-bar {{ height: 10px; background: var(--ws-surface-2); border-radius: 999px; overflow: hidden;
           border: 1px solid var(--ws-border); }}
.ws-fill {{ height: 100%; background: var(--ws-accent); border-radius: 999px; transition: width .4s ease; }}
.ws-progress-text {{ margin-top: 8px; font-size: 15px; color: var(--ws-text); }}
.ws-progress-text span {{ color: var(--ws-muted); }}

#ws-open {{ background: var(--ws-surface-2) !important; border: 1px solid var(--ws-accent) !important;
   color: var(--ws-text) !important; border-radius: 12px !important; font-weight: 600 !important; }}
#ws-gallery, #ws-gallery .wrap, #ws-gallery .gallery-container {{ background: transparent !important;
   border: none !important; height: auto !important; max-height: none !important; }}
#ws-gallery .grid-wrap {{ height: auto !important; max-height: none !important; overflow: visible !important; }}
#ws-gallery .gallery-item {{ height: auto !important; }}
#ws-gallery .thumbnail-item {{ aspect-ratio: 1870 / 4063 !important; height: auto !important;
   border-radius: 14px !important; border: 1px solid var(--ws-border) !important; }}
#ws-gallery .thumbnail-item img {{ object-fit: cover !important; width: 100% !important; height: 100% !important; }}
"""

THEME = gr.themes.Base(
    primary_hue=gr.themes.colors.orange, neutral_hue=gr.themes.colors.zinc,
    font=[gr.themes.GoogleFont("Inter"), "Segoe UI", "system-ui", "sans-serif"],
)
FORCE_DARK = "() => { document.body.classList.add('dark'); }"


with gr.Blocks(title=APP_NAME) as demo:
    # «WallGen» → «Wall» + акцентное «Gen»; любое другое имя — целиком
    head = (f'{APP_NAME[:-3]}<span>{APP_NAME[-3:]}</span>' if APP_NAME.endswith("Gen") else APP_NAME)
    gr.HTML(f'<div class="ws-header"><h1>{head}</h1><p>обои для телефона одной кнопкой</p></div>')

    with gr.Column(elem_classes="ws-card"):
        with gr.Row(elem_classes="ws-links", equal_height=True):
            gr.HTML('<div class="ws-label">Темы</div>')
            all_btn = gr.Button("выбрать все", size="sm", scale=0, elem_id="ws-all")
            none_btn = gr.Button("сбросить", size="sm", scale=0, elem_id="ws-none")
        themes = gr.CheckboxGroup(choices=THEME_CHOICES, value=DEFAULT_THEMES, show_label=False,
                                  elem_id="ws-themes", container=False)
        gr.HTML('<div class="ws-label" style="margin-top:18px">Свои темы</div>')
        custom = gr.Textbox(show_label=False, container=False, lines=3,
                            placeholder="по одной теме на строку, например:\nяпонские храмы осенью\nретро-автомобили на закате")
        gr.HTML('<div class="ws-label" style="margin-top:18px">Количество</div>')
        count = gr.Slider(1, 200, value=100, step=1, show_label=False, container=False)

    run = gr.Button(button_label(100), elem_id="ws-run")

    progress = gr.HTML(visible=False)
    status = gr.Markdown()
    open_btn = gr.Button("Открыть все обои", elem_id="ws-open", visible=False)
    gallery = gr.Gallery(visible=False, columns=4, height="auto", object_fit="cover",
                         show_label=False, elem_id="ws-gallery", allow_preview=True)

    all_btn.click(lambda: [k for _, k in THEME_CHOICES], outputs=themes)
    none_btn.click(lambda: [], outputs=themes)
    count.change(lambda c: gr.update(value=button_label(c)), inputs=count, outputs=run)
    run.click(generate, inputs=[themes, custom, count],
              outputs=[progress, status, gallery, open_btn, run], show_progress="hidden")


if __name__ == "__main__":
    demo.queue().launch(
        theme=THEME, css=CSS, js=FORCE_DARK, inbrowser=not os.environ.get("NO_BROWSER"),
        server_port=int(os.environ.get("PORT", "7860")),
        allowed_paths=[str(config.OUTPUT_DIR)], favicon_path=None,
    )
