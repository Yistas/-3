# -*- coding: utf-8 -*-

"""
Вкладка статистики для закупок
"""

import re
import json
import logging
from datetime import datetime
from collections import defaultdict
from pathlib import Path
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton,
    QTableWidget, QTableWidgetItem, QHeaderView,
    QLabel, QFileDialog, QMessageBox, QComboBox,
    QMenu, QColorDialog, QAbstractItemView, QInputDialog,
    QStyledItemDelegate, QStyle, QStyleOptionViewItem
)
from PySide6.QtGui import QAction, QColor, QPen, QPainter, QBrush, QPaintEvent
from PySide6.QtCore import Qt, QTimer, QEvent, QRect, QPoint

from database.models import Purchase, PurchaseArchive, ImportCountry


class StatisticsTable(QTableWidget):
    """Кастомная таблица с поддержкой разделителей на всю ширину"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self._separators = {}  # {number: 'single' | 'double'}
        self._parent_tab = None
        
    def set_separators(self, separators):
        """Устанавливает разделители"""
        self._separators = separators.copy()
        self.viewport().update()
    
    def set_parent_tab(self, tab):
        """Устанавливает ссылку на родительскую вкладку"""
        self._parent_tab = tab
    
    def paintEvent(self, event):
        """Переопределяем paintEvent для отрисовки разделителей на всю ширину"""
        super().paintEvent(event)
        
        if not self._separators:
            return
        
        painter = QPainter(self.viewport())
        painter.setRenderHint(QPainter.Antialiasing, False)
        
        try:
            # Получаем общую ширину таблицы (включая все колонки)
            total_width = self.viewport().width()
            # Или можно взять ширину последней видимой колонки
            # total_width = self.horizontalHeader().length()
            
            for row in range(self.rowCount()):
                # Получаем номер закупки
                number_item = self.item(row, 0)
                if not number_item:
                    continue
                
                number = number_item.data(Qt.UserRole) or number_item.text()
                if not number:
                    continue
                
                sep_type = self._separators.get(str(number), 'none')
                if sep_type == 'none':
                    continue
                
                # Получаем прямоугольник строки
                rect = self.visualRect(self.model().index(row, 0))
                if not rect.isValid():
                    continue
                
                y = rect.bottom()
                
                # Рисуем разделитель на всю ширину таблицы
                if sep_type == 'single':
                    pen = QPen(QColor(0, 0, 0), 2, Qt.SolidLine)
                    painter.setPen(pen)
                    painter.drawLine(0, y, total_width, y)
                elif sep_type == 'double':
                    pen = QPen(QColor(0, 0, 0), 2, Qt.SolidLine)
                    painter.setPen(pen)
                    painter.drawLine(0, y - 3, total_width, y - 3)
                    painter.drawLine(0, y + 1, total_width, y + 1)
                    
        except Exception as e:
            pass
        finally:
            painter.end()


class StatisticsTab(QWidget):
    """Вкладка статистики закупок"""
    
    def __init__(self, db_manager, parent=None):
        super().__init__(parent)
        self.db_manager = db_manager
        self.logger = logging.getLogger('CoinCollector.GUI.StatisticsTab')
        
        # Хранилища для цветов - привязаны к номеру закупки (не к строке!)
        self._cell_colors = {}      # {number_col: color_name}  number_col = f"{number}_{col}"
        self._row_colors = {}       # {number: color_name}
        self._row_separators = {}   # {number: 'single' | 'double'}  - линия после строки с номером
        
        # Хранилище для данных (номер -> данные)
        self._data_cache = {}  # {number: {'year': str, 'comment': str}}
        
        # Флаг для подавления сигнала itemChanged
        self._updating = False
        
        # Флаг инициализации
        self._initialized = False
        
        # Флаг первой загрузки
        self._first_load = True
        
        # Таймер для отложенного сохранения
        self._save_timer = QTimer()
        self._save_timer.setSingleShot(True)
        self._save_timer.timeout.connect(self._save_colors_to_db)
        
        # Флаг, что мы в процессе перезагрузки (чтобы не сохранять при фильтрации)
        self._is_reloading = False
        
        self.init_ui()
        
        # Загружаем сохранённые данные
        self._load_cached_data()
        
        # Загружаем цвета
        self.load_colors_from_db()
        
        # Загружаем разделители
        self.load_separators_from_db()
        
        # Загружаем данные только после полной инициализации UI
        QTimer.singleShot(100, self._delayed_load)
    
    def _delayed_load(self):
        """Отложенная загрузка данных после инициализации UI"""
        self._initialized = True
        self.load_data()
    
    def init_ui(self):
        """Инициализация интерфейса"""
        layout = QVBoxLayout()
        layout.setContentsMargins(5, 5, 5, 5)
        self.setLayout(layout)
        
        # Заголовок
        title = QLabel("📊 Статистика закупок")
        title.setStyleSheet("""
            font-weight: bold;
            font-size: 16px;
            padding: 8px;
            background-color: #4a6fa5;
            color: white;
            border-radius: 3px;
        """)
        title.setAlignment(Qt.AlignCenter)
        layout.addWidget(title)
        
        # Панель управления
        control_layout = QHBoxLayout()
        
        control_layout.addWidget(QLabel("Показать:"))
        self.show_combo = QComboBox()
        self.show_combo.addItem("📊 Все закупки", "all")
        self.show_combo.addItem("🔴 Активные (прибыль < 0%)", "active")
        self.show_combo.addItem("🟢 Архивные (прибыль > 0%)", "archived")
        self.show_combo.currentIndexChanged.connect(self._on_filter_changed)
        control_layout.addWidget(self.show_combo)
        
        control_layout.addStretch()
        
        self.refresh_btn = QPushButton("🔄 Обновить")
        self.refresh_btn.clicked.connect(self._force_reload)
        control_layout.addWidget(self.refresh_btn)
        
        self.export_btn = QPushButton("📎 Экспорт в CSV")
        self.export_btn.clicked.connect(self.export_to_csv)
        control_layout.addWidget(self.export_btn)
        
        layout.addLayout(control_layout)
        
        # Таблица статистики (кастомная)
        self.table = StatisticsTable()
        self.table.set_parent_tab(self)
        self.table.setAlternatingRowColors(True)
        self.table.setSortingEnabled(True)
        
        # Контекстное меню для таблицы
        self.table.setContextMenuPolicy(Qt.CustomContextMenu)
        self.table.customContextMenuRequested.connect(self._show_table_context_menu)
        
        # Настройка заголовков
        headers = [
            "№", "Кол-во", "Обмен", "Продано", "КОЛ-Я",
            "Продажи (₽)", "Кол-я (₽)", "Выставить",
            "Затраты (₽)", "Прибыль продажи (₽)",
            "% продажи по кол-ву", "Общие продажи (₽)", "% прибыли",
            "ГОД", "Комментарии"
        ]
        
        self.table.setColumnCount(len(headers))
        self.table.setHorizontalHeaderLabels(headers)
        self.table.setEditTriggers(QTableWidget.DoubleClicked | QTableWidget.EditKeyPressed)
        self.table.itemDoubleClicked.connect(self.on_cell_double_clicked)
        
        # Настройка ширины колонок
        header = self.table.horizontalHeader()
        for i, width in enumerate([30, 50, 60, 60, 80, 60, 80, 100, 100, 120, 120, 120, 100, 60, 200]):
            if i < len(headers):
                self.table.setColumnWidth(i, width)
        
        header.setStretchLastSection(True)
        
        layout.addWidget(self.table)
        
        # Статус бар
        self.status_label = QLabel("Готов")
        self.status_label.setStyleSheet("color: #666; font-size: 10px; padding: 2px;")
        layout.addWidget(self.status_label)
        
        # Итоговая строка
        self.total_label = QLabel("")
        self.total_label.setStyleSheet("""
            font-weight: bold;
            background-color: #f0f0f0;
            padding: 5px;
            border-top: 1px solid #ccc;
        """)
        layout.addWidget(self.total_label)
        
        # Принудительно обновляем отображение после загрузки
        QTimer.singleShot(200, self._force_repaint)
    
    def _force_repaint(self):
        """Принудительно перерисовывает таблицу"""
        self.table.viewport().update()
        self.table.repaint()
    
    def _on_filter_changed(self):
        """Обработчик изменения фильтра - НЕ пересохраняет данные, только перерисовывает"""
        self._is_reloading = True
        self.load_data()
        self._is_reloading = False
    
    def _force_reload(self):
        """Принудительная перезагрузка (с сохранением всех изменений)"""
        self._is_reloading = True
        self.load_data()
        self._is_reloading = False
    
    # ========== РАБОТА С КЭШЕМ ДАННЫХ (ГОД, КОММЕНТАРИИ) ==========
    
    def _get_cache_key(self, purchase_number):
        """Возвращает ключ для кэша"""
        return f"stats_{purchase_number}"
    
    def _load_cached_data(self):
        """Загружает сохранённые данные из ConfigDB"""
        try:
            from database.config_db import get_config_db
            config_db = get_config_db()
            cached = config_db.get('statistics_cached_data', {})
            if cached:
                self._data_cache = cached
                self.logger.info(f"✅ Загружено {len(self._data_cache)} записей из кэша")
            else:
                self._data_cache = {}
        except Exception as e:
            self.logger.error(f"Ошибка загрузки кэша: {e}")
            self._data_cache = {}
    
    def _save_cached_data(self):
        """Сохраняет данные в ConfigDB"""
        try:
            from database.config_db import get_config_db
            config_db = get_config_db()
            config_db.set('statistics_cached_data', self._data_cache, 'statistics')
            self.logger.debug("✅ Данные сохранены в кэш")
        except Exception as e:
            self.logger.error(f"Ошибка сохранения кэша: {e}")
    
    def _get_cached_year(self, number):
        """Возвращает сохранённый год для номера"""
        if number in self._data_cache:
            return self._data_cache[number].get('year', '')
        return ''
    
    def _get_cached_comment(self, number):
        """Возвращает сохранённый комментарий для номера"""
        if number in self._data_cache:
            return self._data_cache[number].get('comment', '')
        return ''
    
    def _set_cached_year(self, number, year):
        """Сохраняет год для номера"""
        if number not in self._data_cache:
            self._data_cache[number] = {}
        self._data_cache[number]['year'] = year
        self._save_cached_data()
    
    def _set_cached_comment(self, number, comment):
        """Сохраняет комментарий для номера"""
        if number not in self._data_cache:
            self._data_cache[number] = {}
        self._data_cache[number]['comment'] = comment
        self._save_cached_data()
 
    def _get_cached_costs(self, number):
        """Возвращает вручную введённые затраты для номера закупки из кэша.
        None — если пользователь ещё не вводил значение."""
        rec = self._data_cache.get(number)
        if not rec:
            return None
        if 'costs' in rec and rec['costs'] is not None:
            try:
                return float(rec['costs'])
            except (TypeError, ValueError):
                return None
        return None

    def _set_cached_costs(self, number, costs):
        """Сохраняет РУЧНЫЕ затраты в кэш (ConfigDB, ключ
        'statistics_cached_data'). Это ЕДИНСТВЕННЫЙ источник значения
        колонки 'Затраты' — ничто другое её не переписывает."""
        if number not in self._data_cache:
            self._data_cache[number] = {}
        self._data_cache[number]['costs'] = float(costs)
        self._save_cached_data()
 
    # ========== СОХРАНЕНИЕ И ЗАГРУЗКА ЦВЕТОВ ==========
    
    def _save_colors_to_db(self):
        """Сохраняет цвета и разделители в ConfigDB с задержкой"""
        try:
            from database.config_db import get_config_db
            config_db = get_config_db()
            
            # Сохраняем цвета ячеек (привязаны к номеру)
            config_db.set('statistics_cell_colors', self._cell_colors, 'statistics')
            
            # Сохраняем цвета строк (привязаны к номеру)
            config_db.set('statistics_row_colors', self._row_colors, 'statistics')
            
            # Сохраняем разделители (привязаны к номеру)
            config_db.set('statistics_row_separators', self._row_separators, 'statistics')
            
            self.logger.debug("✅ Цвета и разделители сохранены в ConfigDB")
        except Exception as e:
            self.logger.error(f"Ошибка сохранения цветов: {e}")
    
    def _save_colors_immediate(self):
        """Немедленное сохранение цветов и разделителей"""
        self._save_timer.stop()
        self._save_colors_to_db()
    
    def load_colors_from_db(self):
        """Загружает цвета из ConfigDB"""
        try:
            from database.config_db import get_config_db
            config_db = get_config_db()
            
            # Загружаем цвета ячеек (привязаны к номеру)
            self._cell_colors = config_db.get('statistics_cell_colors', {})
            
            # Загружаем цвета строк (привязаны к номеру)
            self._row_colors = config_db.get('statistics_row_colors', {})
            
            self.logger.debug("✅ Цвета загружены из ConfigDB")
        except Exception as e:
            self.logger.error(f"Ошибка загрузки цветов: {e}")
            self._cell_colors = {}
            self._row_colors = {}
    
    def load_separators_from_db(self):
        """Загружает разделители из ConfigDB"""
        try:
            from database.config_db import get_config_db
            config_db = get_config_db()
            self._row_separators = config_db.get('statistics_row_separators', {})
            self.logger.debug(f"✅ Загружено {len(self._row_separators)} разделителей")
        except Exception as e:
            self.logger.error(f"Ошибка загрузки разделителей: {e}")
            self._row_separators = {}
    
    def _get_row_for_number(self, number):
        """Возвращает индекс строки по номеру закупки"""
        for row in range(self.table.rowCount()):
            item = self.table.item(row, 0)
            if item:
                item_number = item.data(Qt.UserRole) or item.text()
                if str(item_number) == str(number):
                    return row
        return -1
    
    def _apply_saved_colors(self):
        """Применяет сохранённые цвета к таблице (по номеру, а не по строке)"""
        col_count = self.table.columnCount()
        
        # Применяем цвета строк (по номеру)
        for number, color_name in self._row_colors.items():
            row = self._get_row_for_number(number)
            if row >= 0:
                color = QColor(color_name)
                for col in range(col_count):
                    item = self.table.item(row, col)
                    if item:
                        item.setBackground(color)
        
        # Применяем цвета ячеек (по номеру)
        for key, color_name in self._cell_colors.items():
            # key = f"{number}_{col}"
            parts = key.split('_')
            if len(parts) == 2:
                number = parts[0]
                col = int(parts[1])
                row = self._get_row_for_number(number)
                if row >= 0 and 0 <= col < col_count:
                    item = self.table.item(row, col)
                    if item:
                        item.setBackground(QColor(color_name))
    
    # ========== ЗАГРУЗКА ДАННЫХ ==========

    def load_data(self):
        """Загружает данные и заполняет таблицу.
        ВАЖНО: колонка 'Затраты' берётся ТОЛЬКО из ручного значения
        (кэш ConfigDB). Фолбэк 'collection_price × quantity' УДАЛЁН —
        именно он переписывал введённые затраты при появлении строк
        без manual_costs (новые строки, архивирование и т.п.).
        При первом старте значение один раз сидируется из manual_costs БД."""
        if not hasattr(self, '_initialized') or not self._initialized:
            QTimer.singleShot(100, self.load_data)
            return
        if not hasattr(self, 'table') or self.table is None:
            self.logger.error("Таблица не инициализирована")
            return
        # Если мы в процессе перезагрузки, не сохраняем данные
        if not self._is_reloading:
            # Сохраняем текущие данные перед перезагрузкой
            self._save_current_data()
        try:
            show_mode = self.show_combo.currentData()
            active_purchases = self.db_manager.session.query(Purchase).all()
            archived_purchases = self.db_manager.session.query(PurchaseArchive).all()
            stats = defaultdict(lambda: {
                'total': 0, 'on_exchange': 0, 'sold': 0, 'in_collection': 0,
                'sales_sum': 0.0, 'collection_sum': 0.0, 'not_listed': 0,
                'costs': 0.0, 'manual_sum': 0.0, 'profit': 0.0,
                'total_sales': 0.0, 'profit_percent': 0.0,
            })
            # Обрабатываем активные закупки
            for p in active_purchases:
                number = p.purchase_number
                if number:
                    number_str = str(number).strip()
                    if not re.match(r'^-?\d+$', number_str):
                        continue
                    number = number_str
                else:
                    continue
                quantity = p.quantity or 1
                stats[number]['total'] += quantity
                if p.ucoin_exchange:
                    stats[number]['on_exchange'] += quantity
                if p.sold_count and str(p.sold_count).strip():
                    try:
                        sold_val = int(float(str(p.sold_count)))
                        if sold_val > 0:
                            stats[number]['sold'] += sold_val
                    except:
                        stats[number]['sold'] += quantity
                if p.in_collection:
                    stats[number]['in_collection'] += quantity
                if p.sold_sum and p.sold_sum > 0:
                    stats[number]['sales_sum'] += p.sold_sum
                if p.in_collection and p.collection_price:
                    stats[number]['collection_sum'] += p.collection_price * quantity
                # === ТОЛЬКО manual_costs, БЕЗ фолбэка на collection_price ===
                if getattr(p, 'manual_costs', None):
                    try:
                        stats[number]['manual_sum'] += float(p.manual_costs)
                    except (TypeError, ValueError):
                        pass
            # Обрабатываем архивные закупки
            for p in archived_purchases:
                number = p.purchase_number
                if number:
                    number_str = str(number).strip()
                    if not re.match(r'^-?\d+$', number_str):
                        continue
                    number = number_str
                else:
                    continue
                quantity = p.quantity or 1
                stats[number]['total'] += quantity
                if p.ucoin_exchange:
                    stats[number]['on_exchange'] += quantity
                if p.sold_count and str(p.sold_count).strip():
                    try:
                        sold_val = int(float(str(p.sold_count)))
                        if sold_val > 0:
                            stats[number]['sold'] += sold_val
                    except:
                        stats[number]['sold'] += quantity
                if p.in_collection:
                    stats[number]['in_collection'] += quantity
                if p.sold_sum and p.sold_sum > 0:
                    stats[number]['sales_sum'] += p.sold_sum
                if p.in_collection and p.collection_price:
                    stats[number]['collection_sum'] += p.collection_price * quantity
                # === ТОЛЬКО manual_costs, БЕЗ фолбэка на collection_price ===
                if getattr(p, 'manual_costs', None):
                    try:
                        stats[number]['manual_sum'] += float(p.manual_costs)
                    except (TypeError, ValueError):
                        pass
            # Рассчитываем показатели
            for number, data in stats.items():
                # === ЗАТРАТЫ: ТОЛЬКО ручное значение ===
                # 1) из кэша (если пользователь вводил);
                # 2) иначе один раз сидируем из manual_costs БД и запоминаем.
                cached_costs = self._get_cached_costs(number)
                if cached_costs is not None:
                    data['costs'] = cached_costs
                else:
                    data['costs'] = data['manual_sum']
                    if data['manual_sum']:
                        self._set_cached_costs(number, data['manual_sum'])
                data['not_listed'] = data['total'] - (data['sold'] + data['in_collection'] + data['on_exchange'])
                if data['not_listed'] < 0:
                    data['not_listed'] = 0
                data['profit'] = data['sales_sum'] - data['costs']
                data['total_sales'] = data['sales_sum']
                if data['total'] > 0:
                    data['sold_percent'] = (data['sold'] / data['total']) * 100
                else:
                    data['sold_percent'] = 0
                if data['costs'] > 0:
                    data['profit_percent'] = (data['profit'] / data['costs']) * 100
                elif data['sales_sum'] > 0:
                    data['profit_percent'] = 100
                else:
                    data['profit_percent'] = 0
            # Фильтрация по режиму
            items = list(stats.items())
            if show_mode == 'active':
                items = [(num, data) for num, data in items if data['profit_percent'] < 0]
                filter_text = " (отрицательная прибыль)"
            elif show_mode == 'archived':
                items = [(num, data) for num, data in items if data['profit_percent'] > 0]
                filter_text = " (положительная прибыль)"
            else:
                filter_text = ""
            # Сортируем по числовому значению (от большего к меньшему)
            def get_numeric_key(item):
                try:
                    return int(item[0])
                except (ValueError, TypeError):
                    return 0
            items.sort(key=get_numeric_key, reverse=True)
            # Заполняем таблицу
            self.table.setSortingEnabled(False)
            self.table.setRowCount(len(items))
            totals = {
                'total': 0, 'on_exchange': 0, 'sold': 0, 'in_collection': 0,
                'sales_sum': 0.0, 'collection_sum': 0.0, 'not_listed': 0,
                'costs': 0.0, 'profit': 0.0, 'total_sales': 0.0
            }
            for row, (number, data) in enumerate(items):
                totals['total'] += data['total']
                totals['on_exchange'] += data['on_exchange']
                totals['sold'] += data['sold']
                totals['in_collection'] += data['in_collection']
                totals['sales_sum'] += data['sales_sum']
                totals['collection_sum'] += data['collection_sum']
                totals['not_listed'] += data['not_listed']
                totals['costs'] += data['costs']
                totals['profit'] += data['profit']
                totals['total_sales'] += data['total_sales']
                # Номер
                num_item = QTableWidgetItem(number)
                num_item.setData(Qt.UserRole, number)
                num_item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
                self.table.setItem(row, 0, num_item)
                # Количество
                self._set_cell(row, 1, str(data['total']))
                self._set_cell(row, 2, str(data['on_exchange']))
                self._set_cell(row, 3, str(data['sold']))
                self._set_cell(row, 4, str(data['in_collection']))
                # Продажи (₽)
                self._set_cell(row, 5, f"{data['sales_sum']:.2f}" if data['sales_sum'] > 0 else "0")
                # Кол-я (₽)
                self._set_cell(row, 6, f"{data['collection_sum']:.2f}" if data['collection_sum'] > 0 else "0")
                # Выставить
                self._set_cell(row, 7, str(data['not_listed']))
                # === ЗАТРАТЫ (₽): НЕРЕДАКТИРУЕМАЯ ЯЧЕЙКА ===
                # Ввод только через двойной клик (диалог), случайный ввод
                # и любые пересчёты значение не меняют.
                costs_item = QTableWidgetItem(
                    f"{data['costs']:.2f}" if data['costs'] > 0 else "0")
                costs_item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
                costs_item.setFlags(costs_item.flags() & ~Qt.ItemIsEditable)
                self.table.setItem(row, 8, costs_item)
                # Прибыль продажи (₽)
                self._set_cell(row, 9, f"{data['profit']:.2f}" if data['profit'] != 0 else "0")
                # % продажи по кол-ву
                self._set_cell(row, 10, f"{data['sold_percent']:.1f}%" if data['sold_percent'] > 0 else "0%")
                # Общие продажи (₽)
                self._set_cell(row, 11, f"{data['total_sales']:.2f}" if data['total_sales'] > 0 else "0")
                # % прибыли
                self._set_cell(row, 12, f"{data['profit_percent']:.1f}%" if data['profit_percent'] != 0 else "0%")
                # ГОД — из кэша (не перезаписываем)
                year_value = self._get_cached_year(number)
                year_item = QTableWidgetItem(year_value)
                year_item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
                year_item.setFlags(year_item.flags() | Qt.ItemIsEditable)
                self.table.setItem(row, 13, year_item)
                # Комментарии — из кэша (не перезаписываем)
                comment_value = self._get_cached_comment(number)
                comment_item = QTableWidgetItem(comment_value)
                comment_item.setFlags(comment_item.flags() | Qt.ItemIsEditable)
                self.table.setItem(row, 14, comment_item)
            self.table.setSortingEnabled(True)
            # Применяем сохранённые цвета (по номеру, а не по строке)
            self._apply_saved_colors()
            # Применяем сохранённые разделители
            self._apply_saved_separators()
            # Подключаем сигнал изменения
            try:
                self.table.itemChanged.disconnect()
            except:
                pass
            self.table.itemChanged.connect(self._on_item_changed)
            # Итоговая строка
            total_sold_percent = (totals['sold'] / totals['total'] * 100) if totals['total'] > 0 else 0
            total_profit_percent = (totals['profit'] / totals['costs'] * 100) if totals['costs'] > 0 else 0
            self.total_label.setText(
                f"📊 ИТОГО: {totals['total']} монет | "
                f"Продано: {totals['sold']} | "
                f"В коллекцию: {totals['in_collection']} | "
                f"На обмене: {totals['on_exchange']} | "
                f"Прибыль: {totals['profit']:.2f} ₽ | "
                f"% продаж: {total_sold_percent:.1f}% | "
                f"% прибыли: {total_profit_percent:.1f}%"
            )
            self._first_load = False
            if hasattr(self, 'status_label') and self.status_label is not None:
                self.status_label.setText(f"✅ Загружено записей: {len(items)}{filter_text}")
            # Принудительно перерисовываем
            self._force_repaint()
        except Exception as e:
            self.logger.error(f"Ошибка загрузки статистики: {e}")
            import traceback
            traceback.print_exc()
            if hasattr(self, 'status_label') and self.status_label is not None:
                self.status_label.setText(f"❌ Ошибка: {str(e)[:50]}")

    def _save_current_data(self):
        """Сохраняет текущие данные из таблицы перед перезагрузкой"""
        if self._is_reloading:
            return
        
        try:
            col_count = self.table.columnCount()
            year_index = col_count - 2
            comments_index = col_count - 1
            
            for row in range(self.table.rowCount()):
                number_item = self.table.item(row, 0)
                if not number_item:
                    continue
                
                number = number_item.data(Qt.UserRole) or number_item.text()
                if not number:
                    continue
                
                # Сохраняем год
                year_item = self.table.item(row, year_index)
                if year_item:
                    year_text = year_item.text().strip()
                    if number in self._data_cache:
                        if self._data_cache[number].get('year', '') != year_text:
                            self._set_cached_year(number, year_text)
                    else:
                        self._set_cached_year(number, year_text)
                
                # Сохраняем комментарий
                comment_item = self.table.item(row, comments_index)
                if comment_item:
                    comment_text = comment_item.text().strip()
                    if number in self._data_cache:
                        if self._data_cache[number].get('comment', '') != comment_text:
                            self._set_cached_comment(number, comment_text)
                    else:
                        self._set_cached_comment(number, comment_text)
        except Exception as e:
            self.logger.debug(f"Ошибка сохранения текущих данных: {e}")
    
    # ========== ВСПОМОГАТЕЛЬНЫЕ МЕТОДЫ ==========
    
    def _set_cell(self, row, col, value):
        """Устанавливает ячейку с выравниванием"""
        item = QTableWidgetItem(value)
        if col in [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13]:
            item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self.table.setItem(row, col, item)
    
    # ========== КОНТЕКСТНОЕ МЕНЮ ==========
    
    def _show_table_context_menu(self, position):
        """Показывает контекстное меню для таблицы статистики"""
        if not hasattr(self, 'table') or self.table is None:
            return
        
        index = self.table.indexAt(position)
        
        menu = QMenu(self)
        
        color_rows_action = QAction("🟨 Залить выделенные строки", self)
        color_rows_action.triggered.connect(self._color_selected_rows)
        menu.addAction(color_rows_action)
        
        color_cells_action = QAction("🎨 Залить выделенные ячейки", self)
        color_cells_action.triggered.connect(self._color_selected_cells)
        menu.addAction(color_cells_action)
        
        menu.addSeparator()
        
        if index.isValid():
            row = index.row()
            col = index.column()
            
            # Получаем номер закупки
            number_item = self.table.item(row, 0)
            number = number_item.data(Qt.UserRole) or number_item.text() if number_item else None
            
            if number:
                cell_color_action = QAction("🎨 Залить текущую ячейку", self)
                cell_color_action.triggered.connect(lambda: self._set_cell_color(number, col))
                menu.addAction(cell_color_action)
                
                row_color_action = QAction("🟨 Залить текущую строку", self)
                row_color_action.triggered.connect(lambda: self._set_row_color(number))
                menu.addAction(row_color_action)
                
                menu.addSeparator()
                
                clear_cell_action = QAction("🧹 Очистить цвет ячейки", self)
                clear_cell_action.triggered.connect(lambda: self._clear_cell_color(number, col))
                menu.addAction(clear_cell_action)
                
                clear_row_action = QAction("🧹 Очистить цвет строки", self)
                clear_row_action.triggered.connect(lambda: self._clear_row_color(number))
                menu.addAction(clear_row_action)
        
        menu.addSeparator()
        
        # ===== РАЗДЕЛИТЕЛИ =====
        if index.isValid():
            row = index.row()
            
            # Получаем номер закупки
            number_item = self.table.item(row, 0)
            number = number_item.data(Qt.UserRole) or number_item.text() if number_item else None
            
            if number:
                # Определяем текущий разделитель
                current_sep = self._row_separators.get(str(number), 'none')
                
                add_separator_menu = menu.addMenu("📏 Разделители")
                
                # Одиночная линия
                single_action = QAction("━ Одиночная линия", self)
                single_action.setCheckable(True)
                single_action.setChecked(current_sep == 'single')
                single_action.triggered.connect(lambda: self._set_row_separator(number, 'single'))
                add_separator_menu.addAction(single_action)
                
                # Двойная линия
                double_action = QAction("═ Двойная линия", self)
                double_action.setCheckable(True)
                double_action.setChecked(current_sep == 'double')
                double_action.triggered.connect(lambda: self._set_row_separator(number, 'double'))
                add_separator_menu.addAction(double_action)
                
                add_separator_menu.addSeparator()
                
                # Убрать разделитель
                none_action = QAction("✖ Убрать разделитель", self)
                none_action.setCheckable(True)
                none_action.setChecked(current_sep == 'none')
                none_action.triggered.connect(lambda: self._set_row_separator(number, 'none'))
                add_separator_menu.addAction(none_action)
                
                menu.addSeparator()
        
        clear_all_action = QAction("🧹 Очистить все цвета", self)
        clear_all_action.triggered.connect(self._clear_all_colors)
        menu.addAction(clear_all_action)
        
        clear_separators_action = QAction("🧹 Убрать все разделители", self)
        clear_separators_action.triggered.connect(self._clear_all_separators)
        menu.addAction(clear_separators_action)
        
        menu.exec(self.table.viewport().mapToGlobal(position))
    
    # ========== ЗАЛИВКА ЦВЕТОМ (ПРИВЯЗКА К НОМЕРУ) ==========
    
    def _color_selected_rows(self):
        """Заливает цветом все выделенные строки (по номеру)"""
        if not hasattr(self, 'table') or self.table is None:
            QMessageBox.warning(self, "Ошибка", "Таблица не инициализирована")
            return
        
        selected_ranges = self.table.selectedRanges()
        
        if not selected_ranges:
            selected_rows = set()
            selection_model = self.table.selectionModel()
            if selection_model:
                for idx in selection_model.selectedRows():
                    selected_rows.add(idx.row())
            
            if not selected_rows:
                QMessageBox.warning(self, "Предупреждение", "Выделите строки для заливки")
                return
            
            rows_to_color = list(selected_rows)
        else:
            rows_to_color = set()
            for sel_range in selected_ranges:
                for row in range(sel_range.topRow(), sel_range.bottomRow() + 1):
                    rows_to_color.add(row)
            rows_to_color = sorted(list(rows_to_color))
        
        if not rows_to_color:
            QMessageBox.warning(self, "Предупреждение", "Выделите строки для заливки")
            return
        
        color = QColorDialog.getColor(QColor(255, 255, 255), self, "Выберите цвет для выделенных строк")
        
        if not color.isValid():
            return
        
        for row in rows_to_color:
            number_item = self.table.item(row, 0)
            if number_item:
                number = number_item.data(Qt.UserRole) or number_item.text()
                if number:
                    self._row_colors[str(number)] = color.name()
            
            for col in range(self.table.columnCount()):
                item = self.table.item(row, col)
                if item:
                    item.setBackground(color)
        
        self._save_colors_immediate()
        self.status_label.setText(f"✅ Залито {len(rows_to_color)} строк")
    
    def _color_selected_cells(self):
        """Заливает цветом все выделенные ячейки (по номеру)"""
        if not hasattr(self, 'table') or self.table is None:
            QMessageBox.warning(self, "Ошибка", "Таблица не инициализирована")
            return
        
        selected_indexes = self.table.selectedIndexes()
        if not selected_indexes:
            QMessageBox.warning(self, "Предупреждение", "Выделите ячейки для заливки")
            return
        
        color = QColorDialog.getColor(QColor(255, 255, 255), self, "Выберите цвет для выделенных ячеек")
        
        if not color.isValid():
            return
        
        for idx in selected_indexes:
            row = idx.row()
            col = idx.column()
            
            number_item = self.table.item(row, 0)
            if number_item:
                number = number_item.data(Qt.UserRole) or number_item.text()
                if number:
                    key = f"{number}_{col}"
                    self._cell_colors[key] = color.name()
            
            item = self.table.item(row, col)
            if item:
                item.setBackground(color)
        
        self._save_colors_immediate()
        self.status_label.setText(f"✅ Залито {len(selected_indexes)} ячеек")
    
    def _set_cell_color(self, number, col):
        """Устанавливает цвет заливки для ячейки (по номеру)"""
        if not hasattr(self, 'table') or self.table is None:
            return
        
        color = QColorDialog.getColor(QColor(255, 255, 255), self, "Выберите цвет для ячейки")
        
        if color.isValid():
            row = self._get_row_for_number(number)
            if row >= 0:
                item = self.table.item(row, col)
                if item:
                    item.setBackground(color)
                
                key = f"{number}_{col}"
                self._cell_colors[key] = color.name()
                self._save_colors_immediate()
    
    def _set_row_color(self, number):
        """Устанавливает цвет заливки для всей строки (по номеру)"""
        if not hasattr(self, 'table') or self.table is None:
            return
        
        color = QColorDialog.getColor(QColor(255, 255, 255), self, "Выберите цвет для строки")
        
        if color.isValid():
            self._row_colors[str(number)] = color.name()
            
            row = self._get_row_for_number(number)
            if row >= 0:
                for col in range(self.table.columnCount()):
                    item = self.table.item(row, col)
                    if item:
                        item.setBackground(color)
            
            self._save_colors_immediate()
    
    def _clear_cell_color(self, number, col):
        """Очищает цвет заливки ячейки (по номеру)"""
        if not hasattr(self, 'table') or self.table is None:
            return
        
        key = f"{number}_{col}"
        if key in self._cell_colors:
            del self._cell_colors[key]
            
            row = self._get_row_for_number(number)
            if row >= 0:
                item = self.table.item(row, col)
                if item:
                    item.setBackground(QColor(255, 255, 255))
            
            self._save_colors_immediate()
    
    def _clear_row_color(self, number):
        """Очищает цвет заливки строки (по номеру)"""
        if not hasattr(self, 'table') or self.table is None:
            return
        
        if str(number) in self._row_colors:
            del self._row_colors[str(number)]
            
            row = self._get_row_for_number(number)
            if row >= 0:
                for col in range(self.table.columnCount()):
                    item = self.table.item(row, col)
                    if item:
                        item.setBackground(QColor(255, 255, 255))
            
            self._save_colors_immediate()
    
    def _clear_all_colors(self):
        """Очищает все цвета в таблице"""
        if not hasattr(self, 'table') or self.table is None:
            return
        
        for row in range(self.table.rowCount()):
            for col in range(self.table.columnCount()):
                item = self.table.item(row, col)
                if item:
                    item.setBackground(QColor(255, 255, 255))
        
        self._cell_colors.clear()
        self._row_colors.clear()
        self._save_colors_immediate()
        
        QMessageBox.information(self, "Готово", "🧹 Все цвета очищены")
    
    # ========== РАЗДЕЛИТЕЛИ (ПРИВЯЗКА К НОМЕРУ) ==========
    
    def _set_row_separator(self, number, sep_type):
        """Устанавливает разделитель после строки с номером"""
        if not hasattr(self, 'table') or self.table is None:
            return
        
        if sep_type == 'none':
            if str(number) in self._row_separators:
                del self._row_separators[str(number)]
        else:
            self._row_separators[str(number)] = sep_type
        
        # Принудительно перерисовываем таблицу
        self._apply_saved_separators()
        self._save_separators_immediate()
        self.status_label.setText(f"✅ Разделитель установлен для №{number}")
    
    def _apply_saved_separators(self):
        """Применяет сохранённые разделители к таблице (перерисовывает)"""
        self.table.set_separators(self._row_separators)
        self.table.viewport().update()
        self.table.repaint()
    
    def _save_separators_immediate(self):
        """Немедленное сохранение разделителей"""
        try:
            from database.config_db import get_config_db
            config_db = get_config_db()
            config_db.set('statistics_row_separators', self._row_separators, 'statistics')
        except Exception as e:
            self.logger.error(f"Ошибка сохранения разделителей: {e}")
    
    def _clear_all_separators(self):
        """Убирает все разделители"""
        self._row_separators.clear()
        self._save_separators_immediate()
        self._apply_saved_separators()
        QMessageBox.information(self, "Готово", "🧹 Все разделители убраны")
    
    # ========== ЭКСПОРТ ==========
    
    def export_to_csv(self):
        """Экспортирует таблицу в CSV"""
        file_path, _ = QFileDialog.getSaveFileName(
            self, "Сохранить статистику",
            str(Path.home() / f"statistics_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"),
            "CSV files (*.csv);;All files (*.*)"
        )
        
        if file_path:
            try:
                import csv
                with open(file_path, 'w', encoding='utf-8-sig', newline='') as f:
                    writer = csv.writer(f)
                    
                    headers = []
                    for col in range(self.table.columnCount()):
                        headers.append(self.table.horizontalHeaderItem(col).text())
                    writer.writerow(headers)
                    
                    for row in range(self.table.rowCount()):
                        row_data = []
                        for col in range(self.table.columnCount()):
                            item = self.table.item(row, col)
                            row_data.append(item.text() if item else "")
                        writer.writerow(row_data)
                    
                    writer.writerow([])
                    writer.writerow(["Итого:", self.total_label.text()])
                
                QMessageBox.information(self, "Успех", f"Статистика сохранена:\n{file_path}")
            except Exception as e:
                QMessageBox.critical(self, "Ошибка", f"Не удалось保存ить:\n{e}")
    
    # ========== РЕДАКТИРОВАНИЕ ЗАТРАТ ==========

    def on_cell_double_clicked(self, item):
        """Двойной клик: редактируется ТОЛЬКО колонка 'Затраты (₽)' через диалог.
        Новое значение пишется:
        1) в кэш ConfigDB ('statistics_cached_data' → costs) — ЕДИНСТВЕННЫЙ
           источник значения колонки, дальше оно ничем не пересчитывается;
        2) в purchases.manual_costs / purchases_archive.manual_costs —
           синхронизация БД для совместимости с остальными модулями."""
        row = item.row()
        col = item.column()
        if col == 8:  # Затраты
            current_value = item.text()
            try:
                current_float = float(current_value.replace(',', '.')) if current_value else 0
            except Exception:
                current_float = 0
            new_value, ok = QInputDialog.getDouble(
                self,
                "Редактирование затрат",
                "Введите новое значение затрат (₽):",
                current_float,
                -10000000, 10000000,
                2
            )
            if ok:
                item.setText(f"{new_value:.2f}")
                number_item = self.table.item(row, 0)
                number = number_item.data(Qt.UserRole) or number_item.text()
                # 1) КЭШ — главный источник (больше ничто не переписывает)
                self._set_cached_costs(number, new_value)
                # 2) Синхронизация БД (manual_costs) для совместимости
                self.update_costs_in_db(number, new_value)
                self.recalculate_row(row, number, new_value)
        else:
            QMessageBox.information(
                self,
                "Информация",
                f"Колонка '{self.table.horizontalHeaderItem(col).text()}' не редактируется.\n"
                f"Редактировать можно только колонку 'Затраты (₽)'."
            )

    def update_costs_in_db(self, purchase_number, new_costs):
        """Обновляет ручные затраты для всех закупок с указанным номером"""
        try:
            purchases = self.db_manager.session.query(Purchase).filter_by(
                purchase_number=str(purchase_number)
            ).all()
            
            archived_purchases = self.db_manager.session.query(PurchaseArchive).filter_by(
                purchase_number=str(purchase_number)
            ).all()
            
            total_quantity = 0
            for p in purchases:
                total_quantity += p.quantity or 1
            for p in archived_purchases:
                total_quantity += p.quantity or 1
            
            if total_quantity == 0:
                return
            
            cost_per_item = new_costs / total_quantity
            
            for p in purchases:
                qty = p.quantity or 1
                p.manual_costs = cost_per_item * qty
            
            for p in archived_purchases:
                qty = p.quantity or 1
                p.manual_costs = cost_per_item * qty
            
            self.db_manager.session.commit()
            self.logger.info(f"Обновлены ручные затраты для №{purchase_number}: {new_costs:.2f} ₽")
            
        except Exception as e:
            self.db_manager.session.rollback()
            self.logger.error(f"Ошибка обновления затрат: {e}")
    
    def recalculate_row(self, row, purchase_number, new_costs):
        """Пересчитывает прибыль и процент прибыли для строки"""
        try:
            total_item = self.table.item(row, 1)
            sold_item = self.table.item(row, 3)
            sales_sum_item = self.table.item(row, 5)
            
            total = float(total_item.text()) if total_item and total_item.text() else 0
            sold = float(sold_item.text()) if sold_item and sold_item.text() else 0
            sales_sum = float(sales_sum_item.text().replace(',', '.')) if sales_sum_item and sales_sum_item.text() else 0
            
            profit = sales_sum - new_costs
            profit_percent = (profit / new_costs * 100) if new_costs > 0 else (100 if sales_sum > 0 else 0)
            
            self.table.item(row, 9).setText(f"{profit:.2f}" if profit != 0 else "0")
            self.table.item(row, 12).setText(f"{profit_percent:.1f}%" if profit_percent != 0 else "0%")
            
            self._update_total_row()
            
        except Exception as e:
            self.logger.error(f"Ошибка пересчёта строки: {e}")
    
    def _update_total_row(self):
        """Обновляет итоговую строку внизу таблицы"""
        try:
            total_sum = 0
            total_sold = 0
            total_sales = 0
            total_costs = 0
            
            for row in range(self.table.rowCount()):
                costs_item = self.table.item(row, 8)
                if costs_item and costs_item.text():
                    total_costs += float(costs_item.text().replace(',', '.'))
                
                sales_item = self.table.item(row, 5)
                if sales_item and sales_item.text():
                    total_sales += float(sales_item.text().replace(',', '.'))
                
                total_item = self.table.item(row, 1)
                if total_item and total_item.text():
                    total_sum += float(total_item.text())
                
                sold_item = self.table.item(row, 3)
                if sold_item and sold_item.text():
                    total_sold += float(sold_item.text())
            
            total_profit = total_sales - total_costs
            total_sold_percent = (total_sold / total_sum * 100) if total_sum > 0 else 0
            total_profit_percent = (total_profit / total_costs * 100) if total_costs > 0 else 0
            
            self.total_label.setText(
                f"📊 ИТОГО: {total_sum:.0f} монет | "
                f"Продано: {total_sold:.0f} | "
                f"Продажи: {total_sales:.2f} ₽ | "
                f"Затраты: {total_costs:.2f} ₽ | "
                f"Прибыль: {total_profit:.2f} ₽ | "
                f"% продаж: {total_sold_percent:.1f}% | "
                f"% прибыли: {total_profit_percent:.1f}%"
            )
            
        except Exception as e:
            self.logger.error(f"Ошибка обновления итогов: {e}")
    
    # ========== ОБРАБОТЧИК ИЗМЕНЕНИЙ ==========
    
    def _on_item_changed(self, item):
        """Обработчик изменения ячейки (сохраняет только при реальном изменении пользователем)"""
        if self._updating:
            return
        
        if not item:
            return
        
        # Если мы в процессе перезагрузки, не сохраняем
        if self._is_reloading:
            return
        
        row = item.row()
        col = item.column()
        
        col_count = self.table.columnCount()
        year_index = col_count - 2
        comments_index = col_count - 1
        
        number_item = self.table.item(row, 0)
        if not number_item:
            return
        
        number = number_item.data(Qt.UserRole)
        if not number:
            number = number_item.text()
        
        # Только для колонок ГОД и Комментарии
        if col == year_index:
            self._updating = True
            try:
                year_text = item.text().strip()
                # Проверяем, изменилось ли значение
                if number in self._data_cache:
                    current_year = self._data_cache[number].get('year', '')
                    if current_year != year_text:
                        self._set_cached_year(number, year_text)
                        self.logger.debug(f"Сохранён год '{year_text}' для №{number}")
                else:
                    self._set_cached_year(number, year_text)
                    self.logger.debug(f"Сохранён год '{year_text}' для №{number}")
            finally:
                self._updating = False
        
        elif col == comments_index:
            self._updating = True
            try:
                comment_text = item.text().strip()
                # Проверяем, изменилось ли значение
                if number in self._data_cache:
                    current_comment = self._data_cache[number].get('comment', '')
                    if current_comment != comment_text:
                        self._set_cached_comment(number, comment_text)
                        self.logger.debug(f"Сохранён комментарий для №{number}")
                else:
                    self._set_cached_comment(number, comment_text)
                    self.logger.debug(f"Сохранён комментарий для №{number}")
            finally:
                self._updating = False