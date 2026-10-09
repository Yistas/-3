# -*- coding: utf-8 -*-

"""
Делегат для редактирования ячеек таблицы продаж
"""

from PySide6.QtWidgets import QStyledItemDelegate, QLineEdit
from PySide6.QtCore import Qt


class SalesDelegate(QStyledItemDelegate):
    """Делегат для редактирования ячеек таблицы продаж"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self._parent_tab = None
    
    def set_parent_tab(self, tab):
        self._parent_tab = tab
    
    def createEditor(self, parent, option, index):
        editor = QLineEdit(parent)
        text = index.data(Qt.DisplayRole) or ""
        editor.setText(text)
        editor.selectAll()
        editor.setFocus()
        return editor
    
    def setEditorData(self, editor, index):
        text = index.data(Qt.DisplayRole) or ""
        editor.setText(text)
    
    def setModelData(self, editor, model, index):
        new_value = editor.text().strip()
        model.setData(index, new_value, Qt.EditRole)