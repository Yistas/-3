# -*- coding: utf-8 -*-
"""Загрузка отсканированных фото монеты на Google Drive с публичным доступом
и получение прямых ссылок для параметра pictures API Meshok."""
import logging
from pathlib import Path

LOGGER = logging.getLogger('CoinCollector.MeshokPhotoHost')

FOLDER_NAME = 'meshok_photos'


def _get_service():
    """Возвращает (gdrive, service) или (None, None), если Drive не настроен."""
    try:
        from utils.gdrive_oauth import get_gdrive_sync
        gdrive = get_gdrive_sync()
        if gdrive is None or not gdrive.is_available():
            return None, None
        return gdrive, gdrive.service
    except Exception as e:
        LOGGER.error(f"Google Drive недоступен: {e}")
        return None, None


def _find_or_create_folder(service, root_folder_id, name):
    """Папка name внутри root_folder_id (или в корне), создаёт при отсутствии."""
    q = (f"name='{name}' and mimeType='application/vnd.google-apps.folder' "
         f"and trashed=false")
    if root_folder_id:
        q += f" and '{root_folder_id}' in parents"
    res = service.files().list(q=q, spaces='drive',
                               fields='files(id, name)').execute()
    files = res.get('files', [])
    if files:
        return files[0]['id']
    meta = {'name': name, 'mimeType': 'application/vnd.google-apps.folder'}
    if root_folder_id:
        meta['parents'] = [root_folder_id]
    folder = service.files().create(body=meta, fields='id').execute()
    return folder['id']


def _pick_working_url(file_id):
    """Проверяет кандидаты прямых ссылок и возвращает первую,
        которая реально отдаёт изображение (Content-Type: image/*)."""
    candidates = [
        f"https://lh3.googleusercontent.com/d/{file_id}",
        f"https://drive.google.com/thumbnail?id={file_id}&sz=w1600",
        f"https://drive.google.com/uc?export=view&id={file_id}",
    ]
    try:
        import requests
        for url in candidates:
            try:
                r = requests.get(url, timeout=15, stream=True)
                ct = r.headers.get('Content-Type', '')
                ok = (r.status_code == 200 and ct.startswith('image'))
                r.close()
                if ok:
                    return url
            except Exception:
                continue
    except Exception:
        pass
    return candidates[0]


def upload_photo_public(local_path, unique_name=None):
    """Загружает фото на Drive, открывает публичный доступ (anyone/reader),
    возвращает прямую ссылку или None."""
    if not local_path or not Path(local_path).exists():
        return None
    try:
        from googleapiclient.http import MediaFileUpload
        gdrive, service = _get_service()
        if service is None:
            LOGGER.warning("Google Drive не настроен (нет credentials.json)")
            return None
        folder_id = _find_or_create_folder(
            service, getattr(gdrive, 'drive_folder_id', None), FOLDER_NAME)
        name = unique_name or Path(local_path).name
        # удаляем старые файлы с тем же именем (без дублей)
        q = f"name='{name}' and '{folder_id}' in parents and trashed=false"
        old = service.files().list(q=q, fields='files(id)').execute().get('files', [])
        for f in old:
            try:
                service.files().delete(fileId=f['id']).execute()
            except Exception:
                pass
        meta = {'name': name, 'parents': [folder_id]}
        media = MediaFileUpload(str(local_path), mimetype='image/jpeg')
        created = service.files().create(
            body=meta, media_body=media, fields='id').execute()
        file_id = created['id']
        # публичный доступ: любой по ссылке может читать
        service.permissions().create(
            fileId=file_id,
            body={'role': 'reader', 'type': 'anyone'},
            fields='id').execute()
        url = _pick_working_url(file_id)
        LOGGER.info(f"📤 Фото на Google Drive (публично): {url}")
        return url
    except Exception as e:
        LOGGER.error(f"Ошибка загрузки фото на Google Drive: {e}")
        return None


def upload_lot_photos(obverse_path, reverse_path, coin_id=None):
    """Загружает обе стороны монеты. Возвращает список URL (может быть пустым)."""
    urls = []
    prefix = f"coin_{coin_id}" if coin_id else "lot"
    for side, path in (('obverse', obverse_path), ('reverse', reverse_path)):
        url = upload_photo_public(path, unique_name=f"{prefix}_{side}.jpg")
        if url:
            urls.append(url)
    return urls