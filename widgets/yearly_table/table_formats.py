# -*- coding: utf-8 -*-

"""Форматирование таблицы (границы, выравнивание, цвета)"""

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QBrush, QPainter, QPen


class TableFormats:
    """Класс для форматирования таблицы"""
    
    BORDER_NONE = 0
    BORDER_THIN = 1
    BORDER_MEDIUM = 2
    BORDER_THICK = 3
    BORDER_DOUBLE = 4
    
    def set_alignment(self, horizontal=None, vertical=None):
        """Устанавливает выравнивание для выделенных ячеек"""
        # ... код из оригинального файла ...
        pass
    
    def set_border(self, border_type):
        """Устанавливает границы для выделенных ячеек"""
        # ... код из оригинального файла ...
        pass
    
    def _apply_border_to_item(self, item, border_type, side):
        """Применяет границу к элементу"""
        # ... код из оригинального файла ...
        pass
    
    def _draw_double_line(self, painter, p1, p2, orientation):
        """Рисует двойную линию"""
        # ... код из оригинального файла ...
        pass
    
    def paintEvent(self, event):
        """Отрисовка границ"""
        # ... код из оригинального файла ...
        pass