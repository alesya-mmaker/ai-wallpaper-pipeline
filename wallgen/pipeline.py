"""Конвейер заказа: план промптов → параллельная генерация → постобработка → Drive + реестр.

Используется и из CLI, и из веб-интерфейса (через callback on_progress).
"""
from __future__ import annotations

import csv
import json
import random
import re
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Callable

from . import config
from .postprocess import fit_to_target, save_jpeg
from .prompts import PromptSpec, plan_order
from .providers import ProviderError, get_provider
from .qc import check

REGISTRY_HEADER = ["#", "Файл", "Тема", "Промпт", "Сюжет", "Стиль", "Композиция", "Палитра",
                   "Свет", "Настроение", "Seed", "Модель", "Постобработка", "Контроль качества",
                   "Время, с", "Ссылка"]
MAX_RETRY_AFTER = 60  # не ждём «повторите через N с» дольше минуты


def _row(it: dict) -> list:
    return [it["idx"], it["file"], it["theme_name"], it["prompt"], it["subject"], it["style"],
            it["composition"], it["palette"], it["lighting"], it["mood"], it["seed"], it["model"],
            it["post"], it["qc"], it["seconds"], it["link"]]


@dataclass
class OrderResult:
    order_name: str
    local_dir: Path
    folder_link: str = ""
    sheet_link: str = ""
    done: list[dict] = field(default_factory=list)
    failed: list[dict] = field(default_factory=list)
    seconds: float = 0.0
    regenerated: int = 0
    fatal: str = ""                                     # причина остановки всего заказа (нет денег/доступа)
    warnings: list[str] = field(default_factory=list)   # некритичные проблемы (доступ, таблица, загрузка)


_TRANSLIT = str.maketrans({c: t for c, t in zip(
    "абвгдеёжзийклмнопрстуфхцчшщъыьэюя",
    ["a", "b", "v", "g", "d", "e", "e", "zh", "z", "i", "y", "k", "l", "m", "n", "o", "p", "r", "s",
     "t", "u", "f", "h", "ts", "ch", "sh", "sch", "", "y", "", "e", "yu", "ya"])})


def _slug(s: str, n: int = 24) -> str:
    s = re.sub(r"[^a-zA-Z0-9]+", "-", s.lower().translate(_TRANSLIT)).strip("-")
    return s[:n].strip("-") or "img"


def _unique_local_dir(stamp: str) -> Path:
    d, n = config.OUTPUT_DIR / stamp, 2
    while d.exists():
        d, n = config.OUTPUT_DIR / f"{stamp}_{n}", n + 1
    d.mkdir(parents=True)
    return d


def run_order(theme_keys: list[str], custom_themes: list[str], count: int,
              provider_spec: str | None = None, upload: bool = True,
              on_progress: Callable[[str, dict | None], None] | None = None) -> OrderResult:
    t0 = time.time()
    log = on_progress or (lambda msg, item=None: print(msg))
    provider = get_provider(provider_spec or config.PROVIDER)

    now = datetime.now()
    base_name = f"{now:%Y-%m-%d %H-%M} · {count} обоев"
    local_dir = _unique_local_dir(now.strftime("%Y-%m-%d_%H-%M-%S"))
    res = OrderResult(base_name, local_dir)

    log(f"Планирую {count} шт…")
    specs = plan_order(theme_keys, custom_themes, count)
    (local_dir / "prompts.json").write_text(
        json.dumps([s.to_dict() for s in specs], ensure_ascii=False, indent=2), encoding="utf-8")

    drive = folder_id = sheet_id = None
    sheet_lock = threading.Lock()
    pending_rows: list[list] = []          # строки реестра пишем пачками (лимит Sheets ~60 записей/мин)
    local = threading.local()              # клиент Google API не потокобезопасен → свой в каждом потоке

    def thread_drive():
        if not hasattr(local, "drive"):
            from .gdrive import Drive as _Drive
            local.drive = _Drive(creds=drive.creds)   # общие учётные данные, без повторного чтения token.json
        return local.drive

    def flush_rows(force: bool = False) -> bool:
        """Записать накопленные строки. Сеть — вне блокировки, чтобы не тормозить потоки.
        При сбое строки возвращаются в очередь и уйдут со следующей записью."""
        with sheet_lock:
            if not pending_rows or (not force and len(pending_rows) < 10):
                return True
            batch = sorted(pending_rows, key=lambda r: r[0])
            pending_rows.clear()
        for attempt in range(3 if force else 1):
            try:
                thread_drive().append_rows(sheet_id, batch)
                return True
            except Exception as e:  # noqa: BLE001
                log(f"[таблица] запись не удалась, повторю позже: {e}", None)
                if force:
                    time.sleep(3 * (attempt + 1))
        with sheet_lock:
            pending_rows.extend(batch)
        return False

    if upload:
        from .gdrive import Drive
        drive = Drive()
        root = drive.ensure_folder(config.DRIVE_ROOT_FOLDER)
        # у каждого заказа своя папка: при совпадении имени добавляем (2), (3)…
        order_name, n = base_name, 2
        while drive.find_folder(order_name, root):
            order_name, n = f"{base_name} ({n})", n + 1
        res.order_name = order_name
        folder_id = drive.create_folder(order_name, root)
        if config.SHARE_ORDER_FOLDER:
            try:
                drive.share_anyone_reader(folder_id)
            except Exception as e:  # noqa: BLE001 — без публичной ссылки заказ всё равно выполняем
                res.warnings.append("не удалось открыть доступ по ссылке к папке — откройте вручную")
                log(f"[доступ] {e}", None)
        sheet_id = drive.create_sheet(f"Промпты — {order_name}", folder_id, REGISTRY_HEADER)
        res.folder_link, res.sheet_link = drive.folder_link(folder_id), drive.sheet_link(sheet_id)
        log(f"Папка заказа на Google Диске: {res.folder_link}")

    log(f"Генерация: {provider.label}, до {config.GEN_CONCURRENCY} одновременно")
    stop = threading.Event()  # остановка при фатальной ошибке (нет денег/квоты)

    def generate_once(s: PromptSpec):
        """Сгенерировать картинку.
        Временные сбои (сеть, таймаут, 429 «слишком много запросов», 5xx) — до 6 попыток с растущей
        паузой 4→8→16→32→60 с (+случайный разброс, чтобы потоки не били в сервис одновременно);
        «повторите через N с» — ждём N, но не больше минуты. «Нет денег/доступа» — стоп всего заказа."""
        attempts = 6
        for attempt in range(attempts):
            if stop.is_set():
                raise ProviderError("остановлено: " + res.fatal, retryable=False)
            try:
                return provider.generate(s.prompt, s.seed)
            except ProviderError as e:
                if not e.retryable:
                    res.fatal = res.fatal or str(e)
                    stop.set()
                    raise
                err = e
            except Exception as e:  # noqa: BLE001 — непредвиденное считаем временным
                err = ProviderError(str(e))
            if attempt == attempts - 1:
                raise err
            backoff = min(60, 4 * 2 ** attempt)
            wait = min(err.retry_after, MAX_RETRY_AFTER) if err.retry_after else backoff
            time.sleep(wait + random.uniform(0, 2))

    def upload_item(item: dict) -> bool:
        """Загрузить файл на Диск. Идемпотентно: если прошлая попытка на самом деле дошла
        (ответ потерялся), берём уже загруженный файл, а не создаём дубль."""
        path = Path(item["path"])
        for attempt in range(3):
            try:
                f = thread_drive().upload(path, folder_id, description=(
                    f"PROMPT: {item['prompt']}\n\nTheme: {item['theme_name']}\n"
                    f"Model: {item['model']}\nSeed: {item['seed']}"))
                item["link"] = f.get("webViewLink", "")
                return True
            except Exception:  # noqa: BLE001
                time.sleep(2 * (attempt + 1))
                try:
                    existing = thread_drive().find_file(path.name, folder_id)
                    if existing:
                        item["link"] = existing.get("webViewLink", "")
                        return True
                except Exception:  # noqa: BLE001
                    pass
        return False

    def work(s: PromptSpec) -> dict:
        ts = time.time()
        s.model = provider.label
        rng = random.Random(s.seed)
        rejected: list[str] = []
        # генерация → постобработка → автоконтроль; брак перегенерируем с новым seed
        for attempt in range(1 + config.QC_MAX_RETRIES):
            raw = generate_once(s)
            img, post = fit_to_target(raw)
            qc = check(img)
            if qc.ok:
                break
            rejected.append(f"seed {s.seed}: {', '.join(qc.defects)}")
            if attempt < config.QC_MAX_RETRIES:
                s.seed = rng.randrange(1, 2**31)
        qc_label = qc.label + (f" (перегенерировано {len(rejected)}: {'; '.join(rejected)})"
                               if rejected and qc.ok else "")

        fname = f"{s.idx:03d}_{s.theme_key}_{_slug(s.subject, 28)}.jpg"
        path = local_dir / fname
        save_jpeg(img, path, s.prompt, meta=f"theme={s.theme_name}; model={s.model}; seed={s.seed}")
        item = {**s.to_dict(), "file": fname, "path": str(path), "post": post, "qc": qc_label,
                "qc_ok": qc.ok, "regenerated": len(rejected) if qc.ok else len(rejected) - 1,
                "raw_size": f"{raw.width}x{raw.height}", "seconds": round(time.time() - ts, 1),
                "link": "", "uploaded": not drive}
        # сбой загрузки НЕ делает картинку неудачной (она уже оплачена и сохранена) —
        # такие догружаем отдельно в конце, без повторной генерации
        if drive and upload_item(item):
            item["uploaded"] = True
            with sheet_lock:
                pending_rows.append(_row(item))
            flush_rows()
        return item

    def run_batch(batch: list[PromptSpec], workers: int) -> list[PromptSpec]:
        """Обработать пачку; вернуть то, что не получилось сгенерировать."""
        failed: list[PromptSpec] = []
        with ThreadPoolExecutor(max_workers=workers) as pool:
            futures = {pool.submit(work, s): s for s in batch}
            for fut in as_completed(futures):
                s = futures[fut]
                try:
                    item = fut.result()
                    res.done.append(item)
                    log(f"[{len(res.done)}/{count}] {item['file']} ({item['seconds']} с)", item)
                except Exception as e:  # noqa: BLE001
                    failed.append(s)
                    s._error = str(e)  # type: ignore[attr-defined]
                    log(f"[ошибка] #{s.idx} {s.theme_name}: {e}", None)
        return failed

    failed = run_batch(specs, config.GEN_CONCURRENCY)
    # добор: то, что не удалось из-за временных сбоев, пробуем ещё раз меньшим числом потоков,
    # чтобы в папке было ровно столько обоев, сколько заказано
    if failed and not stop.is_set():
        log(f"Добор: повторяю {len(failed)} шт.", None)
        time.sleep(5)
        failed = run_batch(failed, min(4, config.GEN_CONCURRENCY))
    res.failed = [{**s.to_dict(), "error": getattr(s, "_error", "")} for s in failed]

    if drive:
        # догрузка файлов, которые не ушли на Диск с первого раза (без повторной генерации)
        not_uploaded = [it for it in res.done if not it["uploaded"]]
        if not_uploaded:
            log(f"Догружаю на Диск: {len(not_uploaded)} шт.", None)
            time.sleep(5)
            for it in not_uploaded:
                if upload_item(it):
                    it["uploaded"] = True
                    with sheet_lock:
                        pending_rows.append(_row(it))
            left = sum(not it["uploaded"] for it in res.done)
            if left:
                res.warnings.append(f"не загрузились на Диск: {left} шт. — они сохранены локально в {local_dir}")
        if not flush_rows(force=True):
            res.warnings.append(f"в Google-таблицу не записались {len(pending_rows)} строк — "
                                f"полный реестр в {local_dir / 'registry.csv'}")

    # локальный реестр (дублирует Google-таблицу)
    with open(local_dir / "registry.csv", "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f, delimiter=";")
        w.writerow(REGISTRY_HEADER)
        for it in sorted(res.done, key=lambda x: x["idx"]):
            w.writerow(_row(it))
    res.seconds = round(time.time() - t0, 1)
    res.regenerated = sum(it["regenerated"] for it in res.done)
    log(f"Готово: {len(res.done)} из {count}, ошибок: {len(res.failed)}, "
        f"перегенерировано автоконтролем: {res.regenerated}, время: {res.seconds} с", None)
    for w_ in res.warnings:
        log(f"[внимание] {w_}", None)
    return res
