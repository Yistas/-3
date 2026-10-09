# -*- coding: utf-8 -*-

"""Виджет для отдельного листа"""

from PySide6.QtWidgets import QWidget, QVBoxLayout

from .excel_like_table import ExcelLikeTable


class SheetWidget(QWidget):
    """Виджет для отдельного листа Excel"""
    
    def __init__(self, sheet_name, parent=None):
        super().__init__(parent)
        self.sheet_name = sheet_name
        self.table = ExcelLikeTable()
        
        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.table)
        self.setLayout(layout)