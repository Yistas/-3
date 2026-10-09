# ===== gui/dialogs/standard_reference_manager_dialog.py =====

# -*- coding: utf-8 -*-

"""
Диалог управления стандартными справочниками (редкость, сохранность и т.д.)
"""

import logging
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QPushButton,
                               QTableWidget, QTableWidgetItem, QHeaderView,
                               QMessageBox, QLabel, QInputDialog, QLineEdit,
                               QFrame, QSplitter, QAbstractItemView, QComboBox)
from PySide6.QtCore import Qt, Signal

from utils.refresh_manager import RefreshManager


class StandardReferenceManagerDialog(QWidget):
    """Виджет для управления стандартными справочниками"""
    
    data_changed = Signal()
    
    def __init__(self, db_manager, parent=None):
        super().__init__(parent)
        self.db_manager = db_manager
        self.logger = logging.getLogger('CoinCollector.GUI.StandardReferenceManager')
        self.current_field_key = None
        self.current_field_name = None
        self.refresh_manager = RefreshManager()
        
        self.init_ui()
        self.load_reference_types()
    
    def init_ui(self):
        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(2)
        self.setLayout(layout)
        
        # Создаем сплиттер
        splitter = QSplitter(Qt.Horizontal)
        splitter.setHandleWidth(3)
        
        # Левая панель - список типов справочников (1/3)
        left_panel = self.create_types_panel()
        splitter.addWidget(left_panel)
        
        # Правая панель - значения справочника (2/3)
        right_panel = self.create_values_panel()
        splitter.addWidget(right_panel)
        
        splitter.setSizes([300, 600])
        layout.addWidget(splitter)
    
    def create_types_panel(self):
        """Создает панель со списком типов справочников"""
        panel = QWidget()
        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(2)
        panel.setLayout(layout)
        
        # Заголовок
        title = QLabel("📚 Типы справочников")
        title.setStyleSheet("font-weight: bold; font-size: 11px; padding: 2px; background-color: #e0e0e0;")
        title.setAlignment(Qt.AlignCenter)
        layout.addWidget(title)
        
        # Список типов
        self.types_list = QTableWidget()
        self.types_list.setColumnCount(2)
        self.types_list.setHorizontalHeaderLabels(["Справочник", "Ключ"])
        self.types_list.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.types_list.setAlternatingRowColors(True)
        
        self.types_list.verticalHeader().setDefaultSectionSize(22)
        self.types_list.verticalHeader().setVisible(False)
        
        header = self.types_list.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.Stretch)
        header.setSectionResizeMode(1, QHeaderView.ResizeToContents)
        
        self.types_list.itemSelectionChanged.connect(self.on_type_selected)
        
        layout.addWidget(self.types_list)
        
        return panel
    
    def create_values_panel(self):
        """Создает панель со значениями справочника"""
        panel = QWidget()
        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(2)
        panel.setLayout(layout)
        
        # Заголовок
        self.values_title = QLabel("📝 Значения справочника")
        self.values_title.setStyleSheet("font-weight: bold; font-size: 11px; padding: 2px; background-color: #e0e0e0;")
        self.values_title.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.values_title)
        
        # Панель инструментов
        toolbar = QHBoxLayout()
        toolbar.setSpacing(2)
        toolbar.setContentsMargins(0, 0, 0, 0)
        
        self.add_btn = QPushButton("➕ Добавить")
        self.add_btn.clicked.connect(self.add_value)
        self.add_btn.setEnabled(False)
        self.add_btn.setMinimumHeight(26)
        toolbar.addWidget(self.add_btn)
        
        self.edit_btn = QPushButton("✏️ Редактировать")
        self.edit_btn.clicked.connect(self.edit_value)
        self.edit_btn.setEnabled(False)
        self.edit_btn.setMinimumHeight(26)
        toolbar.addWidget(self.edit_btn)
        
        self.delete_btn = QPushButton("🗑️ Удалить")
        self.delete_btn.clicked.connect(self.delete_value)
        self.delete_btn.setEnabled(False)
        self.delete_btn.setMinimumHeight(26)
        toolbar.addWidget(self.delete_btn)
        
        toolbar.addStretch()
        
        layout.addLayout(toolbar)
        
        # Таблица значений
        self.values_table = QTableWidget()
        self.values_table.setColumnCount(3)
        self.values_table.setHorizontalHeaderLabels(["ID", "Значение", "Отображаемое имя"])
        self.values_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.values_table.setAlternatingRowColors(True)
        
        self.values_table.verticalHeader().setDefaultSectionSize(22)
        self.values_table.verticalHeader().setVisible(False)
        
        header = self.values_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.Stretch)
        
        self.values_table.itemSelectionChanged.connect(self.on_value_selected)
        
        layout.addWidget(self.values_table)
        
        return panel
    
    def load_reference_types(self):
        """Загружает типы стандартных справочников"""
        reference_types = [
            ('Редкость', 'rarity'),
            ('Сохранность', 'condition'),
            ('Форма', 'shape'),
            ('Тип выпуска', 'issue_type'),
            ('АВ/РЕВ', 'avrev'),
            ('Статус', 'status'),
            ('Тип приобретения', 'acquisition_type'),
            ('Место хранения', 'storage_location'),
        ]
        
        self.types_list.setSortingEnabled(False)
        self.types_list.setRowCount(len(reference_types))
        
        for row, (name, key) in enumerate(reference_types):
            name_item = QTableWidgetItem(name)
            name_item.setData(Qt.UserRole, key)
            self.types_list.setItem(row, 0, name_item)
            
            key_item = QTableWidgetItem(key)
            key_item.setTextAlignment(Qt.AlignCenter)
            self.types_list.setItem(row, 1, key_item)
        
        self.types_list.setSortingEnabled(True)
        self.types_list.resizeColumnsToContents()
        
        if reference_types:
            self.types_list.selectRow(0)
    
    def on_type_selected(self):
        """Обработчик выбора типа справочника"""
        current_row = self.types_list.currentRow()
        if current_row < 0:
            return
        
        self.current_field_key = self.types_list.item(current_row, 0).data(Qt.UserRole)
        self.current_field_name = self.types_list.item(current_row, 0).text()
        
        self.values_title.setText(f"📝 Значения справочника: {self.current_field_name}")
        self.add_btn.setEnabled(True)
        
        self.load_values()
    
    def load_values(self):
        """Загружает значения выбранного справочника"""
        if not self.current_field_key:
            return
        
        try:
            from database.models import StandardReference
            items = self.db_manager.session.query(StandardReference).filter(
                StandardReference.field_key == self.current_field_key
            ).order_by(StandardReference.sort_order).all()
            
            self.values_table.setSortingEnabled(False)
            self.values_table.setRowCount(len(items))
            
            for row, item in enumerate(items):
                id_item = QTableWidgetItem(str(item.id))
                id_item.setData(Qt.UserRole, item.id)
                id_item.setTextAlignment(Qt.AlignCenter)
                self.values_table.setItem(row, 0, id_item)
                
                value_item = QTableWidgetItem(item.value)
                self.values_table.setItem(row, 1, value_item)
                
                name_item = QTableWidgetItem(item.name)
                self.values_table.setItem(row, 2, name_item)
            
            self.values_table.setSortingEnabled(True)
            self.values_table.resizeColumnsToContents()
            
            self.edit_btn.setEnabled(False)
            self.delete_btn.setEnabled(False)
            
        except Exception as e:
            self.logger.error(f"Ошибка загрузки значений: {e}")
    
    def on_value_selected(self):
        """Обработчик выбора значения"""
        current_row = self.values_table.currentRow()
        self.edit_btn.setEnabled(current_row >= 0)
        self.delete_btn.setEnabled(current_row >= 0)
    
    def add_value(self):
        """Добавляет новое значение в справочник"""
        if not self.current_field_key:
            return
        
        value, ok = QInputDialog.getText(self, "Добавить значение", 
            "Введите значение (код, который будет сохранён в БД):")
        if not ok or not value:
            return
        
        name, ok = QInputDialog.getText(self, "Добавить значение", 
            "Введите отображаемое имя:")
        if not ok or not name:
            return
        
        try:
            from database.models import StandardReference
            ref = StandardReference(
                field_key=self.current_field_key,
                value=value,
                name=name,
                sort_order=self.values_table.rowCount()
            )
            self.db_manager.session.add(ref)
            self.db_manager.session.commit()
            self.load_values()
            QMessageBox.information(self, "Успех", "Значение добавлено")
            self.data_changed.emit()
            self.refresh_manager.notify_reference_changed(self.current_field_name)
        except Exception as e:
            self.logger.error(f"Ошибка добавления: {e}")
            QMessageBox.critical(self, "Ошибка", f"Не удалось добавить значение: {e}")
    
    def edit_value(self):
        """Редактирует выбранное значение"""
        current_row = self.values_table.currentRow()
        if current_row < 0:
            return
        
        item_id = self.values_table.item(current_row, 0).data(Qt.UserRole)
        current_value = self.values_table.item(current_row, 1).text()
        current_name = self.values_table.item(current_row, 2).text()
        
        value, ok = QInputDialog.getText(self, "Редактировать", 
            "Значение (код, который будет сохранён в БД):", text=current_value)
        if not ok:
            return
        
        name, ok = QInputDialog.getText(self, "Редактировать", 
            "Отображаемое имя:", text=current_name)
        if not ok:
            return
        
        try:
            from database.models import StandardReference
            ref = self.db_manager.session.get(StandardReference, item_id)
            if ref:
                ref.value = value
                ref.name = name
                self.db_manager.session.commit()
                self.load_values()
                QMessageBox.information(self, "Успех", "Значение обновлено")
                self.data_changed.emit()
                self.refresh_manager.notify_reference_changed(self.current_field_name)
        except Exception as e:
            self.logger.error(f"Ошибка редактирования: {e}")
            QMessageBox.critical(self, "Ошибка", f"Не удалось обновить значение: {e}")
    
    def delete_value(self):
        """Удаляет выбранное значение"""
        current_row = self.values_table.currentRow()
        if current_row < 0:
            return
        
        item_id = self.values_table.item(current_row, 0).data(Qt.UserRole)
        name = self.values_table.item(current_row, 2).text()
        
        reply = QMessageBox.question(
            self, "Подтверждение",
            f"Удалить значение '{name}'?",
            QMessageBox.Yes | QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            try:
                from database.models import StandardReference
                ref = self.db_manager.session.get(StandardReference, item_id)
                if ref:
                    self.db_manager.session.delete(ref)
                    self.db_manager.session.commit()
                    self.load_values()
                    QMessageBox.information(self, "Успех", "Значение удалено")
                    self.data_changed.emit()
                    self.refresh_manager.notify_reference_changed(self.current_field_name)
            except Exception as e:
                self.logger.error(f"Ошибка удаления: {e}")
                QMessageBox.critical(self, "Ошибка", f"Не удалось удалить значение: {e}")