# -*- coding: utf-8 -*-
"""
Автообрезка сканов листов сделки (двухэтапная, адаптивная).
Этап 1: обрезаем почти ЧЁРНЫЕ края (пустое поле сканера).
Этап 2: на листе ищем bounding box СОДЕРЖИМОГО. Порог белизны
        АДАПТИВНЫЙ: яркость бумаги = 90-й перцентиль яркости листа,
        контент = пиксели темнее (бумага − 25). Работает и на белых
        (250), и на серых (200–230) сканах бумаги.
Затем отступ margin_mm (по умолчанию 5 мм) по DPI скана, обрезка
оригинала и сохранение поверх файла.
Флаг _SAVING защищает глобальный перехват QImage.save от собственной
перезаписи файла при обрезке.
"""
import logging
import sys
from pathlib import Path
from PySide6.QtGui import QImage, qGray
from PySide6.QtCore import Qt, QRect

logger = logging.getLogger('CoinCollector.Utils.AutoCrop')

# Максимальный порог белизны (абсолютный потолок)
DEFAULT_THRESHOLD = 235
# Пиксель темнее этого = чёрный фон пустого сканера
BLACK_THRESHOLD = 40
# Доля чёрных пикселей в строке/колонке для считания чёрной границей
BLACK_LINE_FRACTION = 0.85
# Ширина уменьшенной копии для анализа (px)
ANALYZE_WIDTH = 200
# Не обрезаем, если экономится меньше этой доли площади
MIN_CROP_GAIN = 0.03
# Не обрезаем, если контент меньше этой доли (пустой лист)
MIN_CONTENT_AREA = 0.005
# Игнорируем внешнюю рамку при поиске контента (тени, остатки чёрного)
BORDER_SKIP = 0.02
# Квантиль яркости, считающийся фоном бумаги
BG_PERCENTILE = 0.90
# Насколько темнее бумаги должен быть пиксель, чтобы считаться контентом
BG_GAP = 25

# === ФЛАГ ВНУТРЕННЕГО СОХРАНЕНИЯ ===
# Пока он True, глобальный перехват QImage.save/QPixmap.save пропускает
# событие (иначе обрезка триггерит сама себя).
_SAVING = False


def get_autocrop_settings():
    """Читает настройки автообрезки из ConfigDB
    (ключ 'scan_autocrop_settings'). По умолчанию включена, +5 мм."""
    try:
        from database.config_db import get_config_db
        data = get_config_db().get('scan_autocrop_settings') or {}
        return {
            'enabled': bool(data.get('enabled', True)),
            'margin_mm': float(data.get('margin_mm', 5.0)),
            'threshold': int(data.get('threshold', DEFAULT_THRESHOLD)),
        }
    except Exception:
        return {'enabled': True, 'margin_mm': 5.0,
                'threshold': DEFAULT_THRESHOLD}


def set_autocrop_settings(enabled=None, margin_mm=None, threshold=None):
    """Сохраняет настройки автообрезки в ConfigDB."""
    try:
        from database.config_db import get_config_db
        cur = get_autocrop_settings()
        if enabled is not None:
            cur['enabled'] = bool(enabled)
        if margin_mm is not None:
            cur['margin_mm'] = float(margin_mm)
        if threshold is not None:
            cur['threshold'] = int(threshold)
        get_config_db().set('scan_autocrop_settings', cur, 'ui')
        return True
    except Exception as e:
        logger.error(f"Ошибка сохранения настроек автообрезки: {e}")
        return False


def _estimate_dpi(img, dpi=None):
    """Оценивает DPI скана: явно заданный или по формату листа A4."""
    if dpi:
        return float(dpi)
    w = img.width()
    h = img.height()
    if w <= 0 or h <= 0:
        return 300.0
    ratio = w / h
    if 0.65 <= ratio <= 0.76:      # A4 портрет (210×297 мм)
        mm_width = 210.0
    elif 1.30 <= ratio <= 1.55:    # A4 ландшафт
        mm_width = 297.0
    else:
        return 300.0
    return w / mm_width * 25.4


def _to_analysis_image(img):
    """Уменьшенная копия для быстрого анализа + коэффициент масштаба."""
    w = img.width()
    target = max(32, int(w * min(1.0, ANALYZE_WIDTH / float(w))))
    if target < w:
        small = img.scaledToWidth(target, Qt.SmoothTransformation)
        return small, w / float(small.width())
    return img, 1.0


def _paper_background(small, x0, y0, x1, y1):
    """Яркость бумаги = 90-й перцентиль яркости в области листа.
    Сканы бумаги бывают и 250, и 200–230 серого — фиксированный порог
    235 на таких сканах считал весь лист контентом."""
    vals = []
    step_x = max(1, (x1 - x0) // 40)
    step_y = max(1, (y1 - y0) // 40)
    for y in range(y0, y1, step_y):
        for x in range(x0, x1, step_x):
            vals.append(qGray(small.pixel(x, y)))
    if not vals:
        return DEFAULT_THRESHOLD
    vals.sort()
    idx = min(len(vals) - 1, int(len(vals) * BG_PERCENTILE))
    return vals[idx]


def detect_content_rect(img, threshold=DEFAULT_THRESHOLD,
                        black_threshold=BLACK_THRESHOLD):
    """Возвращает QRect области ЗАПОЛНЕННОГО контента В ОРИГИНАЛЬНЫХ
    координатах (без отступа) или None, если контента нет."""
    if img is None or img.isNull():
        return None
    w, h = img.width(), img.height()
    small, factor = _to_analysis_image(img)
    sw, sh = small.width(), small.height()

    def gray(x, y):
        return qGray(small.pixel(x, y))

    def row_black_frac(y):
        cnt = 0
        for x in range(sw):
            if gray(x, y) < black_threshold:
                cnt += 1
        return cnt / float(sw)

    def col_black_frac(x, ya, yb):
        n = max(1, yb - ya)
        cnt = 0
        for y in range(ya, yb):
            if gray(x, y) < black_threshold:
                cnt += 1
        return cnt / float(n)

    # === ЭТАП 1: обрезаем почти чёрные границы (пустой сканер) ===
    y0, y1 = 0, sh
    while y0 < y1 and row_black_frac(y0) > BLACK_LINE_FRACTION:
        y0 += 1
    while y1 > y0 and row_black_frac(y1 - 1) > BLACK_LINE_FRACTION:
        y1 -= 1
    x0, x1 = 0, sw
    while x0 < x1 and col_black_frac(x0, y0, y1) > BLACK_LINE_FRACTION:
        x0 += 1
    while x1 > x0 and col_black_frac(x1 - 1, y0, y1) > BLACK_LINE_FRACTION:
        x1 -= 1
    trimmed = (x0 > 0 or y0 > 0 or x1 < sw or y1 < sh)
    bw, bh = x1 - x0, y1 - y0
    if bw <= 4 or bh <= 4:
        return None

    # === АДАПТИВНЫЙ ПОРОГ: яркость бумаги минус зазор ===
    bg = _paper_background(small, x0, y0, x1, y1)
    thr = min(threshold, bg - BG_GAP)
    thr = max(thr, 60)

    # === ЭТАП 2: bbox контента (темнее адаптивного порога) ===
    bx = max(1, int(bw * BORDER_SKIP))
    by = max(1, int(bh * BORDER_SKIP))
    min_x, min_y = x1, y1
    max_x, max_y = x0 - 1, y0 - 1
    for y in range(y0 + by, y1 - by):
        for x in range(x0 + bx, x1 - bx):
            g = gray(x, y)
            if g < thr and g >= black_threshold:
                if x < min_x:
                    min_x = x
                if x > max_x:
                    max_x = x
                if y < min_y:
                    min_y = y
                if y > max_y:
                    max_y = y
    if max_x < min_x or max_y < min_y:
        if trimmed:
            return QRect(int(x0 * factor), int(y0 * factor),
                         int(bw * factor), int(bh * factor))
        return None
    return QRect(int(min_x * factor), int(min_y * factor),
                 int((max_x - min_x + 1) * factor),
                 int((max_y - min_y + 1) * factor))


def autocrop_qimage(img, margin_mm=5.0, dpi=None,
                    threshold=DEFAULT_THRESHOLD):
    """Возвращает обрезанный QImage (контент + margin_mm по краям).
    Если обрезать нечего — возвращает исходный объект."""
    if img is None or img.isNull():
        return img
    content = detect_content_rect(img, threshold)
    if content is None:
        return img
    orig = QRect(0, 0, img.width(), img.height())
    if content.width() * content.height() >= \
            orig.width() * orig.height() * (1.0 - MIN_CROP_GAIN):
        return img
    if content.width() * content.height() < \
            orig.width() * orig.height() * MIN_CONTENT_AREA:
        return img
    dpi_est = _estimate_dpi(img, dpi)
    margin_px = int(round(margin_mm / 25.4 * dpi_est))
    crop = content.adjusted(-margin_px, -margin_px, margin_px, margin_px)
    crop = crop.intersected(orig)
    if crop.width() < 10 or crop.height() < 10:
        return img
    return img.copy(crop)


def autocrop_file(path, margin_mm=5.0, dpi=None, threshold=DEFAULT_THRESHOLD):
    """Обрезает скан ПОВЕРХ исходного файла.
    True — файл обрезан и сохранён. На время сохранения ставится флаг
    _SAVING, чтобы глобальный перехват QImage.save не реагировал
    на собственную перезапись файла."""
    global _SAVING
    path = Path(path)
    if not path.exists():
        return False
    img = QImage(str(path))
    if img.isNull():
        return False
    cropped = autocrop_qimage(img, margin_mm=margin_mm,
                              dpi=dpi, threshold=threshold)
    if cropped is img or (cropped.width() == img.width()
                          and cropped.height() == img.height()):
        return False
    suffix = path.suffix.lower().lstrip('.')
    _SAVING = True
    try:
        if suffix in ('jpg', 'jpeg'):
            ok = cropped.save(str(path), 'JPG', 95)
        elif suffix == 'png':
            ok = cropped.save(str(path), 'PNG')
        else:
            ok = cropped.save(str(path))
    finally:
        _SAVING = False
    if ok:
        logger.info(f"✂️ Автообрезка: {path.name} "
                    f"{img.width()}x{img.height()} → "
                    f"{cropped.width()}x{cropped.height()} "
                    f"(+{margin_mm:.0f} мм)")
    return bool(ok)


if __name__ == '__main__':
    # Тест из консоли: python -m utils.image_autocrop file1.jpg file2.png
    logging.basicConfig(level=logging.INFO)
    for arg in sys.argv[1:]:
        res = autocrop_file(arg)
        print(f"{arg}: {'обрезан' if res else 'без изменений'}")