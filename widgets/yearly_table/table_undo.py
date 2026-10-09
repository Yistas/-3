# -*- coding: utf-8 -*-

"""Undo/Redo функционал для таблицы"""

import pickle
import base64
from PySide6.QtWidgets import QApplication, QMessageBox
from PySide6.QtCore import QMimeData


class TableUndo:
    """Класс для Undo/Redo операций"""
    
    def __init__(self):
        self.undo_stack = []
        self.redo_stack = []
        self.max_undo_steps = 100
        self.is_undo_redo = False
    
    def _save_state(self):
        """Сохраняет текущее состояние"""
        # ... код из оригинального файла ...
        pass
    
    def undo(self):
        """Отменяет последнее действие"""
        # ... код из оригинального файла ...
        pass
    
    def redo(self):
        """Повторяет отмененное действие"""
        # ... код из оригинального файла ...
        pass
    
    def copy_selection(self):
        """Копирует выделенные ячейки"""
        # ... код из оригинального файла ...
        pass
    
    def paste_selection(self):
        """Вставляет данные из буфера"""
        # ... код из оригинального файла ...
        pass