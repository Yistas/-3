# -*- coding: utf-8 -*-
"""
Диалог предпросмотра этикеток перед печатью.
Предпросмотр рисует ТОТ ЖЕ код, что и печать
(HolderLabelPrinter._render_page), поэтому вид на экране совпадает
с результатом на бумаге; дублирующий код отрисовки удалён.
"""
import logging
import math
from typing import List
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QPushButton,
    QLabel, QScrollArea, QMessageBox
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap, QPainter, QColor
from database.models import Coin
from .holder_label_model import HolderLabelData
from .holder_label_printer import HolderLabelPrinter


class HolderLabelPreviewDialog(QDialog):
    """Диалог предпросмотра этикеток перед печатью"""

    def __init__(self, coins: List[Coin], parent=None):
        super().__init__(parent)
        self.logger = logging.getLogger(
            'CoinCollector.HolderLabelPreviewDialog')
        self.coins = coins
        self.labels_data = HolderLabelData.from_coins(coins)
        self.setWindowTitle("Предпросмотр этикеток холдеров")
        self.setMinimumSize(900, 700)
        self.init_ui()
        self.render_preview()

    def init_ui(self):
        """Инициализация интерфейса"""
        layout = QVBoxLayout()
        self.setLayout(layout)
        info_label = QLabel(
            f"📋 Подготовлено этикеток: {len(self.labels_data)} | "
            f"Страниц: {self._calc_pages()}"
        )
        info_label.setStyleSheet("padding: 8px; font-weight: bold;")
        layout.addWidget(info_label)
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setAlignment(Qt.AlignCenter)
        # Отслеживаем изменение размера для пересчёта масштаба
        self.scroll_area.resizeEvent = self._on_scroll_resize
        self.preview_label = QLabel()
        self.preview_label.setAlignment(Qt.AlignCenter)
        self.preview_label.setMinimumSize(600, 800)
        self.preview_label.setStyleSheet(
            "background-color: white; border: 1px solid #ccc;")
        self.scroll_area.setWidget(self.preview_label)
        layout.addWidget(self.scroll_area)
        button_layout = QHBoxLayout()
        self.print_btn = QPushButton("🖨️ Печать с предпросмотром")
        self.print_btn.clicked.connect(self.print_with_preview)
        self.print_btn.setMinimumHeight(35)
        self.print_btn.setStyleSheet(
            "background-color: #4CAF50; color: white; font-weight: bold;")
        self.print_direct_btn = QPushButton("⚡ Печать без предпросмотра")
        self.print_direct_btn.clicked.connect(self.print_direct)
        self.print_direct_btn.setMinimumHeight(35)
        self.cancel_btn = QPushButton("❌ Отмена")
        self.cancel_btn.clicked.connect(self.reject)
        self.cancel_btn.setMinimumHeight(35)
        button_layout.addStretch()
        button_layout.addWidget(self.print_btn)
        button_layout.addWidget(self.print_direct_btn)
        button_layout.addWidget(self.cancel_btn)
        button_layout.addStretch()
        layout.addLayout(button_layout)

    def _on_scroll_resize(self, event):
        """При изменении размера scroll_area пересчитываем масштаб"""
        from PySide6.QtWidgets import QScrollArea as _QSA
        _QSA.resizeEvent(self.scroll_area, event)
        self.render_preview()

    def _calc_pages(self) -> int:
        if not self.labels_data:
            return 0
        return math.ceil(len(self.labels_data) / HolderLabelPrinter.PER_PAGE)

    def _compute_preview_scale(self) -> float:
        """Масштаб: базовые пункты → пиксели экрана, чтобы страница A4
        влезала по ширине в scroll_area с отступом."""
        printer = HolderLabelPrinter()
        page_w_pt, _ = printer._get_page_size()
        available_width = self.scroll_area.viewport().width() - 40
        if available_width < 200:
            available_width = 600  # fallback
        scale = available_width / page_w_pt
        return max(0.5, min(scale, 3.0))

    def render_preview(self):
        """Рендерит предпросмотр всех страниц тем же кодом, что и печать"""
        if not self.labels_data:
            return
        printer = HolderLabelPrinter()
        scale = self._compute_preview_scale()
        page_w_pt, page_h_pt = printer._get_page_size()
        page_w = page_w_pt * scale
        page_h = page_h_pt * scale
        pages = self._calc_pages()
        total_height = pages * page_h + (pages - 1) * 20
        pixmap = QPixmap(int(page_w), int(total_height))
        pixmap.fill(QColor(255, 255, 255))
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.Antialiasing)
        for page_num in range(pages):
            y_offset = page_num * (page_h + 20)
            start_idx = page_num * HolderLabelPrinter.PER_PAGE
            end_idx = min(start_idx + HolderLabelPrinter.PER_PAGE,
                          len(self.labels_data))
            page_labels = self.labels_data[start_idx:end_idx]
            printer._render_page(painter, page_labels,
                                 page_w, page_h, scale,
                                 y_offset_dev=y_offset)
        painter.end()
        self.preview_label.setPixmap(pixmap)
        self.preview_label.setFixedSize(pixmap.size())

    def print_with_preview(self):
        """Печать через предпросмотр"""
        try:
            printer = HolderLabelPrinter(self)
            if printer.preview_labels(self.coins):
                QMessageBox.information(self, "Успех",
                                        "✅ Печать выполнена успешно")
                self.accept()
        except Exception as e:
            self.logger.error(f"Ошибка печати: {e}")
            QMessageBox.critical(self, "Ошибка", f"❌ Ошибка печати: {e}")

    def print_direct(self):
        """Прямая печать без предпросмотра"""
        try:
            printer = HolderLabelPrinter(self)
            if printer.print_labels(self.coins):
                QMessageBox.information(self, "Успех",
                                        "✅ Печать выполнена успешно")
                self.accept()
            else:
                QMessageBox.warning(self, "Ошибка",
                                    "❌ Не удалось выполнить печать")
        except Exception as e:
            self.logger.error(f"Ошибка печати: {e}")
            QMessageBox.critical(self, "Ошибка", f"❌ Ошибка печати: {e}")