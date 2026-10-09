# -*- coding: utf-8 -*-
"""
Основная логика печати этикеток холдеров.

ИСПРАВЛЕНО:
1) Шрифт корректно масштабируется: рендер идёт НАПРЯМУЮ в пикселях
   устройства печати (без painter.scale()), шрифт подбирается через
   setPixelSize(базовые_пункты * k) — QFontMetrics совпадает с тем,
   что реально рисуется. Раньше пункты шрифта разрешались в DPI
   принтера И умножались на scale_factor → текст в ~4 раза крупнее.
2) Слово "ПЕРИОД:" больше не дублируется (убрано из строки № в модели).
"""
import logging
import math
from typing import List
from PySide6.QtCore import Qt, QRectF
from PySide6.QtGui import (QPainter, QColor, QFont, QPen, QFontMetricsF,
                           QPageSize, QPageLayout)
from PySide6.QtPrintSupport import QPrinter, QPrintDialog, QPrintPreviewDialog
from database.models import Coin
from .holder_label_model import HolderLabelData


class HolderLabelPrinter:
    """Класс для печати этикеток холдеров"""

    # Размеры в миллиметрах
    PAGE_WIDTH_MM = 210.0
    PAGE_HEIGHT_MM = 297.0
    HOLDER_WIDTH_MM = 50.0
    HOLDER_HEIGHT_MM = 50.0
    MARGIN_LEFT_MM = 10.0
    MARGIN_TOP_MM = 10.0
    MARGIN_RIGHT_MM = 10.0
    MARGIN_BOTTOM_MM = 10.0
    GAP_X_MM = 5.0
    GAP_Y_MM = 5.0
    COLS = 3
    ROWS = 4
    PER_PAGE = COLS * ROWS

    # Высота секций в мм
    TOP_SECTION_HEIGHT_MM = 8.0
    BOTTOM_SECTION_HEIGHT_MM = 8.0
    GAP_HEIGHT_MM = 2.0

    # Базовое DPI для расчётов (PostScript points: 72 DPI)
    BASE_DPI = 72.0
    MM_TO_POINTS = BASE_DPI / 25.4

    def __init__(self, parent=None):
        self.logger = logging.getLogger('CoinCollector.HolderLabelPrinter')
        self.parent = parent

    def mm_to_points(self, mm: float) -> float:
        """Переводит миллиметры в базовые пункты (72 DPI)"""
        return mm * self.MM_TO_POINTS

    def _get_scale_factor(self, printer: QPrinter) -> float:
        """Коэффициент: базовые пункты (72 DPI) → пиксели устройства."""
        dpi = printer.resolution()
        if dpi <= 0:
            dpi = self.BASE_DPI
        return dpi / self.BASE_DPI

    def _get_page_size(self) -> tuple:
        """Размер страницы A4 в базовых пунктах (72 DPI)."""
        return (self.mm_to_points(self.PAGE_WIDTH_MM),
                self.mm_to_points(self.PAGE_HEIGHT_MM))

    def _get_printer(self) -> QPrinter:
        """Создает и настраивает принтер для печати"""
        printer = QPrinter(QPrinter.HighResolution)
        page_size = QPageSize(QPageSize.A4)
        printer.setPageSize(page_size)
        printer.setPageOrientation(QPageLayout.Orientation.Portrait)
        printer.setFullPage(True)
        printer.setResolution(300)
        return printer

    # ================= ПОДБОР ШРИФТА =================
    def _fit_font(self, text, rect_dev, k, bold=False, min_pt=4, max_pt=24):
        """Подбирает шрифт, чтобы текст поместился в rect_dev
        (прямоугольник в ПИКСЕЛЯХ устройства).
        k — коэффициент базовые пункты → пиксели устройства.
        Метрики и отрисовка совпадают, т.к. трансформации painter нет."""
        font = QFont("Arial")
        font.setBold(bold)
        if not text:
            font.setPixelSize(max(1, int(round(min_pt * k))))
            return font
        for size_pt in range(max_pt, min_pt - 1, -1):
            font.setPixelSize(max(1, int(round(size_pt * k))))
            fm = QFontMetricsF(font)
            if (fm.horizontalAdvance(text) <= rect_dev.width()
                    and fm.height() <= rect_dev.height()):
                return font
        font.setPixelSize(max(1, int(round(min_pt * k))))
        return font

    # ================= ЭТИКЕТКА =================
    def _draw_label(self, painter, label_data, rect, k):
        """Рисует одну этикетку. rect — в пикселях устройства;
        k — коэффициент базовые пункты → пиксели."""
        # Толстый контур холдера
        painter.setPen(QPen(QColor(0, 0, 0), max(1.0, 1.5 * k)))
        painter.drawRect(rect)

        top_height = self.mm_to_points(self.TOP_SECTION_HEIGHT_MM) * k
        gap_height = self.mm_to_points(self.GAP_HEIGHT_MM) * k
        bottom_height = self.mm_to_points(self.BOTTOM_SECTION_HEIGHT_MM) * k

        top_rect = QRectF(rect.x(), rect.y(), rect.width(), top_height)
        gap_rect = QRectF(rect.x(), rect.y() + top_height,
                          rect.width(), gap_height)
        bottom_rect = QRectF(
            rect.x(), rect.y() + rect.height() - bottom_height,
            rect.width(), bottom_height)

        thin_pen = QPen(QColor(0, 0, 0), max(1.0, 1.0 * k))

        # === ВЕРХНЯЯ ЧАСТЬ ===
        painter.setPen(thin_pen)
        painter.drawRect(top_rect)
        painter.fillRect(top_rect, QColor(248, 248, 248))
        padding = 1.0 * k
        half_height = top_height / 2.0
        line1 = label_data.get_top_line1()
        if line1:
            r1 = QRectF(top_rect.x() + padding, top_rect.y() + padding,
                        top_rect.width() - 2 * padding,
                        half_height - 2 * padding)
            painter.setFont(self._fit_font(line1, r1, k, bold=True))
            painter.setPen(QColor(0, 0, 0))
            painter.drawText(r1, Qt.AlignCenter, line1)
        line2 = label_data.get_top_line2()
        if line2:
            r2 = QRectF(top_rect.x() + padding,
                        top_rect.y() + half_height + padding,
                        top_rect.width() - 2 * padding,
                        half_height - 2 * padding)
            painter.setFont(self._fit_font(line2, r2, k, bold=False))
            painter.setPen(QColor(0, 0, 0))
            painter.drawText(r2, Qt.AlignCenter, line2)

        # === БЕЛАЯ ПОЛОСА ===
        painter.fillRect(gap_rect, QColor(255, 255, 255))
        painter.setPen(QPen(QColor(180, 180, 180),
                            max(1.0, 0.5 * k), Qt.DashLine))
        mid_y = gap_rect.y() + gap_rect.height() / 2.0
        painter.drawLine(int(gap_rect.x() + 3 * k), int(mid_y),
                         int(gap_rect.x() + gap_rect.width() - 3 * k),
                         int(mid_y))

        # === НИЖНЯЯ ЧАСТЬ ===
        painter.setPen(thin_pen)
        painter.drawRect(bottom_rect)
        painter.fillRect(bottom_rect, QColor(248, 248, 248))
        padding_bottom = 1.0 * k
        half_bottom = bottom_height / 2.0
        number_text = label_data.get_bottom_line1()   # теперь только "№: …"
        period_label = "ПЕРИОД:"
        if number_text:
            r_num = QRectF(bottom_rect.x() + padding_bottom,
                           bottom_rect.y() + padding_bottom,
                           bottom_rect.width() / 2.0 - padding_bottom,
                           half_bottom - 2 * padding_bottom)
            painter.setFont(self._fit_font(number_text, r_num, k, bold=True))
            painter.setPen(QColor(0, 0, 0))
            painter.drawText(r_num, Qt.AlignLeft | Qt.AlignVCenter, number_text)
            r_period_label = QRectF(
                bottom_rect.x() + bottom_rect.width() / 2.0,
                bottom_rect.y() + padding_bottom,
                bottom_rect.width() / 2.0 - padding_bottom,
                half_bottom - 2 * padding_bottom)
            painter.setFont(self._fit_font(period_label, r_period_label,
                                           k, bold=True))
            painter.setPen(QColor(0, 0, 0))
            painter.drawText(r_period_label,
                             Qt.AlignRight | Qt.AlignVCenter, period_label)
        period_text = label_data.get_bottom_line2()
        if period_text:
            r_period = QRectF(bottom_rect.x() + padding_bottom,
                              bottom_rect.y() + half_bottom + padding_bottom,
                              bottom_rect.width() - 2 * padding_bottom,
                              half_bottom - 2 * padding_bottom)
            painter.setFont(self._fit_font(period_text, r_period, k,
                                           bold=False))
            painter.setPen(QColor(0, 0, 0))
            painter.drawText(r_period, Qt.AlignCenter, period_text)

    # ================= СТРАНИЦА =================
    def _render_page(self, painter, labels, page_width_dev, page_height_dev,
                     k, y_offset_dev=0.0):
        """Рендерит страницу НАПРЯМУЮ в пикселях устройства (без scale).
        page_width_dev/page_height_dev — размер страницы в пикселях;
        k — коэффициент базовые пункты → пиксели;
        y_offset_dev — вертикальное смещение (для многостраничного превью)."""
        painter.save()
        painter.translate(0, int(y_offset_dev))
        painter.fillRect(0, 0, int(page_width_dev), int(page_height_dev),
                         QColor(255, 255, 255))

        offset_x = self.mm_to_points(self.MARGIN_LEFT_MM) * k
        offset_y = self.mm_to_points(self.MARGIN_TOP_MM) * k
        gap_x = self.mm_to_points(self.GAP_X_MM) * k
        gap_y = self.mm_to_points(self.GAP_Y_MM) * k
        holder_w = self.mm_to_points(self.HOLDER_WIDTH_MM) * k
        holder_h = self.mm_to_points(self.HOLDER_HEIGHT_MM) * k

        # Линии для разрезания (пунктир, серый)
        painter.setPen(QPen(QColor(180, 180, 180),
                            max(1.0, 0.5 * k), Qt.DashLine))
        for col in range(1, self.COLS):
            x = int(offset_x + col * (holder_w + gap_x) - gap_x / 2.0)
            y_top = int(offset_y)
            y_bottom = int(offset_y + self.ROWS * (holder_h + gap_y) - gap_y)
            painter.drawLine(x, y_top, x, y_bottom)
        for row in range(1, self.ROWS):
            y = int(offset_y + row * (holder_h + gap_y) - gap_y / 2.0)
            x_left = int(offset_x)
            x_right = int(offset_x + self.COLS * (holder_w + gap_x) - gap_x)
            painter.drawLine(x_left, y, x_right, y)

        # Холдеры
        for idx, label_data in enumerate(labels):
            row = idx // self.COLS
            col = idx % self.COLS
            x = offset_x + col * (holder_w + gap_x)
            y = offset_y + row * (holder_h + gap_y)
            rect = QRectF(x, y, holder_w, holder_h)
            self._draw_label(painter, label_data, rect, k)
        painter.restore()

    # ================= ПЕЧАТЬ / ПРЕДПРОСМОТР =================
    def print_labels(self, coins: List[Coin], show_dialog: bool = True) -> bool:
        """Печатает этикетки для списка монет"""
        if not coins:
            self.logger.warning("Нет монет для печати")
            return False
        labels = HolderLabelData.from_coins(coins)
        if not labels:
            self.logger.warning("Нет данных для печати")
            return False
        printer = self._get_printer()
        if show_dialog:
            dialog = QPrintDialog(printer, self.parent)
            if dialog.exec() != QPrintDialog.Accepted:
                return False
        pages = math.ceil(len(labels) / self.PER_PAGE)
        painter = QPainter()
        if not painter.begin(printer):
            self.logger.error("Не удалось начать печать")
            return False
        try:
            k = self._get_scale_factor(printer)
            page_w_pt, page_h_pt = self._get_page_size()
            page_w_dev = page_w_pt * k
            page_h_dev = page_h_pt * k
            for page_num in range(pages):
                if page_num > 0:
                    printer.newPage()
                start_idx = page_num * self.PER_PAGE
                end_idx = min(start_idx + self.PER_PAGE, len(labels))
                page_labels = labels[start_idx:end_idx]
                self._render_page(painter, page_labels,
                                  page_w_dev, page_h_dev, k)
            painter.end()
            self.logger.info(
                f"✅ Напечатано {len(labels)} этикеток на {pages} страницах")
            return True
        except Exception as e:
            painter.end()
            self.logger.error(f"Ошибка печати: {e}")
            raise

    def preview_labels(self, coins: List[Coin]) -> bool:
        """Открывает диалог предпросмотра перед печатью"""
        if not coins:
            return False
        labels = HolderLabelData.from_coins(coins)
        if not labels:
            return False
        printer = self._get_printer()
        preview = QPrintPreviewDialog(printer, self.parent)

        def render_preview(printer_obj):
            painter = QPainter()
            if not painter.begin(printer_obj):
                return
            try:
                k = self._get_scale_factor(printer_obj)
                page_w_pt, page_h_pt = self._get_page_size()
                page_w_dev = page_w_pt * k
                page_h_dev = page_h_pt * k
                pages = math.ceil(len(labels) / self.PER_PAGE)
                for page_num in range(pages):
                    if page_num > 0:
                        printer_obj.newPage()
                    start_idx = page_num * self.PER_PAGE
                    end_idx = min(start_idx + self.PER_PAGE, len(labels))
                    page_labels = labels[start_idx:end_idx]
                    self._render_page(painter, page_labels,
                                      page_w_dev, page_h_dev, k)
                painter.end()
            except Exception as e:
                painter.end()
                self.logger.error(f"Ошибка рендеринга предпросмотра: {e}")
                raise

        preview.paintRequested.connect(render_preview)
        return preview.exec() == QPrintPreviewDialog.Accepted