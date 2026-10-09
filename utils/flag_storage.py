# -*- coding: utf-8 -*-
"""
Хранилище флагов стран.
Основной путь:  data/country_flags/{country_id}.png
Резервный путь: data/custom_images/country_{country_id}_flag.png
"""
import logging
from pathlib import Path
from PySide6.QtGui import QPixmap, QIcon
from PySide6.QtCore import Qt
from utils.paths import paths

logger = logging.getLogger('CoinCollector.Flags')


def flags_dir() -> Path:
    d = paths.get_data_dir() / "country_flags"
    d.mkdir(parents=True, exist_ok=True)
    return d


def main_flag_path(country_id) -> Path:
    return flags_dir() / f"{country_id}.png"


def legacy_flag_path(country_id) -> Path:
    return paths.get_data_dir() / "custom_images" / f"country_{country_id}_flag.png"


def find_flag_path(country_id):
    """Возвращает путь к существующему флагу или None"""
    if not country_id:
        return None
    for p in (main_flag_path(country_id), legacy_flag_path(country_id)):
        try:
            if p.exists():
                return p
        except Exception:
            continue
    return None


def has_flag(country_id) -> bool:
    return find_flag_path(country_id) is not None


def save_flag_from_file(country_id, source_path) -> bool:
    """Сохраняет флаг В ОБА хранилища (основное + резервное)"""
    try:
        src = Path(source_path)
        if not src.exists():
            logger.error(f"❌ Файл не найден: {src}")
            return False
        pix = QPixmap(str(src))
        if pix.isNull():
            logger.error(f"❌ Не удалось декодировать изображение: {src}")
            return False
        ok1 = pix.save(str(main_flag_path(country_id)), "PNG")
        ok2 = pix.save(str(legacy_flag_path(country_id)), "PNG")
        if ok1 or ok2:
            logger.info(f"✅ Флаг сохранён для страны {country_id}")
            return True
        logger.error("❌ Не удалось записать файл флага")
        return False
    except Exception as e:
        logger.error(f"❌ Ошибка сохранения флага: {e}")
        return False


def pick_and_save_flag(parent_widget, country_id) -> bool:
    from PySide6.QtWidgets import QFileDialog, QMessageBox
    path, _ = QFileDialog.getOpenFileName(
        parent_widget, "Выберите файл флага", str(Path.home()),
        "Изображения (*.png *.jpg *.jpeg *.webp *.bmp *.gif);;Все файлы (*)")
    if not path:
        return False
    ok = save_flag_from_file(country_id, path)
    if not ok:
        QMessageBox.warning(parent_widget, "Флаг страны",
                            "Не удалось сохранить флаг.\nПодробности — в логе.")
    return ok


def load_pixmap(country_id, width=None, height=None):
    p = find_flag_path(country_id)
    if p is None:
        return None
    pix = QPixmap(str(p))
    if pix.isNull():
        return None
    if width or height:
        pix = pix.scaled(width or 999, height or 999,
                         Qt.KeepAspectRatio, Qt.SmoothTransformation)
    return pix


def load_icon(country_id, width=20, height=14):
    pix = load_pixmap(country_id, width, height)
    return QIcon(pix) if pix else None