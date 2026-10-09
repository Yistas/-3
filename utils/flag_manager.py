# -*- coding: utf-8 -*-
"""
Менеджер флагов стран.
Флаг загружается из любого места на диске, сохраняется в
data/country_flags/{country_id}.png и используется в дереве стран,
главной таблице и информации о стране.
"""
import logging
from pathlib import Path

from PySide6.QtGui import QIcon, QPixmap
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFileDialog

from utils.paths import paths


class FlagManager:
    """Синглтон: единая точка работы с флагами"""
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return
        self._initialized = True
        self.logger = logging.getLogger('CoinCollector.Flags')
        self.flags_dir = paths.get_data_dir() / "country_flags"
        self.flags_dir.mkdir(parents=True, exist_ok=True)
        self._icon_cache = {}

    # ------------------------------------------------------------------ пути
    def flag_path(self, country_id):
        """Путь к файлу флага страны: data/country_flags/{id}.png"""
        return self.flags_dir / f"{country_id}.png"

    def has_flag(self, country_id):
        """Есть ли сохранённый флаг у страны"""
        return bool(country_id) and self.flag_path(country_id).exists()

    # ------------------------------------------------------------ сохранение
    def save_flag_from_file(self, country_id, source_path):
        """Копирует изображение из любого места в data/country_flags/{id}.png"""
        try:
            src = Path(source_path)
            if not src.exists():
                self.logger.warning(f"⚠️ Файл не найден: {src}")
                return False
            pixmap = QPixmap(str(src))
            if pixmap.isNull():
                self.logger.warning(f"⚠️ Не удалось прочитать изображение: {src}")
                return False
            ok = pixmap.save(str(self.flag_path(country_id)), "PNG")
            if ok:
                # сбрасываем кэш иконок этой страны
                self._icon_cache = {
                    k: v for k, v in self._icon_cache.items() if k[0] != country_id
                }
                self.logger.info(f"🏳️ Флаг сохранён: {self.flag_path(country_id)}")
            return ok
        except Exception as e:
            self.logger.error(f"Ошибка сохранения флага: {e}")
            return False

    def pick_and_save_flag(self, parent, country_id):
        """Диалог выбора файла флага + сохранение. Возвращает True при успехе."""
        path, _ = QFileDialog.getOpenFileName(
            parent, "Выберите файл флага", str(self.flags_dir),
            "Изображения (*.png *.jpg *.jpeg *.webp *.bmp *.gif);;Все файлы (*)")
        if not path:
            return False
        return self.save_flag_from_file(country_id, path)

    # ------------------------------------------------------------ чтение
    def get_icon(self, country_id, width=20, height=14):
        """QIcon флага страны (масштабированный, с кэшем). None, если флага нет."""
        if not self.has_flag(country_id):
            return None
        key = (country_id, width, height)
        if key in self._icon_cache:
            return self._icon_cache[key]
        pixmap = QPixmap(str(self.flag_path(country_id)))
        if pixmap.isNull():
            return None
        icon = QIcon(pixmap.scaled(width, height,
                                   Qt.KeepAspectRatio, Qt.SmoothTransformation))
        self._icon_cache[key] = icon
        return icon

    def get_pixmap(self, country_id, width=60, height=40):
        """QPixmap флага страны для карточки. None, если флага нет."""
        if not self.has_flag(country_id):
            return None
        pixmap = QPixmap(str(self.flag_path(country_id)))
        if pixmap.isNull():
            return None
        return pixmap.scaled(width, height,
                             Qt.KeepAspectRatio, Qt.SmoothTransformation)


flag_manager = FlagManager()