# -*- coding: utf-8 -*-

"""
Диалог для просмотра истории рыночных цен
"""

from PySide6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QPushButton,
                               QTableWidget, QTableWidgetItem, QHeaderView,
                               QLabel, QDateEdit, QComboBox, QMessageBox)
from PySide6.QtCore import Qt, QDate
from datetime import datetime


class PriceHistoryDialog(QDialog):
    """Диалог для просмотра истории рыночных цен"""
    
    def __init__(self, db_manager, parent=None, coin_id=None):
        super().__init__(parent)
        self.db_manager = db_manager
        self.coin_id = coin_id
        self.setWindowTitle("История рыночных цен")
        self.setMinimumSize(800, 500)
        
        self.init_ui()
        self.load_history()
    
    def init_ui(self):
        layout = QVBoxLayout()
        self.setLayout(layout)
        
        # Заголовок
        title = QLabel("📊 История рыночных цен")
        title.setStyleSheet("""
            font-weight: bold;
            font-size: 14px;
            padding: 8px;
            background-color: #4a6fa5;
            color: white;
            border-radius: 3px;
        """)
        title.setAlignment(Qt.AlignCenter)
        layout.addWidget(title)
        
        # Панель фильтров
        filter_layout = QHBoxLayout()
        
        filter_layout.addWidget(QLabel("Монета:"))
        self.coin_combo = QComboBox()
        self.coin_combo.setMinimumWidth(200)
        self.load_coins()
        filter_layout.addWidget(self.coin_combo)
        
        filter_layout.addWidget(QLabel("С даты:"))
        self.start_date = QDateEdit()
        self.start_date.setDate(QDate(2020, 1, 1))
        self.start_date.setCalendarPopup(True)
        filter_layout.addWidget(self.start_date)
        
        filter_layout.addWidget(QLabel("По дату:"))
        self.end_date = QDateEdit()
        self.end_date.setDate(QDate.currentDate())
        self.end_date.setCalendarPopup(True)
        filter_layout.addWidget(self.end_date)
        
        self.filter_btn = QPushButton("🔍 Применить фильтр")
        self.filter_btn.clicked.connect(self.load_history)
        filter_layout.addWidget(self.filter_btn)
        
        filter_layout.addStretch()
        layout.addLayout(filter_layout)
        
        # Таблица истории
        self.table = QTableWidget()
        self.table.setColumnCount(6)
        self.table.setHorizontalHeaderLabels([
            "ID", "Страна", "Номинал", "Год", "Цена (₽)", "Дата цены"
        ])
        self.table.setAlternatingRowColors(True)
        self.table.setSortingEnabled(True)
        
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.Stretch)
        header.setSectionResizeMode(2, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(3, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(4, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(5, QHeaderView.ResizeToContents)
        
        layout.addWidget(self.table)
        
        # Кнопки
        button_layout = QHBoxLayout()
        button_layout.addStretch()
        
        export_btn = QPushButton("📎 Экспорт в CSV")
        export_btn.clicked.connect(self.export_csv)
        button_layout.addWidget(export_btn)
        
        close_btn = QPushButton("❌ Закрыть")
        close_btn.clicked.connect(self.accept)
        button_layout.addWidget(close_btn)
        
        layout.addLayout(button_layout)
    
    def load_coins(self):
        """Загружает список монет для фильтра"""
        self.coin_combo.clear()
        self.coin_combo.addItem("— Все монеты —", None)
        
        coins = self.db_manager.get_all_coins()
        for coin in coins[:500]:  # Ограничиваем для производительности
            text = f"{coin.country.name if coin.country else '?'} {coin.denomination_value or ''} {coin.year or ''}".strip()
            self.coin_combo.addItem(text, coin.id)
    
    def load_history(self):
        """Загружает историю цен в таблицу"""
        coin_id = self.coin_combo.currentData()
        start_date = self.start_date.date().toPython()
        end_date = self.end_date.date().toPython()
        
        history = self.db_manager.get_market_price_history(
            coin_id=coin_id,
            start_date=start_date,
            end_date=end_date,
            limit=1000
        )
        
        self.table.setRowCount(len(history))
        
        for row, record in enumerate(history):
            # ID
            id_item = QTableWidgetItem(str(record.id))
            id_item.setTextAlignment(Qt.AlignCenter)
            self.table.setItem(row, 0, id_item)
            
            # Страна
            self.table.setItem(row, 1, QTableWidgetItem(record.country_name or "—"))
            
            # Номинал
            self.table.setItem(row, 2, QTableWidgetItem(record.denomination or "—"))
            
            # Год
            year_item = QTableWidgetItem(str(record.year) if record.year else "—")
            year_item.setTextAlignment(Qt.AlignCenter)
            self.table.setItem(row, 3, year_item)
            
            # Цена
            price_item = QTableWidgetItem(f"{record.market_price:,.2f}")
            price_item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            self.table.setItem(row, 4, price_item)
            
            # Дата
            date_item = QTableWidgetItem(record.price_date.strftime("%d.%m.%Y"))
            date_item.setTextAlignment(Qt.AlignCenter)
            self.table.setItem(row, 5, date_item)
        
        self.table.resizeColumnsToContents()
        self.setWindowTitle(f"История рыночных цен ({len(history)} записей)")
    
    def export_csv(self):
        """Экспортирует историю в CSV файл"""
        from PySide6.QtWidgets import QFileDialog
        from pathlib import Path
        
        file_path, _ = QFileDialog.getSaveFileName(
            self, "Сохранить историю цен",
            str(Path.home() / "price_history.csv"),
            "CSV files (*.csv);;All files (*.*)"
        )
        
        if file_path:
            try:
                import csv
                with open(file_path, 'w', encoding='utf-8-sig', newline='') as f:
                    writer = csv.writer(f)
                    writer.writerow(["ID", "Страна", "Номинал", "Год", "Цена (₽)", "Дата цены"])
                    
                    for row in range(self.table.rowCount()):
                        row_data = []
                        for col in range(self.table.columnCount()):
                            item = self.table.item(row, col)
                            row_data.append(item.text() if item else "")
                        writer.writerow(row_data)
                
                QMessageBox.information(self, "Успех", f"История сохранена:\n{file_path}")
            except Exception as e:
                QMessageBox.critical(self, "Ошибка", f"Не удалось сохранить: {e}")