# -*- coding: utf-8 -*-

"""
Диалог для управления справочником стран приобретения
"""

import logging
from datetime import datetime
from PySide6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QPushButton,
                               QTableWidget, QTableWidgetItem, QHeaderView,
                               QMessageBox, QLabel, QTextEdit,
                               QGroupBox, QAbstractItemView, QWidget)
from PySide6.QtCore import Qt

from gui.dialogs.purchase_country_dialog import PurchaseCountryDialog


class PurchaseCountryManagerDialog(QDialog):
    """Диалог для управления справочником стран приобретения"""
    
    def __init__(self, db_manager, parent=None):
        super().__init__(parent)
        self.logger = logging.getLogger('CoinCollector.GUI.PurchaseCountryManagerDialog')
        self.db_manager = db_manager
        self.setWindowTitle("Справочник стран приобретения")
        self.setMinimumSize(800, 500)
        
        layout = QVBoxLayout()
        self.setLayout(layout)
        
        # Заголовок
        title_label = QLabel("🌍 Справочник стран приобретения")
        title_label.setStyleSheet("font-weight: bold; font-size: 16px; padding: 8px; background-color: #4a6fa5; color: white; border-radius: 3px;")
        title_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(title_label)
        
        # Пояснение
        info_label = QLabel("Страны, из которых были приобретены монеты (например, поездка в Германию)")
        info_label.setStyleSheet("color: #666; padding: 5px;")
        layout.addWidget(info_label)
        
        # Панель инструментов
        toolbar_layout = QHBoxLayout()
        
        self.add_btn = QPushButton("➕ Добавить")
        self.add_btn.clicked.connect(self.add_country)
        self.add_btn.setMinimumHeight(30)
        toolbar_layout.addWidget(self.add_btn)
        
        self.edit_btn = QPushButton("✏️ Редактировать")
        self.edit_btn.clicked.connect(self.edit_country)
        self.edit_btn.setMinimumHeight(30)
        toolbar_layout.addWidget(self.edit_btn)
        
        self.delete_btn = QPushButton("🗑️ Удалить")
        self.delete_btn.clicked.connect(self.delete_country)
        self.delete_btn.setMinimumHeight(30)
        toolbar_layout.addWidget(self.delete_btn)
        
        toolbar_layout.addStretch()
        
        self.refresh_btn = QPushButton("🔄 Обновить")
        self.refresh_btn.clicked.connect(self.load_countries)
        self.refresh_btn.setMinimumHeight(30)
        toolbar_layout.addWidget(self.refresh_btn)
        
        layout.addLayout(toolbar_layout)
        
        # Таблица
        self.table = QTableWidget()
        self.table.setColumnCount(3)
        self.table.setHorizontalHeaderLabels(["ID", "Страна", "Описание"])
        
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.Stretch)
        header.setSectionResizeMode(2, QHeaderView.Stretch)
        
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setAlternatingRowColors(True)
        self.table.itemSelectionChanged.connect(self.on_country_selected)
        
        layout.addWidget(QLabel("Список стран:"))
        layout.addWidget(self.table)
        
        # Информация
        self.info_group = QGroupBox("Информация")
        info_layout = QVBoxLayout()
        
        self.info_text = QTextEdit()
        self.info_text.setReadOnly(True)
        self.info_text.setMaximumHeight(150)
        info_layout.addWidget(self.info_text)
        
        self.info_group.setLayout(info_layout)
        layout.addWidget(self.info_group)
        
        # Кнопка закрытия
        button_layout = QHBoxLayout()
        button_layout.addStretch()
        
        close_btn = QPushButton("❌ Закрыть")
        close_btn.clicked.connect(self.accept)
        close_btn.setMinimumHeight(35)
        button_layout.addWidget(close_btn)
        
        layout.addLayout(button_layout)
        
        # Загружаем список
        self.load_countries()
    
    def load_countries(self):
        """Загружает список стран в таблицу"""
        try:
            from database.models import PurchaseCountry, Coin
            
            countries = self.db_manager.get_all_purchase_countries()
            
            self.table.setRowCount(len(countries))
            self.table.setSortingEnabled(False)
            
            for row, country in enumerate(countries):
                # ID
                id_item = QTableWidgetItem(str(country.id))
                id_item.setTextAlignment(Qt.AlignCenter)
                id_item.setData(Qt.UserRole, country.id)
                self.table.setItem(row, 0, id_item)
                
                # Название
                name_item = QTableWidgetItem(country.name)
                name_item.setData(Qt.UserRole, country.id)
                self.table.setItem(row, 1, name_item)
                
                # Описание
                desc_item = QTableWidgetItem(country.description or "")
                self.table.setItem(row, 2, desc_item)
            
            self.table.setSortingEnabled(True)
            self.table.resizeColumnsToContents()
            
            if countries:
                self.table.selectRow(0)
            
        except Exception as e:
            self.logger.error(f"Ошибка загрузки: {e}")
            QMessageBox.critical(self, "Ошибка", f"Не удалось загрузить список: {e}")
    
    def on_country_selected(self):
        """Обработчик выбора страны"""
        current_row = self.table.currentRow()
        if current_row < 0:
            self.info_text.clear()
            return
        
        try:
            from database.models import PurchaseCountry, Coin
            
            country_id = self.table.item(current_row, 0).data(Qt.UserRole)
            country = self.db_manager.session.query(PurchaseCountry).get(country_id)
            
            if country:
                coin_count = self.db_manager.session.query(Coin).filter_by(purchase_country_id=country_id).count()
                
                info = []
                info.append(f"ID: {country.id}")
                info.append(f"Страна: {country.name}")
                info.append("")
                info.append(f"Используется в монетах: {coin_count}")
                
                if country.description:
                    info.append("")
                    info.append("Описание:")
                    info.append(country.description)
                
                self.info_text.setText("\n".join(info))
            
        except Exception as e:
            self.logger.error(f"Ошибка: {e}")
            self.info_text.setText(f"Ошибка загрузки информации: {e}")
    
    def add_country(self):
        """Добавляет новую страну"""
        dialog = PurchaseCountryDialog(self.db_manager, self)
        if dialog.exec():
            self.load_countries()
    
    def edit_country(self):
        """Редактирует выбранную страну"""
        current_row = self.table.currentRow()
        if current_row < 0:
            QMessageBox.warning(self, "Предупреждение", "Выберите страну для редактирования")
            return
        
        country_id = self.table.item(current_row, 0).data(Qt.UserRole)
        dialog = PurchaseCountryDialog(self.db_manager, self, country_id)
        if dialog.exec():
            self.load_countries()
    
    def delete_country(self):
        """Удаляет выбранную страну"""
        current_row = self.table.currentRow()
        if current_row < 0:
            QMessageBox.warning(self, "Предупреждение", "Выберите страну для удаления")
            return
        
        country_name = self.table.item(current_row, 1).text()
        country_id = self.table.item(current_row, 0).data(Qt.UserRole)
        
        reply = QMessageBox.question(
            self, "Подтверждение",
            f"Удалить страну '{country_name}'?",
            QMessageBox.Yes | QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            try:
                success, message = self.db_manager.delete_purchase_country(country_id)
                if success:
                    QMessageBox.information(self, "Успех", message)
                    self.load_countries()
                else:
                    QMessageBox.warning(self, "Предупреждение", message)
            except Exception as e:
                QMessageBox.critical(self, "Ошибка", f"Не удалось удалить: {e}")