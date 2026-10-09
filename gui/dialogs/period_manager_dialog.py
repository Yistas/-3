# ===== gui/dialogs/period_manager_dialog.py =====
# СОЗДАТЬ НОВЫЙ ФАЙЛ

# -*- coding: utf-8 -*-

"""
Диалог для управления справочником периодов
"""

import logging
from PySide6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QPushButton,
                               QTableWidget, QTableWidgetItem, QHeaderView,
                               QMessageBox, QLabel, QTextEdit, QGroupBox,
                               QAbstractItemView, QWidget, QComboBox)
from PySide6.QtCore import Qt

from gui.dialogs.period_dialog import PeriodDialog


class PeriodManagerDialog(QDialog):
    """Диалог для управления справочником периодов"""
    
    def __init__(self, db_manager, parent=None):
        super().__init__(parent)
        self.logger = logging.getLogger('CoinCollector.GUI.PeriodManagerDialog')
        self.db_manager = db_manager
        self.setWindowTitle("Справочник периодов")
        self.setMinimumSize(900, 600)
        
        layout = QVBoxLayout()
        self.setLayout(layout)
        
        # Заголовок
        title_label = QLabel("📅 Справочник периодов")
        title_label.setStyleSheet("font-weight: bold; font-size: 16px; padding: 8px; background-color: #4a6fa5; color: white; border-radius: 3px;")
        title_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(title_label)
        
        # Панель фильтрации по стране
        filter_layout = QHBoxLayout()
        filter_layout.addWidget(QLabel("Фильтр по стране:"))
        
        self.filter_country_combo = QComboBox()
        self.filter_country_combo.addItem("— Все страны —", None)
        self.load_countries()
        self.filter_country_combo.currentIndexChanged.connect(self.load_periods)
        filter_layout.addWidget(self.filter_country_combo)
        
        filter_layout.addStretch()
        layout.addLayout(filter_layout)
        
        # Панель инструментов
        toolbar_layout = QHBoxLayout()
        
        self.add_btn = QPushButton("➕ Добавить")
        self.add_btn.clicked.connect(self.add_period)
        self.add_btn.setMinimumHeight(30)
        toolbar_layout.addWidget(self.add_btn)
        
        self.edit_btn = QPushButton("✏️ Редактировать")
        self.edit_btn.clicked.connect(self.edit_period)
        self.edit_btn.setMinimumHeight(30)
        toolbar_layout.addWidget(self.edit_btn)
        
        self.delete_btn = QPushButton("🗑️ Удалить")
        self.delete_btn.clicked.connect(self.delete_period)
        self.delete_btn.setMinimumHeight(30)
        toolbar_layout.addWidget(self.delete_btn)
        
        toolbar_layout.addStretch()
        
        self.refresh_btn = QPushButton("🔄 Обновить")
        self.refresh_btn.clicked.connect(self.load_periods)
        self.refresh_btn.setMinimumHeight(30)
        toolbar_layout.addWidget(self.refresh_btn)
        
        layout.addLayout(toolbar_layout)
        
        # Таблица периодов
        self.table = QTableWidget()
        self.table.setColumnCount(5)
        self.table.setHorizontalHeaderLabels(["ID", "Период", "Страна", "Годы", "Описание"])
        
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.Stretch)
        header.setSectionResizeMode(2, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(3, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(4, QHeaderView.Stretch)
        
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setAlternatingRowColors(True)
        self.table.itemSelectionChanged.connect(self.on_period_selected)
        
        layout.addWidget(QLabel("Список периодов:"))
        layout.addWidget(self.table)
        
        # Информация о выбранном периоде
        self.info_group = QGroupBox("Информация о периоде")
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
        self.load_periods()
    
    def load_countries(self):
        """Загружает список стран для фильтра"""
        countries = self.db_manager.get_all_countries()
        for country in countries:
            self.filter_country_combo.addItem(country.name, country.id)
    
    def load_periods(self):
        """Загружает список периодов в таблицу"""
        try:
            from database.models import Period
            
            country_id = self.filter_country_combo.currentData()
            
            if country_id:
                periods = self.db_manager.get_periods_by_country(country_id)
            else:
                periods = self.db_manager.get_all_periods()
            
            self.table.setRowCount(len(periods))
            self.table.setSortingEnabled(False)
            
            for row, period in enumerate(periods):
                # ID
                id_item = QTableWidgetItem(str(period.id))
                id_item.setTextAlignment(Qt.AlignCenter)
                id_item.setData(Qt.UserRole, period.id)
                self.table.setItem(row, 0, id_item)
                
                # Название периода
                name_item = QTableWidgetItem(period.name)
                name_item.setData(Qt.UserRole, period.id)
                self.table.setItem(row, 1, name_item)
                
                # Страна
                country_name = period.country.name if period.country else "—"
                country_item = QTableWidgetItem(country_name)
                self.table.setItem(row, 2, country_item)
                
                # Годы
                years = []
                if period.start_year:
                    years.append(str(period.start_year))
                if period.end_year:
                    years.append(str(period.end_year))
                years_text = "–".join(years) if years else "—"
                years_item = QTableWidgetItem(years_text)
                years_item.setTextAlignment(Qt.AlignCenter)
                self.table.setItem(row, 3, years_item)
                
                # Описание
                desc_item = QTableWidgetItem(period.description or "")
                self.table.setItem(row, 4, desc_item)
            
            self.table.setSortingEnabled(True)
            self.table.resizeColumnsToContents()
            
            if periods:
                self.table.selectRow(0)
            
        except Exception as e:
            self.logger.error(f"Ошибка при загрузке периодов: {e}")
            QMessageBox.critical(self, "Ошибка", f"Не удалось загрузить список периодов: {e}")
    
    def on_period_selected(self):
        """Обработчик выбора периода в таблице"""
        current_row = self.table.currentRow()
        if current_row < 0:
            self.info_text.clear()
            return
        
        try:
            from database.models import Period, Coin
            
            period_id = self.table.item(current_row, 0).data(Qt.UserRole)
            period = self.db_manager.session.query(Period).get(period_id)
            
            if period:
                coin_count = self.db_manager.session.query(Coin).filter_by(period_id=period_id).count()
                
                info = []
                info.append(f"ID: {period.id}")
                info.append(f"Название: {period.name}")
                if period.country:
                    info.append(f"Страна: {period.country.name}")
                if period.start_year:
                    info.append(f"Начальный год: {period.start_year}")
                if period.end_year:
                    info.append(f"Конечный год: {period.end_year}")
                info.append("")
                info.append(f"Используется в монетах: {coin_count}")
                
                if period.description:
                    info.append("")
                    info.append("Описание:")
                    info.append(period.description)
                
                self.info_text.setText("\n".join(info))
            
        except Exception as e:
            self.logger.error(f"Ошибка при выборе периода: {e}")
            self.info_text.setText(f"Ошибка загрузки информации: {e}")
    
    def add_period(self):
        """Добавляет новый период"""
        dialog = PeriodDialog(self.db_manager, self)
        if dialog.exec():
            self.load_periods()
    
    def edit_period(self):
        """Редактирует выбранный период"""
        current_row = self.table.currentRow()
        if current_row < 0:
            QMessageBox.warning(self, "Предупреждение", "Выберите период для редактирования")
            return
        
        period_id = self.table.item(current_row, 0).data(Qt.UserRole)
        dialog = PeriodDialog(self.db_manager, self, period_id)
        if dialog.exec():
            self.load_periods()
    
    def delete_period(self):
        """Удаляет выбранный период"""
        current_row = self.table.currentRow()
        if current_row < 0:
            QMessageBox.warning(self, "Предупреждение", "Выберите период для удаления")
            return
        
        period_name = self.table.item(current_row, 1).text()
        period_id = self.table.item(current_row, 0).data(Qt.UserRole)
        
        reply = QMessageBox.question(
            self, "Подтверждение",
            f"Удалить период '{period_name}'?",
            QMessageBox.Yes | QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            try:
                success, message = self.db_manager.delete_period(period_id)
                if success:
                    QMessageBox.information(self, "Успех", message)
                    self.load_periods()
                else:
                    QMessageBox.warning(self, "Предупреждение", message)
            except Exception as e:
                QMessageBox.critical(self, "Ошибка", f"Не удалось удалить период: {e}")