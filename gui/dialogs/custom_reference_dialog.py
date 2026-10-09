# ===== gui/dialogs/custom_reference_dialog.py =====
# СОЗДАТЬ НОВЫЙ ФАЙЛ

# -*- coding: utf-8 -*-

"""
Диалог для управления пользовательским справочником
"""

from PySide6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QPushButton,
                               QTableWidget, QTableWidgetItem, QHeaderView,
                               QMessageBox, QLabel, QInputDialog, QLineEdit,
                               QGroupBox, QAbstractItemView)
from PySide6.QtCore import Qt, Signal


class CustomReferenceDialog(QDialog):
    """Диалог для управления пользовательским справочником"""
    
    data_changed = Signal()
    
    def __init__(self, db_manager, field_key, field_name, parent=None):
        super().__init__(parent)
        self.db_manager = db_manager
        self.field_key = field_key
        self.field_name = field_name
        self.setWindowTitle(f"Справочник: {field_name}")
        self.setMinimumSize(400, 500)
        
        layout = QVBoxLayout()
        self.setLayout(layout)
        
        # Заголовок
        title = QLabel(f"📚 Управление справочником '{field_name}'")
        title.setStyleSheet("font-weight: bold; font-size: 14px; padding: 5px; background-color: #4a6fa5; color: white; border-radius: 3px;")
        title.setAlignment(Qt.AlignCenter)
        layout.addWidget(title)
        
        # Панель инструментов
        toolbar = QHBoxLayout()
        
        self.add_btn = QPushButton("➕ Добавить")
        self.add_btn.clicked.connect(self.add_value)
        toolbar.addWidget(self.add_btn)
        
        self.edit_btn = QPushButton("✏️ Редактировать")
        self.edit_btn.clicked.connect(self.edit_value)
        toolbar.addWidget(self.edit_btn)
        
        self.delete_btn = QPushButton("🗑️ Удалить")
        self.delete_btn.clicked.connect(self.delete_value)
        toolbar.addWidget(self.delete_btn)
        
        toolbar.addStretch()
        
        self.refresh_btn = QPushButton("🔄 Обновить")
        self.refresh_btn.clicked.connect(self.load_data)
        toolbar.addWidget(self.refresh_btn)
        
        layout.addLayout(toolbar)
        
        # Таблица значений
        self.table = QTableWidget()
        self.table.setColumnCount(3)
        self.table.setHorizontalHeaderLabels(["ID", "Название", "Значение"])
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setAlternatingRowColors(True)
        
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.Stretch)
        header.setSectionResizeMode(2, QHeaderView.Stretch)
        
        layout.addWidget(self.table)
        
        # Кнопка закрытия
        button_layout = QHBoxLayout()
        button_layout.addStretch()
        
        close_btn = QPushButton("❌ Закрыть")
        close_btn.clicked.connect(self.accept)
        close_btn.setMinimumHeight(35)
        button_layout.addWidget(close_btn)
        
        layout.addLayout(button_layout)
        
        # Загружаем данные
        self.load_data()
    
    def load_data(self):
        """Загружает данные справочника"""
        try:
            items = self.db_manager.get_custom_references(self.field_key)
            
            self.table.setRowCount(len(items))
            self.table.setSortingEnabled(False)
            
            for row, item in enumerate(items):
                # ID
                id_item = QTableWidgetItem(str(item.id))
                id_item.setData(Qt.UserRole, item.id)
                id_item.setTextAlignment(Qt.AlignCenter)
                self.table.setItem(row, 0, id_item)
                
                # Название
                name_item = QTableWidgetItem(item.name)
                self.table.setItem(row, 1, name_item)
                
                # Значение
                value_item = QTableWidgetItem(item.value)
                self.table.setItem(row, 2, value_item)
            
            self.table.setSortingEnabled(True)
            self.table.resizeColumnsToContents()
            
        except Exception as e:
            QMessageBox.critical(self, "Ошибка", f"Не удалось загрузить данные: {e}")
    
    def add_value(self):
        """Добавляет новое значение"""
        name, ok = QInputDialog.getText(self, "Добавить значение", "Введите название:")
        if not ok or not name:
            return
        
        value, ok = QInputDialog.getText(self, "Добавить значение", "Введите значение (то, что будет сохранено):")
        if not ok or not value:
            return
        
        self.db_manager.add_custom_reference(self.field_key, name, value)
        self.load_data()
        self.data_changed.emit()
    
    def edit_value(self):
        """Редактирует выбранное значение"""
        current_row = self.table.currentRow()
        if current_row < 0:
            QMessageBox.warning(self, "Предупреждение", "Выберите значение для редактирования")
            return
        
        item_id = self.table.item(current_row, 0).data(Qt.UserRole)
        current_name = self.table.item(current_row, 1).text()
        current_value = self.table.item(current_row, 2).text()
        
        name, ok = QInputDialog.getText(self, "Редактировать", "Название:", text=current_name)
        if not ok:
            return
        
        value, ok = QInputDialog.getText(self, "Редактировать", "Значение:", text=current_value)
        if not ok:
            return
        
        self.db_manager.update_custom_reference(item_id, name, value)
        self.load_data()
        self.data_changed.emit()
    
    def delete_value(self):
        """Удаляет выбранное значение"""
        current_row = self.table.currentRow()
        if current_row < 0:
            QMessageBox.warning(self, "Предупреждение", "Выберите значение для удаления")
            return
        
        item_id = self.table.item(current_row, 0).data(Qt.UserRole)
        name = self.table.item(current_row, 1).text()
        
        reply = QMessageBox.question(
            self, "Подтверждение",
            f"Удалить '{name}'?",
            QMessageBox.Yes | QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            self.db_manager.delete_custom_reference(item_id)
            self.load_data()
            self.data_changed.emit()