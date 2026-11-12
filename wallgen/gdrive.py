"""Google Drive / Sheets: авторизация (OAuth Desktop), папки, загрузка файлов, реестр промптов.

Scope drive.file: приложение видит только файлы и папки, которые создало само.
"""
from __future__ import annotations

import os
from pathlib import Path

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

ROOT = Path(__file__).resolve().parent.parent
SCOPES = ["https://www.googleapis.com/auth/drive.file"]
TOKEN_FILE = ROOT / "token.json"
FOLDER_MIME = "application/vnd.google-apps.folder"


def get_credentials() -> Credentials:
    creds = None
    if TOKEN_FILE.exists():
        creds = Credentials.from_authorized_user_file(str(TOKEN_FILE), SCOPES)
    if creds and creds.valid:
        return creds
    if creds and creds.expired and creds.refresh_token:
        creds.refresh(Request())
    else:
        secret = ROOT / os.environ.get("GOOGLE_CLIENT_SECRET_FILE", "client_secret.json")
        flow = InstalledAppFlow.from_client_secrets_file(str(secret), SCOPES)
        creds = flow.run_local_server(port=0, open_browser=True)
    TOKEN_FILE.write_text(creds.to_json(), encoding="utf-8")
    return creds


class Drive:
    def __init__(self, creds: Credentials | None = None) -> None:
        # creds можно передать готовые — так потоки не перечитывают и не перезаписывают token.json
        creds = creds or get_credentials()
        self.creds = creds
        self.drive = build("drive", "v3", credentials=creds, cache_discovery=False)
        self.sheets = build("sheets", "v4", credentials=creds, cache_discovery=False)

    # --- папки -------------------------------------------------------------
    def ensure_folder(self, name: str, parent_id: str | None = None) -> str:
        """Найти папку по имени (среди созданных приложением) или создать."""
        q = f"name = '{name.replace(chr(39), chr(92) + chr(39))}' and mimeType = '{FOLDER_MIME}' and trashed = false"
        if parent_id:
            q += f" and '{parent_id}' in parents"
        found = self.drive.files().list(q=q, fields="files(id)", pageSize=1).execute().get("files", [])
        if found:
            return found[0]["id"]
        meta = {"name": name, "mimeType": FOLDER_MIME}
        if parent_id:
            meta["parents"] = [parent_id]
        return self.drive.files().create(body=meta, fields="id").execute()["id"]

    def find_folder(self, name: str, parent_id: str | None = None) -> str | None:
        safe = name.replace("\\", "\\\\").replace("'", "\\'")
        q = f"name = '{safe}' and mimeType = '{FOLDER_MIME}' and trashed = false"
        if parent_id:
            q += f" and '{parent_id}' in parents"
        found = self.drive.files().list(q=q, fields="files(id)", pageSize=1).execute().get("files", [])
        return found[0]["id"] if found else None

    def list_folders(self, parent_id: str) -> list[dict]:
        q = f"'{parent_id}' in parents and mimeType = '{FOLDER_MIME}' and trashed = false"
        return self.drive.files().list(q=q, fields="files(id, name)", pageSize=200).execute().get("files", [])

    def create_folder(self, name: str, parent_id: str) -> str:
        meta = {"name": name, "mimeType": FOLDER_MIME, "parents": [parent_id]}
        return self.drive.files().create(body=meta, fields="id").execute()["id"]

    def find_file(self, name: str, parent_id: str) -> dict | None:
        """Найти файл по имени в папке (для идемпотентной повторной загрузки)."""
        safe = name.replace("\\", "\\\\").replace("'", "\\'")
        q = f"name = '{safe}' and '{parent_id}' in parents and trashed = false"
        found = self.drive.files().list(q=q, fields="files(id, webViewLink)", pageSize=1).execute()
        return (found.get("files") or [None])[0]

    def rename(self, file_id: str, new_name: str) -> None:
        self.drive.files().update(fileId=file_id, body={"name": new_name}).execute()

    def move(self, file_id: str, new_parent: str) -> None:
        parents = self.drive.files().get(fileId=file_id, fields="parents").execute().get("parents", [])
        self.drive.files().update(fileId=file_id, addParents=new_parent,
                                  removeParents=",".join(parents)).execute()

    def share_anyone_reader(self, file_id: str) -> None:
        """Доступ «Просмотр по ссылке» для всех, у кого есть ссылка."""
        self.drive.permissions().create(fileId=file_id, body={"type": "anyone", "role": "reader"}).execute()

    # --- файлы -------------------------------------------------------------
    def upload(self, path: Path, folder_id: str, description: str = "", mimetype: str = "image/jpeg",
               name: str | None = None, convert_to: str | None = None) -> dict:
        """Загрузить файл. convert_to — mimeType Google-формата (например, Google Docs из Markdown)."""
        meta = {"name": name or path.name, "parents": [folder_id], "description": description[:30000]}
        if convert_to:
            meta["mimeType"] = convert_to
        media = MediaFileUpload(str(path), mimetype=mimetype, resumable=path.stat().st_size > 5_000_000)
        return self.drive.files().create(body=meta, media_body=media, fields="id, webViewLink").execute()

    def delete(self, file_id: str) -> None:
        self.drive.files().delete(fileId=file_id).execute()

    @staticmethod
    def folder_link(folder_id: str) -> str:
        return f"https://drive.google.com/drive/folders/{folder_id}"

    # --- реестр (Google Sheets) -------------------------------------------
    def create_sheet(self, title: str, folder_id: str, header: list[str]) -> str:
        meta = {"name": title, "mimeType": "application/vnd.google-apps.spreadsheet", "parents": [folder_id]}
        sheet_id = self.drive.files().create(body=meta, fields="id").execute()["id"]
        self.append_rows(sheet_id, [header])
        return sheet_id

    def append_rows(self, sheet_id: str, rows: list[list]) -> None:
        self.sheets.spreadsheets().values().append(
            spreadsheetId=sheet_id, range="A1", valueInputOption="USER_ENTERED",
            insertDataOption="INSERT_ROWS", body={"values": rows},
        ).execute()

    @staticmethod
    def sheet_link(sheet_id: str) -> str:
        return f"https://docs.google.com/spreadsheets/d/{sheet_id}"
