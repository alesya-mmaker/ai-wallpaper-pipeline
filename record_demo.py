"""Запись демо-видео WallGen (Playwright → WebM → ffmpeg → MP4 с таймлапсом ожидания).

Сценарий: открыть приложение → выбрать все темы → вписать свои темы → задать количество →
«Сгенерировать» → (ожидание ускоряется) → «Готово» → открыть картинку в галерее →
открыть папку с обоями на Google Диске.

  python record_demo.py --count 3                 # репетиция
  python record_demo.py --count 100 --out output/demo/wallgen_demo.mp4
"""
from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

import imageio_ffmpeg
import requests
from playwright.sync_api import sync_playwright

sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(__file__).resolve().parent
PORT = 7870
URL = f"http://127.0.0.1:{PORT}"
W, H = 1120, 788          # окно браузера (чуть меньше → в видео крупнее текст)
VW, VH = 1280, 900        # размер итогового видео

# Видимый курсор с подсветкой (в headless-записи системного курсора нет).
# Стрелка + оранжевый ореол; при клике — расходящееся кольцо.
CURSOR_JS = """
(() => {
  const init = () => {
    if (document.getElementById('demo-cursor')) return;
    const st = document.createElement('style');
    st.textContent = `
      #demo-cursor{position:fixed;left:-100px;top:-100px;z-index:2147483647;pointer-events:none;}
      #demo-cursor .halo{position:absolute;left:-26px;top:-26px;width:52px;height:52px;border-radius:50%;
        background:radial-gradient(circle,rgba(255,170,110,.32) 0%,rgba(255,122,69,.18) 55%,rgba(255,122,69,0) 72%);}
      #demo-cursor svg{position:absolute;left:-2px;top:-2px;filter:drop-shadow(1px 2px 2px rgba(0,0,0,.6));}
      .demo-ripple{position:fixed;z-index:2147483646;pointer-events:none;width:20px;height:20px;margin:-10px 0 0 -10px;
        border:3px solid rgba(255,122,69,.95);border-radius:50%;animation:demo-rip .55s ease-out forwards;}
      @keyframes demo-rip{to{transform:scale(4);opacity:0;}}`;
    document.head.appendChild(st);
    const c = document.createElement('div');
    c.id = 'demo-cursor';
    c.innerHTML = '<div class="halo"></div><svg width="22" height="32" viewBox="0 0 22 32">' +
      '<path d="M1 1 L1 26 L7.5 20 L12.5 31 L17 29 L12 18.5 L21 18.5 Z" fill="#fff" stroke="#111" stroke-width="1.5" stroke-linejoin="round"/></svg>';
    document.body.appendChild(c);
    document.addEventListener('mousemove', e => { c.style.left = e.clientX + 'px'; c.style.top = e.clientY + 'px'; }, true);
    document.addEventListener('mousedown', e => {
      const r = document.createElement('div'); r.className = 'demo-ripple';
      r.style.left = e.clientX + 'px'; r.style.top = e.clientY + 'px';
      document.body.appendChild(r); setTimeout(() => r.remove(), 700);
    }, true);
  };
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', init); else init();

  // Подписи этапов: window.demoCaption(номер, заголовок, пояснение)
  window.demoCaption = (n, title, sub) => {
    let box = document.getElementById('demo-caption');
    if (!box) {
      const st = document.createElement('style');
      st.textContent = `
        #demo-caption{position:fixed;right:28px;top:18px;z-index:2147483640;display:flex;align-items:center;gap:16px;
          padding:14px 26px 14px 16px;border-radius:18px;background:rgba(12,13,18,.9);border:1px solid rgba(255,255,255,.14);
          box-shadow:0 10px 30px rgba(0,0,0,.45);font-family:'Segoe UI',Inter,system-ui,sans-serif;
          transition:opacity .35s ease, transform .35s ease;opacity:0;transform:translateY(12px);}
        #demo-caption.show{opacity:1;transform:none;}
        #demo-caption.bottom{top:auto;bottom:28px;}
        #demo-caption .n{width:42px;height:42px;border-radius:50%;background:#ff7a45;color:#140a05;font-weight:800;
          font-size:22px;display:flex;align-items:center;justify-content:center;flex:none;}
        #demo-caption .t{color:#ecedf1;font-size:24px;font-weight:600;line-height:1.15;}
        #demo-caption .s{color:#9a9fb0;font-size:16px;margin-top:3px;}`;
      document.head.appendChild(st);
      box = document.createElement('div'); box.id = 'demo-caption';
      if (location.hostname.includes('google')) box.classList.add('bottom');  // на Диске вверху кнопка «Войти»
      document.body.appendChild(box);
    }
    box.classList.remove('show');
    setTimeout(() => {
      box.innerHTML = `<div class="n">${n}</div><div><div class="t">${title}</div><div class="s">${sub}</div></div>`;
      box.classList.add('show');
    }, box.innerHTML ? 250 : 0);
  };
})();
"""

STEPS = {
    1: ("Выбираем темы", "можно все сразу или по одной"),
    2: ("Добавляем свои темы", "любые, на любом языке"),
    3: ("Указываем количество", "от 1 до 200"),
    4: ("Запускаем", "одна кнопка — дальше всё автоматически"),
    5: ("Идёт генерация", "каждая картинка проверяется и сохраняется на Диск"),
    6: ("Готово", "в случае брака автоконтроль сам перегенерирует картинку"),
    7: ("Результат на Google Диске", "100 обоев + таблица промптов"),
}


def start_app() -> subprocess.Popen:
    env = {**os.environ, "NO_BROWSER": "1", "PORT": str(PORT), "PYTHONIOENCODING": "utf-8"}
    proc = subprocess.Popen([sys.executable, "app.py"], cwd=ROOT, env=env,
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    for _ in range(60):
        try:
            if requests.get(URL, timeout=2).ok:
                return proc
        except requests.RequestException:
            pass
        time.sleep(1)
    proc.kill()
    raise RuntimeError("приложение не запустилось")


def record(count: int, custom: list[str], out: Path) -> None:
    tmp = ROOT / "output" / "demo" / "_raw"
    shutil.rmtree(tmp, ignore_errors=True)
    tmp.mkdir(parents=True)
    marks: dict[str, float] = {}

    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        ctx = browser.new_context(viewport={"width": W, "height": H}, device_scale_factor=1,
                                  # пишем в размере окна (иначе Playwright добавляет серые поля),
                                  # до VW×VH увеличивает ffmpeg
                                  record_video_dir=str(tmp), record_video_size={"width": W, "height": H},
                                  locale="ru-RU")
        ctx.add_init_script(CURSOR_JS)
        t0 = time.monotonic()
        page = ctx.new_page()
        mark = lambda k: marks.__setitem__(k, time.monotonic() - t0)  # noqa: E731

        def caption(n, hold=1.4):
            title, sub = STEPS[n]
            if n == 7:
                sub = f"{count} обоев + таблица промптов"
            page.evaluate("([n, t, s]) => window.demoCaption(n, t, s)", [n, title, sub])
            page.wait_for_timeout(int(hold * 1000))

        def move_click(locator, pause=0.6) -> bool:
            """Плавно подвести курсор и кликнуть. Невидимый/отсутствующий элемент — пропуск, без падения."""
            try:
                if not locator.count() or not locator.first.is_visible():
                    return False
                locator = locator.first
                locator.scroll_into_view_if_needed(timeout=5000)
                b = locator.bounding_box()
            except Exception:  # noqa: BLE001
                return False
            if not b:
                return False
            page.mouse.move(b["x"] + b["width"] / 2, b["y"] + b["height"] / 2, steps=30)
            page.wait_for_timeout(250)
            page.mouse.down(); page.mouse.up()
            page.wait_for_timeout(int(pause * 1000))
            return True

        try:
            scenario(page, ctx, caption, move_click, mark, count, custom)
        except Exception as e:  # noqa: BLE001 — запись всё равно сохраняем
            print(f"[запись] сценарий прерван: {e}")
        finally:
            mark("end")
            video = page.video.path()
            ctx.close()      # только после закрытия контекста видео дописывается на диск
            browser.close()

    print("Метки, с:", {k: round(v, 1) for k, v in marks.items()})
    make_mp4(Path(video), out, marks)


def scenario(page, ctx, caption, move_click, mark, count: int, custom: list[str]) -> None:
    """Сценарий демо. Любое исключение здесь не теряет запись — её дописывает record()."""
    if True:  # единый блок сценария
        page.goto(URL)
        page.wait_for_selector("#ws-run")
        page.mouse.move(W / 2, 120)
        page.wait_for_timeout(1800)

        # 1. темы
        caption(1, 1.0)
        move_click(page.locator("#ws-none"), 0.5)
        move_click(page.locator("#ws-all"), 1.0)
        # 2. свои темы
        if custom:
            caption(2, 0.8)
            move_click(page.locator("textarea"), 0.3)
            for i, theme in enumerate(custom):   # одна тема — одна строка
                if i:
                    page.keyboard.press("Enter")
                page.keyboard.type(theme, delay=55)
            page.wait_for_timeout(700)
        # 3. количество
        caption(3, 0.8)
        num = page.locator("input[type=number]").first
        move_click(num, 0.2)
        num.fill(str(count))
        num.press("Enter")
        page.wait_for_timeout(900)
        # 4. запуск
        caption(4, 1.2)
        move_click(page.locator("#ws-run"), 0.3)
        caption(5, 0.2)
        mark("gen_start")
        page.mouse.move(W - 60, H - 60, steps=20)
        page.wait_for_timeout(2500)
        page.mouse.wheel(0, 500)  # прокрутить к прогрессу
        # ждём «Готово:» ИЛИ сообщение об ошибке «⚠️», чтобы не висеть час при сбое
        page.locator("text=Готово:").or_(page.locator("text=⚠️")).first.wait_for(timeout=60 * 60 * 1000)
        mark("gen_done")
        page.wait_for_timeout(500)
        if not page.locator("text=Готово:").count():
            print("[запись] заказ завершился ошибкой — заканчиваю запись на сообщении")
            page.wait_for_timeout(4000)
            return
        caption(6, 1.0)
        page.mouse.wheel(0, 700)
        page.wait_for_timeout(1800)

        # 5. открыть картинку в галерее
        if move_click(page.locator("#ws-gallery .thumbnail-item"), 2.5):
            page.keyboard.press("Escape")
            page.wait_for_timeout(800)

        # 6. папка с обоями (кнопка есть, только если заказ загружен на Диск)
        btn = page.locator("#ws-open")
        page.mouse.wheel(0, -400)
        page.wait_for_timeout(600)
        if not (btn.count() and btn.first.is_visible()):
            print("[запись] кнопки «Открыть все обои» нет — пропускаю шаг с Диском")
            page.wait_for_timeout(3000)
            return
        link = page.evaluate("""() => { const b = document.querySelector('#ws-open');
            const a = b && (b.closest('a') || b.querySelector('a')); return a ? a.href : null; }""")
        if not link:
            with page.expect_popup() as pop:
                move_click(btn, 0.2)
            link = pop.value.url
            pop.value.close()
        else:
            move_click(btn, 0.2)
            for p in ctx.pages[1:]:
                p.close()
        if link:
            page.goto(link)
            page.wait_for_timeout(4500)
            # закрыть промо-окно Диска и включить вид «Сетка» с превью
            close = page.locator('[aria-label="Закрыть"]')
            for i in range(close.count()):
                if close.nth(i).is_visible():
                    move_click(close.nth(i), 0.5)
                    break
            grid = page.locator('[aria-label="Сетка"]')
            if grid.count() and grid.first.is_visible():
                move_click(grid.first, 0.3)
            page.mouse.move(W / 2, H - 80, steps=20)
            caption(7, 3.0)
            for _ in range(4):
                page.mouse.wheel(0, 350)
                page.wait_for_timeout(900)
            page.wait_for_timeout(2000)


def make_mp4(src: Path, out: Path, m: dict[str, float], timelapse_sec: float = 16.0) -> None:
    """Начало и конец — в реальном времени, ожидание генерации — ускоренный таймлапс."""
    ff = imageio_ffmpeg.get_ffmpeg_exe()
    out.parent.mkdir(parents=True, exist_ok=True)
    if "gen_start" not in m:  # сценарий прервался до запуска — просто конвертируем
        subprocess.run([ff, "-y", "-loglevel", "error", "-i", str(src),
                        "-vf", f"scale={VW}:{VH}:flags=lanczos,fps=30,format=yuv420p",
                        "-c:v", "libx264", "-crf", "20", "-movflags", "+faststart", str(out)], check=True)
        print(f"Видео (без таймлапса): {out}")
        return
    m.setdefault("gen_done", m["end"])
    a = m["gen_start"] + 4           # первые секунды прогресса — вживую
    b = max(a + 1, m["gen_done"] - 1.5)
    speed = max(1.0, (b - a) / timelapse_sec)
    fc = (f"[0:v]trim=0:{a:.2f},setpts=PTS-STARTPTS[v1];"
          f"[0:v]trim={a:.2f}:{b:.2f},setpts=(PTS-STARTPTS)/{speed:.3f}[v2];"
          f"[0:v]trim={b:.2f},setpts=PTS-STARTPTS[v3];"
          f"[v1][v2][v3]concat=n=3:v=1:a=0,scale={VW}:{VH}:flags=lanczos,fps=30,format=yuv420p[v]")
    subprocess.run([ff, "-y", "-loglevel", "error", "-i", str(src), "-filter_complex", fc, "-map", "[v]",
                    "-c:v", "libx264", "-crf", "20", "-preset", "medium", "-movflags", "+faststart", str(out)],
                   check=True)
    print(f"Видео: {out}  (ожидание {b - a:.0f} с ускорено в {speed:.0f}×)")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--count", type=int, default=3)
    ap.add_argument("--custom", nargs="*", default=["японские храмы осенью", "ретро-автомобили на закате"])
    ap.add_argument("--out", default="output/demo/wallgen_demo_test.mp4")
    a = ap.parse_args()
    app = start_app()
    try:
        record(a.count, a.custom, ROOT / a.out)
    finally:
        app.kill()
