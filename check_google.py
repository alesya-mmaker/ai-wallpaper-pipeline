"""Проверка связи с Google: вход, папка, загрузка файла, таблица."""
from pathlib import Path

from dotenv import load_dotenv
from PIL import Image

load_dotenv()
from wallgen.gdrive import Drive  # noqa: E402

d = Drive()
print("Вход в Google: OK")
root = d.ensure_folder("AI Wallpapers")
test = d.ensure_folder("_connection_test", root)
print("Папка:", d.folder_link(root))

jpg = Path("output/tests/lucid_test.jpg")
Image.open("output/tests/lucid.png").convert("RGB").save(jpg, "JPEG", quality=95)
f = d.upload(jpg, test, description="PROMPT: test upload")
print("Загрузка файла: OK", f["webViewLink"])

sid = d.create_sheet("_test_registry", test, ["file", "prompt"])
d.append_rows(sid, [[jpg.name, "test prompt"]])
print("Таблица: OK", d.sheet_link(sid))

d.delete(test)  # убираем тестовую папку вместе с содержимым
print("Тестовая папка удалена. Всё работает.")
