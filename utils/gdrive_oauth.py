# ===== ФАЙЛ: utils/gdrive_oauth.py =====
# ПОЛНОСТЬЮ ЗАМЕНИТЬ ФАЙЛ

# -*- coding: utf-8 -*-

"""
Модуль синхронизации с Google Drive через OAuth 2.0
"""

import os
import json
import logging
import shutil
import pickle
import tempfile
from pathlib import Path
from datetime import datetime, timezone
from typing import Dict, Optional, List

from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload, MediaIoBaseDownload
from googleapiclient.errors import HttpError

from utils.paths import paths


class GoogleDriveOAuth:
    """Синхронизация с Google Drive через OAuth 2.0"""

    # OAuth 2.0 scopes
    SCOPES = ['https://www.googleapis.com/auth/drive.file']

    # Имя папки в корне Google Drive
    DRIVE_FOLDER_NAME = "CoinCollector"

    # Максимальное количество копий каждого файла в облаке
    MAX_CLOUD_BACKUPS = 3

    # ===== ФАЙЛЫ ДЛЯ СИНХРОНИЗАЦИИ =====
    
    # Файлы в корне system_data/
    ROOT_FILES = [
        "version_config.json",
        "passwords.enc",
        "password.key",
    ]

    # Файлы в папке system_data/data/ - ТОЛЬКО ОСНОВНЫЕ БД
    DATA_FILES = [
        # === КОНФИГУРАЦИОННАЯ БД ===
        "config.db",
        # === ОСНОВНАЯ БД ===
        "coins.db",
    ]

    # Папки для синхронизации (в system_data/data/)
    SYNC_FOLDERS = [
        "coin_images",
        "continent_maps",
        "custom_icons",
        "custom_images",
        "yearly_tables",
    ]

    def __init__(self):
        """Инициализация синхронизации"""
        self.logger = logging.getLogger('CoinCollector.GoogleDriveOAuth')

        # ===== ПОЛУЧАЕМ ПУТИ ЧЕРЕЗ paths =====
        self.system_data_dir = paths.normalize_path(paths.get_system_data_dir())
        self.data_dir = paths.normalize_path(paths.get_data_dir())

        # Создаём папки если их нет
        self.system_data_dir.mkdir(parents=True, exist_ok=True)
        self.data_dir.mkdir(parents=True, exist_ok=True)

        self.logger.info(f"📁 system_data: {self.system_data_dir}")
        self.logger.info(f"📁 data: {self.data_dir}")

        # Путь к файлу с токеном
        self.token_file = self.data_dir / "gdrive_token.pickle"

        # Поиск credentials.json
        self.credentials_file = None
        possible_paths = [
            self.data_dir / "credentials.json",
            self.system_data_dir / "credentials.json",
            paths.get_project_root() / "credentials.json",
        ]

        for path in possible_paths:
            if path.exists():
                self.credentials_file = path
                self.logger.info(f"🔍 Найден credentials: {path}")
                break

        if self.credentials_file:
            self.logger.info(f"✅ Найден файл credentials: {self.credentials_file}")
        else:
            self.logger.warning(f"❌ Файл credentials.json не найден")
            self.logger.info("   Положите credentials.json в папку system_data/data/")

        self.service = None
        self.drive_folder_id = None

        if self.credentials_file:
            self._authenticate()

    def _authenticate(self):
        """Аутентификация через OAuth 2.0"""
        creds = None

        # Загружаем сохранённый токен
        if self.token_file.exists():
            try:
                with open(self.token_file, 'rb') as token:
                    creds = pickle.load(token)
                self.logger.info("📁 Загружен сохранённый токен")
            except Exception as e:
                self.logger.error(f"Ошибка загрузки токена: {e}")

        # Если токен не валиден, обновляем или создаём новый
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                try:
                    creds.refresh(Request())
                    self.logger.info("🔄 Токен обновлён")
                except Exception as e:
                    self.logger.error(f"Ошибка обновления токена: {e}")
                    creds = None

            if not creds:
                try:
                    self.logger.info("🔐 Запуск авторизации...")
                    flow = InstalledAppFlow.from_client_secrets_file(
                        str(self.credentials_file), self.SCOPES
                    )
                    creds = flow.run_local_server(port=0)
                    self.logger.info("✅ Авторизация успешна")
                except Exception as e:
                    self.logger.error(f"❌ Ошибка авторизации: {e}")
                    return

            # Сохраняем токен
            try:
                with open(self.token_file, 'wb') as token:
                    pickle.dump(creds, token)
                self.logger.info("💾 Токен сохранён")
            except Exception as e:
                self.logger.error(f"Ошибка сохранения токена: {e}")

        try:
            self.service = build('drive', 'v3', credentials=creds)
            self.drive_folder_id = self._get_or_create_folder()
            self.logger.info("✅ Google Drive OAuth готов к работе")
        except Exception as e:
            self.logger.error(f"Ошибка создания сервиса: {e}")
            self.service = None

    def _get_or_create_folder(self) -> Optional[str]:
        """Находит или создаёт папку в корне Google Drive"""
        try:
            results = self.service.files().list(
                q=f"name='{self.DRIVE_FOLDER_NAME}' and mimeType='application/vnd.google-apps.folder' and trashed=false",
                spaces='drive',
                fields='files(id, name)'
            ).execute()

            files = results.get('files', [])

            if files:
                folder_id = files[0]['id']
                self.logger.info(f"📁 Найдена папка: {self.DRIVE_FOLDER_NAME}")
                return folder_id

            file_metadata = {
                'name': self.DRIVE_FOLDER_NAME,
                'mimeType': 'application/vnd.google-apps.folder'
            }
            folder = self.service.files().create(body=file_metadata, fields='id').execute()
            folder_id = folder.get('id')
            self.logger.info(f"📁 Создана папка: {self.DRIVE_FOLDER_NAME}")
            return folder_id

        except HttpError as e:
            self.logger.error(f"❌ Ошибка при работе с папкой: {e}")
            return None

    def _get_file_id(self, file_name: str, parent_id: str) -> Optional[str]:
        """Получает ID файла на Google Drive"""
        try:
            query = f"name='{file_name}' and '{parent_id}' in parents and trashed=false"
            results = self.service.files().list(
                q=query,
                spaces='drive',
                fields='files(id, name)'
            ).execute()

            files = results.get('files', [])
            if files:
                return files[0]['id']
            return None

        except Exception as e:
            self.logger.error(f"Ошибка получения ID для {file_name}: {e}")
            return None

    def _get_or_create_subfolder(self, folder_name: str, parent_id: str) -> Optional[str]:
        """Находит или создаёт подпапку"""
        try:
            query = f"name='{folder_name}' and '{parent_id}' in parents and mimeType='application/vnd.google-apps.folder' and trashed=false"
            results = self.service.files().list(
                q=query,
                spaces='drive',
                fields='files(id, name)'
            ).execute()

            files = results.get('files', [])
            if files:
                return files[0]['id']

            file_metadata = {
                'name': folder_name,
                'mimeType': 'application/vnd.google-apps.folder',
                'parents': [parent_id]
            }
            folder = self.service.files().create(body=file_metadata, fields='id').execute()
            return folder.get('id')

        except Exception as e:
            self.logger.error(f"Ошибка создания папки {folder_name}: {e}")
            return None

    def _get_cloud_folder_id(self, relative_path: str) -> Optional[str]:
        """Получает ID папки в облаке по относительному пути."""
        try:
            current_parent = self.drive_folder_id
            parts = relative_path.split('/')

            for folder_name in parts:
                if not folder_name:
                    continue

                query = f"name='{folder_name}' and '{current_parent}' in parents and mimeType='application/vnd.google-apps.folder' and trashed=false"
                results = self.service.files().list(
                    q=query,
                    spaces='drive',
                    fields='files(id, name)',
                    pageSize=10
                ).execute()

                files = results.get('files', [])

                if not files:
                    self.logger.debug(f"   ❌ Папка не найдена: {folder_name}")
                    return None

                current_parent = files[0]['id']
                self.logger.debug(f"   ✅ Найдена папка: {folder_name} (ID: {current_parent})")

            return current_parent

        except Exception as e:
            self.logger.error(f"Ошибка получения ID папки {relative_path}: {e}")
            return None

    def _ensure_cloud_folder(self, relative_path: str) -> Optional[str]:
        """Создаёт папку в облаке, если её нет."""
        try:
            current_parent = self.drive_folder_id
            parts = relative_path.split('/')

            for folder_name in parts:
                if not folder_name:
                    continue

                query = f"name='{folder_name}' and '{current_parent}' in parents and mimeType='application/vnd.google-apps.folder' and trashed=false"
                results = self.service.files().list(
                    q=query,
                    spaces='drive',
                    fields='files(id, name)',
                    pageSize=10
                ).execute()

                files = results.get('files', [])

                if files:
                    current_parent = files[0]['id']
                else:
                    file_metadata = {
                        'name': folder_name,
                        'mimeType': 'application/vnd.google-apps.folder',
                        'parents': [current_parent]
                    }
                    folder = self.service.files().create(body=file_metadata, fields='id').execute()
                    current_parent = folder.get('id')
                    self.logger.info(f"   📁 Создана папка в облаке: {folder_name}")

            return current_parent

        except Exception as e:
            self.logger.error(f"Ошибка создания папки {relative_path}: {e}")
            return None

    def _cleanup_old_versions(self, file_name: str, parent_id: str):
        """Удаляет старые версии файла в облаке, оставляя только MAX_CLOUD_BACKUPS последних"""
        try:
            # Ищем все файлы с таким именем в папке
            query = f"name='{file_name}' and '{parent_id}' in parents and trashed=false"
            results = self.service.files().list(
                q=query,
                spaces='drive',
                fields='files(id, name, modifiedTime)',
                orderBy='modifiedTime desc',
                pageSize=100
            ).execute()

            files = results.get('files', [])

            if len(files) <= self.MAX_CLOUD_BACKUPS:
                return

            # Удаляем лишние файлы (начиная с самых старых)
            to_delete = files[self.MAX_CLOUD_BACKUPS:]
            self.logger.info(f"   🧹 Удаление {len(to_delete)} старых версий {file_name} (оставляем {self.MAX_CLOUD_BACKUPS})")

            for file_info in to_delete:
                try:
                    self.service.files().delete(fileId=file_info['id']).execute()
                    self.logger.info(f"      ✅ Удалена старая версия: {file_info['id']}")
                except Exception as e:
                    self.logger.error(f"      ❌ Ошибка удаления {file_info['id']}: {e}")

        except Exception as e:
            self.logger.error(f"Ошибка очистки старых версий {file_name}: {e}")

    def _upload_file(self, local_file: Path, parent_id: str, filename: str) -> bool:
        """Загружает файл в Google Drive"""
        try:
            media = MediaFileUpload(
                str(local_file),
                mimetype='application/octet-stream',
                resumable=True
            )

            file_metadata = {
                'name': filename,
                'parents': [parent_id]
            }

            self.service.files().create(
                body=file_metadata,
                media_body=media,
                fields='id'
            ).execute()

            self.logger.info(f"   📤 Загружен: {filename}")

            # Очищаем старые версии этого файла
            self._cleanup_old_versions(filename, parent_id)

            return True

        except Exception as e:
            self.logger.error(f"   ❌ Ошибка загрузки: {e}")
            return False

    def _download_file(self, file_id: str, local_file: Path) -> bool:
        """Скачивает файл из Google Drive"""
        try:
            local_file.parent.mkdir(parents=True, exist_ok=True)

            with tempfile.NamedTemporaryFile(delete=False, suffix='.tmp') as tmp:
                tmp_path = Path(tmp.name)

            request = self.service.files().get_media(fileId=file_id)

            with open(tmp_path, 'wb') as f:
                downloader = MediaIoBaseDownload(f, request)
                done = False
                while not done:
                    status, done = downloader.next_chunk()

            shutil.copy2(tmp_path, local_file)
            tmp_path.unlink()

            self.logger.info(f"   📥 Скачан: {local_file.name}")
            return True

        except Exception as e:
            self.logger.error(f"   ❌ Ошибка скачивания: {e}")
            return False

    def _get_file_mtime(self, file_id: str) -> Optional[datetime]:
        """Получает время модификации файла в облаке (в локальном часовом поясе)"""
        try:
            file_meta = self.service.files().get(fileId=file_id, fields='modifiedTime').execute()
            modified_time = file_meta['modifiedTime']
            if 'Z' in modified_time:
                modified_time = modified_time.replace('Z', '+00:00')
            dt = datetime.fromisoformat(modified_time)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            # Конвертируем UTC время в локальное время пользователя (GMT+3 = 08:56:59)
            dt = dt.astimezone()  # astimezone() без аргументов = локальный часовой пояс
            return dt.replace(tzinfo=None)
        except Exception as e:
            self.logger.error(f"Ошибка получения времени для file_id {file_id}: {e}")
            return None

    def _get_local_mtime(self, local_file: Path) -> Optional[datetime]:
        """Получает время модификации локального файла"""
        try:
            timestamp = local_file.stat().st_mtime
            return datetime.fromtimestamp(timestamp)
        except Exception as e:
            self.logger.error(f"Ошибка получения времени для {local_file}: {e}")
            return None

    def sync_root_file(self, filename: str) -> bool:
        """Синхронизирует файл из корня system_data/"""
        if not self.service or not self.drive_folder_id:
            return False

        local_file = self.system_data_dir / filename
        cloud_path = f"system_data/{filename}"

        return self._sync_file(local_file, cloud_path)

    def sync_data_file(self, filename: str) -> bool:
        """Синхронизирует файл из папки system_data/data/"""
        if not self.service or not self.drive_folder_id:
            return False

        local_file = self.data_dir / filename
        cloud_path = f"system_data/data/{filename}"

        return self._sync_file(local_file, cloud_path)

    def _sync_file(self, local_file: Path, cloud_path: str) -> bool:
        """Универсальный метод синхронизации одного файла."""
        if not self.service or not self.drive_folder_id:
            return False

        filename = local_file.name
        cloud_folder_path = '/'.join(cloud_path.split('/')[:-1]) if '/' in cloud_path else ""

        self.logger.info(f"📁 Синхронизация: {filename}")
        self.logger.info(f"   Локальный путь: {local_file}")
        self.logger.info(f"   Облачный путь: {cloud_path}")

        local_exists = local_file.exists()
        self.logger.info(f"   Локальный файл существует: {local_exists}")

        cloud_folder_id = self._get_cloud_folder_id(cloud_folder_path) if cloud_folder_path else self.drive_folder_id

        if not cloud_folder_id:
            cloud_folder_id = self._ensure_cloud_folder(cloud_folder_path)
            if not cloud_folder_id:
                self.logger.error(f"   ❌ Не удалось создать папку в облаке: {cloud_folder_path}")
                return False

        file_id = self._get_file_id(filename, cloud_folder_id)
        cloud_exists = file_id is not None
        self.logger.info(f"   Файл в облаке существует: {cloud_exists}")

        if not local_exists and not cloud_exists:
            self.logger.info(f"   📝 Файл отсутствует локально и в облаке, создаём пустой файл")
            try:
                local_file.parent.mkdir(parents=True, exist_ok=True)
                with open(local_file, 'w', encoding='utf-8') as f:
                    json.dump({}, f, ensure_ascii=False, indent=2)
                self.logger.info(f"   ✅ Создан пустой файл: {local_file}")
                return self._upload_file(local_file, cloud_folder_id, filename)
            except Exception as e:
                self.logger.error(f"   ❌ Не удалось создать файл: {e}")
                return False

        if local_exists and not cloud_exists:
            self.logger.info(f"   📤 Загрузка (только локально)")
            return self._upload_file(local_file, cloud_folder_id, filename)

        if not local_exists and cloud_exists:
            self.logger.info(f"   📥 Скачивание (только в облаке)")
            return self._download_file(file_id, local_file)

        cloud_time = self._get_file_mtime(file_id)
        local_time = self._get_local_mtime(local_file)

        if cloud_time is None or local_time is None:
            self.logger.warning(f"   ⚠️ Не удалось сравнить время, пропускаем")
            return False

        time_diff = abs((cloud_time - local_time).total_seconds())
        self.logger.info(f"   Облако: {cloud_time.strftime('%Y-%m-%d %H:%M:%S')}")
        self.logger.info(f"   Локально: {local_time.strftime('%Y-%m-%d %H:%M:%S')}")
        self.logger.info(f"   Разница: {time_diff:.1f} сек")

        if time_diff <= 2:
            self.logger.info(f"   ⏭️ Файлы одинаковые, пропускаем")
            return False

        if local_time > cloud_time:
            self.logger.info(f"   📤 Локальный новее, загружаем в облако")
            return self._upload_file(local_file, cloud_folder_id, filename)
        else:
            self.logger.info(f"   📥 Облачный новее, скачиваем")
            return self._download_file(file_id, local_file)

    def sync_folder(self, folder_name: str) -> Dict[str, int]:
        """Синхронизирует папку (в system_data/data/)"""
        result = {'uploaded': 0, 'downloaded': 0, 'skipped': 0, 'errors': 0}

        if not self.service or not self.drive_folder_id:
            return result

        local_folder = self.data_dir / folder_name
        cloud_path = f"system_data/data/{folder_name}"

        self.logger.info(f"📂 Синхронизация папки: {folder_name}")
        self.logger.info(f"   Локальный путь: {local_folder}")
        self.logger.info(f"   Облачный путь: {cloud_path}")

        if not local_folder.exists():
            local_folder.mkdir(parents=True, exist_ok=True)
            self.logger.info(f"   📁 Создана локальная папка: {local_folder}")

        cloud_folder_id = self._get_cloud_folder_id(cloud_path)

        if not cloud_folder_id:
            cloud_folder_id = self._ensure_cloud_folder(cloud_path)
            if not cloud_folder_id:
                result['errors'] += 1
                self.logger.error(f"   ❌ Не удалось создать папку в облаке: {cloud_path}")
                return result

        self.logger.info(f"   Cloud folder ID: {cloud_folder_id}")

        cloud_files = {}
        try:
            page_token = None
            while True:
                results = self.service.files().list(
                    q=f"'{cloud_folder_id}' in parents and trashed=false",
                    spaces='drive',
                    fields='nextPageToken, files(id, name, modifiedTime)',
                    pageToken=page_token
                ).execute()

                for file in results.get('files', []):
                    cloud_files[file['name']] = {
                        'id': file['id'],
                        'modified': self._get_file_mtime(file['id'])
                    }

                page_token = results.get('nextPageToken', None)
                if not page_token:
                    break
        except Exception as e:
            self.logger.error(f"Ошибка получения списка файлов: {e}")
            result['errors'] += 1
            return result

        self.logger.info(f"   Файлов в облаке: {len(cloud_files)}")
        local_files = list(local_folder.iterdir()) if local_folder.exists() else []
        self.logger.info(f"   Локальных файлов: {len(local_files)}")

        for file_path in local_files:
            if not file_path.is_file():
                continue

            self.logger.info(f"   Обработка: {file_path.name}")
            cloud_file = cloud_files.get(file_path.name)

            if not cloud_file:
                self.logger.info(f"   📤 Загрузка (нет в облаке): {file_path.name}")
                if self._upload_file(file_path, cloud_folder_id, file_path.name):
                    result['uploaded'] += 1
                else:
                    result['errors'] += 1
            else:
                local_time = self._get_local_mtime(file_path)
                cloud_time = cloud_file['modified']

                if local_time is None or cloud_time is None:
                    result['errors'] += 1
                    continue

                time_diff = abs((cloud_time - local_time).total_seconds())

                if time_diff <= 2:
                    self.logger.info(f"   ⏭️ Пропущено: {file_path.name}")
                    result['skipped'] += 1
                elif local_time > cloud_time:
                    self.logger.info(f"   📤 Загрузка (новей): {file_path.name}")
                    if self._upload_file(file_path, cloud_folder_id, file_path.name):
                        result['uploaded'] += 1
                    else:
                        result['errors'] += 1
                else:
                    self.logger.info(f"   📥 Скачивание (новей в облаке): {file_path.name}")
                    if self._download_file(cloud_file['id'], file_path):
                        result['downloaded'] += 1
                    else:
                        result['errors'] += 1

        for file_name, cloud_file in cloud_files.items():
            local_file = local_folder / file_name
            if not local_file.exists():
                self.logger.info(f"   📥 Скачивание (нет локально): {file_name}")
                if self._download_file(cloud_file['id'], local_file):
                    result['downloaded'] += 1
                else:
                    result['errors'] += 1

        self.logger.info(f"   📊 Итог: загружено {result['uploaded']}, скачано {result['downloaded']}, пропущено {result['skipped']}")
        return result

    def sync_all_files(self) -> Dict[str, int]:
        """Синхронизирует все конфигурационные файлы"""
        result = {'uploaded': 0, 'downloaded': 0, 'skipped': 0, 'errors': 0}

        if not self.service or not self.drive_folder_id:
            self.logger.error("❌ Google Drive не настроен")
            return result

        self.logger.info("=" * 60)
        self.logger.info("🔄 СИНХРОНИЗАЦИЯ КОНФИГУРАЦИОННЫХ ФАЙЛОВ")
        self.logger.info("=" * 60)

        for filename in self.ROOT_FILES:
            try:
                if self.sync_root_file(filename):
                    local_file = self.system_data_dir / filename
                    if local_file.exists():
                        result['uploaded'] += 1
                    else:
                        result['downloaded'] += 1
                else:
                    result['skipped'] += 1
            except Exception as e:
                self.logger.error(f"Ошибка синхронизации {filename}: {e}")
                result['errors'] += 1

        for filename in self.DATA_FILES:
            try:
                if self.sync_data_file(filename):
                    local_file = self.data_dir / filename
                    if local_file.exists():
                        result['uploaded'] += 1
                    else:
                        result['downloaded'] += 1
                else:
                    result['skipped'] += 1
            except Exception as e:
                self.logger.error(f"Ошибка синхронизации {filename}: {e}")
                result['errors'] += 1

        self.logger.info("-" * 60)
        self.logger.info(f"📊 РЕЗУЛЬТАТЫ:")
        self.logger.info(f"  📤 Загружено: {result['uploaded']}")
        self.logger.info(f"  📥 Скачано: {result['downloaded']}")
        self.logger.info(f"  ⏭️ Пропущено: {result['skipped']}")
        self.logger.info(f"  ❌ Ошибок: {result['errors']}")
        self.logger.info("=" * 60)

        return result

    def sync_all(self) -> Dict[str, int]:
        """Синхронизирует все файлы и папки"""
        result = {'uploaded': 0, 'downloaded': 0, 'skipped': 0, 'errors': 0}

        if not self.service or not self.drive_folder_id:
            self.logger.error("❌ Google Drive не настроен")
            return result

        self.logger.info("=" * 50)
        self.logger.info("🚀 НАЧАЛО СИНХРОНИЗАЦИИ С GOOGLE DRIVE")
        self.logger.info("=" * 50)

        file_result = self.sync_all_files()
        result['uploaded'] += file_result['uploaded']
        result['downloaded'] += file_result['downloaded']
        result['skipped'] += file_result['skipped']
        result['errors'] += file_result['errors']

        for folder_name in self.SYNC_FOLDERS:
            try:
                folder_result = self.sync_folder(folder_name)
                result['uploaded'] += folder_result['uploaded']
                result['downloaded'] += folder_result['downloaded']
                result['skipped'] += folder_result['skipped']
                result['errors'] += folder_result['errors']
            except Exception as e:
                self.logger.error(f"Ошибка синхронизации папки {folder_name}: {e}")
                result['errors'] += 1

        self.logger.info("-" * 50)
        self.logger.info(f"📊 РЕЗУЛЬТАТЫ:")
        self.logger.info(f"  📤 Загружено: {result['uploaded']}")
        self.logger.info(f"  📥 Скачано: {result['downloaded']}")
        self.logger.info(f"  ⏭️ Пропущено: {result['skipped']}")
        self.logger.info(f"  ❌ Ошибок: {result['errors']}")
        self.logger.info("=" * 50)

        return result

    def is_available(self) -> bool:
        return self.service is not None and self.drive_folder_id is not None

    def get_status(self) -> dict:
        return {
            'cloud_type': 'Google Drive (OAuth)',
            'available': self.is_available(),
            'credentials_file': str(self.credentials_file) if self.credentials_file else None,
            'token_file': str(self.token_file) if self.token_file.exists() else None,
            'system_data_dir': str(self.system_data_dir),
            'data_dir': str(self.data_dir),
        }

    def auto_sync_core(self) -> Dict[str, int]:
        """
        Автоматическая синхронизация основных файлов.
        Синхронизирует только config.db и coins.db (без временных файлов).
        """
        result = {'uploaded': 0, 'downloaded': 0, 'skipped': 0, 'errors': 0}

        if not self.service or not self.drive_folder_id:
            self.logger.error("❌ Google Drive не настроен")
            return result

        self.logger.info("🔄 Автоматическая синхронизация БД и настроек...")

        # === ОСНОВНЫЕ ФАЙЛЫ ДЛЯ АВТО-СИНХРОНИЗАЦИИ ===
        core_files = [
            "config.db",
            "coins.db",
        ]

        for filename in core_files:
            try:
                if self.sync_data_file(filename):
                    local_file = self.data_dir / filename
                    if local_file.exists():
                        result['uploaded'] += 1
                    else:
                        result['downloaded'] += 1
                else:
                    result['skipped'] += 1
            except Exception as e:
                self.logger.error(f"Ошибка синхронизации {filename}: {e}")
                result['errors'] += 1

        self.logger.info(f"  📤 Загружено: {result['uploaded']}, 📥 Скачано: {result['downloaded']}, ⏭️ Пропущено: {result['skipped']}")
        return result

    def cleanup_old_configs(self) -> Dict[str, int]:
        """
        Удаляет старые JSON файлы настроек из облака и локально.
        ВНИМАНИЕ: Вызывать только после полного переноса всех настроек в config.db!
        """
        result = {'deleted_cloud': 0, 'deleted_local': 0, 'errors': 0}

        if not self.service or not self.drive_folder_id:
            self.logger.error("❌ Google Drive не настроен")
            return result

        # Список файлов для удаления (все настройки теперь в config.db)
        old_config_files = [
            "backup_settings.json",
            "deals_tab_filters.json",
            "deals_tab_column_settings.json",
            "exchange_tab_filters.json",
            "sales_tab_filters.json",
            "settings.json",
            "statistics_colors.json",
            "statistics_comments.json",
            "window_settings.json",
            "silver_column_settings.json",
            "color_settings.json",
        ]

        self.logger.info("=" * 60)
        self.logger.info("🧹 ОЧИСТКА СТАРЫХ КОНФИГОВ")
        self.logger.info("=" * 60)

        # Получаем ID папки data в облаке
        cloud_data_folder_id = self._get_cloud_folder_id("system_data/data")

        if not cloud_data_folder_id:
            self.logger.error("❌ Не найдена папка data в облаке")
            result['errors'] += 1
            return result

        # Удаляем файлы из облака
        for filename in old_config_files:
            try:
                file_id = self._get_file_id(filename, cloud_data_folder_id)
                if file_id:
                    self.service.files().delete(fileId=file_id).execute()
                    self.logger.info(f"   ☁️ Удалён из облака: {filename}")
                    result['deleted_cloud'] += 1
                else:
                    self.logger.info(f"   ⏭️ Нет в облаке: {filename}")
            except Exception as e:
                self.logger.error(f"   ❌ Ошибка удаления {filename} из облака: {e}")
                result['errors'] += 1

            # Удаляем локальные файлы
            try:
                local_file = self.data_dir / filename
                if local_file.exists():
                    # Создаём бекап перед удалением
                    backup_file = self.data_dir / f"_deleted_{filename}"
                    shutil.copy2(local_file, backup_file)
                    local_file.unlink()
                    self.logger.info(f"   💾 Локально удалён: {filename} (бекап: _deleted_{filename})")
                    result['deleted_local'] += 1
                else:
                    self.logger.info(f"   ⏭️ Нет локально: {filename}")
            except Exception as e:
                self.logger.error(f"   ❌ Ошибка удаления {filename} локально: {e}")
                result['errors'] += 1

        self.logger.info("-" * 60)
        self.logger.info(f"📊 РЕЗУЛЬТАТЫ ОЧИСТКИ:")
        self.logger.info(f"  ☁️ Удалено из облака: {result['deleted_cloud']}")
        self.logger.info(f"  💾 Удалено локально: {result['deleted_local']}")
        self.logger.info(f"  ❌ Ошибок: {result['errors']}")
        self.logger.info("=" * 60)

        return result


_gdrive_instance = None


def get_gdrive_sync() -> GoogleDriveOAuth:
    global _gdrive_instance
    if _gdrive_instance is None:
        _gdrive_instance = GoogleDriveOAuth()
    return _gdrive_instance