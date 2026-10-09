# -*- coding: utf-8 -*-

"""Поддержка формул в таблице"""

import re
import math
from PySide6.QtWidgets import QInputDialog, QMessageBox
from PySide6.QtGui import QBrush, QColor


class TableFormulas:
    """Класс для работы с формулами"""
    
    def __init__(self):
        self.formulas = {}
    
    def insert_formula_dialog(self):
        """Диалог для вставки формулы"""
        # ... код из оригинального файла ...
        pass
    
    def set_formula(self, row, col, formula):
        """Устанавливает формулу в ячейку"""
        # ... код из оригинального файла ...
        pass
    
    def evaluate_formula(self, formula, current_row, current_col):
        """Вычисляет значение формулы"""
        # ... код из оригинального файла ...
        pass
    
    def _col_letter_to_index(self, col_letter):
        """Преобразует букву колонки в индекс"""
        result = 0
        for char in col_letter.upper():
            result = result * 26 + (ord(char) - ord('A') + 1)
        return result - 1
    
    def _index_to_col_letter(self, index):
        """Преобразует индекс в букву колонки"""
        result = ""
        index += 1
        while index > 0:
            index -= 1
            result = chr(ord('A') + (index % 26)) + result
            index //= 26
        return result