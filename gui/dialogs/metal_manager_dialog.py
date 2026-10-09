# -*- coding: utf-8 -*-

"""
Диалог для управления справочником металлов
"""

import logging
from datetime import datetime
from PySide6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QPushButton,
                               QTableWidget, QTableWidgetItem, QHeaderView,
                               QMessageBox, QLabel, QSplitter, QTextEdit,
                               QGroupBox, QAbstractItemView, QWidget)
from PySide6.QtCore import Qt

from gui.dialogs.metal_dialog import MetalDialog


class MetalManagerDialog(QDialog):
    """Диалог для управления справочником металлов"""
    
    def __init__(self, db_manager, parent=None):
        super().__init__(parent)
        self.logger = logging.getLogger('CoinCollector.GUI.MetalManagerDialog')
        self.db_manager = db_manager
        self.setWindowTitle("Справочник металлов")
        self.setMinimumSize(900, 600)
        
        layout = QVBoxLayout()
        self.setLayout(layout)
        
        # Заголовок
        title_label = QLabel("⚙️ Справочник металлов")
        title_label.setStyleSheet("font-weight: bold; font-size: 16px; padding: 8px; background-color: #4a6fa5; color: white; border-radius: 3px;")
        title_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(title_label)
        
        # Панель инструментов
        toolbar_layout = QHBoxLayout()
        
        self.add_btn = QPushButton("➕ Добавить")
        self.add_btn.clicked.connect(self.add_metal)
        self.add_btn.setMinimumHeight(30)
        toolbar_layout.addWidget(self.add_btn)
        
        self.edit_btn = QPushButton("✏️ Редактировать")
        self.edit_btn.clicked.connect(self.edit_metal)
        self.edit_btn.setMinimumHeight(30)
        toolbar_layout.addWidget(self.edit_btn)
        
        self.delete_btn = QPushButton("🗑️ Удалить")
        self.delete_btn.clicked.connect(self.delete_metal)
        self.delete_btn.setMinimumHeight(30)
        toolbar_layout.addWidget(self.delete_btn)
        
        toolbar_layout.addStretch()
        
        self.refresh_btn = QPushButton("🔄 Обновить")
        self.refresh_btn.clicked.connect(self.load_metals)
        self.refresh_btn.setMinimumHeight(30)
        toolbar_layout.addWidget(self.refresh_btn)
        
        layout.addLayout(toolbar_layout)
        
        # Таблица металлов
        self.table = QTableWidget()
        self.table.setColumnCount(5)
        self.table.setHorizontalHeaderLabels(["ID", "Металл", "Проба", "Курс", "Обновлено"])
        
        # Настройка автоматической ширины колонок по содержимому
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeToContents)  # ID по содержимому
        header.setSectionResizeMode(1, QHeaderView.Stretch)  # Металл растягивается
        header.setSectionResizeMode(2, QHeaderView.ResizeToContents)  # Проба по содержимому
        header.setSectionResizeMode(3, QHeaderView.ResizeToContents)  # Курс по содержимому
        header.setSectionResizeMode(4, QHeaderView.ResizeToContents)  # Дата по содержимому
        
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setAlternatingRowColors(True)
        self.table.itemSelectionChanged.connect(self.on_metal_selected)
        
        layout.addWidget(QLabel("Список металлов:"))
        layout.addWidget(self.table)
        
        # Информация о выбранном металле
        self.info_group = QGroupBox("Информация о металле")
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
        
        # Загружаем список металлов
        self.load_metals()
    
    def load_metals(self):
        """Загружает список металлов в таблицу"""
        try:
            from database.models import Metal
            
            metals = self.db_manager.session.query(Metal).order_by(Metal.name).all()
            
            self.table.setRowCount(len(metals))
            self.table.setSortingEnabled(False)  # Отключаем сортировку на время заполнения
            
            for row, metal in enumerate(metals):
                # ID
                id_item = QTableWidgetItem(str(metal.id))
                id_item.setTextAlignment(Qt.AlignCenter)
                id_item.setData(Qt.UserRole, metal.id)
                self.table.setItem(row, 0, id_item)
                
                # Название
                name_item = QTableWidgetItem(metal.name)
                name_item.setData(Qt.UserRole, metal.id)
                self.table.setItem(row, 1, name_item)
                
                # Проба
                purity_item = QTableWidgetItem(metal.purity or "")
                purity_item.setTextAlignment(Qt.AlignCenter)
                self.table.setItem(row, 2, purity_item)
                
                # Курс
                price_text = ""
                if metal.current_price:
                    price_text = f"{metal.current_price:.2f} {metal.price_currency}/г"
                    if metal.price_date:
                        price_text += f" ({metal.price_date.strftime('%d.%m.%Y')})"
                price_item = QTableWidgetItem(price_text)
                price_item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
                self.table.setItem(row, 3, price_item)
                
                # Дата обновления
                date_text = ""
                if metal.updated_at:
                    date_text = metal.updated_at.strftime("%d.%m.%Y %H:%M")
                date_item = QTableWidgetItem(date_text)
                date_item.setTextAlignment(Qt.AlignCenter)
                self.table.setItem(row, 4, date_item)
            
            self.table.setSortingEnabled(True)  # Включаем сортировку обратно
            
            # Автоматически подгоняем ширину колонок
            self.table.resizeColumnsToContents()
            
            # Устанавливаем минимальную ширину для колонки "Металл"
            if self.table.columnWidth(1) < 150:
                self.table.setColumnWidth(1, 150)
            
            # Выбираем первую строку, если есть
            if metals:
                self.table.selectRow(0)
            
        except Exception as e:
            self.logger.error(f"Ошибка при загрузке металлов: {e}")
            QMessageBox.critical(self, "Ошибка", f"Не удалось загрузить список металлов: {e}")
    
    def on_metal_selected(self):
        """Обработчик выбора металла в таблице"""
        current_row = self.table.currentRow()
        if current_row < 0:
            self.info_text.clear()
            return
        
        try:
            from database.models import Metal
            from database.models import Coin
            
            metal_id = self.table.item(current_row, 0).data(Qt.UserRole)
            metal = self.db_manager.session.query(Metal).get(metal_id)
            
            if metal:
                # Считаем количество монет из этого металла
                coin_count = self.db_manager.session.query(Coin).filter_by(metal_id=metal_id).count()
                
                # Формируем информацию о металле
                info = []
                info.append(f"ID: {metal.id}")
                info.append(f"Металл: {metal.name}")
                if metal.purity:
                    info.append(f"Проба: {metal.purity}")
                if metal.current_price:
                    price_date = f" (на {metal.price_date.strftime('%d.%m.%Y')})" if metal.price_date else ""
                    info.append(f"Текущий курс: {metal.current_price:.2f} {metal.price_currency}/г{price_date}")
                info.append("")
                info.append(f"Используется в монетах: {coin_count}")
                
                if metal.description:
                    info.append("")
                    info.append("Описание:")
                    info.append(metal.description)
                
                self.info_text.setText("\n".join(info))
            
        except Exception as e:
            self.logger.error(f"Ошибка при выборе металла: {e}")
            self.info_text.setText(f"Ошибка загрузки информации: {e}")
    
    def add_metal(self):
        """Добавляет новый металл"""
        try:
            dialog = MetalDialog(self.db_manager, self)
            if dialog.exec():
                self.load_metals()
        except Exception as e:
            self.logger.error(f"Ошибка при добавлении металла: {e}")
            QMessageBox.critical(self, "Ошибка", f"Не удалось открыть диалог добавления: {e}")
    
    def edit_metal(self):
        """Редактирует выбранный металл"""
        current_row = self.table.currentRow()
        if current_row < 0:
            QMessageBox.warning(self, "Предупреждение", "Выберите металл для редактирования")
            return
        
        try:
            metal_id = self.table.item(current_row, 0).data(Qt.UserRole)
            dialog = MetalDialog(self.db_manager, self, metal_id)
            if dialog.exec():
                self.load_metals()
        except Exception as e:
            self.logger.error(f"Ошибка при редактировании металла: {e}")
            QMessageBox.critical(self, "Ошибка", f"Не удалось открыть диалог редактирования: {e}")
    
    def delete_metal(self):
        """Удаляет выбранный металл"""
        current_row = self.table.currentRow()
        if current_row < 0:
            QMessageBox.warning(self, "Предупреждение", "Выберите металл для удаления")
            return
        
        try:
            metal_name = self.table.item(current_row, 1).text()
            metal_purity = self.table.item(current_row, 2).text()
            metal_id = self.table.item(current_row, 0).data(Qt.UserRole)
            
            full_name = f"{metal_name} {metal_purity}".strip()
            
            # Проверяем, используется ли металл в монетах
            from database.models import Coin
            coin_count = self.db_manager.session.query(Coin).filter_by(metal_id=metal_id).count()
            
            if coin_count > 0:
                QMessageBox.warning(self, "Предупреждение", 
                    f"Нельзя удалить металл '{full_name}', так как он используется в {coin_count} монетах.")
                return
            
            reply = QMessageBox.question(
                self, "Подтверждение",
                f"Вы уверены, что хотите удалить металл '{full_name}'?",
                QMessageBox.Yes | QMessageBox.No
            )
            
            if reply == QMessageBox.Yes:
                from database.models import Metal
                metal = self.db_manager.session.query(Metal).get(metal_id)
                if metal:
                    self.db_manager.session.delete(metal)
                    self.db_manager.session.commit()
                    QMessageBox.information(self, "Успех", "Металл удален")
                    self.load_metals()
        except Exception as e:
            self.logger.error(f"Ошибка при удалении металла: {e}")
            QMessageBox.critical(self, "Ошибка", f"Не удалось удалить металл: {e}")