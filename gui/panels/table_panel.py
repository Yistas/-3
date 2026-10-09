# -*- coding: utf-8 -*-

"""
Менеджер центральной панели с таблицей монет
"""

import logging
import json
import os
from datetime import datetime
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QTableWidget, 
                               QTableWidgetItem, QHeaderView, QLabel, QToolBar, 
                               QMenu, QMessageBox, QApplication, QLineEdit, 
                               QPushButton, QFrame, QInputDialog)
from PySide6.QtCore import Qt, QSize, QTimer
from PySide6.QtGui import QAction, QIcon, QPixmap

from gui.dialogs.column_selector import ColumnSelectorDialog
from gui.widgets.color_delegate import ContinentColorDelegate
from database.models import Coin, Country, StandardReference
from sqlalchemy.orm.exc import DetachedInstanceError

class TablePanelManager:
    """Управление центральной панелью с таблицей монет"""
    
    def __init__(self, main_window):
        self.main = main_window
        self.logger = logging.getLogger('CoinCollector.GUI.TablePanel')
        self.table = None
        self.current_columns = None
        self.color_delegate = None
        self.custom_fields = []
        
        # Переменные для сортировки
        self.sort_column = None
        self.sort_order = 0
        
        # Переменные для сохранения позиции
        self._scroll_position = 0
        self._selected_row = -1
        
        # Кнопка скрытия панели
        self.toggle_panel_action = None
        
        # Информационная метка
        self.info_label = None
        
        # Строка поиска
        self.search_input = None
        self.search_frame = None
        self.clear_search_btn = None
        self.hide_search_btn = None
        self.search_count_label = None
        
        # Флаг для отслеживания подключения сигнала
        self._signal_connected = False
        
        # Переменные для фильтрации
        self._all_coins = []
        self._filtered_coins = []
        self._column_filter = None  # {'key': column_key, 'value': value, 'name': column_name}
        
        # Метка активного фильтра
        self.filter_label = None
        
        # Кэш для справочников
        self._status_cache = {}
        self._status_value_cache = {}
        self._condition_cache = {}
        self._condition_value_cache = {}
        self._rarity_cache = {}
        self._rarity_value_cache = {}
        self._shape_cache = {}
        self._shape_value_cache = {}
        self._issue_type_cache = {}
        self._issue_type_value_cache = {}
        self._avrev_cache = {}
        self._avrev_value_cache = {}
        self._acquisition_type_cache = {}
        self._acquisition_type_value_cache = {}
        self._storage_location_cache = {}
        self._storage_location_value_cache = {}
        
        # Загружаем пользовательские поля
        self.load_custom_fields()
        
    def load_custom_fields(self):
        """Загружает пользовательские поля из базы данных"""
        try:
            self.custom_fields = self.main.db_manager.get_active_custom_fields()
            self.logger.info(f"Загружено {len(self.custom_fields)} пользовательских полей")
        except Exception as e:
            self.logger.error(f"Ошибка загрузки пользовательских полей: {e}")
            self.custom_fields = []
    
    def load_reference_caches(self):
        """Загружает все справочники в кэш"""
        try:
            all_refs = self.main.db_manager.session.query(StandardReference).all()
            
            self._status_cache = {}
            self._status_value_cache = {}
            self._condition_cache = {}
            self._condition_value_cache = {}
            self._rarity_cache = {}
            self._rarity_value_cache = {}
            self._shape_cache = {}
            self._shape_value_cache = {}
            self._issue_type_cache = {}
            self._issue_type_value_cache = {}
            self._avrev_cache = {}
            self._avrev_value_cache = {}
            self._acquisition_type_cache = {}
            self._acquisition_type_value_cache = {}
            self._storage_location_cache = {}
            self._storage_location_value_cache = {}
            
            for ref in all_refs:
                if ref.field_key == 'status':
                    self._status_cache[ref.id] = ref.name
                    self._status_value_cache[ref.id] = ref.value
                elif ref.field_key == 'condition':
                    self._condition_cache[ref.id] = ref.name
                    self._condition_value_cache[ref.id] = ref.value
                elif ref.field_key == 'rarity':
                    self._rarity_cache[ref.id] = ref.name
                    self._rarity_value_cache[ref.id] = ref.value
                elif ref.field_key == 'shape':
                    self._shape_cache[ref.id] = ref.name
                    self._shape_value_cache[ref.id] = ref.value
                elif ref.field_key == 'issue_type':
                    self._issue_type_cache[ref.id] = ref.name
                    self._issue_type_value_cache[ref.id] = ref.value
                elif ref.field_key == 'avrev':
                    self._avrev_cache[ref.id] = ref.name
                    self._avrev_value_cache[ref.id] = ref.value
                elif ref.field_key == 'acquisition_type':
                    self._acquisition_type_cache[ref.id] = ref.name
                    self._acquisition_type_value_cache[ref.id] = ref.value
                elif ref.field_key == 'storage_location':
                    self._storage_location_cache[ref.id] = ref.name
                    self._storage_location_value_cache[ref.id] = ref.value
            
            self.logger.debug(f"Загружено справочников: статусы={len(self._status_cache)}")
        except Exception as e:
            self.logger.error(f"Ошибка загрузки справочников: {e}")
    
    def cleanup(self):
        """Очистка перед закрытием"""
        if self._signal_connected:
            try:
                self.table.itemChanged.disconnect(self._on_item_checkbox_changed)
                self._signal_connected = False
            except:
                pass
        
    def create_panel(self):
        """Создает центральную панель с таблицей"""
        panel = QWidget()
        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        panel.setLayout(layout)
        # Тулбар
        self.toolbar = self._create_toolbar()
        layout.addWidget(self.toolbar)
        # Информационная метка
        self.info_label = QLabel()
        self.info_label.setMinimumHeight(30)
        layout.addWidget(self.info_label)
        # Строка поиска (скрыта по умолчанию)
        self.search_frame = QFrame()
        self.search_frame.setVisible(False)
        search_layout = QHBoxLayout()
        search_layout.setSpacing(5)
        search_layout.setContentsMargins(0, 2, 0, 2)
        self.search_frame.setLayout(search_layout)
        search_label = QLabel("🔍 Фильтр:")
        search_label.setFixedWidth(50)
        search_layout.addWidget(search_label)
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Введите текст для поиска по всем столбцам...")
        self.search_input.setMinimumHeight(28)
        self.search_input.textChanged.connect(self._on_search_text_changed)
        search_layout.addWidget(self.search_input)
        # Кнопка очистки
        self.clear_search_btn = QPushButton("✕")
        self.clear_search_btn.setFixedSize(28, 28)
        self.clear_search_btn.setToolTip("Очистить фильтр")
        self.clear_search_btn.clicked.connect(self._clear_search)
        self.clear_search_btn.setVisible(False)
        search_layout.addWidget(self.clear_search_btn)
        # Кнопка скрытия поиска
        self.hide_search_btn = QPushButton("✕")
        self.hide_search_btn.setFixedSize(28, 28)
        self.hide_search_btn.setToolTip("Скрыть поиск")
        self.hide_search_btn.clicked.connect(self._hide_search)
        search_layout.addWidget(self.hide_search_btn)
        # Метка количества найденных
        self.search_count_label = QLabel("")
        search_layout.addWidget(self.search_count_label)
        search_layout.addStretch()
        layout.addWidget(self.search_frame)
        # Метка активного фильтра колонки
        self.filter_label = QLabel("")
        self.filter_label.setVisible(False)
        layout.addWidget(self.filter_label)
        # Таблица
        self.table = QTableWidget()
        self.table.currentItemChanged.connect(self.main.on_coin_selected)
        # Делегат для раскраски
        self.color_delegate = ContinentColorDelegate(self.table)
        self.table.setItemDelegate(self.color_delegate)
        # Настройка перетаскивания колонок
        header = self.table.horizontalHeader()
        header.setSectionsMovable(True)
        header.setDragEnabled(True)
        header.setDropIndicatorShown(True)
        header.setSectionsClickable(True)
        header.sectionMoved.connect(self._on_column_moved)
        header.sectionClicked.connect(self._on_header_clicked)
        # ЗАПОМИНАЕМ ШИРИНУ ПРИ РУЧНОМ ИЗМЕНЕНИИ И ПИШЕМ В БАЗУ
        header.sectionResized.connect(self._on_section_resized)
        self.table.setSortingEnabled(False)
        self.table.setContextMenuPolicy(Qt.CustomContextMenu)
        self.table.customContextMenuRequested.connect(self._show_context_menu)
        # Подключаем контекстное меню для заголовков колонок
        header.setContextMenuPolicy(Qt.CustomContextMenu)
        header.customContextMenuRequested.connect(self._show_header_filter_menu)
        layout.addWidget(self.table)
        # Применяем стили текущей темы
        self.update_style()
        # Загружаем кэш справочников
        self.load_reference_caches()
        # Восстанавливаем ширины колонок после построения таблицы
        from PySide6.QtCore import QTimer
        QTimer.singleShot(0, self._apply_column_widths)
        return panel

    def _create_toolbar(self):
        """Создает панель инструментов"""
        toolbar = QToolBar()
        toolbar.setIconSize(QSize(24, 24))
        # Добавление монеты
        add_action = QAction("➕ Добавить", self.main)
        add_action.triggered.connect(self.main.add_coin)
        toolbar.addAction(add_action)
        # Редактирование
        edit_action = QAction("✏️ Редактировать", self.main)
        edit_action.triggered.connect(self.main.edit_coin)
        toolbar.addAction(edit_action)
        # Удаление → МАССОВОЕ удаление выделенных строк
        # (кнопки тулбара — это QAction, поэтому подключаем .triggered,
        #  а не self.delete_btn.clicked — такой переменной здесь нет)
        delete_action = QAction("🗑️ Удалить", self.main)
        delete_action.triggered.connect(self._on_delete_clicked)
        toolbar.addAction(delete_action)
        toolbar.addSeparator()
        # Справочники
        ref_action = QAction("📚 Справочники", self.main)
        ref_action.triggered.connect(self.main.show_references)
        toolbar.addAction(ref_action)
        toolbar.addSeparator()
        # Управление полями
        manage_fields_action = QAction("📊 ПОЛЯ", self.main)
        manage_fields_action.triggered.connect(self.main.manage_custom_fields)
        toolbar.addAction(manage_fields_action)
        toolbar.addSeparator()
        # Кнопка поиска/фильтра
        search_action = QAction("🔍 Поиск", self.main)
        search_action.triggered.connect(self._show_search)
        search_action.setShortcut("Ctrl+F")
        toolbar.addAction(search_action)
        toolbar.addSeparator()
        # Скрыть/показать панель
        self.toggle_panel_action = QAction("▶️ Панель", self.main)
        self.toggle_panel_action.setCheckable(True)
        self.toggle_panel_action.setChecked(self.main.right_panel_visible)
        self.toggle_panel_action.triggered.connect(self.main.toggle_right_panel)
        toolbar.addAction(self.toggle_panel_action)
        toolbar.addSeparator()
        # Обновление
        refresh_action = QAction("🔄 Обновить", self.main)
        refresh_action.triggered.connect(self.main.load_coins)
        toolbar.addAction(refresh_action)
        return toolbar

    def update_style(self):
        """Применяет стили текущей темы ко всем виджетам панели"""
        t = self.main.theme_manager.current_theme
        text = t.get('text', '#e4e4ef')
        muted = t.get('tab_text', '#8888aa')
        base = t.get('base', '#1a1a2e')
        alt_base = t.get('alternate_base', '#16213e')
        border = t.get('border', '#2a2a4a')
        accent = t.get('accent', '#6c63ff')
        surface_hover = t.get('surface_hover', '#1f2b47')
        surface_active = t.get('surface_active', '#253352')
        window_bg = t.get('window_bg', '#0f0f1a')
        header_bg = t.get('table_header', '#16213e')
        header_text = t.get('table_header_text', '#a8a8d0')
        button_bg = t.get('button', '#16213e')
        input_bg = t.get('input_bg', '#16213e')
        error = t.get('error', '#f44336')

        # Тулбар
        if getattr(self, 'toolbar', None) is not None:
            self.toolbar.setStyleSheet(f"""
                QToolBar {{
                    border: none;
                    background-color: {window_bg};
                    padding: 2px;
                    spacing: 4px;
                }}
                QToolButton {{
                    background-color: transparent;
                    color: {text};
                    border-radius: 6px;
                    padding: 4px;
                }}
                QToolButton:hover {{
                    background-color: {surface_hover};
                }}
                QToolButton:pressed {{
                    background-color: {surface_active};
                }}
            """)

        # Информационная метка
        if getattr(self, 'info_label', None) is not None:
            self.info_label.setStyleSheet(f"""
                color: {muted};
                padding: 5px;
                background-color: {base};
                border: 1px solid {border};
                border-radius: 6px;
            """)

        # Строка поиска
        if getattr(self, 'search_frame', None) is not None:
            self.search_frame.setStyleSheet(f"""
                QFrame {{
                    background-color: {window_bg};
                    border: none;
                }}
            """)
        if getattr(self, 'search_input', None) is not None:
            self.search_input.setStyleSheet(f"""
                QLineEdit {{
                    background-color: {input_bg};
                    color: {text};
                    border: 1px solid {border};
                    border-radius: 6px;
                    padding: 3px 8px;
                    font-size: 12px;
                }}
                QLineEdit:focus {{
                    border-color: {accent};
                }}
            """)
        for btn in (getattr(self, 'clear_search_btn', None), getattr(self, 'hide_search_btn', None)):
            if btn is not None:
                btn.setStyleSheet(f"""
                    QPushButton {{
                        background-color: {button_bg};
                        color: {text};
                        border: 1px solid {border};
                        border-radius: 6px;
                        font-size: 14px;
                        font-weight: bold;
                    }}
                    QPushButton:hover {{
                        background-color: {surface_hover};
                        border-color: {accent};
                    }}
                """)
        if getattr(self, 'search_count_label', None) is not None:
            self.search_count_label.setStyleSheet(f"color: {accent}; font-size: 11px;")
        if getattr(self, 'filter_label', None) is not None:
            self.filter_label.setStyleSheet(f"color: {error}; font-size: 11px; padding: 2px 5px;")

        # Таблица
        if getattr(self, 'table', None) is not None:
            self.table.setStyleSheet(f"""
                QTableWidget {{
                    background-color: {base};
                    alternate-background-color: {alt_base};
                    color: {text};
                    gridline-color: {border};
                    selection-background-color: {accent};
                    selection-color: #ffffff;
                    border: 1px solid {border};
                    border-radius: 8px;
                }}
                QTableWidget::item:selected {{
                    background-color: {accent};
                    color: #ffffff;
                }}
                QTableWidget::item:hover {{
                    background-color: {surface_hover};
                    color: {text};
                }}
                QHeaderView::section {{
                    background-color: {header_bg};
                    color: {header_text};
                    padding: 5px;
                    border: none;
                    border-bottom: 2px solid {accent};
                    border-right: 1px solid {border};
                    font-weight: bold;
                }}
                QHeaderView::section:hover {{
                    background-color: {surface_hover};
                    color: {text};
                }}
                QHeaderView::section:down {{
                    background-color: {surface_active};
                }}
            """)

    def _show_search(self):
        """Показывает строку поиска"""
        self.search_frame.setVisible(True)
        self.search_input.setFocus()
        self.search_input.selectAll()
    
    def _hide_search(self):
        """Скрывает строку поиска и очищает фильтр"""
        self.search_input.clear()
        self.search_frame.setVisible(False)
        self._apply_filter("")
    
    def _on_search_text_changed(self, text):
        """Обработчик изменения текста в строке поиска"""
        if text.strip():
            self.clear_search_btn.setVisible(True)
        else:
            self.clear_search_btn.setVisible(False)
        
        # Применяем фильтр
        self._apply_filter(text)
    
    def _clear_search(self):
        """Очищает строку поиска"""
        self.search_input.clear()
        self.clear_search_btn.setVisible(False)
    
    def _apply_filter(self, text):
        """Фильтрует монеты по тексту во всех столбцах"""
        search_text = text.lower().strip()
        
        if not hasattr(self, '_all_coins') or not self._all_coins:
            return
        
        if not search_text:
            # Показываем все монеты
            self._filtered_coins = self._all_coins
            self.search_count_label.setText("")
        else:
            # Фильтруем
            filtered = []
            for coin in self._all_coins:
                if self._coin_matches_search(coin, search_text):
                    filtered.append(coin)
            self._filtered_coins = filtered
            
            # Обновляем метку
            total = len(self._all_coins)
            found = len(filtered)
            if found < total:
                self.search_count_label.setText(f"Найдено: {found} из {total}")
            else:
                self.search_count_label.setText(f"Всего: {total}")
        
        # Применяем также фильтр по колонке
        coins_to_show = self._apply_column_filter_to_list(self._filtered_coins)
        
        # Перестраиваем таблицу
        self.rebuild_table(coins_to_show)
        
        # Обновляем информационную метку
        filter_text = ""
        if search_text:
            filter_text += f" (фильтр: '{search_text}')"
        if self._column_filter:
            filter_text += f" (колонка: {self._column_filter['name']} = '{self._column_filter['value']}')"
        self.update_info_label(coins_to_show, filter_text)
    
    def _coin_matches_search(self, coin, search_text):
        """Проверяет, соответствует ли монета поисковому запросу"""
        if coin is None:
            return False
        
        # Проверяем все поля монеты
        fields_to_check = [
            coin.catalog_number,
            coin.denomination_value,
            coin.currency,
            str(coin.year) if coin.year else "",
            coin.mint,
            coin.mint_mark,
            coin.condition,
            getattr(coin, 'rarity', ''),
            getattr(coin, 'shape', ''),
            getattr(coin, 'issue_type', ''),
            getattr(coin, 'avrev', ''),
            getattr(coin, 'storage_location', ''),
            getattr(coin, 'acquisition_type', ''),
            getattr(coin, 'purchase_where', ''),
            getattr(coin, 'purchase_info', ''),
            getattr(coin, 'coin_info', ''),
            getattr(coin, 'notes', ''),
            str(coin.weight) if coin.weight else "",
            str(coin.diameter) if coin.diameter else "",
            str(coin.purchase_price) if coin.purchase_price else "",
            str(coin.market_price) if coin.market_price else "",
        ]
        
        # Проверяем страну
        if coin.country and search_text in coin.country.name.lower():
            return True
        
        # Проверяем покупку
        if hasattr(coin, 'purchase_country_obj') and coin.purchase_country_obj:
            if search_text in coin.purchase_country_obj.name.lower():
                return True
        
        # Проверяем металл
        if coin.metal_obj and search_text in coin.metal_obj.get_display_text().lower():
            return True
        
        # Проверяем монетный двор
        if coin.mint_obj and search_text in coin.mint_obj.get_display_text().lower():
            return True
        
        # Проверяем валюту
        if coin.currency_obj and search_text in coin.currency_obj.get_display_text().lower():
            return True
        
        # Проверяем поле периода
        if hasattr(coin, 'period_obj') and coin.period_obj:
            if search_text in coin.period_obj.get_display_text().lower():
                return True
        
        # Проверяем ID (точное совпадение)
        if search_text == str(coin.id):
            return True
        
        # Проверяем все текстовые поля
        for field in fields_to_check:
            if field and search_text in str(field).lower():
                return True
        
        # Проверяем пользовательские данные
        if hasattr(coin, 'custom_data') and coin.custom_data:
            try:
                import json
                custom_data = json.loads(coin.custom_data)
                for value in custom_data.values():
                    if value and search_text in str(value).lower():
                        return True
            except:
                pass
        
        # Проверяем справочники по ID
        if hasattr(coin, 'condition_ref') and coin.condition_ref:
            if search_text in coin.condition_ref.name.lower() or search_text in coin.condition_ref.value.lower():
                return True
        if hasattr(coin, 'rarity_ref') and coin.rarity_ref:
            if search_text in coin.rarity_ref.name.lower() or search_text in coin.rarity_ref.value.lower():
                return True
        if hasattr(coin, 'shape_ref') and coin.shape_ref:
            if search_text in coin.shape_ref.name.lower() or search_text in coin.shape_ref.value.lower():
                return True
        if hasattr(coin, 'issue_type_ref') and coin.issue_type_ref:
            if search_text in coin.issue_type_ref.name.lower() or search_text in coin.issue_type_ref.value.lower():
                return True
        if hasattr(coin, 'avrev_ref') and coin.avrev_ref:
            if search_text in coin.avrev_ref.name.lower() or search_text in coin.avrev_ref.value.lower():
                return True
        if hasattr(coin, 'status_ref') and coin.status_ref:
            if search_text in coin.status_ref.name.lower() or search_text in coin.status_ref.value.lower():
                return True
        if hasattr(coin, 'acquisition_type_ref') and coin.acquisition_type_ref:
            if search_text in coin.acquisition_type_ref.name.lower() or search_text in coin.acquisition_type_ref.value.lower():
                return True
        if hasattr(coin, 'storage_location_ref') and coin.storage_location_ref:
            if search_text in coin.storage_location_ref.name.lower() or search_text in coin.storage_location_ref.value.lower():
                return True
        
        return False
    
    def _show_header_filter_menu(self, position):
        """Показывает контекстное меню с уникальными значениями колонки для фильтрации"""
        header = self.table.horizontalHeader()
        logical_index = header.logicalIndexAt(position)
        
        if logical_index < 0 or logical_index >= len(self.current_columns):
            return
        
        column_info = self.current_columns[logical_index]
        column_key = column_info["key"]
        column_name = column_info["name"]
        
        # Пропускаем колонку с чекбоксами
        if column_key == "select":
            return
        
        # Собираем уникальные значения из видимых монет (с учетом фильтра дерева)
        coins = self._all_coins if hasattr(self, '_all_coins') else []
        unique_values = set()
        has_empty = False
        
        for coin in coins:
            if coin is None:
                continue
            value = self.main.get_coin_value(coin, column_key)
            if value and value.strip():
                unique_values.add(value.strip())
            else:
                has_empty = True
        
        # Создаем меню
        menu = QMenu(self.main)
        menu.setWindowTitle(f"Фильтр: {column_name}")
        
        # Заголовок меню
        title_action = QAction(f"📌 Фильтр по '{column_name}'", self.main)
        title_action.setEnabled(False)
        menu.addAction(title_action)
        menu.addSeparator()
        
        # Кнопка сброса фильтра
        clear_action = QAction("🔄 Сбросить фильтр", self.main)
        clear_action.triggered.connect(self._clear_column_filter)
        menu.addAction(clear_action)
        menu.addSeparator()
        
        # Фильтр по пустым значениям
        if has_empty:
            empty_action = QAction("📭 Пустые значения", self.main)
            empty_action.triggered.connect(lambda checked, k=column_key, n=column_name: 
                                           self._apply_column_filter_empty(k, n))
            menu.addAction(empty_action)
            menu.addSeparator()
        
        # Условия > и < для числовых колонок
        if column_key in ["year", "weight", "diameter", "purchase_price", "market_price", "id"]:
            greater_action = QAction(f"📈 {column_name} > ...", self.main)
            greater_action.triggered.connect(lambda checked, k=column_key, n=column_name: 
                                             self._apply_column_filter_condition(k, n, ">"))
            menu.addAction(greater_action)
            
            less_action = QAction(f"📉 {column_name} < ...", self.main)
            less_action.triggered.connect(lambda checked, k=column_key, n=column_name: 
                                          self._apply_column_filter_condition(k, n, "<"))
            menu.addAction(less_action)
            
            menu.addSeparator()
        
        # Добавляем значения
        if unique_values:
            sorted_values = sorted(unique_values, key=str)
            
            # Если значений больше 10, создаем подменю с прокруткой
            if len(sorted_values) > 10:
                # Создаем подменю со скроллом (имитация через QMenu)
                values_menu = QMenu(f"📋 Значения ({len(sorted_values)})", self.main)
                
                # Разбиваем на группы по 15 для вложенных меню
                chunk_size = 15
                for i in range(0, len(sorted_values), chunk_size):
                    chunk = sorted_values[i:i + chunk_size]
                    if i == 0:
                        chunk_menu = values_menu
                    else:
                        start_val = chunk[0][:20]
                        end_val = chunk[-1][:20]
                        chunk_menu = QMenu(f"{start_val}... — ...{end_val}", self.main)
                        values_menu.addMenu(chunk_menu)
                    
                    for value in chunk:
                        # Обрезаем длинные значения
                        display_value = value if len(value) <= 40 else value[:37] + "..."
                        action = QAction(display_value, self.main)
                        action.setToolTip(value)
                        action.triggered.connect(lambda checked, v=value, k=column_key, n=column_name: 
                                                 self._apply_column_filter(v, k, n))
                        chunk_menu.addAction(action)
                
                menu.addMenu(values_menu)
            else:
                # Если значений 10 или меньше — показываем прямо в меню
                for value in sorted_values:
                    display_value = value if len(value) <= 40 else value[:37] + "..."
                    action = QAction(display_value, self.main)
                    action.setToolTip(value)
                    action.triggered.connect(lambda checked, v=value, k=column_key, n=column_name: 
                                             self._apply_column_filter(v, k, n))
                    menu.addAction(action)
        
        menu.exec(header.mapToGlobal(position))

    def _apply_column_filter(self, value, column_key, column_name):
        """Применяет фильтр по значению в колонке"""
        self._column_filter = {
            'key': column_key,
            'value': value,
            'name': column_name
        }
        
        # Показываем метку фильтра
        self.filter_label.setText(f"🔍 Фильтр: {column_name} = '{value}'  [нажмите для сброса]")
        self.filter_label.setVisible(True)
        self.filter_label.setCursor(Qt.PointingHandCursor)
        self.filter_label.mousePressEvent = lambda event: self._clear_column_filter()
        
        # Применяем фильтр
        self._apply_filter(self.search_input.text() if self.search_input else "")
    
    def _clear_column_filter(self):
        """Сбрасывает фильтр по колонке"""
        self._column_filter = None
        self.filter_label.setVisible(False)
        
        # Восстанавливаем таблицу
        self._apply_filter(self.search_input.text() if self.search_input else "")
    
    def _apply_column_filter_to_list(self, coins):
        """Применяет фильтр колонки к списку монет"""
        if not self._column_filter:
            return coins
        
        column_key = self._column_filter['key']
        filter_value = self._column_filter['value']
        condition = self._column_filter.get('condition', 'equal')
        
        filtered = []
        for coin in coins:
            if coin is None:
                continue
            
            value = self.main.get_coin_value(coin, column_key)
            value_str = value.strip() if value else ""
            
            if condition == 'empty':
                # Фильтр по пустым значениям
                if not value_str:
                    filtered.append(coin)
                    
            elif condition == '>':
                # Фильтр "больше"
                try:
                    num_value = float(value_str.replace(',', '.')) if value_str else None
                    if num_value is not None and num_value > filter_value:
                        filtered.append(coin)
                except (ValueError, TypeError):
                    pass
                    
            elif condition == '<':
                # Фильтр "меньше"
                try:
                    num_value = float(value_str.replace(',', '.')) if value_str else None
                    if num_value is not None and num_value < filter_value:
                        filtered.append(coin)
                except (ValueError, TypeError):
                    pass
                    
            else:
                # Фильтр по точному совпадению
                if value_str == filter_value:
                    filtered.append(coin)
        
        return filtered

    def refresh_columns(self):
        """Обновляет колонки таблицы без перезагрузки данных"""
        self.logger.info("=== ОБНОВЛЕНИЕ КОЛОНОК ===")
        
        # Сохраняем текущую ширину колонок
        current_widths = {}
        if self.table and self.current_columns:
            for i, col in enumerate(self.current_columns):
                if i < self.table.columnCount():
                    current_widths[col["key"]] = self.table.columnWidth(i)
        
        # Сохраняем текущие данные
        current_coins = self.main.current_coins if hasattr(self.main, 'current_coins') else []
        
        # Загружаем свежие настройки полей
        self.load_custom_fields()
        
        # Загружаем настройки всех полей из БД
        field_settings = {f.field_key: f for f in self.main.db_manager.get_all_field_settings()}
        
        # Создаём новый список колонок
        new_columns = []
        
        # Добавляем select в начало
        from gui.dialogs.column_selector import ColumnSelectorDialog
        for col in ColumnSelectorDialog.STANDARD_COLUMNS:
            if col["key"] == "select":
                select_col = col.copy()
                select_col['width'] = current_widths.get("select", 30)
                new_columns.append(select_col)
                break
        
        # Добавляем стандартные колонки в соответствии с настройками
        for col in ColumnSelectorDialog.STANDARD_COLUMNS:
            if col["key"] == "select":
                continue
            
            settings = field_settings.get(col["key"])
            if settings and not settings.show_in_table:
                continue
            if not settings and not col.get("default", False):
                continue
            
            col_copy = col.copy()
            if settings and settings.name:
                col_copy["name"] = settings.name
            
            # Восстанавливаем сохранённую ширину
            if col["key"] in current_widths:
                col_copy["width"] = current_widths[col["key"]]
            else:
                col_copy["width"] = col.get("width", 100)
            
            new_columns.append(col_copy)
        
        # Добавляем пользовательские поля
        for field in self.custom_fields:
            if field.show_in_table:
                col = {
                    "key": f"custom_{field.field_key}",
                    "field_key": field.field_key,
                    "name": field.name,
                    "width": current_widths.get(f"custom_{field.field_key}", 120),
                    "is_custom": True,
                    "field_type": field.field_type
                }
                new_columns.append(col)
        
        # Обновляем текущие колонки
        self.current_columns = new_columns
        
        # Перестраиваем заголовки таблицы
        self.table.setColumnCount(len(self.current_columns))
        headers = [col["name"] for col in self.current_columns]
        self.table.setHorizontalHeaderLabels(headers)
        
        # Восстанавливаем ширину колонок
        header = self.table.horizontalHeader()
        for i, col in enumerate(self.current_columns):
            header.setSectionResizeMode(i, QHeaderView.Interactive)
            width = col.get("width", 100)
            if width > 0:
                self.table.setColumnWidth(i, width)
        
        # Перезаполняем таблицу данными
        if current_coins:
            self.save_state()
            self.rebuild_table(current_coins)
            QTimer.singleShot(50, self.restore_state)
        
        self.logger.info(f"Колонки обновлены, всего {len(self.current_columns)} колонок")
    
    def initialize_table_columns(self):
        """Инициализирует колонки таблицы"""
        try:
            from gui.dialogs.column_selector import ColumnSelectorDialog
            self.logger.info("Начало инициализации колонок")
            # Загружаем пользовательские поля
            self.load_custom_fields()
            # Загружаем кэш справочников
            self.load_reference_caches()
            # Загружаем настройки всех полей из БД
            self.logger.info("Загрузка настроек полей из БД...")
            field_settings = {f.field_key: f for f in self.main.db_manager.get_all_field_settings()}
            self.logger.info(f"Загружено настроек: {len(field_settings)}")
            # Если колонки еще не загружены, создаем с дефолтными
            if not self.current_columns:
                self.logger.info("Создание колонок по умолчанию")
                self.current_columns = []
                # Добавляем стандартные колонки
                for col in ColumnSelectorDialog.STANDARD_COLUMNS:
                    if col["key"] == "select":
                        continue
                    settings = field_settings.get(col["key"])
                    if settings and not settings.show_in_table:
                        continue
                    if not settings and not col.get("default", False):
                        continue
                    col_copy = col.copy()
                    if settings and settings.name:
                        col_copy["name"] = settings.name
                    self.current_columns.append(col_copy)
                # Добавляем пользовательские поля
                for field in self.custom_fields:
                    if field.show_in_table:
                        self.current_columns.append({
                            "key": f"custom_{field.field_key}",
                            "field_key": field.field_key,
                            "name": field.name,
                            "width": 120,
                            "is_custom": True,
                            "field_type": field.field_type
                        })
                # Добавляем колонку select в начало
                for col in ColumnSelectorDialog.STANDARD_COLUMNS:
                    if col["key"] == "select":
                        select_col = col.copy()
                        select_col['width'] = 30
                        self.current_columns.insert(0, select_col)
                        break
                self.logger.info(f"Создано {len(self.current_columns)} колонок")
            # === УДАЛЯЕМ ДУБЛИКАТЫ КОЛОНОК ===
            seen_keys = set()
            unique_columns = []
            for col in self.current_columns:
                key = col["key"]
                if key not in seen_keys:
                    seen_keys.add(key)
                    unique_columns.append(col)
                else:
                    self.logger.warning(f"⚠️ Удалён дубликат колонки: {key}")
            if len(unique_columns) < len(self.current_columns):
                self.current_columns = unique_columns
                self.logger.info(f"После удаления дубликатов: {len(self.current_columns)} колонок")
            # === ПОДСТАВЛЯЕМ СОХРАНЁННЫЕ ШИРИНЫ ИЗ БАЗЫ В current_columns ===
            # Благодаря этому И initialize, И каждый rebuild_table используют сохранённые ширины
            saved = getattr(self, '_saved_columns_info', None)
            if saved:
                saved_by_label = {c.get('label'): c for c in saved}
                for col in self.current_columns:
                    s = saved_by_label.get(col["name"])
                    if s and s.get('width') and s['width'] > 10:
                        col["width"] = s['width']
                self.logger.info("💾 Сохранённые ширины подставлены в current_columns")
            # Устанавливаем колонки
            self.logger.info("Установка колонок в таблицу...")
            self.table.setColumnCount(len(self.current_columns))
            headers = [col["name"] for col in self.current_columns]
            self.table.setHorizontalHeaderLabels(headers)
            # Настраиваем ширину
            header = self.table.horizontalHeader()
            for i, col in enumerate(self.current_columns):
                header.setSectionResizeMode(i, QHeaderView.Interactive)
                width = col.get("width", 100)
                if width > 0:
                    self.table.setColumnWidth(i, width)
            # Поверх применяем сохранённые ширины и видимость (на случай скрытых колонок)
            self._apply_column_widths()
            # Подключаем сигнал
            if not self._signal_connected:
                self.logger.info("Подключение сигнала itemChanged...")
                try:
                    self.table.itemChanged.connect(self._on_item_checkbox_changed)
                    self._signal_connected = True
                except Exception as e:
                    self.logger.error(f"Ошибка подключения сигнала: {e}")
            # Перестраиваем таблицу
            if hasattr(self.main, 'current_coins') and self.main.current_coins:
                self.logger.info("Перестройка таблицы...")
                self.rebuild_table(self.main.current_coins)
            self.logger.info(f"✅ Таблица инициализирована с {len(self.current_columns)} колонками")
        except Exception as e:
            self.logger.error(f"Ошибка в initialize_table_columns: {e}", exc_info=True)
            raise

    def load_columns_from_settings(self, column_info):
        """Загружает сохранённые ширины/видимость колонок"""
        self._saved_columns_info = column_info
        if getattr(self, 'table', None):
            self._apply_column_widths()

    def apply_column_order(self, column_order):
        """Применяет порядок колонок из настроек"""
        if not column_order or not self.current_columns:
            return
        
        columns_dict = {col["key"]: col for col in self.current_columns}
        ordered_columns = []
        
        if "select" in columns_dict:
            ordered_columns.append(columns_dict["select"])
        
        for col_key in column_order:
            if col_key in columns_dict and col_key != "select":
                ordered_columns.append(columns_dict[col_key])
        
        for col in self.current_columns:
            if col not in ordered_columns and col["key"] != "select":
                ordered_columns.append(col)
        
        if len(ordered_columns) == len(self.current_columns):
            self.current_columns = ordered_columns

    def get_columns_info(self):
        """Возвращает информацию о колонках (ширина, видимость) для сохранения"""
        if not getattr(self, 'table', None):
            return getattr(self, '_saved_columns_info', [])
        info = []
        for i in range(self.table.columnCount()):
            item = self.table.horizontalHeaderItem(i)
            label = item.text() if item else str(i)
            info.append({
                'label': label,
                'width': self.table.columnWidth(i),
                'hidden': self.table.isColumnHidden(i),
            })
        self._saved_columns_info = info
        return info
    
    def get_column_order(self):
        """Возвращает порядок колонок для сохранения"""
        if not self.current_columns:
            return []
        return [col["key"] for col in self.current_columns]
    
    def _configure_columns(self):
        """Открывает диалог настройки колонок"""
        current_keys = [col["key"] for col in self.current_columns] if self.current_columns else []
        
        dialog = ColumnSelectorDialog(self.main, current_keys, self.main.db_manager)
        dialog.columns_changed.connect(self._on_columns_changed)
        if dialog.exec():
            selected_columns = dialog.get_selected_columns()
            if selected_columns:
                self._apply_column_settings(selected_columns)
    
    def _on_columns_changed(self):
        """Обработчик изменения колонок"""
        self.initialize_table_columns()
        self.main.load_coins()
    
    def _apply_column_settings(self, selected_columns):
        """Применяет настройки колонок"""
        from gui.dialogs.column_selector import ColumnSelectorDialog
        
        # Сохраняем текущую ширину колонок
        current_widths = {}
        if self.table and self.current_columns:
            for i, col in enumerate(self.current_columns):
                if i < self.table.columnCount():
                    current_widths[col["key"]] = self.table.columnWidth(i)
        
        field_settings = {f.field_key: f for f in self.main.db_manager.get_all_field_settings()}
        
        filtered_columns = []
        for col in selected_columns:
            if col["key"] == "select":
                if col["key"] in current_widths:
                    col["width"] = current_widths[col["key"]]
                filtered_columns.append(col)
                continue
            
            if col.get("is_custom") or col["key"].startswith("custom_"):
                field_key = col.get("field_key") or col["key"].replace("custom_", "")
                for field in self.custom_fields:
                    if field.field_key == field_key and field.show_in_table:
                        if col["key"] in current_widths:
                            col["width"] = current_widths[col["key"]]
                        filtered_columns.append(col)
                        break
            else:
                settings = field_settings.get(col["key"])
                if settings and not settings.show_in_table:
                    continue
                if col["key"] in current_widths:
                    col["width"] = current_widths[col["key"]]
                filtered_columns.append(col)
        
        has_select = any(col["key"] == "select" for col in filtered_columns)
        if not has_select:
            for col in ColumnSelectorDialog.STANDARD_COLUMNS:
                if col["key"] == "select":
                    select_col = col.copy()
                    select_col['width'] = current_widths.get("select", 30)
                    filtered_columns.insert(0, select_col)
                    break
        
        self.current_columns = filtered_columns
        self.refresh_columns()
        
        self.sort_column = None
        self.sort_order = 0
        
        self.main.save_settings()
        self.main.status_bar.showMessage("Колонки обновлены", 3000)
    
    def _on_column_moved(self, logical_index, old_visual_index, new_visual_index):
        """Обработчик перемещения колонок"""
        header = self.table.horizontalHeader()
        new_order = []
        
        for visual_pos in range(header.count()):
            logical_idx = header.logicalIndex(visual_pos)
            if 0 <= logical_idx < len(self.current_columns):
                new_order.append(self.current_columns[logical_idx])
        
        if len(new_order) == len(self.current_columns):
            old_keys = [col["key"] for col in self.current_columns]
            new_keys = [col["key"] for col in new_order]
            
            if old_keys != new_keys:
                self.current_columns = new_order
                headers = [col["name"] for col in self.current_columns]
                self.table.setHorizontalHeaderLabels(headers)
                self.main.save_settings()
                self.rebuild_table(self.main.current_coins)
    
    def _on_header_clicked(self, logical_index):
        """Обработчик клика по заголовку для сортировки"""
        if logical_index < 0 or logical_index >= len(self.current_columns):
            return
        
        column_key = self.current_columns[logical_index]["key"]
        
        if self.sort_column != column_key:
            self.sort_column = column_key
            self.sort_order = 1
        else:
            self.sort_order = (self.sort_order + 1) % 3
            if self.sort_order == 0:
                self.sort_column = None
        
        self.main.load_coins()
        self.main.save_settings()
        
        if hasattr(self.main, 'current_coins'):
            self.update_info_label(self.main.current_coins)
    
    def get_custom_field_value(self, coin, field_key):
        """Получает значение пользовательского поля монеты"""
        return coin.get_custom_value(field_key)
    
    def rebuild_table(self, coins):
        """Перестройка таблицы с пагинацией.
        Полный список — в _full_coins и _frozen_list (только словари)."""
        self._full_coins = list(coins or [])
        if not hasattr(self, '_current_page'):
            self._current_page = 0
        if not hasattr(self, '_page_size'):
            self._page_size = 500
        # Самозащита: если колонки не инициализированы — инициализируем
        if not self.current_columns and hasattr(self, 'initialize_table_columns'):
            try:
                self.initialize_table_columns()
            except Exception as e:
                self.logger.error(f"Не удалось инициализировать колонки: {e}")
        self._ensure_pagination_bar()
        self._render_page()
        # Страховка: если при старте что-то пошло не так — перерисуем через 700мс
        if self.table.rowCount() <= 1 and len(self._full_coins) > 1:
            from PySide6.QtCore import QTimer
            QTimer.singleShot(700, self._render_page)

    def update_info_label(self, coins):
        """Обновляет информационную надпись под таблицей.
        Защищено от DetachedInstanceError через getattr/try-except."""
        if not coins:
            if hasattr(self, 'info_label') and self.info_label is not None:
                try:
                    self.info_label.setText("Коллекция пуста")
                except RuntimeError:
                    pass
            return

        total = len(coins)
        in_collection = 0
        total_value = 0.0
        
        for coin in coins:
            if not coin:
                continue
            try:
                # Безопасное чтение атрибутов (не падает на detached-объектах)
                if getattr(coin, 'in_collection', False):
                    in_collection += 1
                price = getattr(coin, 'purchase_price', None)
                if price:
                    try:
                        total_value += float(price)
                    except (TypeError, ValueError):
                        pass
            except Exception:
                # Объект откреплён от сессии — пропускаем
                continue

        if hasattr(self, 'info_label') and self.info_label is not None:
            try:
                text = f"Всего: {total} | В коллекции: {in_collection}"
                if total_value > 0:
                    text += f" | Сумма: {total_value:,.2f}"
                self.info_label.setText(text)
            except RuntimeError:
                pass
 
    def update_toggle_panel_action(self, visible):
        """Обновляет состояние кнопки скрытия панели"""
        if self.toggle_panel_action:
            if visible:
                self.toggle_panel_action.setText("▶️ Скрыть панель")
                self.toggle_panel_action.setChecked(True)
            else:
                self.toggle_panel_action.setText("◀️ Показать панель")
                self.toggle_panel_action.setChecked(False)
    
    def save_state(self):
        """Сохраняет состояние таблицы"""
        if self.table:
            scroll_bar = self.table.verticalScrollBar()
            if scroll_bar:
                self._scroll_position = scroll_bar.value()
            
            current_row = self.table.currentRow()
            self._selected_row = current_row if current_row >= 0 else -1
    
    def restore_state(self):
        """Восстанавливает состояние таблицы"""
        if not self.table:
            return
        
        if self._selected_row >= 0 and self._selected_row < self.table.rowCount():
            self.table.selectRow(self._selected_row)
            self.table.setCurrentCell(self._selected_row, 0)
        
        if self._scroll_position > 0:
            scroll_bar = self.table.verticalScrollBar()
            if scroll_bar:
                QTimer.singleShot(50, lambda: scroll_bar.setValue(self._scroll_position))
    
    def _show_context_menu(self, position):
        """Контекстное меню монеты. TablePanelManager — НЕ виджет,
        поэтому родитель всех QMenu/QAction — self.main."""
        from sqlalchemy.orm.exc import DetachedInstanceError
        parent = self.main
        try:
            index = self.table.indexAt(position)
            if not index.isValid():
                return
            row = index.row()
            coin = None
            coin_id = None
            # Строка может быть словарём (пагинация) — берём _id
            frozen = getattr(self, '_frozen_list', []) or []
            if 0 <= row < len(frozen):
                d = frozen[row]
                coin_id = d.get('_id') if isinstance(d, dict) else getattr(d, 'id', None)
            if coin_id is None:
                coins = getattr(self, '_filtered_coins', None) or []
                if 0 <= row < len(coins):
                    c = coins[row]
                    coin = c if not isinstance(c, dict) else None
                    coin_id = getattr(c, 'id', None) if isinstance(c, dict) is False else (c.get('_id') if isinstance(c, dict) else None)
            if coin_id is None:
                return
            # Свежий объект из БД — DetachedInstanceError невозможен
            if coin is None:
                coin = self.main.db_manager.get_coin(coin_id)
            if coin is None:
                return
            try:
                country_id = coin.country_id
            except DetachedInstanceError:
                coin = self.main.db_manager.get_coin(coin_id)
                country_id = getattr(coin, 'country_id', None)

            menu = QMenu(parent)
            menu.setWindowTitle("Монета")

            edit_action = QAction("✏️ Редактировать", parent)
            edit_action.triggered.connect(lambda: self._edit_coin(coin))
            menu.addAction(edit_action)

            if getattr(coin, 'in_collection', False):
                coll_action = QAction("➖ Убрать из коллекции", parent)
            else:
                coll_action = QAction("➕ Добавить в коллекцию", parent)
            coll_action.triggered.connect(lambda: self._toggle_collection(coin))
            menu.addAction(coll_action)

            menu.addSeparator()
            copy_action = QAction("📋 Копировать данные", parent)
            copy_action.triggered.connect(lambda: self._copy_coin_data(coin))
            menu.addAction(copy_action)

            if country_id or getattr(coin, 'ucoin_url', None):
                ucoin_action = QAction("🌐 Открыть на UCOIN", parent)
                ucoin_action.triggered.connect(
                    lambda: self._open_coin_url(coin.id, 'ucoin'))
                menu.addAction(ucoin_action)
            meshok_action = QAction("🛒 Искать на Meshok", parent)
            meshok_action.triggered.connect(
                lambda: self._open_coin_url(coin.id, 'meshok'))
            menu.addAction(meshok_action)

            menu.addSeparator()
            status_menu = menu.addMenu("🏷️ Сменить статус")
            try:
                for st in self.main.db_manager.session.query(
                        StandardReference).filter_by(field_key='status').all():
                    act = QAction(st.name, parent)
                    act.triggered.connect(
                        lambda checked, sid=coin.id, sv=st.value:
                        self._set_status_for_coin(sid, sv))
                    status_menu.addAction(act)
            except Exception:
                pass

            menu.addSeparator()
            mark_action = QAction("☑ Отметить выделенные строки", parent)
            mark_action.triggered.connect(self._mark_selected_rows)
            menu.addAction(mark_action)
            mass_action = QAction("✏️ Массовое изменение выделенных", parent)
            mass_action.triggered.connect(self._mass_edit_selected_rows)
            menu.addAction(mass_action)
            print_action = QAction("🖨️ Печать этикеток", parent)
            print_action.triggered.connect(self._print_holder_labels)
            menu.addAction(print_action)

            menu.addSeparator()
            delete_action = QAction("🗑️ Удалить", parent)
            delete_action.triggered.connect(lambda: self._delete_coin(coin))
            menu.addAction(delete_action)
            refresh_action = QAction("🔄 Обновить таблицу", parent)
            refresh_action.triggered.connect(self.main.load_coins)
            menu.addAction(refresh_action)

            menu.exec(self.table.viewport().mapToGlobal(position))
        except DetachedInstanceError as e:
            self.logger.warning(f"⚠️ DetachedInstanceError при ПКМ: {e}")
            menu = QMenu(parent)
            act = QAction("🔄 Обновить таблицу", parent)
            act.triggered.connect(self.main.load_coins)
            menu.addAction(act)
            menu.exec(self.table.viewport().mapToGlobal(position))
        except Exception as e:
            self.logger.error(f"Ошибка построения контекстного меню: {e}")
            import traceback
            traceback.print_exc()

    def _set_status_for_coin(self, coin_id, status_value):
        """Устанавливает статус для одной монеты"""
        try:
            from database.models import StandardReference, Coin
            from datetime import datetime
            
            status_ref = self.main.db_manager.session.query(StandardReference).filter_by(
                field_key='status', value=status_value
            ).first()
            
            if status_ref:
                self.main.db_manager.session.query(Coin).filter(
                    Coin.id == coin_id
                ).update({
                    'status': status_value,
                    'status_id': status_ref.id,
                    'updated_at': datetime.now()
                })
                self.main.db_manager.session.commit()
                
                self.main.load_coins()
                self.main.status_bar.showMessage(f"✅ Статус изменён на {status_ref.name}", 2000)
        except Exception as e:
            self.logger.error(f"Ошибка при смене статуса: {e}")
            self.main.db_manager.session.rollback()
    
    def _set_status_for_selected(self, status_value):
        """Устанавливает статус для всех выбранных монет (по чекбоксам)"""
        selected_ids = self.get_selected_coin_ids()
        if not selected_ids:
            QMessageBox.warning(self.main, "Предупреждение", "Нет выбранных монет")
            return
        
        from database.models import StandardReference, Coin
        from datetime import datetime
        
        status_ref = self.main.db_manager.session.query(StandardReference).filter_by(
            field_key='status', value=status_value
        ).first()
        
        if not status_ref:
            return
        
        count = 0
        for coin_id in selected_ids:
            try:
                self.main.db_manager.session.query(Coin).filter(
                    Coin.id == coin_id
                ).update({
                    'status': status_value,
                    'status_id': status_ref.id,
                    'updated_at': datetime.now()
                })
                count += 1
            except Exception as e:
                self.logger.error(f"Ошибка при обновлении монеты {coin_id}: {e}")
        
        self.main.db_manager.session.commit()
        self.main.load_coins()
        self.main.status_bar.showMessage(f"✅ Статус изменён для {count} монет", 3000)
    
    def _set_status_for_selected_rows(self, status_value):
        """Устанавливает статус для всех выделенных строк (синим)"""
        selected_rows = set()
        for selected_range in self.table.selectedRanges():
            for row in range(selected_range.topRow(), selected_range.bottomRow() + 1):
                selected_rows.add(row)
        
        if not selected_rows:
            QMessageBox.warning(self.main, "Предупреждение", "Нет выделенных строк")
            return
        
        select_col = -1
        for col, col_info in enumerate(self.current_columns):
            if col_info["key"] == "select":
                select_col = col
                break
        
        coin_ids = []
        for row in selected_rows:
            if select_col != -1:
                item = self.table.item(row, select_col)
                if item:
                    coin_id = item.data(Qt.UserRole)
                    if coin_id:
                        coin_ids.append(coin_id)
            else:
                item = self.table.item(row, 0)
                if item:
                    coin_id = item.data(Qt.UserRole)
                    if coin_id:
                        coin_ids.append(coin_id)
        
        if not coin_ids:
            QMessageBox.warning(self.main, "Предупреждение", "Не удалось получить ID монет")
            return
        
        from database.models import StandardReference, Coin
        from datetime import datetime
        
        status_ref = self.main.db_manager.session.query(StandardReference).filter_by(
            field_key='status', value=status_value
        ).first()
        
        if not status_ref:
            return
        
        count = 0
        for coin_id in coin_ids:
            try:
                self.main.db_manager.session.query(Coin).filter(
                    Coin.id == coin_id
                ).update({
                    'status': status_value,
                    'status_id': status_ref.id,
                    'updated_at': datetime.now()
                })
                count += 1
            except Exception as e:
                self.logger.error(f"Ошибка при обновлении монеты {coin_id}: {e}")
        
        self.main.db_manager.session.commit()
        self.main.load_coins()
        self.main.status_bar.showMessage(f"✅ Статус изменён для {count} монет", 3000)
    
    def _mass_edit_selected(self):
        """Массовое изменение выбранных монет (по чекбоксам)"""
        selected_ids = self.get_selected_coin_ids()
        if not selected_ids:
            QMessageBox.warning(self.main, "Предупреждение", 
                "Нет выбранных монет.\nОтметьте монеты в колонке ☑")
            return
        
        selected_coins = []
        for coin in self.main.current_coins:
            if coin and coin.id in selected_ids:
                selected_coins.append(coin)
        
        try:
            from gui.dialogs.mass_edit_dialog import MassEditDialog
            dialog = MassEditDialog(self.main.db_manager, selected_coins, self.main)
            if dialog.exec():
                changes = dialog.get_changes()
                if changes:
                    self._apply_mass_edit(selected_ids, changes)
        except ImportError as e:
            self.logger.error(f"Не удалось импортировать MassEditDialog: {e}")
            QMessageBox.critical(self.main, "Ошибка", 
                "Не удалось загрузить диалог массового изменения.\n"
                "Убедитесь, что файл gui/dialogs/mass_edit_dialog.py существует")
    
    def _mass_edit_selected_rows(self):
        """Массовое изменение выделенных строк (синим)"""
        selected_rows = set()
        for selected_range in self.table.selectedRanges():
            for row in range(selected_range.topRow(), selected_range.bottomRow() + 1):
                selected_rows.add(row)
        
        if not selected_rows:
            QMessageBox.warning(self.main, "Предупреждение", "Нет выделенных строк")
            return
        
        select_col = -1
        for col, col_info in enumerate(self.current_columns):
            if col_info["key"] == "select":
                select_col = col
                break
        
        coin_ids = []
        for row in selected_rows:
            if select_col != -1:
                item = self.table.item(row, select_col)
                if item:
                    coin_id = item.data(Qt.UserRole)
                    if coin_id:
                        coin_ids.append(coin_id)
            else:
                item = self.table.item(row, 0)
                if item:
                    coin_id = item.data(Qt.UserRole)
                    if coin_id:
                        coin_ids.append(coin_id)
        
        if not coin_ids:
            QMessageBox.warning(self.main, "Предупреждение", "Не удалось получить ID монет")
            return
        
        selected_coins = []
        for coin in self.main.current_coins:
            if coin and coin.id in coin_ids:
                selected_coins.append(coin)
        
        try:
            from gui.dialogs.mass_edit_dialog import MassEditDialog
            dialog = MassEditDialog(self.main.db_manager, selected_coins, self.main)
            if dialog.exec():
                changes = dialog.get_changes()
                if changes:
                    self._apply_mass_edit(coin_ids, changes)
        except ImportError as e:
            self.logger.error(f"Не удалось импортировать MassEditDialog: {e}")
            QMessageBox.critical(self.main, "Ошибка", 
                "Не удалось загрузить диалог массового изменения.")

    def _apply_mass_edit(self, coin_ids, changes):
        """Применяет массовые изменения к монетам"""
        try:
            self.logger.info(f"Массовое изменение {len(coin_ids)} монет")
            
            updated_count = 0
            error_count = 0
            
            for coin_id in coin_ids:
                try:
                    success = self.main.db_manager.update_coin(coin_id, changes)
                    if success:
                        updated_count += 1
                    else:
                        error_count += 1
                except Exception as e:
                    self.logger.error(f"Ошибка при обновлении монеты {coin_id}: {e}")
                    error_count += 1
            
            self.save_state()
            self.main.load_coins()
            self.main.load_country_tree(preserve_expanded=True)
            QTimer.singleShot(100, self.restore_state)
            
            QMessageBox.information(
                self.main, "Массовое изменение",
                f"✅ Обновлено монет: {updated_count}\n"
                f"❌ Ошибок: {error_count}"
            )
            
            self.main.status_bar.showMessage(f"✅ Массовое изменение: {updated_count} монет обновлено", 5000)
            
        except Exception as e:
            self.logger.error(f"Ошибка при массовом изменении: {e}")
            QMessageBox.critical(self.main, "Ошибка", f"Не удалось выполнить массовое изменение:\n{e}")

    def get_table(self):
        """Возвращает виджет таблицы"""
        return self.table
    
    def get_selected_coin_ids(self):
        """Возвращает список ID выбранных монет (по чекбоксам)"""
        selected_ids = []
        select_col = -1
        for col, col_info in enumerate(self.current_columns):
            if col_info["key"] == "select":
                select_col = col
                break
        
        if select_col == -1:
            return selected_ids
        
        for row in range(self.table.rowCount()):
            item = self.table.item(row, select_col)
            if item and item.checkState() == Qt.Checked:
                coin_id = item.data(Qt.UserRole)
                if coin_id:
                    selected_ids.append(coin_id)
        return selected_ids
    
    def select_all(self):
        """Отмечает все монеты"""
        from database.models import Coin
        
        select_col = -1
        for col, col_info in enumerate(self.current_columns):
            if col_info["key"] == "select":
                select_col = col
                break
        
        if select_col == -1:
            return
        
        try:
            for row in range(self.table.rowCount()):
                item = self.table.item(row, select_col)
                if item:
                    coin_id = item.data(Qt.UserRole)
                    if coin_id:
                        self.main.db_manager.session.query(Coin).filter(
                            Coin.id == coin_id
                        ).update({"selected": True})
                        item.setCheckState(Qt.Checked)
            
            self.main.db_manager.session.commit()
            self.update_info_label(self.main.current_coins)
            
        except Exception as e:
            self.logger.error(f"Ошибка при выделении всех: {e}")
            self.main.db_manager.session.rollback()
    
    def clear_selection(self):
        """Снимает отметки со всех монет"""
        from database.models import Coin
        
        select_col = -1
        for col, col_info in enumerate(self.current_columns):
            if col_info["key"] == "select":
                select_col = col
                break
        
        if select_col == -1:
            return
        
        try:
            for row in range(self.table.rowCount()):
                item = self.table.item(row, select_col)
                if item:
                    coin_id = item.data(Qt.UserRole)
                    if coin_id:
                        self.main.db_manager.session.query(Coin).filter(
                            Coin.id == coin_id
                        ).update({"selected": False})
                        item.setCheckState(Qt.Unchecked)
            
            self.main.db_manager.session.commit()
            self.update_info_label(self.main.current_coins)
            
        except Exception as e:
            self.logger.error(f"Ошибка при снятии выделения: {e}")
            self.main.db_manager.session.rollback()

    def invert_selection(self):
        """Инвертирует выделение"""
        select_col = -1
        for col, col_info in enumerate(self.current_columns):
            if col_info["key"] == "select":
                select_col = col
                break
        
        if select_col == -1:
            return
        
        for row in range(self.table.rowCount()):
            item = self.table.item(row, select_col)
            if item:
                new_state = Qt.Unchecked if item.checkState() == Qt.Checked else Qt.Checked
                item.setCheckState(new_state)
    
    def get_selection_count(self):
        """Возвращает количество выбранных монет"""
        select_col = -1
        for col, col_info in enumerate(self.current_columns):
            if col_info["key"] == "select":
                select_col = col
                break
        
        if select_col == -1:
            return 0
        
        count = 0
        for row in range(self.table.rowCount()):
            item = self.table.item(row, select_col)
            if item and item.checkState() == Qt.Checked:
                count += 1
        return count
    
    def _mark_selected_rows(self):
        """Отмечает чекбоксами выделенные строки (синим)"""
        from database.models import Coin
        
        select_col = -1
        for col, col_info in enumerate(self.current_columns):
            if col_info["key"] == "select":
                select_col = col
                break
        
        if select_col == -1:
            QMessageBox.warning(self.main, "Предупреждение", "Колонка с чекбоксами не найдена")
            return
        
        selected_rows = set()
        for selected_range in self.table.selectedRanges():
            for row in range(selected_range.topRow(), selected_range.bottomRow() + 1):
                selected_rows.add(row)
        
        if not selected_rows:
            QMessageBox.warning(self.main, "Предупреждение", "Нет выделенных строк")
            return
        
        try:
            for row in selected_rows:
                item = self.table.item(row, select_col)
                if item:
                    coin_id = item.data(Qt.UserRole)
                    if coin_id:
                        self.main.db_manager.session.query(Coin).filter(
                            Coin.id == coin_id
                        ).update({"selected": True})
                        item.setCheckState(Qt.Checked)
            
            self.main.db_manager.session.commit()
            self.update_info_label(self.main.current_coins)
            self.main.status_bar.showMessage(f"✅ Отмечено {len(selected_rows)} монет", 3000)
            
        except Exception as e:
            self.logger.error(f"Ошибка при отметке выделенных строк: {e}")
            self.main.db_manager.session.rollback()
            QMessageBox.critical(self.main, "Ошибка", f"Не удалось отметить монеты:\n{e}")
    
    def save_selected_state(self):
        """Сохраняет состояние выбранных монет в базу данных"""
        from database.models import Coin
        
        select_col = -1
        for col, col_info in enumerate(self.current_columns):
            if col_info["key"] == "select":
                select_col = col
                break
        
        if select_col == -1:
            return
        
        try:
            for row in range(self.table.rowCount()):
                item = self.table.item(row, select_col)
                if item:
                    coin_id = item.data(Qt.UserRole)
                    if coin_id:
                        is_selected = (item.checkState() == Qt.Checked)
                        self.main.db_manager.session.query(Coin).filter(
                            Coin.id == coin_id
                        ).update({"selected": is_selected})
            
            self.main.db_manager.session.commit()
            self.logger.debug("Состояние выделения сохранено в БД")
        except Exception as e:
            self.logger.error(f"Ошибка при сохранении состояния выделения: {e}")
            self.main.db_manager.session.rollback()
    
    def _on_item_checkbox_changed(self, item):
        """Обработчик изменения чекбокса"""
        if item is None:
            return
        
        from database.models import Coin, Country
        
        select_col = -1
        for col, col_info in enumerate(self.current_columns):
            if col_info["key"] == "select":
                select_col = col
                break
        
        if select_col == -1:
            return
        
        if item.column() == select_col:
            coin_id = item.data(Qt.UserRole)
            if coin_id:
                is_selected = (item.checkState() == Qt.Checked)
                try:
                    self.main.db_manager.session.query(Coin).filter(
                        Coin.id == coin_id
                    ).update({"selected": is_selected})
                    self.main.db_manager.session.commit()
                    self.update_info_label(self.main.current_coins)
                    
                except Exception as e:
                    self.logger.error(f"Ошибка при сохранении состояния: {e}")
                    self.main.db_manager.session.rollback()
    
    def _open_coin_url(self, coin_id, site):
        """Открывает ссылку на монету на указанном сайте"""
        coin = self.main.db_manager.get_coin(coin_id)
        if not coin:
            return
        
        url = None
        
        if site == 'ucoin':
            url = getattr(coin, 'ucoin_url', None)
            if not url:
                # Автоматически генерируем ссылку на поиск в ucoin
                search_parts = []
                if coin.country:
                    search_parts.append(coin.country.name)
                if coin.denomination_value:
                    search_parts.append(coin.denomination_value)
                if coin.year:
                    search_parts.append(str(coin.year))
                
                if search_parts:
                    search_query = " ".join(search_parts)
                    from urllib.parse import quote
                    url = f"https://ru.ucoin.net/table/?country=&period=&denomination=&year={coin.year or ''}&search={quote(search_query)}"
            
        elif site == 'meshok':
            url = getattr(coin, 'meshok_url', None)
            if not url:
                # Автоматически генерируем ссылку на meshok.net
                search_parts = []
                if coin.country:
                    search_parts.append(coin.country.name)
                if coin.denomination_value:
                    search_parts.append(coin.denomination_value)
                if coin.year:
                    search_parts.append(str(coin.year))
                
                if search_parts:
                    search_query = " ".join(search_parts)
                    from urllib.parse import quote
                    url = f"https://meshok.net/listing?good=252&opt=3&search={quote(search_query)}&sort=cur_price"
        
        if not url:
            QMessageBox.warning(self.main, "Предупреждение", f"Не удалось сформировать ссылку для этой монеты")
            return
        
        if hasattr(self.main, 'center_tab_widget'):
            for i in range(self.main.center_tab_widget.count()):
                if "Браузер" in self.main.center_tab_widget.tabText(i):
                    self.main.center_tab_widget.setCurrentIndex(i)
                    browser = self.main.center_tab_widget.widget(i)
                    if hasattr(browser, 'add_new_tab'):
                        browser.add_new_tab(url)
                    elif hasattr(browser, 'web_view'):
                        from PySide6.QtCore import QUrl
                        browser.web_view.setUrl(QUrl(url))
                    break
            else:
                import webbrowser
                webbrowser.open(url)
                
    def _apply_column_filter_empty(self, column_key, column_name):
        """Применяет фильтр по пустым значениям в колонке"""
        self._column_filter = {
            'key': column_key,
            'value': '__EMPTY__',
            'name': column_name,
            'condition': 'empty'
        }
        
        # Показываем метку фильтра
        self.filter_label.setText(f"🔍 Фильтр: {column_name} = пусто  [нажмите для сброса]")
        self.filter_label.setVisible(True)
        self.filter_label.setCursor(Qt.PointingHandCursor)
        self.filter_label.mousePressEvent = lambda event: self._clear_column_filter()
        
        # Применяем фильтр
        self._apply_filter(self.search_input.text() if self.search_input else "")
    
    def _apply_column_filter_condition(self, column_key, column_name, condition):
        """Применяет фильтр по условию (>, <) с запросом значения"""
        value, ok = QInputDialog.getText(
            self.main, 
            f"Фильтр: {column_name} {condition}",
            f"Введите значение для условия:\n{column_name} {condition} ...",
            text=""
        )
        
        if not ok or not value.strip():
            return
        
        try:
            # Пробуем преобразовать в число
            num_value = float(value.strip().replace(',', '.'))
        except ValueError:
            QMessageBox.warning(self.main, "Предупреждение", f"Введите числовое значение для колонки '{column_name}'")
            return
        
        self._column_filter = {
            'key': column_key,
            'value': num_value,
            'name': column_name,
            'condition': condition
        }
        
        # Показываем метку фильтра
        self.filter_label.setText(f"🔍 Фильтр: {column_name} {condition} {num_value}  [нажмите для сброса]")
        self.filter_label.setVisible(True)
        self.filter_label.setCursor(Qt.PointingHandCursor)
        self.filter_label.mousePressEvent = lambda event: self._clear_column_filter()
        
        # Применяем фильтр
        self._apply_filter(self.search_input.text() if self.search_input else "")
        
        
    def get_selected_coin_ids(self):
        """Возвращает список ID выбранных монет (по чекбоксам)"""
        selected_ids = []
        select_col = -1
        for col, col_info in enumerate(self.current_columns):
            if col_info["key"] == "select":
                select_col = col
                break
        
        if select_col == -1:
            return selected_ids
        
        for row in range(self.table.rowCount()):
            item = self.table.item(row, select_col)
            if item and item.checkState() == Qt.Checked:
                coin_id = item.data(Qt.UserRole)
                if coin_id:
                    selected_ids.append(coin_id)
        return selected_ids
        
        
# ===== gui/panels/table_panel.py =====
# ДОБАВИТЬ В КОНЕЦ КЛАССА TablePanelManager

    # ========== ПАГИНАЦИЯ ДЛЯ БОЛЬШИХ ТАБЛИЦ ==========
    
    def set_pagination(self, enabled=True, page_size=200):
        """
        Включает пагинацию для таблицы.
        
        Args:
            enabled: включить пагинацию
            page_size: количество строк на странице
        """
        self._pagination_enabled = enabled and len(self._all_coins) > page_size
        self._page_size = page_size
        self._current_page = 0
        
        if self._pagination_enabled:
            self._add_pagination_controls()
        else:
            self._remove_pagination_controls()
    
    def _add_pagination_controls(self):
        """Добавляет элементы управления пагинацией"""
        if hasattr(self, '_pagination_widget'):
            return
        
        from PySide6.QtWidgets import QWidget, QHBoxLayout, QPushButton, QLabel, QSpinBox
        
        self._pagination_widget = QWidget()
        layout = QHBoxLayout()
        layout.setContentsMargins(5, 2, 5, 2)
        layout.setSpacing(5)
        
        # Кнопка "Назад"
        self._prev_btn = QPushButton("◀")
        self._prev_btn.setFixedSize(28, 28)
        self._prev_btn.clicked.connect(self._prev_page)
        layout.addWidget(self._prev_btn)
        
        # Информация о странице
        self._page_info = QLabel("Страница 1 / 1")
        self._page_info.setStyleSheet("font-size: 11px; color: #666;")
        layout.addWidget(self._page_info)
        
        # Кнопка "Вперёд"
        self._next_btn = QPushButton("▶")
        self._next_btn.setFixedSize(28, 28)
        self._next_btn.clicked.connect(self._next_page)
        layout.addWidget(self._next_btn)
        
        # Переход к странице
        layout.addWidget(QLabel("Перейти:"))
        self._page_spin = QSpinBox()
        self._page_spin.setRange(1, 1)
        self._page_spin.setFixedWidth(50)
        self._page_spin.valueChanged.connect(self._goto_page)
        layout.addWidget(self._page_spin)
        
        # Количество строк
        self._total_label = QLabel(f"Всего: {len(self._all_coins)}")
        self._total_label.setStyleSheet("font-size: 11px; color: #666;")
        layout.addWidget(self._total_label)
        
        layout.addStretch()
        self._pagination_widget.setLayout(layout)
        
        # Добавляем в основной layout (перед таблицей)
        parent_layout = self.table.parent().layout()
        if parent_layout:
            parent_layout.insertWidget(parent_layout.count() - 1, self._pagination_widget)
        
        self._update_pagination()
    
    def _remove_pagination_controls(self):
        """Удаляет элементы управления пагинацией"""
        if hasattr(self, '_pagination_widget') and self._pagination_widget:
            self._pagination_widget.deleteLater()
            self._pagination_widget = None
    
    def _get_page_coins(self):
        """Возвращает монеты для текущей страницы"""
        if not self._pagination_enabled:
            return self._all_coins
        
        start = self._current_page * self._page_size
        end = start + self._page_size
        return self._all_coins[start:end]
    
    def _update_pagination(self):
        """Обновляет состояние пагинации"""
        if not hasattr(self, '_pagination_widget'):
            return
        
        total_pages = (len(self._all_coins) + self._page_size - 1) // self._page_size
        if total_pages == 0:
            total_pages = 1
        
        self._current_page = min(self._current_page, total_pages - 1)
        self._current_page = max(0, self._current_page)
        
        self._page_info.setText(f"Страница {self._current_page + 1} / {total_pages}")
        self._page_spin.blockSignals(True)
        self._page_spin.setRange(1, total_pages)
        self._page_spin.setValue(self._current_page + 1)
        self._page_spin.blockSignals(False)
        
        self._prev_btn.setEnabled(self._current_page > 0)
        self._next_btn.setEnabled(self._current_page < total_pages - 1)
        
        # Обновляем таблицу
        page_coins = self._get_page_coins()
        self.rebuild_table(page_coins)
        self.update_info_label(page_coins, f" (стр. {self._current_page + 1}/{total_pages})")
    
    def _prev_page(self):
        """Переход на предыдущую страницу"""
        if self._current_page > 0:
            self._current_page -= 1
            self._update_pagination()
    
    def _next_page(self):
        """Переход на следующую страницу"""
        total_pages = (len(self._all_coins) + self._page_size - 1) // self._page_size
        if self._current_page < total_pages - 1:
            self._current_page += 1
            self._update_pagination()
    
    def _goto_page(self, page_num):
        """Переход на указанную страницу"""
        self._current_page = page_num - 1
        self._update_pagination()
    


    def _render_page(self):
        """Рендерит текущую страницу таблицы.
        РАБОТАЕТ ТОЛЬКО С ЗАМОРОЖЕННЫМИ СЛОВАРЯМИ (_frozen_list) —
        объекты Coin не трогаются, DetachedInstanceError невозможен.
        Сортировка выполняется по ВСЕМУ списку, а не только по странице."""
        if not self.table or not self.current_columns:
            return

        # Самозащита: если колонки не инициализированы
        if not self.current_columns and hasattr(self, 'initialize_table_columns'):
            try:
                self.initialize_table_columns()
            except Exception:
                pass

        # Используем ТОЛЬКО список замороженных словарей
        frozen_list = list(getattr(self, '_frozen_list', []) or [])
        if not frozen_list:
            self.table.setRowCount(0)
            return

        # === СОРТИРОВКА ПО ВСЕМУ СПИСКУ (через словари) ===
        if getattr(self, 'sort_column', None) and getattr(self, 'sort_order', 0):
            key = self.sort_column
            aliases = {
                'country': 'country_name', 'metal': 'metal_name',
                'currency': 'currency_name', 'mint': 'mint_name',
                'edge': 'edge_name', 'period': 'period_name',
                'acquisition_type': 'acquisition_type_name',
                'condition': 'condition_name',
                'rarity': 'rarity_name',
                'status': 'status_name',
                'shape': 'shape_name',
                'issue_type': 'issue_type_name',
                'avrev': 'avrev_name',
                'storage_location': 'storage_location_name',
            }
            dict_key = aliases.get(key, key)
            try:
                def sort_tuple(d):
                    v = d.get(dict_key)
                    if v is None and dict_key != key:
                        v = d.get(key)
                    if v is None:
                        return (1, '')
                    if isinstance(v, (int, float)):
                        return (0, v)
                    return (0, str(v).lower())
                frozen_list.sort(key=sort_tuple, reverse=(self.sort_order == 2))
            except Exception as e:
                self.logger.error(f"Ошибка сортировки: {e}")

        self._frozen_list = frozen_list

        total = len(frozen_list)
        size = getattr(self, '_page_size', 500)
        self._total_pages = max(1, (total + size - 1) // size)
        self._current_page = max(0, min(self._current_page, self._total_pages - 1))
        start = self._current_page * size
        page_dicts = frozen_list[start:start + size]

        # Подпись пагинации
        if hasattr(self, '_pg_label') and self._pg_label is not None:
            self._pg_label.setText(f"{self._current_page + 1}/{self._total_pages} ({total} монет)")

        # === БЛОКИРУЕМ ВСЁ НА ВРЕМЯ ЗАПОЛНЕНИЯ ===
        self.table.setSortingEnabled(False)  # Qt-сортировку отключаем
        self.table.setUpdatesEnabled(False)
        self.table.blockSignals(True)
        try:
            if self._signal_connected:
                self.table.itemChanged.disconnect(self._on_item_checkbox_changed)
                self._signal_connected = False
        except (RuntimeError, TypeError):
            pass

        try:
            self.table.setRowCount(len(page_dicts))
            self.table.setColumnCount(len(self.current_columns))
            self.table.setHorizontalHeaderLabels([c["name"] for c in self.current_columns])

            if not page_dicts:
                if len(self.current_columns) > 0:
                    self.table.setSpan(0, 0, 1, len(self.current_columns))
                    empty_item = QTableWidgetItem("Нет монет для отображения")
                    empty_item.setTextAlignment(Qt.AlignCenter)
                    self.table.setItem(0, 0, empty_item)
                return

            from PySide6.QtWidgets import QTableWidgetItem, QApplication
            numeric_keys = {"id", "year", "weight", "diameter", "mintage",
                            "thickness", "purchase_price", "sale_price", "century",
                            "purchase_date", "market_price"}

            # Алиасы для связанных полей
            aliases = {
                'country': 'country_name', 'metal': 'metal_name',
                'currency': 'currency_name', 'mint': 'mint_name',
                'edge': 'edge_name', 'period': 'period_name',
                'acquisition_type': 'acquisition_type_name',
                'condition': 'condition_name',
                'rarity': 'rarity_name',
                'status': 'status_name',
                'shape': 'shape_name',
                'issue_type': 'issue_type_name',
                'avrev': 'avrev_name',
                'storage_location': 'storage_location_name',
            }

            # === ЦИКЛ ПО СЛОВАРЯМ (без объектов Coin!) ===
            for row, d in enumerate(page_dicts):
                coin_id = d.get('_id')
                if coin_id is None:
                    continue

                for col, col_info in enumerate(self.current_columns):
                    key = col_info.get("key", "")
                    col_name = (col_info.get("name") or "").lower()

                    # === КОЛОНКА С ФЛАГОМ (иконка из data/country_flags) ===
                    if key in ("flag", "country_flag", "fr") or "флаг" in col_name:
                        from utils.flag_manager import flag_manager
                        item = QTableWidgetItem()
                        icon = flag_manager.get_icon(d.get('country_id'))
                        if icon:
                            item.setIcon(icon)
                        item.setData(Qt.UserRole, coin_id)
                        item.setToolTip(d.get('country_name') or '')
                        self.table.setItem(row, col, item)
                        continue

                    # === ОБЫЧНЫЕ КОЛОНКИ: значение из замороженного словаря ===
                    dict_key = aliases.get(key, key)
                    value = d.get(dict_key)
                    if value is None and dict_key != key:
                        value = d.get(key)
                    if value is None:
                        value = ""

                    item = QTableWidgetItem(str(value))
                    item.setData(Qt.UserRole, coin_id)
                    if key in numeric_keys:
                        item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
                    if key == "select":
                        item.setFlags(item.flags() | Qt.ItemIsUserCheckable)
                        selected = bool(d.get('selected', False))
                        item.setCheckState(Qt.Checked if selected else Qt.Unchecked)
                    self.table.setItem(row, col, item)

                if row % 500 == 0:
                    QApplication.processEvents()

            # Ширины колонок
            for col, col_info in enumerate(self.current_columns):
                w = col_info.get("width", 100)
                if w and w > 0:
                    self.table.setColumnWidth(col, w)

            self.table.scrollToTop()

        except Exception as e:
            self.logger.error(f"Ошибка _render_page: {e}")
            import traceback
            traceback.print_exc()
        finally:
            self.table.setUpdatesEnabled(True)
            self.table.blockSignals(False)
            self.table.setSortingEnabled(False)  # Qt-сортировка остаётся отключённой
            if not self._signal_connected:
                self.table.itemChanged.connect(self._on_item_checkbox_changed)
                self._signal_connected = True

    def _get_country_flag_icon(self, d):
        """Возвращает QIcon флага страны.
        Источник №1: data/country_flags/{id}.png (flag_manager).
        Fallback: старые папки data/flags (по коду / имени / id)."""
        import os
        from PySide6.QtGui import QIcon, QPixmap
        from utils.flag_manager import flag_manager

        cache = getattr(self, '_flag_icon_cache', None)
        if cache is None:
            self._flag_icon_cache = {}
            cache = self._flag_icon_cache

        cid = d.get('country_id')
        if cid in cache:
            return cache[cid]

        icon = None

        # === 1) Основной источник — data/country_flags/{id}.png ===
        if cid:
            icon = flag_manager.get_icon(cid, 20, 14)

        # === 2) Fallback — старые папки ===
        if icon is None:
            code = (d.get('country_code') or '').strip()
            name = (d.get('country_name') or '').strip()
            exts = ('.png', '.jpg', '.jpeg', '.webp', '.gif')
            candidates = []
            if d.get('country_icon_path'):
                candidates.append(str(d['country_icon_path']))
            try:
                from utils.paths import paths
                data_dir = paths.get_data_dir()
            except Exception:
                data_dir = Path(__file__).parent.parent.parent / 'data'
            bases = [data_dir / 'flags', data_dir / 'flags' / 'app',
                     data_dir / 'country_flags']
            for base in bases:
                if code:
                    candidates += [str(base / f"{code}{ext}") for ext in exts]
                if name:
                    candidates += [str(base / f"{name}{ext}") for ext in exts]
                if cid is not None:
                    candidates += [str(base / f"{cid}{ext}") for ext in exts]
            for p in candidates:
                try:
                    if p and os.path.exists(p):
                        pix = QPixmap(p)
                        if not pix.isNull():
                            icon = QIcon(pix.scaled(
                                20, 14, Qt.KeepAspectRatio, Qt.SmoothTransformation))
                            break
                except Exception:
                    continue

        cache[cid] = icon
        return icon

    def _ensure_pagination_bar(self):
        """Создаёт нижнюю панель пагинации один раз.
        TablePanelManager — не виджет, поэтому бар создаётся БЕЗ родителя
        и вставляется в лейаут родителя таблицы."""
        if getattr(self, '_pagination_bar', None) is not None:
            return
        from PySide6.QtWidgets import (QFrame, QHBoxLayout, QPushButton,
                                       QLabel, QComboBox, QSplitter)
        bar = QFrame()
        bar.setObjectName("pagination_bar")
        lay = QHBoxLayout(bar)
        lay.setContentsMargins(4, 2, 4, 2)
        lay.setSpacing(4)

        self._pg_first = QPushButton("⏮")
        self._pg_prev = QPushButton("◀")
        self._pg_label = QLabel("стр. 1/1")
        self._pg_next = QPushButton("▶")
        self._pg_last = QPushButton("⏭")
        self._pg_size = QComboBox()
        self._pg_size.addItems(["200", "500", "1000", "2000", "Все"])
        self._pg_size.setCurrentText(str(getattr(self, '_page_size', 500)))

        for btn in (self._pg_first, self._pg_prev, self._pg_next, self._pg_last):
            btn.setFixedWidth(30)
            btn.setFixedHeight(24)
        self._pg_first.clicked.connect(lambda: self._goto_page(0))
        self._pg_prev.clicked.connect(lambda: self._goto_page(self._current_page - 1))
        self._pg_next.clicked.connect(lambda: self._goto_page(self._current_page + 1))
        self._pg_last.clicked.connect(lambda: self._goto_page(self._total_pages - 1))
        self._pg_size.currentTextChanged.connect(self._on_page_size_changed)

        lay.addWidget(QLabel("Страница:"))
        lay.addWidget(self._pg_first)
        lay.addWidget(self._pg_prev)
        lay.addWidget(self._pg_label)
        lay.addWidget(self._pg_next)
        lay.addWidget(self._pg_last)
        lay.addStretch()
        lay.addWidget(QLabel("Строк:"))
        lay.addWidget(self._pg_size)

        # Вставляем панель сразу после таблицы (в лейаут её родителя)
        try:
            parent = self.table.parentWidget()
            if parent is not None:
                parent_layout = parent.layout()
                if parent_layout is not None:
                    idx = parent_layout.indexOf(self.table)
                    if idx >= 0:
                        parent_layout.insertWidget(idx + 1, bar)
                    else:
                        parent_layout.addWidget(bar)
                elif isinstance(parent, QSplitter):
                    idx = parent.indexOf(self.table)
                    parent.insertWidget(idx + 1, bar)
                else:
                    # Крайний случай: просто показываем бар как дочерний виджет
                    bar.setParent(parent)
                    bar.show()
        except Exception as e:
            self.logger.error(f"Не удалось вставить панель пагинации: {e}")
        self._pagination_bar = bar

    def _goto_page(self, page):
        """Переход на страницу с защитой от выхода за диапазон"""
        total = getattr(self, '_total_pages', 1)
        page = max(0, min(int(page), total - 1))
        if page == self._current_page:
            return
        self._current_page = page
        self._render_page()

    def _on_page_size_changed(self, text):
        """Смена размера страницы"""
        try:
            self._page_size = 1000000 if text == "Все" else int(text)
        except ValueError:
            self._page_size = 500
        self._current_page = 0
        self._render_page()

    def set_pagination(self, enabled=True, page_size=500):
        """Совместимость: устанавливает размер страницы"""
        self._page_size = page_size
        if getattr(self, '_pg_size', None) is not None:
            self._pg_size.blockSignals(True)
            self._pg_size.setCurrentText(str(page_size))
            self._pg_size.blockSignals(False)
        self._current_page = 0
        if hasattr(self, '_full_coins'):
            self._render_page()
          
    def _print_holder_labels(self):
        """Печатает этикетки для выделенных монет"""
        selected_ids = self.get_selected_coin_ids()

        if not selected_ids:
            from PySide6.QtWidgets import QMessageBox
            QMessageBox.warning(self.main, "Предупреждение", "Выделите монеты для печати")
            return

        # Получаем объекты монет
        coins = []
        for coin_id in selected_ids:
            coin = self.main.db_manager.get_coin(coin_id)
            if coin:
                coins.append(coin)

        if not coins:
            from PySide6.QtWidgets import QMessageBox
            QMessageBox.warning(self.main, "Предупреждение", "Не удалось загрузить данные монет")
            return

        try:
            from gui.widgets.holder_label import HolderLabelPreviewDialog
            dialog = HolderLabelPreviewDialog(coins, self.main)
            dialog.exec()
        except ImportError as e:
            from PySide6.QtWidgets import QMessageBox
            QMessageBox.critical(
                self.main,
                "Ошибка",
                f"Не удалось загрузить модуль печати:\n{e}\n\n"
                f"Убедитесь, что созданы файлы:\n"
                f"gui/widgets/holder_label/__init__.py\n"
                f"gui/widgets/holder_label/holder_label_model.py\n"
                f"gui/widgets/holder_label/holder_label_printer.py\n"
                f"gui/widgets/holder_label/holder_label_preview.py"
            )
        except Exception as e:
            from PySide6.QtWidgets import QMessageBox
            import traceback
            traceback.print_exc()
            QMessageBox.critical(self.main, "Ошибка", f"Ошибка печати:\n{e}")
            
    def _apply_column_widths(self):
        """Применяет сохранённые ширины и видимость к текущим колонкам таблицы"""
        if not getattr(self, 'table', None) or not getattr(self, '_saved_columns_info', None):
            return
        label_to_col = {}
        for i in range(self.table.columnCount()):
            item = self.table.horizontalHeaderItem(i)
            if item:
                label_to_col[item.text()] = i
        for col_info in self._saved_columns_info:
            label = col_info.get('label')
            if label in label_to_col:
                c = label_to_col[label]
                w = col_info.get('width')
                if w and w > 10:
                    self.table.setColumnWidth(c, w)
                self.table.setColumnHidden(c, bool(col_info.get('hidden', False)))
                
    def _on_section_resized(self, logical_index, old_size, new_size):
        """Запоминает новую ширину колонки и пишет её в настройки (БД)"""
        if self.current_columns and 0 <= logical_index < len(self.current_columns):
            self.current_columns[logical_index]['width'] = new_size
        if getattr(self, '_saved_columns_info', None) and self.table:
            item = self.table.horizontalHeaderItem(logical_index)
            if item:
                label = item.text()
                for col_info in self._saved_columns_info:
                    if col_info.get('label') == label:
                        col_info['width'] = new_size
                        break
        # Отложенное сохранение в базу (не пишем при каждом пикселе)
        self._schedule_save_columns()

    def _schedule_save_columns(self):
        """Сохраняет ширины колонок в базу с задержкой"""
        if not hasattr(self, '_save_columns_timer'):
            self._save_columns_timer = QTimer(self.main)
            self._save_columns_timer.setSingleShot(True)
            self._save_columns_timer.setInterval(800)
            self._save_columns_timer.timeout.connect(self._save_columns_now)
        self._save_columns_timer.start()

    def _save_columns_now(self):
        """Пишет текущие ширины колонок в config.db"""
        try:
            self.main.save_settings()
            self.logger.info("💾 Ширины колонок сохранены в базу")
        except Exception as e:
            self.logger.error(f"Ошибка сохранения ширин колонок: {e}")
            
    def _get_country_flag_icon(self, d):
        """Возвращает иконку флага страны — тот же файл, что использует дерево стран.
        Порядок поиска: прямой путь из БД -> папки флагов (по коду, названию, ID).
        Результат кэшируется (включая None)."""
        import os
        from pathlib import Path
        from PySide6.QtGui import QIcon, QPixmap

        cache = getattr(self, '_flag_icon_cache', None)
        if cache is None:
            self._flag_icon_cache = {}
            cache = self._flag_icon_cache

        cid = d.get('country_id')
        if cid in cache:
            return cache[cid]

        code = (d.get('country_code') or '').strip()
        name = (d.get('country_name') or '').strip()
        exts = ('.png', '.jpg', '.jpeg', '.webp', '.gif')

        candidates = []
        # 1) Прямой путь к иконке из БД (как в дереве)
        if d.get('country_icon_path'):
            candidates.append(str(d['country_icon_path']))

        # 2) Стандартные папки с флагами, загруженными вручную
        try:
            from utils.paths import paths
            data_dir = paths.get_data_dir()
        except Exception:
            data_dir = Path(__file__).parent.parent.parent / 'data'
        bases = [
            data_dir / 'flags',
            data_dir / 'flags' / 'app',
            data_dir / 'country_flags',
            data_dir / 'country_icons',
            data_dir / 'custom_images',
            Path(__file__).parent.parent.parent / 'resources' / 'flags',
        ]
        for base in bases:
            if code:
                for ext in exts:
                    candidates.append(str(base / f"{code}{ext}"))
            if name:
                for ext in exts:
                    candidates.append(str(base / f"{name}{ext}"))
            if cid is not None:
                for ext in exts:
                    candidates.append(str(base / f"{cid}{ext}"))

        icon = None
        for path in candidates:
            try:
                if path and os.path.exists(path):
                    pix = QPixmap(path)
                    if not pix.isNull():
                        icon = QIcon(pix.scaled(
                            20, 14, Qt.KeepAspectRatio, Qt.SmoothTransformation))
                        break
            except Exception:
                continue

        cache[cid] = icon
        return icon
        
    def _get_main_window(self):
        """Возвращает главное окно.
        TablePanelManager — НЕ виджет, поэтому self.parent() недопустим:
        используем прямую ссылку self.main."""
        return getattr(self, 'main', None)

    def _on_delete_clicked(self):
        """Обработчик кнопки «🗑 Удалить»:
        делегирует МАССОВОЕ удаление выделенных строк главному окну.
        Приоритет выделения (внутри delete_selected_coins):
        1) строки с галочками ☑; 2) выделенные строки таблицы; 3) текущая монета."""
        main_window = getattr(self, 'main', None)
        if main_window is None:
            return
        if hasattr(main_window, 'delete_selected_coins'):
            main_window.delete_selected_coins()
        else:
            # Фолбэк: старое одиночное удаление текущей монеты
            coin = getattr(getattr(main_window, 'detail_panel', None),
                           'current_coin', None)
            if (coin is not None and getattr(coin, 'id', None)
                    and hasattr(main_window, '_delete_coin_by_id')):
                main_window._delete_coin_by_id(coin.id)
                
                
    def _toggle_collection(self, coin):
        """Переключает состояние 'в коллекции' для монеты"""
        try:
            current_state = getattr(coin, 'in_collection', False)
            coin.in_collection = not current_state
            self.main.db_manager.session.commit()
            self.main.load_coins()
            state_text = "добавлена в коллекцию" if coin.in_collection else "убрана из коллекции"
            self.main.status_bar.showMessage(f"✅ Монета {state_text}", 2000)
        except Exception as e:
            self.logger.error(f"Ошибка переключения коллекции: {e}")
            self.main.db_manager.session.rollback()

    def _copy_coin_data(self, coin):
        """Копирует основные данные монеты в буфер обмена"""
        try:
            from PySide6.QtWidgets import QApplication
            parts = []
            if getattr(coin, 'country', None): 
                parts.append(f"Страна: {coin.country.name}")
            if getattr(coin, 'denomination_value', None): 
                parts.append(f"Номинал: {coin.denomination_value}")
            if getattr(coin, 'currency', None): 
                parts.append(f"Валюта: {coin.currency}")
            if getattr(coin, 'year', None): 
                parts.append(f"Год: {coin.year}")
            if getattr(coin, 'catalog_number', None): 
                parts.append(f"Каталог: {coin.catalog_number}")
            if getattr(coin, 'metal_obj', None):
                parts.append(f"Металл: {coin.metal_obj.get_display_text()}")
                
            text = "\n".join(parts) if parts else "Нет данных для копирования"
            QApplication.clipboard().setText(text)
            self.main.status_bar.showMessage("📋 Данные монеты скопированы в буфер", 2000)
        except Exception as e:
            self.logger.error(f"Ошибка копирования данных: {e}")
            
            
    def _edit_coin(self, coin):
        """Выбирает монету и открывает режим редактирования."""
        try:
            if hasattr(self.main, 'select_coin_by_id'):
                self.main.select_coin_by_id(coin.id)
            self.main.edit_coin()
        except Exception as e:
            self.logger.error(f"Ошибка открытия редактирования: {e}")

    def _toggle_collection(self, coin):
        """Добавляет/убирает монету из коллекции."""
        try:
            coin.in_collection = not getattr(coin, 'in_collection', False)
            self.main.db_manager.session.commit()
            state = "добавлена в коллекцию" if coin.in_collection else "убрана из коллекции"
            self.main.status_bar.showMessage(f"✅ Монета {state}", 2000)
            self.main.load_coins()
        except Exception as e:
            self.logger.error(f"Ошибка переключения коллекции: {e}")
            self.main.db_manager.session.rollback()

    def _copy_coin_data(self, coin):
        """Копирует основные данные монеты в буфер обмена."""
        try:
            parts = []
            if getattr(coin, 'country', None):
                parts.append(f"Страна: {coin.country.name}")
            if getattr(coin, 'denomination_value', None):
                parts.append(f"Номинал: {coin.denomination_value}")
            if getattr(coin, 'currency', None):
                parts.append(f"Валюта: {coin.currency}")
            if getattr(coin, 'year', None):
                parts.append(f"Год: {coin.year}")
            if getattr(coin, 'catalog_number', None):
                parts.append(f"Каталог: {coin.catalog_number}")
            QApplication.clipboard().setText("\n".join(parts))
            self.main.status_bar.showMessage("📋 Данные скопированы", 2000)
        except Exception as e:
            self.logger.error(f"Ошибка копирования: {e}")

    def _delete_coin(self, coin):
        """Удаляет монету с подтверждением."""
        reply = QMessageBox.question(
            self.main, "Подтверждение",
            f"Удалить монету ID {coin.id}?",
            QMessageBox.Yes | QMessageBox.No)
        if reply == QMessageBox.Yes:
            try:
                self.main._delete_coin_by_id(coin.id)
            except Exception as e:
                self.logger.error(f"Ошибка удаления: {e}")