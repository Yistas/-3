# -*- coding: utf-8 -*-
"""
Делегат для раскраски строк таблицы по континентам (темозависимый)
"""
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QBrush, QPalette
from PySide6.QtWidgets import QStyledItemDelegate


class ContinentColorDelegate(QStyledItemDelegate):
    """Делегат для раскраски строк таблицы на основе континента страны"""

    # Цвета для СВЕТЛОЙ темы
    LIGHT_CONTINENT_COLORS = {
        "Европа": QColor(255, 255, 0, 50),      # Жёлтый
        "Азия": QColor(0, 255, 0, 50),          # Зелёный
        "Америка": QColor(255, 0, 0, 50),       # Красный
        "Африка": QColor(128, 0, 128, 50),      # Фиолетовый
        "Океания": QColor(0, 255, 255, 50),     # Голубой
    }

    # Цвета для ТЁМНОЙ темы (насыщеннее, видны на тёмном фоне)
    DARK_CONTINENT_COLORS = {
        "Европа": QColor(74, 111, 165, 70),
        "Азия": QColor(230, 126, 34, 60),
        "Америка": QColor(39, 174, 96, 60),
        "Африка": QColor(241, 196, 15, 50),
        "Океания": QColor(155, 89, 182, 70),
    }

    def __init__(self, parent=None):
        super().__init__(parent)
        self.parent_table = parent
        self.coin_continent_map = {}  # {row: continent_name}

    def set_coin_continent_map(self, row, continent_name):
        """Устанавливает континент для строки"""
        self.coin_continent_map[row] = continent_name

    def clear_continent_map(self):
        """Очищает карту континентов"""
        self.coin_continent_map.clear()

    def get_continent_for_row(self, row):
        """Возвращает континент для строки"""
        return self.coin_continent_map.get(row)

    def _is_dark_theme(self):
        """Определяет тёмную тему по яркости фона таблицы"""
        try:
            bg = self.parent_table.palette().color(QPalette.Base)
            return bg.lightness() < 128
        except Exception:
            return True

    def initStyleOption(self, option, index):
        """Инициализация опций перед отрисовкой"""
        super().initStyleOption(option, index)
        if not index.isValid():
            return
        row = index.row()
        continent = self.get_continent_for_row(row)
        if not continent:
            return
        if self._is_dark_theme():
            colors = self.DARK_CONTINENT_COLORS
        else:
            colors = self.LIGHT_CONTINENT_COLORS
        if continent in colors:
            option.backgroundBrush = QBrush(colors[continent])