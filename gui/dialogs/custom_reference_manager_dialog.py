# ===== gui/dialogs/custom_reference_manager_dialog.py =====

# -*- coding: utf-8 -*-

"""
Диалог управления пользовательскими справочниками
"""

import json
import logging
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QPushButton,
                               QTableWidget, QTableWidgetItem, QHeaderView,
                               QMessageBox, QLabel, QInputDialog, QLineEdit,
                               QGroupBox, QAbstractItemView, QComboBox,
                               QWidget, QSplitter, QFrame)
from PySide6.QtCore import Qt, Signal

from utils.refresh_manager import RefreshManager


class CustomReferenceManagerDialog(QWidget):
    """Виджет для управления пользовательскими справочниками"""
    
    data_changed = Signal()
    
    def __init__(self, db_manager, parent=None):
        super().__init__(parent)
        self.db_manager = db_manager
        self.logger = logging.getLogger('CoinCollector.GUI.CustomReferenceManager')
        self.current_field_key = None
        self.refresh_manager = RefreshManager()
        
        self.init_ui()
    
    def init_ui(self):
        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(2)
        self.setLayout(layout)
        
        # Создаем сплиттер
        splitter = QSplitter(Qt.Horizontal)
        splitter.setHandleWidth(3)
        
        # Левая панель - список справочников (1/3)
        left_panel = self.create_reference_list_panel()
        splitter.addWidget(left_panel)
        
        # Правая панель - значения справочника (2/3)
        right_panel = self.create_values_panel()
        splitter.addWidget(right_panel)
        
        splitter.setSizes([300, 600])
        layout.addWidget(splitter)
    
    def create_reference_list_panel(self):
        """Создает панель со списком справочников"""
        panel = QWidget()
        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(2)
        panel.setLayout(layout)
        
        # Заголовок
        title = QLabel("📚 Справочники")
        title.setStyleSheet("font-weight: bold; font-size: 11px; padding: 2px; background-color: #e0e0e0;")
        title.setAlignment(Qt.AlignCenter)
        layout.addWidget(title)
        
        # Список справочников
        self.ref_list = QTableWidget()
        self.ref_list.setColumnCount(2)
        self.ref_list.setHorizontalHeaderLabels(["Название", "Ключ"])
        self.ref_list.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.ref_list.setAlternatingRowColors(True)
        
        self.ref_list.verticalHeader().setDefaultSectionSize(22)
        self.ref_list.verticalHeader().setVisible(False)
        
        header = self.ref_list.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.Stretch)
        header.setSectionResizeMode(1, QHeaderView.ResizeToContents)
        
        self.ref_list.itemSelectionChanged.connect(self.on_reference_selected)
        
        layout.addWidget(self.ref_list)
        
        # Кнопка обновления
        refresh_btn = QPushButton("🔄 Обновить список")
        refresh_btn.clicked.connect(self.load_data)
        refresh_btn.setMinimumHeight(26)
        layout.addWidget(refresh_btn)
        
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
        self.values_table.setHorizontalHeaderLabels(["ID", "Название", "Значение"])
        self.values_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.values_table.setAlternatingRowColors(True)
        
        self.values_table.verticalHeader().setDefaultSectionSize(22)
        self.values_table.verticalHeader().setVisible(False)
        
        header = self.values_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.Stretch)
        header.setSectionResizeMode(2, QHeaderView.Stretch)
        
        self.values_table.itemSelectionChanged.connect(self.on_value_selected)
        
        layout.addWidget(self.values_table)
        
        return panel
    
    def load_data(self):
        """Загружает список справочников"""
        try:
            from database.models import FieldSettings
            list_fields = self.db_manager.session.query(FieldSettings).filter(
                FieldSettings.field_type == "list"
            ).order_by(FieldSettings.name).all()
            
            self.ref_list.setSortingEnabled(False)
            self.ref_list.setRowCount(len(list_fields))
            
            for row, field in enumerate(list_fields):
                name_item = QTableWidgetItem(field.name)
                name_item.setData(Qt.UserRole, field.field_key)
                self.ref_list.setItem(row, 0, name_item)
                
                key_item = QTableWidgetItem(field.field_key)
                key_item.setTextAlignment(Qt.AlignCenter)
                self.ref_list.setItem(row, 1, key_item)
            
            self.ref_list.setSortingEnabled(True)
            self.ref_list.resizeColumnsToContents()
            
            if list_fields:
                self.ref_list.selectRow(0)
            else:
                self.values_title.setText("📝 Значения справочника (нет справочников)")
                self.values_table.setRowCount(0)
                self.add_btn.setEnabled(False)
                self.edit_btn.setEnabled(False)
                self.delete_btn.setEnabled(False)
            
        except Exception as e:
            self.logger.error(f"Ошибка загрузки справочников: {e}")
            QMessageBox.critical(self, "Ошибка", f"Не удалось загрузить справочники: {e}")
    
    def on_reference_selected(self):
        """Обработчик выбора справочника"""
        current_row = self.ref_list.currentRow()
        if current_row < 0:
            return
        
        field_key = self.ref_list.item(current_row, 0).data(Qt.UserRole)
        field_name = self.ref_list.item(current_row, 0).text()
        self.current_field_key = field_key
        
        self.values_title.setText(f"📝 Значения справочника: {field_name}")
        self.add_btn.setEnabled(True)
        
        self.load_values()
    
    def load_values(self):
        """Загружает значения выбранного справочника"""
        if not self.current_field_key:
            return
        
        try:
            from database.models import CustomReference
            items = self.db_manager.session.query(CustomReference).filter(
                CustomReference.field_key == self.current_field_key
            ).order_by(CustomReference.sort_order).all()
            
            self.values_table.setSortingEnabled(False)
            self.values_table.setRowCount(len(items))
            
            for row, item in enumerate(items):
                id_item = QTableWidgetItem(str(item.id))
                id_item.setData(Qt.UserRole, item.id)
                id_item.setTextAlignment(Qt.AlignCenter)
                self.values_table.setItem(row, 0, id_item)
                
                name_item = QTableWidgetItem(item.name)
                self.values_table.setItem(row, 1, name_item)
                
                value_item = QTableWidgetItem(item.value)
                self.values_table.setItem(row, 2, value_item)
            
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
        
        name, ok = QInputDialog.getText(self, "Добавить значение", "Введите название:")
        if not ok or not name:
            return
        
        value, ok = QInputDialog.getText(self, "Добавить значение", "Введите значение (то, что будет сохранено):")
        if not ok or not value:
            return
        
        try:
            from database.models import CustomReference
            ref = CustomReference(
                field_key=self.current_field_key,
                name=name,
                value=value,
                sort_order=self.values_table.rowCount()
            )
            self.db_manager.session.add(ref)
            self.db_manager.session.commit()
            self.load_values()
            QMessageBox.information(self, "Успех", "Значение добавлено")
            self.data_changed.emit()
            self.refresh_manager.notify_reference_changed(self.current_field_key)
        except Exception as e:
            self.logger.error(f"Ошибка добавления: {e}")
            QMessageBox.critical(self, "Ошибка", f"Не удалось добавить значение: {e}")
    
    def edit_value(self):
        """Редактирует выбранное значение"""
        current_row = self.values_table.currentRow()
        if current_row < 0:
            return
        
        item_id = self.values_table.item(current_row, 0).data(Qt.UserRole)
        current_name = self.values_table.item(current_row, 1).text()
        current_value = self.values_table.item(current_row, 2).text()
        
        name, ok = QInputDialog.getText(self, "Редактировать", "Название:", text=current_name)
        if not ok:
            return
        
        value, ok = QInputDialog.getText(self, "Редактировать", "Значение:", text=current_value)
        if not ok:
            return
        
        try:
            from database.models import CustomReference
            ref = self.db_manager.session.get(CustomReference, item_id)
            if ref:
                ref.name = name
                ref.value = value
                self.db_manager.session.commit()
                self.load_values()
                QMessageBox.information(self, "Успех", "Значение обновлено")
                self.data_changed.emit()
                self.refresh_manager.notify_reference_changed(self.current_field_key)
        except Exception as e:
            self.logger.error(f"Ошибка редактирования: {e}")
            QMessageBox.critical(self, "Ошибка", f"Не удалось обновить значение: {e}")
    
    def delete_value(self):
        """Удаляет выбранное значение"""
        current_row = self.values_table.currentRow()
        if current_row < 0:
            return
        
        item_id = self.values_table.item(current_row, 0).data(Qt.UserRole)
        name = self.values_table.item(current_row, 1).text()
        
        reply = QMessageBox.question(
            self, "Подтверждение",
            f"Удалить значение '{name}'?",
            QMessageBox.Yes | QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            try:
                from database.models import CustomReference
                ref = self.db_manager.session.get(CustomReference, item_id)
                if ref:
                    self.db_manager.session.delete(ref)
                    self.db_manager.session.commit()
                    self.load_values()
                    QMessageBox.information(self, "Успех", "Значение удалено")
                    self.data_changed.emit()
                    self.refresh_manager.notify_reference_changed(self.current_field_key)
            except Exception as e:
                self.logger.error(f"Ошибка удаления: {e}")
                QMessageBox.critical(self, "Ошибка", f"Не удалось удалить значение: {e}")