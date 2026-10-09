# ===== gui/dialogs/column_selector.py =====
# ПОЛНОСТЬЮ ЗАМЕНИТЬ ФАЙЛ

# -*- coding: utf-8 -*-

"""
Диалог для выбора отображаемых колонок
"""

import json
from PySide6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel,
                               QPushButton, QScrollArea, QWidget, QCheckBox,
                               QDialogButtonBox, QGroupBox, QMessageBox)
from PySide6.QtCore import Qt, Signal


class ColumnSelectorDialog(QDialog):
    """Диалог для выбора отображаемых колонок"""
    
    # Сигнал для обновления колонок
    columns_changed = Signal()
    
    # Все доступные стандартные колонки с их названиями и ключами
# ===== gui/dialogs/column_selector.py =====
# НАЙТИ STANDARD_COLUMNS И УБЕДИТЬСЯ, ЧТО У КОЛОНОК ЕСТЬ default=True

    STANDARD_COLUMNS = [
        # Специальные
        {"key": "select", "name": "☑", "category": "Специальные", "field_type": "checkbox", "default": True, "width": 30},
        {"key": "id", "name": "ID", "category": "Специальные", "field_type": "number", "default": False, "width": 50},
        
        # Основные
        {"key": "flag", "name": "🇫🇷", "category": "Основные", "field_type": "icon", "default": True, "width": 35},
        {"key": "country", "name": "Страна", "category": "Основные", "field_type": "text", "default": True, "width": 150},
        {"key": "catalog_number", "name": "№ каталога", "category": "Основные", "field_type": "text", "default": True, "width": 120},
        {"key": "denomination_value", "name": "Номинал", "category": "Основные", "field_type": "text", "default": True, "width": 80},
        {"key": "currency", "name": "Валюта", "category": "Основные", "field_type": "text", "default": True, "width": 80},
        {"key": "year", "name": "Год", "category": "Основные", "field_type": "number", "default": True, "width": 70},
        {"key": "period", "name": "Период", "category": "Основные", "field_type": "text", "default": True, "width": 150},
        {"key": "century", "name": "Век", "category": "Основные", "field_type": "text", "default": False, "width": 70},
        
        # Монетный двор
        {"key": "mint", "name": "Монетный двор", "category": "Монетный двор", "field_type": "text", "default": True, "width": 120},
        {"key": "mint_mark", "name": "Знак МД", "category": "Монетный двор", "field_type": "text", "default": False, "width": 70},
        
        # Характеристики
        {"key": "metal", "name": "Металл", "category": "Характеристики", "field_type": "text", "default": True, "width": 100},
        {"key": "weight", "name": "Вес (г)", "category": "Характеристики", "field_type": "number", "default": False, "width": 70},
        {"key": "diameter", "name": "Размер (мм)", "category": "Характеристики", "field_type": "number", "default": False, "width": 80},
        {"key": "shape", "name": "Форма", "category": "Характеристики", "field_type": "text", "default": False, "width": 80},
        
        # Гурт
        {"key": "edge", "name": "Гурт", "category": "Гурт", "field_type": "text", "default": False, "width": 100},
        {"key": "edge_description", "name": "Описание гурта", "category": "Гурт", "field_type": "textarea", "default": False, "width": 150},
        
        # Состояние
        {"key": "condition", "name": "Сохранность", "category": "Состояние", "field_type": "text", "default": True, "width": 90},
        {"key": "rarity", "name": "Редкость", "category": "Состояние", "field_type": "text", "default": False, "width": 90},
        {"key": "storage_location", "name": "Альбом", "category": "Состояние", "field_type": "text", "default": False, "width": 100},
        {"key": "issue_type", "name": "Тип выпуска", "category": "Состояние", "field_type": "text", "default": False, "width": 120},
        {"key": "avrev", "name": "АВ/РЕВ", "category": "Состояние", "field_type": "text", "default": False, "width": 100},
        {"key": "status", "name": "Статус", "category": "Состояние", "field_type": "text", "default": True, "width": 100},
        
        # Покупка
        {"key": "purchase_date", "name": "Дата покупки", "category": "Покупка", "field_type": "date", "default": False, "width": 100},
        {"key": "purchase_price", "name": "Цена покупки", "category": "Покупка", "field_type": "number", "default": False, "width": 100},
        {"key": "purchase_where", "name": "Где куплена", "category": "Покупка", "field_type": "text", "default": False, "width": 120},
        {"key": "purchase_country", "name": "Страна покупки", "category": "Покупка", "field_type": "text", "default": False, "width": 120},
        {"key": "acquisition_type", "name": "Тип приобретения", "category": "Покупка", "field_type": "text", "default": False, "width": 100},
        {"key": "purchase_info", "name": "Информация о покупке", "category": "Покупка", "field_type": "textarea", "default": False, "width": 150},
        
        # Рыночная цена
        {"key": "market_price", "name": "Рыночная цена", "category": "Рыночная цена", "field_type": "number", "default": False, "width": 120},
        {"key": "market_price_date", "name": "Дата цены", "category": "Рыночная цена", "field_type": "date", "default": False, "width": 100},
        
        # Ссылки
        {"key": "ucoin_url", "name": "UCOIN ссылка", "category": "Ссылки", "field_type": "text", "default": False, "width": 150},
        {"key": "meshok_url", "name": "Meshok ссылка", "category": "Ссылки", "field_type": "text", "default": False, "width": 150},
        
        # Информация
        {"key": "coin_info", "name": "Информация о монете", "category": "Информация", "field_type": "textarea", "default": False, "width": 150},
    
    ]
    
    def __init__(self, parent=None, current_columns=None, db_manager=None):
        super().__init__(parent)
        self.db_manager = db_manager
        self.setWindowTitle("Настройка колонок таблицы")
        self.setMinimumWidth(750)
        self.setMinimumHeight(600)
        
        self.selected_columns = []
        self.checkboxes = {}  # {key: checkbox}
        self.custom_checkboxes = {}  # {field_key: checkbox}
        
        # Загружаем пользовательские поля
        self.custom_columns = []
        if db_manager:
            self.load_custom_fields()
        
        layout = QVBoxLayout()
        self.setLayout(layout)
        
        # Информация
        info_label = QLabel("Выберите колонки для отображения в таблице:")
        info_label.setStyleSheet("font-weight: bold; margin: 5px;")
        layout.addWidget(info_label)
        
        # Пояснение
        hint_label = QLabel("💡 Колонку ☑ нельзя скрыть — она необходима для выделения монет")
        hint_label.setStyleSheet("color: #666; font-size: 10px; margin-bottom: 5px;")
        layout.addWidget(hint_label)
        
        # Создаем прокручиваемую область с чекбоксами
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.StyledPanel)
        
        scroll_widget = QWidget()
        scroll_layout = QVBoxLayout()
        scroll_widget.setLayout(scroll_layout)
        
        # Группируем стандартные колонки по категориям
        categories = {}
        for col in self.STANDARD_COLUMNS:
            cat = col.get("category", "Другие")
            if cat not in categories:
                categories[cat] = []
            categories[cat].append(col)
        
        # Добавляем стандартные колонки
        for category, cols in categories.items():
            # Заголовок категории
            category_label = QLabel(category)
            category_label.setStyleSheet("font-weight: bold; color: #4a6fa5; margin-top: 10px; font-size: 12px;")
            scroll_layout.addWidget(category_label)
            
            # Чекбоксы для колонок категории
            for col in cols:
                checkbox = QCheckBox(col["name"])
                
                # Устанавливаем состояние по умолчанию
                if current_columns and col["key"] in current_columns:
                    checkbox.setChecked(True)
                elif not current_columns and col["default"]:
                    checkbox.setChecked(True)
                
                # Колонку select нельзя скрыть
                if col["key"] == "select":
                    checkbox.setChecked(True)
                    checkbox.setEnabled(False)
                    checkbox.setToolTip("Эта колонка необходима для выделения монет и не может быть скрыта")
                
                self.checkboxes[col["key"]] = checkbox
                scroll_layout.addWidget(checkbox)
        
        # Добавляем пользовательские поля
        if self.custom_columns:
            # Разделитель
            separator = QLabel("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
            separator.setStyleSheet("color: #999; margin-top: 10px;")
            scroll_layout.addWidget(separator)
            
            category_label = QLabel("📌 Пользовательские поля")
            category_label.setStyleSheet("font-weight: bold; color: #9b59b6; margin-top: 10px; font-size: 12px;")
            scroll_layout.addWidget(category_label)
            
            for col in self.custom_columns:
                checkbox = QCheckBox(col["name"])
                
                # Устанавливаем состояние
                if current_columns and col["key"] in current_columns:
                    checkbox.setChecked(True)
                elif col.get("show_in_table", True):
                    checkbox.setChecked(True)
                
                self.custom_checkboxes[col["field_key"]] = {
                    'checkbox': checkbox,
                    'data': col
                }
                scroll_layout.addWidget(checkbox)
        
        scroll.setWidget(scroll_widget)
        layout.addWidget(scroll)
        
        # Кнопки управления
        button_layout = QHBoxLayout()
        
        # Кнопка "Выбрать все"
        select_all_btn = QPushButton("✓ Выбрать все")
        select_all_btn.clicked.connect(self.select_all)
        select_all_btn.setMinimumHeight(30)
        button_layout.addWidget(select_all_btn)
        
        # Кнопка "Сбросить все"
        clear_all_btn = QPushButton("✗ Сбросить все")
        clear_all_btn.clicked.connect(self.clear_all)
        clear_all_btn.setMinimumHeight(30)
        button_layout.addWidget(clear_all_btn)
        
        button_layout.addStretch()
        
        # Кнопка "Восстановить по умолчанию"
        default_btn = QPushButton("🔄 Восстановить по умолчанию")
        default_btn.clicked.connect(self.restore_default)
        default_btn.setMinimumHeight(30)
        button_layout.addWidget(default_btn)
        
        # Кнопка управления пользовательскими полями
        if self.db_manager:
            manage_btn = QPushButton("⚙️ Управление полями")
            manage_btn.clicked.connect(self.manage_custom_fields)
            manage_btn.setMinimumHeight(30)
            button_layout.addWidget(manage_btn)
        
        layout.addLayout(button_layout)
        
        # Кнопки OK/Отмена
        dialog_buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        dialog_buttons.accepted.connect(self.accept)
        dialog_buttons.rejected.connect(self.reject)
        dialog_buttons.setMinimumHeight(35)
        layout.addWidget(dialog_buttons)
        
        # Устанавливаем размеры по умолчанию
        self.resize(750, 600)
    
    def load_custom_fields(self):
        """Загружает пользовательские поля из базы данных"""
        try:
            fields = self.db_manager.get_active_custom_fields()
            self.custom_columns = []
            for field in fields:
                if field.show_in_table:
                    self.custom_columns.append({
                        "key": f"custom_{field.field_key}",
                        "field_key": field.field_key,
                        "name": field.name,
                        "default": True,
                        "width": 120,
                        "category": "Пользовательские",
                        "field_type": field.field_type,
                        "is_custom": True
                    })
        except Exception as e:
            print(f"Ошибка загрузки пользовательских полей: {e}")
    
    def select_all(self):
        """Выбирает все колонки"""
        for key, checkbox in self.checkboxes.items():
            if checkbox.isEnabled():
                checkbox.setChecked(True)
        for item in self.custom_checkboxes.values():
            item['checkbox'].setChecked(True)
    
    def clear_all(self):
        """Снимает выбор со всех колонок, но оставляет обязательные"""
        for key, checkbox in self.checkboxes.items():
            if key != "select":
                checkbox.setChecked(False)
            else:
                checkbox.setChecked(True)
        for item in self.custom_checkboxes.values():
            item['checkbox'].setChecked(False)
    
    def restore_default(self):
        """Восстанавливает колонки по умолчанию"""
        # Стандартные колонки
        for col in self.STANDARD_COLUMNS:
            if col["key"] in self.checkboxes:
                if col["key"] == "select":
                    self.checkboxes[col["key"]].setChecked(True)
                else:
                    self.checkboxes[col["key"]].setChecked(col["default"])
        
        # Пользовательские колонки
        for item in self.custom_checkboxes.values():
            item['checkbox'].setChecked(item['data'].get("show_in_table", True))
        
        # Обязательно включаем основные колонки
        for key in ["country", "catalog_number", "denomination_value", "currency", "year", "mint", "condition", "status"]:
            if key in self.checkboxes:
                self.checkboxes[key].setChecked(True)
    
    def manage_custom_fields(self):
        """Открывает диалог управления пользовательскими полями"""
        from gui.dialogs.custom_fields_dialog import CustomFieldsDialog
        dialog = CustomFieldsDialog(self.db_manager, self)
        dialog.fields_changed.connect(self.on_custom_fields_changed)
        if dialog.exec():
            self.on_custom_fields_changed()
    
    def on_custom_fields_changed(self):
        """Обработчик изменения пользовательских полей"""
        # Перезагружаем пользовательские поля
        self.load_custom_fields()
        
        # Перестраиваем интерфейс
        self.refresh_ui()
        
        self.columns_changed.emit()
    
    def refresh_ui(self):
        """Обновляет интерфейс (перестраивает список колонок)"""
        # Сохраняем текущие выбранные колонки
        current_keys = self.get_selected_keys()
        
        # Перестраиваем диалог
        self.close()
        new_dialog = ColumnSelectorDialog(self.parent(), current_keys, self.db_manager)
        new_dialog.columns_changed.connect(self.columns_changed)
        new_dialog.exec()
    
    def get_selected_keys(self):
        """Возвращает список ключей выбранных колонок"""
        selected = []
        
        # Стандартные колонки
        for key, checkbox in self.checkboxes.items():
            if checkbox.isChecked():
                selected.append(key)
        
        # Пользовательские колонки
        for field_key, item in self.custom_checkboxes.items():
            if item['checkbox'].isChecked():
                selected.append(f"custom_{field_key}")
        
        return selected
    
    def get_selected_columns(self):
        """Возвращает список выбранных колонок с полной информацией"""
        selected = []
        
        # Стандартные колонки
        for col in self.STANDARD_COLUMNS:
            if col["key"] in self.checkboxes and self.checkboxes[col["key"]].isChecked():
                selected.append(col.copy())
        
        # Пользовательские колонки
        for field_key, item in self.custom_checkboxes.items():
            if item['checkbox'].isChecked():
                col_data = item['data'].copy()
                col_data["key"] = f"custom_{field_key}"
                col_data["is_custom"] = True
                selected.append(col_data)
        
        return selected