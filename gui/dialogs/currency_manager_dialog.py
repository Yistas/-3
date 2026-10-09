# -*- coding: utf-8 -*-

"""
Упрощенный диалог управления справочником валют
"""

from PySide6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QPushButton,
                               QTableWidget, QTableWidgetItem, QHeaderView,
                               QMessageBox, QLabel, QSplitter, QTextEdit,
                               QGroupBox, QAbstractItemView, QWidget)
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont

from gui.dialogs.currency_dialog import CurrencyDialog


class CurrencyManagerDialog(QDialog):
    """Упрощенный диалог для управления справочником валют"""
    
    def __init__(self, db_manager, parent=None):
        super().__init__(parent)
        self.db_manager = db_manager
        self.setWindowTitle("Справочник валют")
        self.setMinimumSize(800, 500)
        
        layout = QVBoxLayout()
        self.setLayout(layout)
        
        # Заголовок
        title_label = QLabel("💰 Справочник валют")
        title_label.setStyleSheet("font-weight: bold; font-size: 16px; padding: 8px; background-color: #4a6fa5; color: white; border-radius: 3px;")
        title_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(title_label)
        
        # Панель инструментов
        toolbar_layout = QHBoxLayout()
        
        add_btn = QPushButton("➕ Добавить")
        add_btn.clicked.connect(self.add_currency)
        add_btn.setMinimumHeight(30)
        toolbar_layout.addWidget(add_btn)
        
        edit_btn = QPushButton("✏️ Редактировать")
        edit_btn.clicked.connect(self.edit_currency)
        edit_btn.setMinimumHeight(30)
        toolbar_layout.addWidget(edit_btn)
        
        delete_btn = QPushButton("🗑️ Удалить")
        delete_btn.clicked.connect(self.delete_currency)
        delete_btn.setMinimumHeight(30)
        toolbar_layout.addWidget(delete_btn)
        
        toolbar_layout.addStretch()
        
        refresh_btn = QPushButton("🔄 Обновить")
        refresh_btn.clicked.connect(self.load_currencies)
        refresh_btn.setMinimumHeight(30)
        toolbar_layout.addWidget(refresh_btn)
        
        layout.addLayout(toolbar_layout)
        
        # Таблица валют
        self.table = QTableWidget()
        self.table.setColumnCount(5)
        self.table.setHorizontalHeaderLabels(["ID", "Название", "Код", "Символ", "Курс"])
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setAlternatingRowColors(True)
        self.table.itemSelectionChanged.connect(self.on_currency_selected)
        
        layout.addWidget(QLabel("Список валют:"))
        layout.addWidget(self.table)
        
        # Информация о выбранной валюте
        self.info_group = QGroupBox("Информация о валюте")
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
        
        # Загружаем список валют
        self.load_currencies()
    
    def load_currencies(self):
        """Загружает список валют в таблицу"""
        try:
            currencies = self.db_manager.get_all_currencies()
            
            self.table.setRowCount(len(currencies))
            
            for row, currency in enumerate(currencies):
                # ID
                id_item = QTableWidgetItem(str(currency.id))
                id_item.setTextAlignment(Qt.AlignCenter)
                self.table.setItem(row, 0, id_item)
                
                # Название
                name_item = QTableWidgetItem(currency.name)
                self.table.setItem(row, 1, name_item)
                
                # Код
                code_item = QTableWidgetItem(currency.code or "")
                code_item.setTextAlignment(Qt.AlignCenter)
                self.table.setItem(row, 2, code_item)
                
                # Символ
                symbol_item = QTableWidgetItem(currency.symbol or "")
                symbol_item.setTextAlignment(Qt.AlignCenter)
                self.table.setItem(row, 3, symbol_item)
                
                # Курс
                rate_text = f"{currency.exchange_rate:.4f} ₽" if currency.exchange_rate else ""
                rate_item = QTableWidgetItem(rate_text)
                rate_item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
                self.table.setItem(row, 4, rate_item)
            
            # Выбираем первую строку, если есть
            if currencies:
                self.table.selectRow(0)
            
        except Exception as e:
            QMessageBox.critical(self, "Ошибка", f"Не удалось загрузить список валют: {e}")
    
    def on_currency_selected(self):
        """Обработчик выбора валюты в таблице"""
        current_row = self.table.currentRow()
        if current_row < 0:
            self.info_text.clear()
            return
        
        try:
            currency_id = int(self.table.item(current_row, 0).text())
            currency = self.db_manager.get_currency(currency_id)
            
            if currency:
                # Формируем информацию о валюте
                info = []
                info.append(f"ID: {currency.id}")
                info.append(f"Название: {currency.name}")
                if currency.code:
                    info.append(f"Код: {currency.code}")
                if currency.symbol:
                    info.append(f"Символ: {currency.symbol}")
                if currency.exchange_rate:
                    info.append(f"Курс к рублю: {currency.exchange_rate:.4f} ₽")
                
                if currency.description:
                    info.append("")
                    info.append("Описание:")
                    info.append(currency.description)
                
                self.info_text.setText("\n".join(info))
            
        except Exception as e:
            self.info_text.setText(f"Ошибка загрузки информации: {e}")
    
    def add_currency(self):
        """Добавляет новую валюту"""
        dialog = CurrencyDialog(self.db_manager, self)
        if dialog.exec():
            self.load_currencies()
    
    def edit_currency(self):
        """Редактирует выбранную валюту"""
        current_row = self.table.currentRow()
        if current_row < 0:
            QMessageBox.warning(self, "Предупреждение", "Выберите валюту для редактирования")
            return
        
        currency_id = int(self.table.item(current_row, 0).text())
        dialog = CurrencyDialog(self.db_manager, self, currency_id)
        if dialog.exec():
            self.load_currencies()
    
    def delete_currency(self):
        """Удаляет выбранную валюту"""
        current_row = self.table.currentRow()
        if current_row < 0:
            QMessageBox.warning(self, "Предупреждение", "Выберите валюту для удаления")
            return
        
        currency_name = self.table.item(current_row, 1).text()
        currency_id = int(self.table.item(current_row, 0).text())
        
        reply = QMessageBox.question(
            self, "Подтверждение",
            f"Вы уверены, что хотите удалить валюту '{currency_name}'?\n\n"
            "Если валюта используется в монетах, удаление будет невозможно.",
            QMessageBox.Yes | QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            try:
                success, message = self.db_manager.delete_currency(currency_id)
                if success:
                    QMessageBox.information(self, "Успех", message)
                    self.load_currencies()
                else:
                    QMessageBox.warning(self, "Предупреждение", message)
            except Exception as e:
                QMessageBox.critical(self, "Ошибка", f"Не удалось удалить валюту: {e}")