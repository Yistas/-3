# -*- coding: utf-8 -*-
"""
ГЛОБАЛЬНЫЙ перехват сохранения изображений для автообрезки.
Патчит QImage.save и QPixmap.save один раз при старте программы:
если путь файла попадает в отслеживаемые папки (data/, scans/, temp/,
coin_images/, deal_scans/) — сохранённое изображение автоматически
обрезается по контенту + 5 мм.

Покрытие 100%: срабатывает независимо от того, из какого метода/диалога
сохраняется скан (coin_scanner, deals_tab, exchange_browser и т.д.).
"""
import logging
from pathlib import Path

logger = logging.getLogger('CoinCollector.Utils.GlobalAutoCrop')

_INSTALLED = False


def _tracked_folders():
    """Набор отслеживаемых папок (нормализованные абсолютные пути)."""
    folders = set()
    try:
        from utils.paths import paths_instance as paths
        for d in (paths.get_data_dir(),
                  paths.get_data_dir() / 'scans',
                  paths.get_data_dir() / 'coin_images',
                  paths.get_data_dir() / 'deal_scans',
                  paths.get_data_dir() / 'temp',
                  paths.get_root_dir() / 'scans'):
            try:
                folders.add(str(Path(d).resolve()))
            except Exception:
                pass
    except Exception:
        pass
    try:
        from PySide6.QtCore import QDir
        folders.add(str(Path(QDir.tempPath()).resolve()))
    except Exception:
        pass
    return folders


def _is_tracked(path_str):
    """Путь находится в одной из отслеживаемых папок?"""
    try:
        p = Path(path_str).resolve()
    except Exception:
        return False
    ps = str(p)
    for folder in _tracked_folders():
        if ps.startswith(folder):
            return True
    return False


def install_global_autocrop():
    """Устанавливает перехват QImage.save / QPixmap.save.
    Идемпотентна — повторные вызовы ничего не делают."""
    global _INSTALLED
    if _INSTALLED:
        return
    try:
        from PySide6.QtGui import QImage, QPixmap
    except Exception as e:
        logger.warning(f"Не удалось импортировать QImage/QPixmap: {e}")
        return

    _orig_image_save = QImage.save
    _orig_pixmap_save = QPixmap.save

    def _patched_image_save(self, *args, **kwargs):
        ok = _orig_image_save(self, *args, **kwargs)
        if ok and args:
            _maybe_autocrop(args[0])
        return ok

    def _patched_pixmap_save(self, *args, **kwargs):
        ok = _orig_pixmap_save(self, *args, **kwargs)
        if ok and args:
            _maybe_autocrop(args[0])
        return ok

    QImage.save = _patched_image_save
    QPixmap.save = _patched_pixmap_save
    _INSTALLED = True
    logger.info("✂️ Глобальный перехват QImage.save/QPixmap.save установлен")


def _maybe_autocrop(path_arg):
    """Проверяет путь и запускает автообрезку, если он в отслеживаемых
    папках. ПРОПУСКАЕТ сохранение, выполненное самой автообрезкой
    (флаг image_autocrop._SAVING) — иначе обрезка триггерит сама себя."""
    try:
        if isinstance(path_arg, (str, Path)):
            path_str = str(path_arg)
        else:
            return
        try:
            from utils import image_autocrop
            if getattr(image_autocrop, '_SAVING', False):
                return
        except Exception:
            pass
        if not _is_tracked(path_str):
            return
        from PySide6.QtCore import QTimer
        QTimer.singleShot(150, lambda p=path_str: _do_autocrop(p))
    except Exception as e:
        logger.debug(f"maybe_autocrop: {e}")


def _do_autocrop(path_str):
    try:
        from utils import image_autocrop
        if getattr(image_autocrop, '_SAVING', False):
            return
        from utils.image_autocrop import autocrop_file, get_autocrop_settings
        st = get_autocrop_settings()
        if not st['enabled']:
            return
        if autocrop_file(path_str, margin_mm=st['margin_mm'],
                         threshold=st['threshold']):
            logger.info(f"✂️ Автообрезка (глобальный перехват): {path_str}")
    except Exception as e:
        logger.debug(f"_do_autocrop: {e}")