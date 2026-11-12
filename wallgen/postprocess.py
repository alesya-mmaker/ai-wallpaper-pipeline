"""Постобработка: (апскейл при необходимости) → кроп под пропорцию → 1870×4063 → JPEG q95 + EXIF."""
from __future__ import annotations

import os
import subprocess
import tempfile
import threading
from pathlib import Path

from PIL import Image

from . import config

_gpu_lock = threading.Lock()  # видеокарта одна — апскейлим по очереди


def upscale_available() -> bool:
    return config.REALESRGAN_EXE.exists()


def upscale(img: Image.Image, scale: int = 2) -> Image.Image:
    """Real-ESRGAN (ncnn-vulkan) на локальной GPU. ×2 — быстрая модель, ×4 — x4plus."""
    model = "realesr-animevideov3" if scale == 2 else "realesrgan-x4plus"
    exe = config.REALESRGAN_EXE
    with tempfile.TemporaryDirectory() as tmp, _gpu_lock:
        src, dst = Path(tmp) / "in.png", Path(tmp) / "out.png"
        img.save(src)
        subprocess.run([str(exe), "-i", str(src), "-o", str(dst), "-n", model, "-s", str(scale)],
                       cwd=exe.parent, capture_output=True, check=True,
                       creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        return Image.open(dst).convert("RGB")


def fit_to_target(img: Image.Image) -> tuple[Image.Image, str]:
    """Довести до точного размера. Возвращает (картинка, описание шага для реестра)."""
    W, H = config.TARGET_W, config.TARGET_H
    steps = []
    # 1) если исходник заметно меньше нужного — нейросетевой апскейл
    if (img.width < W * 0.95 or img.height < H * 0.95) and upscale_available():
        img = upscale(img, 2)
        steps.append("Real-ESRGAN x2")
    # 2) центрированный кроп под пропорцию 1870:4063
    r = W / H
    w, h = img.size
    if abs(w / h - r) > 1e-3:
        if w / h > r:
            nw = round(h * r)
            img = img.crop(((w - nw) // 2, 0, (w - nw) // 2 + nw, h))
        else:
            nh = round(w / r)
            img = img.crop((0, (h - nh) // 2, w, (h - nh) // 2 + nh))
        steps.append("crop")
    # 3) точный размер
    if img.size != (W, H):
        img = img.resize((W, H), Image.LANCZOS)
        steps.append("lanczos")
    return img, " + ".join(steps) or "native"


def save_jpeg(img: Image.Image, path: Path, prompt: str, meta: str = "") -> None:
    """JPEG q95; промпт пишется в EXIF ImageDescription и в XPComment (видно в свойствах файла Windows)."""
    exif = Image.Exif()
    exif[0x010E] = prompt.encode("ascii", "replace").decode()      # ImageDescription
    exif[0x0131] = "wallgen (AI wallpaper generator)"               # Software
    exif[0x9C9C] = (prompt + ("\n" + meta if meta else "")).encode("utf-16le")  # XPComment
    path.parent.mkdir(parents=True, exist_ok=True)
    img.save(path, "JPEG", quality=config.JPEG_QUALITY, exif=exif.tobytes(), optimize=True)
    os.utime(path, None)
