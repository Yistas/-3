# -*- coding: utf-8 -*-
"""
АВТОМАТИЧЕСКАЯ обрезка сканов через наблюдение за файловой системой.
ОБРАБАТЫВАЮТСЯ ТОЛЬКО НОВЫЕ/ИЗМЕНЁННЫЕ ФАЙЛЫ:
- при подключении папки делается снимок существующих файлов —
  старые сканы НЕ трогаются;
- файлы старше 10 минут помечаются обработанными и пропускаются;
- после попытки обрезки (успешной или нет) mtime запоминается —
  повторных попыток по тому же файлу нет;
- собственная перезапись файла при обрезке не триггерит повтор
  (флаг _SAVING в image_autocrop + сравнение mtime).
"""
import logging
import time
from pathlib import Path
from PySide6.QtCore import QObject, QFileSystemWatcher, QTimer
from PySide6.QtWidgets import QApplication, QListWidget

logger = logging.getLogger('CoinCollector.Utils.AutoCropWatcher')

_IMAGE_SUFFIXES = ('.jpg', '.jpeg', '.png', '.bmp', '.tif', '.tiff')
# Пауза после события ФС: запись файла должна завершиться
STABILITY_MS = 900
# Файлы старше этого возраста (сек) считаются старыми и НЕ обрабатываются
MAX_FILE_AGE = 600


class AutoCropWatcher(QObject):
    """Синглтон: наблюдает за папками сканов и автообрезает НОВЫЕ файлы."""

    _instance = None

    @classmethod
    def instance(cls):
        if cls._instance is None:
            cls._instance = AutoCropWatcher()
        return cls._instance

    def __init__(self):
        super().__init__()
        self._watcher = QFileSystemWatcher(self)
        self._pending = {}   # path -> QTimer (ожидание стабильной записи)
        self._done = {}      # path -> mtime (обработано / старо / не трогать)
        self._dirs = set()
        self._watcher.directoryChanged.connect(self._on_dir_changed)
        self._watcher.fileChanged.connect(self._on_file_changed)

    # ================= ПУБЛИЧНОЕ =================
    def watch_folder(self, folder):
        """Подключает наблюдение за папкой и ЗАПОМИНАЕТ существующие
        в ней файлы (они не будут обрезаны)."""
        folder = Path(folder)
        try:
            folder.mkdir(parents=True, exist_ok=True)
        except Exception:
            return False
        s = str(folder)
        if s in self._dirs:
            return True
        if self._watcher.addPath(s):
            self._dirs.add(s)
            # === СНИМОК СУЩЕСТВУЮЩИХ ФАЙЛОВ: старое не трогаем ===
            try:
                for f in folder.glob('*'):
                    if f.is_file() and f.suffix.lower() in _IMAGE_SUFFIXES:
                        self._done[str(f)] = f.stat().st_mtime
            except Exception:
                pass
            logger.info(f"✂️ Наблюдатель: слежу за папкой {s} "
                        f"(старых файлов пропущено: "
                        f"{sum(1 for k in self._done if k.startswith(s))})")
            return True
        return False

    def watch_default_folders(self):
        """Стандартные папки сканов листа сделки."""
        try:
            from utils.paths import paths_instance as paths
            data = Path(paths.get_data_dir())
            self.watch_folder(data / 'temp')
            self.watch_folder(data / 'temp' / 'obmen_image')
            self.watch_folder(data / 'scans')
        except Exception as e:
            logger.debug(f"watch_default_folders: {e}")

    # ================= СЛОТЫ ФС =================
    def _on_dir_changed(self, path):
        """Изменилась папка: новые файлы или появилась подпапка."""
        # Страховка: Qt может сбросить наблюдение после переименований
        if path not in self._watcher.directories():
            self._watcher.addPath(path)
            self._dirs.add(path)
        p = Path(path)
        try:
            for child in p.iterdir():
                if child.is_dir() and child.name in ('obmen_image', 'scans'):
                    self.watch_folder(child)
        except Exception:
            pass
        self._schedule_for_folder(p)

    def _on_file_changed(self, path):
        self._schedule_file(Path(path))

    def _schedule_for_folder(self, folder):
        """Ставит в очередь ТОЛЬКО новые/свежие изменённые файлы."""
        now = time.time()
        try:
            files = list(folder.glob('*'))
        except Exception:
            return
        for f in files:
            try:
                if not f.is_file() or f.suffix.lower() not in _IMAGE_SUFFIXES:
                    continue
                m = f.stat().st_mtime
            except Exception:
                continue
            key = str(f)
            # Уже обработан / помечен — не трогаем
            if self._done.get(key) == m:
                continue
            # Старый файл (старше MAX_FILE_AGE) — запоминаем и пропускаем
            if now - m > MAX_FILE_AGE:
                self._done[key] = m
                continue
            self._schedule_file(f)

    def _schedule_file(self, f):
        """Дебаунс записи: обрезка после паузы STABILITY_MS."""
        try:
            mtime = f.stat().st_mtime
        except Exception:
            return
        if self._done.get(str(f)) == mtime:
            return
        timer = self._pending.get(str(f))
        if timer is not None:
            timer.stop()
        else:
            timer = QTimer(self)
            timer.setSingleShot(True)
            timer.timeout.connect(lambda p=str(f): self._crop_when_stable(p))
            self._pending[str(f)] = timer
        timer.start(STABILITY_MS)

    # ================= ОБРЕЗКА =================
    def _crop_when_stable(self, path_str):
        """Запись завершена — одна попытка обрезки, результат запоминаем."""
        self._pending.pop(path_str, None)
        f = Path(path_str)
        try:
            mtime = f.stat().st_mtime
        except Exception:
            return
        if self._done.get(path_str) == mtime:
            return
        try:
            from utils.image_autocrop import autocrop_file, get_autocrop_settings
            st = get_autocrop_settings()
            if not st['enabled']:
                self._done[path_str] = mtime
                return
            if autocrop_file(f, margin_mm=st['margin_mm'],
                             threshold=st['threshold']):
                try:
                    self._done[path_str] = f.stat().st_mtime
                except Exception:
                    self._done[path_str] = mtime
                logger.info(f"✂️ Скан обрезан автоматически: {f.name}")
                self._refresh_open_scan_dialogs()
            else:
                # Обрезать нечего — запоминаем, больше не пытаемся
                self._done[path_str] = mtime
                logger.debug(f"✂️ Обрезка не требуется: {f.name}")
        except Exception as e:
            logger.debug(f"_crop_when_stable: {e}")
            try:
                self._done[path_str] = f.stat().st_mtime
            except Exception:
                pass

    # ================= ОБНОВЛЕНИЕ ДИАЛОГА СКАНИРОВАНИЯ =================
    def _refresh_open_scan_dialogs(self):
        """Best-effort: если открыт диалог сканирования — обновляем превью/
        список, чтобы сразу был виден обрезанный кадр."""
        try:
            for w in QApplication.topLevelWidgets():
                title = w.windowTitle() or ''
                if not ('Скан' in title or 'скан' in title or 'Scan' in title):
                    continue
                for name in ('refresh', 'reload', 'update_preview',
                             '_update_preview', 'load_data', '_load_data',
                             'refresh_data', '_refresh_data',
                             'update_list', '_update_list',
                             '_show_selected', 'show_image', '_show_image'):
                    fn = getattr(w, name, None)
                    if callable(fn):
                        try:
                            fn()
                            return
                        except Exception:
                            continue
                lists = w.findChildren(QListWidget)
                if lists:
                    lw = lists[0]
                    row = lw.currentRow()
                    if row >= 0:
                        lw.currentRowChanged.emit(row)
        except Exception:
            pass