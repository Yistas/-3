# ===== gui/dialogs/references_dialog.py =====
# ПОЛНОСТЬЮ ЗАМЕНИТЬ ФАЙЛ

# -*- coding: utf-8 -*-

"""
Единое окно для управления всеми справочниками
"""

from PySide6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QPushButton,
                               QListWidget, QListWidgetItem, QStackedWidget,
                               QWidget, QLabel, QSplitter, QMessageBox,
                               QTableWidget, QTableWidgetItem, QHeaderView,
                               QAbstractItemView, QTextEdit, QGroupBox,
                               QFormLayout, QLineEdit, QComboBox, QSpinBox,
                               QDoubleSpinBox, QScrollArea, QSizePolicy)
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QFont

from gui.dialogs.currency_dialog import CurrencyDialog
from gui.dialogs.mint_dialog import MintDialog
from gui.dialogs.country_reference_dialog import CountryReferenceDialog
from gui.dialogs.continent_reference_dialog import ContinentReferenceDialog
from gui.dialogs.metal_manager_dialog import MetalManagerDialog
from gui.dialogs.edge_manager_dialog import EdgeManagerDialog
from gui.dialogs.purchase_country_manager_dialog import PurchaseCountryManagerDialog
from gui.dialogs.period_manager_dialog import PeriodManagerDialog
from gui.dialogs.custom_reference_manager_dialog import CustomReferenceManagerDialog
from gui.dialogs.standard_reference_manager_dialog import StandardReferenceManagerDialog

class ReferencesDialog(QDialog):
    """Единое окно для управления всеми справочниками"""
    
    # Типы справочников
    REF_CURRENCY = 0
    REF_MINT = 1
    REF_COUNTRY = 2
    REF_CONTINENT = 3
    REF_METAL = 4
    REF_EDGE = 5
    REF_PURCHASE_COUNTRY = 6
    REF_PERIOD = 7
    REF_CUSTOM_REFERENCE = 8
    REF_STANDARD_REFERENCE = 9
    
    def __init__(self, db_manager, parent=None, initial_ref=REF_CURRENCY):
        super().__init__(parent)
        self.db_manager = db_manager
        self.current_ref = initial_ref
        self.setWindowTitle("Справочники")
        self.setMinimumSize(1100, 750)
        
        layout = QVBoxLayout()
        self.setLayout(layout)
        
        # Заголовок
        title_label = QLabel("📚 Справочники")
        title_label.setStyleSheet("font-weight: bold; font-size: 16px; padding: 8px; background-color: #4a6fa5; color: white; border-radius: 3px;")
        title_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(title_label)
        
        # Создаем сплиттер для списка справочников и содержимого
        splitter = QSplitter(Qt.Horizontal)
        
        # Левая панель - список справочников
        left_panel = QWidget()
        left_layout = QVBoxLayout()
        left_panel.setLayout(left_layout)
        
        left_layout.addWidget(QLabel("Выберите справочник:"))
        
        self.ref_list = QListWidget()
        self.ref_list.setMaximumWidth(220)
        self.ref_list.setMinimumWidth(180)
        
        # Добавляем пункты справочников
        currency_item = QListWidgetItem("💰 Валюты")
        currency_item.setData(Qt.UserRole, self.REF_CURRENCY)
        self.ref_list.addItem(currency_item)
        
        mint_item = QListWidgetItem("🏭 Монетные дворы")
        mint_item.setData(Qt.UserRole, self.REF_MINT)
        self.ref_list.addItem(mint_item)
        
        country_item = QListWidgetItem("🌍 Страны")
        country_item.setData(Qt.UserRole, self.REF_COUNTRY)
        self.ref_list.addItem(country_item)
        
        continent_item = QListWidgetItem("🗺️ Континенты")
        continent_item.setData(Qt.UserRole, self.REF_CONTINENT)
        self.ref_list.addItem(continent_item)
        
        metal_item = QListWidgetItem("⚙️ Металлы")
        metal_item.setData(Qt.UserRole, self.REF_METAL)
        self.ref_list.addItem(metal_item)
        
        edge_item = QListWidgetItem("⚙️ Гурты")
        edge_item.setData(Qt.UserRole, self.REF_EDGE)
        self.ref_list.addItem(edge_item)
        
        purchase_item = QListWidgetItem("🏪 Страны приобретения")
        purchase_item.setData(Qt.UserRole, self.REF_PURCHASE_COUNTRY)
        self.ref_list.addItem(purchase_item)
        
        period_item = QListWidgetItem("📅 Периоды")
        period_item.setData(Qt.UserRole, self.REF_PERIOD)
        self.ref_list.addItem(period_item)
        
        custom_ref_item = QListWidgetItem("📋 Пользовательские справочники")
        custom_ref_item.setData(Qt.UserRole, self.REF_CUSTOM_REFERENCE)
        self.ref_list.addItem(custom_ref_item)
        
        standard_ref_item = QListWidgetItem("📋 Стандартные справочники")
        standard_ref_item.setData(Qt.UserRole, self.REF_STANDARD_REFERENCE)
        self.ref_list.addItem(standard_ref_item)
        
        self.ref_list.currentRowChanged.connect(self.on_ref_changed)
        left_layout.addWidget(self.ref_list)
        
        splitter.addWidget(left_panel)
        
        # Правая панель - содержимое справочника
        self.right_panel = QWidget()
        self.right_layout = QVBoxLayout()
        self.right_panel.setLayout(self.right_layout)
        
        # Стек для разных справочников
        self.stack = QStackedWidget()
        
        # Создаем виджеты для каждого справочника
        self.currency_widget = self.create_currency_widget()
        self.mint_widget = self.create_mint_widget()
        self.country_widget = CountryReferenceDialog(self.db_manager, self)
        self.continent_widget = ContinentReferenceDialog(self.db_manager, self)
        self.metal_widget = MetalManagerDialog(self.db_manager, self)
        self.edge_widget = EdgeManagerDialog(self.db_manager, self)
        self.purchase_widget = PurchaseCountryManagerDialog(self.db_manager, self)
        self.period_widget = PeriodManagerDialog(self.db_manager, self)
        self.custom_reference_widget = CustomReferenceManagerDialog(self.db_manager, self)  # ДОБАВИТЬ
        self.standard_reference_widget = StandardReferenceManagerDialog(self.db_manager, self)
        self.stack.addWidget(self.standard_reference_widget)
        
        # Убираем кнопки закрытия из виджетов
        for widget in [self.country_widget, self.continent_widget, self.metal_widget, self.edge_widget, self.purchase_widget, self.period_widget]:
            for child in widget.findChildren(QPushButton):
                if child.text() and "Закрыть" in child.text():
                    child.hide()
                    break
        
        self.stack.addWidget(self.currency_widget)      # индекс 0
        self.stack.addWidget(self.mint_widget)          # индекс 1
        self.stack.addWidget(self.country_widget)       # индекс 2
        self.stack.addWidget(self.continent_widget)     # индекс 3
        self.stack.addWidget(self.metal_widget)         # индекс 4
        self.stack.addWidget(self.edge_widget)          # индекс 5
        self.stack.addWidget(self.purchase_widget)      # индекс 6
        self.stack.addWidget(self.period_widget)        # индекс 7
        self.stack.addWidget(self.custom_reference_widget)  # индекс 8
        self.stack.addWidget(self.standard_reference_widget)  # индекс 9 
 
        self.right_layout.addWidget(self.stack)
        
        splitter.addWidget(self.right_panel)
        
        # Устанавливаем соотношение размеров (1:5)
        splitter.setSizes([200, 900])
        
        layout.addWidget(splitter)
        
        # Кнопка закрытия
        button_layout = QHBoxLayout()
        button_layout.addStretch()
        
        close_btn = QPushButton("❌ Закрыть")
        close_btn.clicked.connect(self.accept)
        close_btn.setMinimumHeight(35)
        close_btn.setMinimumWidth(120)
        button_layout.addWidget(close_btn)
        
        layout.addLayout(button_layout)
        
        # Выбираем начальный справочник
        self.ref_list.setCurrentRow(initial_ref)
    
# ===== gui/dialogs/references_dialog.py =====
# В МЕТОДЕ on_ref_changed, ПРОВЕРИТЬ ВСЕ ВЕТКИ

    def on_ref_changed(self, row):
        """Обработчик изменения выбранного справочника"""
        if row < 0:
            return
        
        self.current_ref = row
        self.stack.setCurrentIndex(row)
        
        # Обновляем данные при переключении
        if row == self.REF_CURRENCY:
            self.load_currencies()
        elif row == self.REF_MINT:
            self.load_mints()
        elif row == self.REF_COUNTRY:
            self.country_widget.load_countries()
        elif row == self.REF_CONTINENT:
            self.continent_widget.load_continents()
        elif row == self.REF_METAL:
            self.metal_widget.load_metals()
        elif row == self.REF_EDGE:
            self.edge_widget.load_edges()
        elif row == self.REF_PURCHASE_COUNTRY:
            self.purchase_widget.load_countries()
        elif row == self.REF_PERIOD:
            self.period_widget.load_periods()
        elif row == self.REF_CUSTOM_REFERENCE:
            self.custom_reference_widget.load_data()
        elif row == self.REF_STANDARD_REFERENCE:
            self.standard_reference_widget.load_values()
    
    # === Валюты ===
    
    def create_currency_widget(self):
        """Создает виджет для управления валютами"""
        widget = QWidget()
        layout = QVBoxLayout()
        widget.setLayout(layout)
        
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
        self.currency_table = QTableWidget()
        self.currency_table.setColumnCount(5)
        self.currency_table.setHorizontalHeaderLabels(["ID", "Название", "Код", "Символ", "Курс"])
        self.currency_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.currency_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.currency_table.setAlternatingRowColors(True)
        self.currency_table.itemSelectionChanged.connect(self.on_currency_selected)
        
        layout.addWidget(QLabel("Список валют:"))
        layout.addWidget(self.currency_table)
        
        # Информация о выбранной валюте
        self.currency_info_group = QGroupBox("Информация о валюте")
        info_layout = QVBoxLayout()
        
        self.currency_info_text = QTextEdit()
        self.currency_info_text.setReadOnly(True)
        self.currency_info_text.setMaximumHeight(150)
        info_layout.addWidget(self.currency_info_text)
        
        self.currency_info_group.setLayout(info_layout)
        layout.addWidget(self.currency_info_group)
        
        return widget
    
    def load_currencies(self):
        """Загружает список валют в таблицу"""
        try:
            currencies = self.db_manager.get_all_currencies()
            
            self.currency_table.setRowCount(len(currencies))
            
            for row, currency in enumerate(currencies):
                # ID
                id_item = QTableWidgetItem(str(currency.id))
                id_item.setTextAlignment(Qt.AlignCenter)
                self.currency_table.setItem(row, 0, id_item)
                
                # Название
                name_item = QTableWidgetItem(currency.name)
                self.currency_table.setItem(row, 1, name_item)
                
                # Код
                code_item = QTableWidgetItem(currency.code or "")
                code_item.setTextAlignment(Qt.AlignCenter)
                self.currency_table.setItem(row, 2, code_item)
                
                # Символ
                symbol_item = QTableWidgetItem(currency.symbol or "")
                symbol_item.setTextAlignment(Qt.AlignCenter)
                self.currency_table.setItem(row, 3, symbol_item)
                
                # Курс
                rate_text = f"{currency.exchange_rate:.4f} ₽" if currency.exchange_rate else ""
                rate_item = QTableWidgetItem(rate_text)
                rate_item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
                self.currency_table.setItem(row, 4, rate_item)
            
            # Выбираем первую строку, если есть
            if currencies:
                self.currency_table.selectRow(0)
            else:
                self.currency_info_text.clear()
            
        except Exception as e:
            QMessageBox.critical(self, "Ошибка", f"Не удалось загрузить список валют: {e}")
    
    def on_currency_selected(self):
        """Обработчик выбора валюты в таблице"""
        current_row = self.currency_table.currentRow()
        if current_row < 0:
            self.currency_info_text.clear()
            return
        
        try:
            currency_id = int(self.currency_table.item(current_row, 0).text())
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
                
                self.currency_info_text.setText("\n".join(info))
            
        except Exception as e:
            self.currency_info_text.setText(f"Ошибка загрузки информации: {e}")
    
    def add_currency(self):
        """Добавляет новую валюту"""
        dialog = CurrencyDialog(self.db_manager, self)
        if dialog.exec():
            self.load_currencies()
    
    def edit_currency(self):
        """Редактирует выбранную валюту"""
        current_row = self.currency_table.currentRow()
        if current_row < 0:
            QMessageBox.warning(self, "Предупреждение", "Выберите валюту для редактирования")
            return
        
        currency_id = int(self.currency_table.item(current_row, 0).text())
        dialog = CurrencyDialog(self.db_manager, self, currency_id)
        if dialog.exec():
            self.load_currencies()
    
    def delete_currency(self):
        """Удаляет выбранную валюту"""
        current_row = self.currency_table.currentRow()
        if current_row < 0:
            QMessageBox.warning(self, "Предупреждение", "Выберите валюту для удаления")
            return
        
        currency_name = self.currency_table.item(current_row, 1).text()
        currency_id = int(self.currency_table.item(current_row, 0).text())
        
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
    
    # === Монетные дворы ===
    
    def create_mint_widget(self):
        """Создает виджет для управления монетными дворами"""
        widget = QWidget()
        layout = QVBoxLayout()
        widget.setLayout(layout)
        
        # Панель инструментов
        toolbar_layout = QHBoxLayout()
        
        add_btn = QPushButton("➕ Добавить")
        add_btn.clicked.connect(self.add_mint)
        add_btn.setMinimumHeight(30)
        toolbar_layout.addWidget(add_btn)
        
        edit_btn = QPushButton("✏️ Редактировать")
        edit_btn.clicked.connect(self.edit_mint)
        edit_btn.setMinimumHeight(30)
        toolbar_layout.addWidget(edit_btn)
        
        delete_btn = QPushButton("🗑️ Удалить")
        delete_btn.clicked.connect(self.delete_mint)
        delete_btn.setMinimumHeight(30)
        toolbar_layout.addWidget(delete_btn)
        
        toolbar_layout.addStretch()
        
        refresh_btn = QPushButton("🔄 Обновить")
        refresh_btn.clicked.connect(self.load_mints)
        refresh_btn.setMinimumHeight(30)
        toolbar_layout.addWidget(refresh_btn)
        
        layout.addLayout(toolbar_layout)
        
        # Таблица монетных дворов
        self.mint_table = QTableWidget()
        self.mint_table.setColumnCount(6)
        self.mint_table.setHorizontalHeaderLabels(["ID", "Название", "Краткое", "Знак", "Страна", "Город"])
        self.mint_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.mint_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.mint_table.setAlternatingRowColors(True)
        self.mint_table.itemSelectionChanged.connect(self.on_mint_selected)
        
        layout.addWidget(QLabel("Список монетных дворов:"))
        layout.addWidget(self.mint_table)
        
        # Информация о выбранном монетном дворе
        self.mint_info_group = QGroupBox("Информация о монетном дворе")
        info_layout = QVBoxLayout()
        
        self.mint_info_text = QTextEdit()
        self.mint_info_text.setReadOnly(True)
        self.mint_info_text.setMaximumHeight(150)
        info_layout.addWidget(self.mint_info_text)
        
        self.mint_info_group.setLayout(info_layout)
        layout.addWidget(self.mint_info_group)
        
        return widget
    
    def load_mints(self):
        """Загружает список монетных дворов в таблицу"""
        try:
            mints = self.db_manager.get_all_mints()
            
            self.mint_table.setRowCount(len(mints))
            
            for row, mint in enumerate(mints):
                # ID
                id_item = QTableWidgetItem(str(mint.id))
                id_item.setTextAlignment(Qt.AlignCenter)
                self.mint_table.setItem(row, 0, id_item)
                
                # Название
                name_item = QTableWidgetItem(mint.name)
                self.mint_table.setItem(row, 1, name_item)
                
                # Краткое название
                short_name_item = QTableWidgetItem(mint.short_name or "")
                short_name_item.setTextAlignment(Qt.AlignCenter)
                self.mint_table.setItem(row, 2, short_name_item)
                
                # Знак
                mark_item = QTableWidgetItem(mint.mark or "")
                mark_item.setTextAlignment(Qt.AlignCenter)
                self.mint_table.setItem(row, 3, mark_item)
                
                # Страна
                country_name = mint.country.name if mint.country else ""
                country_item = QTableWidgetItem(country_name)
                self.mint_table.setItem(row, 4, country_item)
                
                # Город
                city_item = QTableWidgetItem(mint.city or "")
                self.mint_table.setItem(row, 5, city_item)
            
            # Выбираем первую строку, если есть
            if mints:
                self.mint_table.selectRow(0)
            else:
                self.mint_info_text.clear()
            
        except Exception as e:
            QMessageBox.critical(self, "Ошибка", f"Не удалось загрузить список монетных дворов: {e}")
    
    def on_mint_selected(self):
        """Обработчик выбора монетного двора в таблице"""
        current_row = self.mint_table.currentRow()
        if current_row < 0:
            self.mint_info_text.clear()
            return
        
        try:
            mint_id = int(self.mint_table.item(current_row, 0).text())
            mint = self.db_manager.get_mint(mint_id)
            
            if mint:
                # Формируем информацию о монетном дворе
                info = []
                info.append(f"ID: {mint.id}")
                info.append(f"Название: {mint.name}")
                if mint.short_name:
                    info.append(f"Краткое название: {mint.short_name}")
                if mint.mark:
                    info.append(f"Знак на монетах: {mint.mark}")
                if mint.country:
                    info.append(f"Страна: {mint.country.name}")
                if mint.city:
                    info.append(f"Город: {mint.city}")
                if mint.founded_year:
                    info.append(f"Год основания: {mint.founded_year}")
                if mint.closed_year:
                    info.append(f"Год закрытия: {mint.closed_year}")
                if mint.website:
                    info.append(f"Веб-сайт: {mint.website}")
                
                if mint.description:
                    info.append("")
                    info.append("Описание:")
                    info.append(mint.description)
                
                self.mint_info_text.setText("\n".join(info))
            
        except Exception as e:
            self.mint_info_text.setText(f"Ошибка загрузки информации: {e}")
    
    def add_mint(self):
        """Добавляет новый монетный двор"""
        dialog = MintDialog(self.db_manager, self)
        if dialog.exec():
            self.load_mints()
    
    def edit_mint(self):
        """Редактирует выбранный монетный двор"""
        current_row = self.mint_table.currentRow()
        if current_row < 0:
            QMessageBox.warning(self, "Предупреждение", "Выберите монетный двор для редактирования")
            return
        
        mint_id = int(self.mint_table.item(current_row, 0).text())
        dialog = MintDialog(self.db_manager, self, mint_id)
        if dialog.exec():
            self.load_mints()
    
    def delete_mint(self):
        """Удаляет выбранный монетный двор"""
        current_row = self.mint_table.currentRow()
        if current_row < 0:
            QMessageBox.warning(self, "Предупреждение", "Выберите монетный двор для удаления")
            return
        
        mint_name = self.mint_table.item(current_row, 1).text()
        mint_id = int(self.mint_table.item(current_row, 0).text())
        
        reply = QMessageBox.question(
            self, "Подтверждение",
            f"Вы уверены, что хотите удалить монетный двор '{mint_name}'?\n\n"
            "Если монетный двор используется в монетах, удаление будет невозможно.",
            QMessageBox.Yes | QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            try:
                success, message = self.db_manager.delete_mint(mint_id)
                if success:
                    QMessageBox.information(self, "Успех", message)
                    self.load_mints()
                else:
                    QMessageBox.w.warning(self, "Предупреждение", message)
            except Exception as e:
                QMessageBox.critical(self, "Ошибка", f"Не удалось удалить монетный двор: {e}")
            except Exception as e:
                QMessageBox.critical(self, "Ошибка", f"Не удалось удалить монетный двор:Не удалось удалить монетный двор: {e}")