# ===== gui/widgets/notebook/task_item.py =====
# НОВЫЙ ФАЙЛ

# -*- coding: utf-8 -*-

"""
Виджет для отображения задачи с чекбоксом
"""

from PySide6.QtWidgets import QWidget, QHBoxLayout, QCheckBox, QLabel, QPushButton
from PySide6.QtCore import Qt, Signal


class TaskItem(QWidget):
    """Виджет задачи с чекбоксом и кнопкой удаления"""
    
    task_deleted = Signal(object)  # Сигнал при удалении задачи
    task_toggled = Signal(object, bool)  # Сигнал при изменении состояния
    
    def __init__(self, text, is_checked=False, parent=None):
        super().__init__(parent)
        self.text = text
        self.is_checked = is_checked
        
        self.init_ui()
    
    def init_ui(self):
        """Инициализация интерфейса"""
        layout = QHBoxLayout()
        layout.setContentsMargins(0, 2, 0, 2)
        layout.setSpacing(5)
        self.setLayout(layout)
        
        self.checkbox = QCheckBox()
        self.checkbox.setChecked(self.is_checked)
        self.checkbox.stateChanged.connect(self._on_checkbox_changed)
        layout.addWidget(self.checkbox)
        
        self.label = QLabel(self.text)
        self.label.setWordWrap(True)
        
        # Зачёркивание текста для выполненных задач
        if self.is_checked:
            self.label.setStyleSheet("text-decoration: line-through; color: #999;")
        
        layout.addWidget(self.label, 1)
        
        self.delete_btn = QPushButton("✕")
        self.delete_btn.setFixedSize(20, 20)
        self.delete_btn.setCursor(Qt.PointingHandCursor)
        self.delete_btn.setStyleSheet("""
            QPushButton {
                background-color: transparent;
                border: none;
                font-size: 12px;
                color: #999;
            }
            QPushButton:hover {
                color: #dc3545;
            }
        """)
        self.delete_btn.clicked.connect(self._on_delete)
        layout.addWidget(self.delete_btn)
    
    def _on_checkbox_changed(self, state):
        """Обработчик изменения состояния чекбокса"""
        self.is_checked = (state == Qt.Checked)
        
        if self.is_checked:
            self.label.setStyleSheet("text-decoration: line-through; color: #999;")
        else:
            self.label.setStyleSheet("")
        
        self.task_toggled.emit(self, self.is_checked)
    
    def _on_delete(self):
        """Обработчик нажатия на кнопку удаления"""
        self.task_deleted.emit(self)
    
    def get_text(self):
        """Возвращает текст задачи"""
        return self.text
    
    def is_checked(self):
        """Возвращает состояние задачи"""
        return self.is_checked