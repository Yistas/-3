# ===== gui/widgets/base_tab.py =====
# НОВЫЙ ФАЙЛ

# -*- coding: utf-8 -*-

"""
Базовый класс для вкладок с таблицами (Deals, Sales, Purchases)
Устраняет дублирование кода
"""

import logging
import json
from pathlib import Path
from datetime import datetime

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTableView, QHeaderView,
    QPushButton, QLabel, QMessageBox, QMenu, QApplication, QLineEdit,
    QFrame, QProgressBar, QAbstractItemView
)
from PySide6.QtCore import Qt, QTimer, QPoint, QModelIndex, QAbstractTableModel, QSettings


class BaseTab(QWidget):
    """Базовый класс для вкладок с таблицами"""
    
    # Должны быть переопределены в наследниках
    COLUMN_KEYS = []
    HEADERS = []
    DEFAULT_COLUMN_WIDTHS = []
    MODEL_CLASS = None
    DB_MODEL = None
    SETTINGS_PREFIX = "base_tab"
    
    def __init__(self, db_manager, parent=None):
        super().__init__(parent)
        self.db_manager = db_manager
        self.logger = logging.getLogger(f'CoinCollector.{self.__class__.__name__}')
        
        # Данные
        self._all_items = []
        self._filtered_items = []
        self._dirty_ids = set()
        self._column_filters = {}
        self._disabled_filters = {}
        
        # Undo/Redo
        self._last_changes = []
        self._redo_stack = []
        
        # Таймер сохранения
        self._save_timer = QTimer()
        self._save_timer.setSingleShot(True)
        self._save_timer.timeout.connect(self._flush_changes)
        
        # Кэш для скопированных данных
        self._copied_cells_data = None
        self._copied_row_data = None
        
        self.init_ui()
        self._restore_column_state()
        self._load_column_filters_from_json()
        
        QTimer.singleShot(100, self.load_data)
        self.setFocusPolicy(Qt.StrongFocus)
    
    # ========== АБСТРАКТНЫЕ МЕТОДЫ (ДОЛЖНЫ БЫТЬ ПЕРЕОПРЕДЕЛЕНЫ) ==========
    
    def load_data(self):
        """Загружает данные из БД"""
        raise NotImplementedError("Должен быть реализован в наследнике")
    
    def _get_item_value(self, item, column_key):
        """Возвращает значение для колонки"""
        raise NotImplementedError("Должен быть реализован в наследнике")
    
    def _on_cell_edited(self, item, column_key, new_value):
        """Обработчик редактирования ячейки"""
        raise NotImplementedError("Должен быть реализован в наследнике")
    
    def _create_model(self):
        """Создаёт модель данных"""
        if self.MODEL_CLASS:
            return self.MODEL_CLASS(self, self.db_manager)
        raise NotImplementedError("Должен быть реализован в наследнике")
    
    # ========== БАЗОВАЯ ИНИЦИАЛИЗАЦИЯ UI ==========
    
    def init_ui(self):
        """Инициализация интерфейса"""
        layout = QVBoxLayout()
        layout.setContentsMargins(5, 5, 5, 5)
        layout.setSpacing(5)
        self.setLayout(layout)
        
        # Панель инструментов
        toolbar = self._create_toolbar()
        layout.addWidget(toolbar)
        
        # Фильтры
        self._create_filters(layout)
        
        # Метка фильтров
        self.filter_label = QLabel("")
        self.filter_label.setStyleSheet("color: #dc3545; font-size: 9px; padding: 0px 2px;")
        self.filter_label.setVisible(False)
        self.filter_label.setCursor(Qt.PointingHandCursor)
        self.filter_label.mousePressEvent = lambda e: self._clear_all_filters()
        layout.addWidget(self.filter_label)
        
        # Модель и таблица
        self.model = self._create_model()
        self._setup_table()
        layout.addWidget(self.table)
        
        # Статус-бар
        self._create_status_bar(layout)
        
        # Загружаем данные
        QTimer.singleShot(100, self.load_data)
    
    def _create_toolbar(self):
        """Создаёт панель инструментов"""
        toolbar = QFrame()
        toolbar.setFixedHeight(40)
        toolbar.setStyleSheet("background-color: #f5f5f5; border: 1px solid #ddd; border-radius: 3px;")
        
        layout = QHBoxLayout()
        layout.setContentsMargins(5, 2, 5, 2)
        layout.setSpacing(8)
        toolbar.setLayout(layout)
        
        # Кнопка добавления
        add_btn = QPushButton("➕ Добавить")
        add_btn.clicked.connect(self._add_item)
        add_btn.setFixedHeight(32)
        layout.addWidget(add_btn)
        
        # Кнопка удаления
        del_btn = QPushButton("🗑️ Удалить")
        del_btn.clicked.connect(self._delete_selected)
        del_btn.setFixedHeight(32)
        del_btn.setStyleSheet("background-color: #dc3545; color: white; font-weight: bold; border-radius: 3px;")
        layout.addWidget(del_btn)
        
        # Разделитель
        sep = QFrame()
        sep.setFrameShape(QFrame.VLine)
        sep.setFrameShadow(QFrame.Sunken)
        sep.setFixedSize(2, 28)
        layout.addWidget(sep)
        
        # Навигация
        nav_widget = self._create_navigation_panel()
        layout.addWidget(nav_widget)
        
        layout.addStretch()
        
        # Очистка и обновление
        clear_btn = QPushButton("🗑️ Очистить всё")
        clear_btn.clicked.connect(self._clear_all)
        clear_btn.setFixedHeight(32)
        clear_btn.setStyleSheet("background-color: #dc3545; color: white; font-weight: bold; border-radius: 3px;")
        layout.addWidget(clear_btn)
        
        refresh_btn = QPushButton("🔄 Обновить")
        refresh_btn.clicked.connect(self.load_data)
        refresh_btn.setFixedHeight(32)
        refresh_btn.setStyleSheet("background-color: #6c757d; color: white; font-weight: bold; border-radius: 3px;")
        layout.addWidget(refresh_btn)
        
        return toolbar
    
    def _create_navigation_panel(self):
        """Создаёт панель навигации"""
        nav_widget = QWidget()
        nav_layout = QHBoxLayout()
        nav_layout.setContentsMargins(0, 0, 0, 0)
        nav_layout.setSpacing(5)
        nav_widget.setLayout(nav_layout)
        
        self.top_btn = QPushButton("▲")
        self.top_btn.setFixedSize(32, 32)
        self.top_btn.setToolTip("Перейти к первой строке")
        self.top_btn.clicked.connect(self._scroll_to_top)
        nav_layout.addWidget(self.top_btn)
        
        self.bottom_btn = QPushButton("▼")
        self.bottom_btn.setFixedSize(32, 32)
        self.bottom_btn.setToolTip("Перейти к последней строке")
        self.bottom_btn.clicked.connect(self._scroll_to_bottom)
        nav_layout.addWidget(self.bottom_btn)
        
        self.count_label = QLabel("Записей: 0")
        self.count_label.setStyleSheet("color: #666; font-size: 11px; padding: 0 10px;")
        nav_layout.addWidget(self.count_label)
        
        nav_layout.addStretch()
        return nav_widget
    
    def _create_filters(self, parent_layout):
        """Создаёт фильтры (переопределяется в наследниках)"""
        pass
    
    def _create_status_bar(self, parent_layout):
        """Создаёт статус-бар"""
        status_bar = QFrame()
        status_bar.setFrameShape(QFrame.StyledPanel)
        status_bar.setFixedHeight(28)
        status_bar.setStyleSheet("QFrame { background-color: #f0f0f0; }")
        
        layout = QHBoxLayout()
        layout.setContentsMargins(5, 2, 5, 2)
        
        self.status_label = QLabel("Готов")
        self.status_label.setStyleSheet("color: #666;")
        layout.addWidget(self.status_label)
        
        layout.addStretch()
        parent_layout.addWidget(status_bar)
    
    def _setup_table(self):
        """Настраивает таблицу"""
        self.table = QTableView()
        self.table.setModel(self.model)
        self.table.setAlternatingRowColors(True)
        self.table.setSelectionBehavior(QAbstractItemView.SelectItems)
        self.table.setSelectionMode(QAbstractItemView.ExtendedSelection)
        
        self.table.setEditTriggers(
            QAbstractItemView.CurrentChanged |
            QAbstractItemView.EditKeyPressed
        )
        
        self.table.setSortingEnabled(True)
        self.table.horizontalHeader().setSortIndicatorShown(True)
        self.table.clicked.connect(self._on_table_clicked)
        
        # Контекстное меню
        self.table.setContextMenuPolicy(Qt.CustomContextMenu)
        self.table.customContextMenuRequested.connect(self._show_cell_context_menu)
        
        header = self.table.horizontalHeader()
        header.setSectionsMovable(True)
        header.setContextMenuPolicy(Qt.CustomContextMenu)
        header.customContextMenuRequested.connect(self._show_header_filter_menu)
        header.sectionMoved.connect(self._on_column_moved)
        header.sectionResized.connect(self._on_column_resized)
        
        v_header = self.table.verticalHeader()
        v_header.setContextMenuPolicy(Qt.CustomContextMenu)
        v_header.customContextMenuRequested.connect(self._show_row_context_menu)
        
        # Делегат
        self._setup_delegate()
        
        # Ширина колонок
        for i, width in enumerate(self.DEFAULT_COLUMN_WIDTHS):
            if i < len(self.HEADERS):
                self.table.setColumnWidth(i, width)
                header.setSectionResizeMode(i, QHeaderView.Interactive)
    
    def _setup_delegate(self):
        """Настраивает делегат (переопределяется в наследниках)"""
        pass
    
    # ========== БАЗОВЫЕ ДЕЙСТВИЯ ==========
    
    def _add_item(self):
        """Добавляет новый элемент (переопределяется в наследниках)"""
        raise NotImplementedError("Должен быть реализован в наследнике")
    
    def _delete_selected(self):
        """Удаляет выбранные элементы (переопределяется в наследниках)"""
        raise NotImplementedError("Должен быть реализован в наследнике")
    
    def _clear_all(self):
        """Очищает все элементы (переопределяется в наследниках)"""
        raise NotImplementedError("Должен быть реализован в наследнике")
    
    def _flush_changes(self):
        """Сохраняет изменения в БД"""
        if not self._dirty_ids:
            return
        
        try:
            self.db_manager.session.commit()
            self._dirty_ids.clear()
            self.status_label.setText("💾 Изменения сохранены")
            self.status_label.setStyleSheet("color: #28a745;")
            QTimer.singleShot(2000, lambda: self.status_label.setStyleSheet("color: #666;"))
        except Exception as e:
            self.db_manager.session.rollback()
            self.logger.error(f"Ошибка сохранения: {e}")
            self.status_label.setText(f"❌ Ошибка: {str(e)[:30]}")
            self.status_label.setStyleSheet("color: #dc3545;")
    
    # ========== НАВИГАЦИЯ ==========
    
    def _scroll_to_top(self):
        """Прокручивает к первой строке"""
        model = self.table.model()
        if model.rowCount() == 0:
            return
        
        first_index = model.index(0, 0)
        if first_index.isValid():
            self.table.scrollTo(first_index, QAbstractItemView.PositionAtTop)
            self.table.setCurrentIndex(first_index)
            self.table.selectRow(first_index.row())
    
    def _scroll_to_bottom(self):
        """Прокручивает к последней строке"""
        model = self.table.model()
        row_count = model.rowCount()
        if row_count == 0:
            return
        
        last_index = model.index(row_count - 1, 0)
        if last_index.isValid():
            self.table.scrollTo(last_index, QAbstractItemView.PositionAtBottom)
            self.table.setCurrentIndex(last_index)
            self.table.selectRow(last_index.row())
    
    # ========== СОХРАНЕНИЕ СОСТОЯНИЯ ==========
    
# ===== gui/widgets/base_tab.py =====
# ЗАМЕНИТЬ МЕТОД _save_column_state

    def _save_column_state(self):
        """Сохраняет состояние колонок"""
        try:
            header = self.table.horizontalHeader()
            order = [header.logicalIndex(vp) for vp in range(header.count())]
            
            settings = QSettings('CoinCollector', self.SETTINGS_PREFIX)
            settings.setValue('column_order', order)
            
            widths = []
            for li in range(len(self.HEADERS)):
                vi = header.visualIndex(li)
                w = self.table.columnWidth(vi)
                widths.append(int(w) if w > 0 else 0)
            settings.setValue('column_widths', widths)
        except Exception as e:
            self.logger.debug(f"Ошибка сохранения состояния колонок: {e}")

    def _restore_column_state(self):
        """Восстанавливает состояние колонок"""
        try:
            settings = QSettings('CoinCollector', self.SETTINGS_PREFIX)
            header = self.table.horizontalHeader()
            
            saved_order = settings.value('column_order')
            if saved_order and isinstance(saved_order, list):
                for vi, li in enumerate(saved_order):
                    try:
                        li = int(li)
                        if li < len(self.HEADERS):
                            cv = header.visualIndex(li)
                            if cv != vi:
                                header.moveSection(cv, vi)
                    except (ValueError, TypeError):
                        continue
            
            saved_widths = settings.value('column_widths')
            if saved_widths and isinstance(saved_widths, list):
                for li, w in enumerate(saved_widths):
                    try:
                        # ПРЕОБРАЗУЕМ В INT
                        width = int(w) if w is not None else 0
                        if li < len(self.HEADERS) and width > 0:
                            vi = header.visualIndex(li)
                            self.table.setColumnWidth(vi, width)
                    except (ValueError, TypeError):
                        continue
        except Exception as e:
            self.logger.debug(f"Ошибка восстановления состояния колонок: {e}")
    
    def _save_column_filters_to_json(self):
        """Сохраняет фильтры в JSON"""
        filters_file = Path("data") / f"{self.SETTINGS_PREFIX}_filters.json"
        filters_file.parent.mkdir(exist_ok=True)
        
        try:
            filters_to_save = {}
            for k, v in self._column_filters.items():
                if isinstance(v, set):
                    filters_to_save[str(k)] = list(v)
                else:
                    filters_to_save[str(k)] = v
            
            with open(filters_file, 'w', encoding='utf-8') as f:
                json.dump(filters_to_save, f, ensure_ascii=False, indent=2)
        except Exception as e:
            self.logger.error(f"Ошибка сохранения фильтров: {e}")
    
    def _load_column_filters_from_json(self):
        """Загружает фильтры из JSON"""
        filters_file = Path("data") / f"{self.SETTINGS_PREFIX}_filters.json"
        if not filters_file.exists():
            return
        
        try:
            with open(filters_file, 'r', encoding='utf-8') as f:
                saved = json.load(f)
            
            for k, v in saved.items():
                self._column_filters[int(k)] = set(v) if isinstance(v, list) else v
            
            self._update_filter_label()
        except Exception as e:
            self.logger.error(f"Ошибка загрузки фильтров: {e}")
    
    # ========== ФИЛЬТРАЦИЯ ==========
    
    def _update_filter_label(self):
        """Обновляет метку активных фильтров"""
        if not self._column_filters:
            self.filter_label.setVisible(False)
            return
        
        self.filter_label.setVisible(True)
        parts = []
        for col, val in sorted(self._column_filters.items()):
            col_name = self.HEADERS[col] if col < len(self.HEADERS) else str(col)
            if isinstance(val, set):
                parts.append(f"{col_name}: {len(val)} знач.")
            else:
                parts.append(f"{col_name}: {val}")
        self.filter_label.setText("🔍 Фильтры: " + " | ".join(parts) + "  [нажмите для сброса]")
    
    def _clear_all_filters(self):
        """Сбрасывает все фильтры"""
        self._column_filters.clear()
        self.filter_label.setVisible(False)
        self._save_column_filters_to_json()
        self._apply_filters()
    
    def _apply_filters(self):
        """Применяет фильтры (переопределяется в наследниках)"""
        raise NotImplementedError("Должен быть реализован в наследнике")
    
    def _filter_by_value(self, col, value):
        """Фильтрует по значению"""
        self._column_filters[col] = {value}
        self._update_filter_label()
        self._save_column_filters_to_json()
        self._apply_filters()
    
    def _filter_exclude_value(self, col, value):
        """Исключает значение"""
        all_values = set()
        for item in self._all_items:
            key = self.COLUMN_KEYS[col]
            if key == 'id':
                continue
            val = self._get_item_value(item, key)
            if val and str(val).strip():
                all_values.add(str(val).strip())
        
        filtered = all_values - {value}
        if filtered:
            self._column_filters[col] = filtered
        else:
            self._column_filters.pop(col, None)
        
        self._update_filter_label()
        self._save_column_filters_to_json()
        self._apply_filters()
    
    # ========== КОНТЕКСТНЫЕ МЕНЮ ==========
    
    def _show_cell_context_menu(self, position):
        """Показывает контекстное меню для ячейки"""
        index = self.table.indexAt(position)
        if not index.isValid():
            return
        
        row = index.row()
        col = index.column()
        
        # Получаем элемент
        item = self.model.get_item(row) if hasattr(self.model, 'get_item') else None
        if not item:
            return
        
        value = index.data(Qt.DisplayRole)
        col_name = self.HEADERS[col] if col < len(self.HEADERS) else ""
        
        menu = QMenu(self)
        
        title = QAction(f"📌 Колонка: {col_name}", menu)
        title.setEnabled(False)
        menu.addAction(title)
        menu.addSeparator()
        
        if value and str(value).strip():
            filter_action = QAction(f"🔍 Показать только «{value}»", menu)
            filter_action.triggered.connect(lambda: self._filter_by_value(col, value))
            menu.addAction(filter_action)
            
            exclude_action = QAction(f"🚫 Скрыть «{value}»", menu)
            exclude_action.triggered.connect(lambda: self._filter_exclude_value(col, value))
            menu.addAction(exclude_action)
            
            menu.addSeparator()
        
        # Копировать/Вставить
        copy_action = QAction("📋 Копировать ячейку", menu)
        copy_action.setShortcut("Ctrl+C")
        copy_action.triggered.connect(self._copy_selected_cells)
        menu.addAction(copy_action)
        
        paste_action = QAction("📌 Вставить", menu)
        paste_action.setShortcut("Ctrl+V")
        paste_action.triggered.connect(self._paste_to_selected_cells)
        menu.addAction(paste_action)
        
        menu.addSeparator()
        
        # Отмена
        undo_action = QAction("↩ Отменить", menu)
        undo_action.setShortcut("Ctrl+Z")
        undo_action.triggered.connect(self._undo_last_change)
        menu.addAction(undo_action)
        
        menu.exec(self.table.viewport().mapToGlobal(position))
    
    def _show_row_context_menu(self, position):
        """Показывает контекстное меню для строки"""
        row = self.table.verticalHeader().logicalIndexAt(position)
        if row < 0 or row >= self.table.model().rowCount():
            return
        
        selected_rows = set()
        for idx in self.table.selectionModel().selectedRows():
            selected_rows.add(idx.row())
        
        if not selected_rows:
            selected_rows.add(row)
        
        count = len(selected_rows)
        
        menu = QMenu(self)
        
        insert_menu = menu.addMenu("⬇️ Вставить строки")
        insert_menu.addAction("1 строку", lambda: self._insert_empty_row(row))
        insert_menu.addAction("5 строк", lambda: self._insert_n_rows(row, 5))
        insert_menu.addAction("10 строк", lambda: self._insert_n_rows(row, 10))
        insert_menu.addAction("✏️ Своё количество...", lambda: self._insert_n_rows(row, None))
        
        menu.addSeparator()
        
        copy_action = QAction("📝 Копировать строки", menu)
        copy_action.triggered.connect(lambda: self._copy_row(list(selected_rows)))
        menu.addAction(copy_action)
        
        menu.addSeparator()
        
        menu.addAction(f"🗑️ Удалить {count} строк", self._delete_selected)
        
        menu.exec(self.table.verticalHeader().mapToGlobal(position))
    
    def _show_header_filter_menu(self, position):
        """Показывает меню фильтрации для заголовка"""
        header = self.table.horizontalHeader()
        logical_index = header.logicalIndexAt(position)
        
        if logical_index < 0 or logical_index >= len(self.HEADERS):
            return
        
        column_name = self.HEADERS[logical_index]
        
        all_values = set()
        for item in self._all_items:
            key = self.COLUMN_KEYS[logical_index]
            if key == 'id':
                continue
            val = self._get_item_value(item, key)
            if val and str(val).strip():
                all_values.add(str(val).strip())
        
        dialog = QDialog(self)
        dialog.setWindowTitle(f"Фильтр: {column_name}")
        dialog.setMinimumWidth(350)
        dialog.setModal(True)
        
        layout = QVBoxLayout(dialog)
        
        title_label = QLabel(f"📌 Фильтр по '{column_name}'")
        title_label.setStyleSheet("font-weight: bold; font-size: 13px; padding: 5px;")
        layout.addWidget(title_label)
        
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll_widget = QWidget()
        scroll_layout = QVBoxLayout(scroll_widget)
        
        checkboxes = []
        for value in sorted(all_values):
            cb = QCheckBox(value)
            cb.setChecked(logical_index in self._column_filters and value in self._column_filters[logical_index])
            scroll_layout.addWidget(cb)
            checkboxes.append((cb, value))
        
        scroll_layout.addStretch()
        scroll.setWidget(scroll_widget)
        layout.addWidget(scroll)
        
        btn_layout = QHBoxLayout()
        ok_btn = QPushButton("✅ Применить")
        cancel_btn = QPushButton("❌ Отмена")
        
        def apply():
            selected = {v for cb, v in checkboxes if cb.isChecked()}
            if selected:
                self._column_filters[logical_index] = selected
            else:
                self._column_filters.pop(logical_index, None)
            self._update_filter_label()
            self._save_column_filters_to_json()
            self._apply_filters()
            dialog.accept()
        
        ok_btn.clicked.connect(apply)
        cancel_btn.clicked.connect(dialog.reject)
        
        btn_layout.addWidget(ok_btn)
        btn_layout.addWidget(cancel_btn)
        layout.addLayout(btn_layout)
        
        dialog.exec()
    
    # ========== ВСТАВКА СТРОК ==========
    
    def _insert_empty_row(self, row):
        """Вставляет пустую строку (переопределяется в наследниках)"""
        pass
    
    def _insert_n_rows(self, row, n):
        """Вставляет N строк (переопределяется в наследниках)"""
        pass
    
    def _copy_row(self, rows):
        """Копирует строки (переопределяется в наследниках)"""
        pass
    
    def _copy_selected_cells(self):
        """Копирует выделенные ячейки"""
        selected_indexes = self.table.selectionModel().selectedIndexes()
        if not selected_indexes:
            return
        
        rows = {}
        for idx in selected_indexes:
            row = idx.row()
            col = idx.column()
            if row not in rows:
                rows[row] = {}
            value = idx.data(Qt.DisplayRole) or ""
            rows[row][col] = value
        
        lines = []
        for row in sorted(rows.keys()):
            cols = rows[row]
            max_col = max(cols.keys()) if cols else 0
            line = []
            for col in range(max_col + 1):
                line.append(cols.get(col, ""))
            lines.append("\t".join(line))
        
        clipboard = QApplication.clipboard()
        clipboard.setText("\n".join(lines))
        
        self.status_label.setText(f"📋 Скопировано {len(selected_indexes)} ячеек")
        self.status_label.setStyleSheet("color: #28a745;")
        QTimer.singleShot(2000, lambda: self.status_label.setStyleSheet("color: #666;"))
    
    def _paste_to_selected_cells(self):
        """Вставляет данные из буфера"""
        clipboard = QApplication.clipboard()
        text = clipboard.text()
        if not text:
            return
        
        rows_data = [line.split("\t") for line in text.strip().split("\n")]
        if not rows_data:
            return
        
        selected_indexes = self.table.selectionModel().selectedIndexes()
        if not selected_indexes:
            current = self.table.currentIndex()
            if current.isValid():
                selected_indexes = [current]
        
        if not selected_indexes:
            return
        
        selected_indexes.sort(key=lambda x: (x.row(), x.column()))
        
        source_rows = len(rows_data)
        source_cols = len(rows_data[0]) if source_rows > 0 else 0
        
        if source_rows == 0 or source_cols == 0:
            return
        
        self.table.setUpdatesEnabled(False)
        self.model.blockSignals(True)
        
        try:
            changes = []
            
            for i, target_idx in enumerate(selected_indexes):
                source_row = i % source_rows
                source_col = (i // source_rows) % source_cols
                value = rows_data[source_row][source_col] if source_col < len(rows_data[source_row]) else ""
                
                row = target_idx.row()
                col = target_idx.column()
                
                # Получаем элемент
                item = self.model.get_item(row) if hasattr(self.model, 'get_item') else None
                if not item:
                    continue
                
                field_name = self.COLUMN_KEYS[col] if col < len(self.COLUMN_KEYS) else None
                if field_name and field_name != 'id':
                    old_value = getattr(item, field_name, None)
                    if str(old_value) != value:
                        changes.append({
                            'item_id': item.id,
                            'field': field_name,
                            'old_value': old_value,
                            'new_value': value
                        })
                        self._on_cell_edited(item, field_name, value)
            
            if changes:
                self._last_changes.append(changes)
                self._redo_stack.clear()
            
            self.model.dataChanged.emit(
                self.model.index(0, 0),
                self.model.index(self.model.rowCount() - 1, self.model.columnCount() - 1),
                [Qt.DisplayRole]
            )
            
            self.status_label.setText(f"📌 Вставлено в {len(selected_indexes)} ячеек")
            self.status_label.setStyleSheet("color: #28a745;")
            QTimer.singleShot(2000, lambda: self.status_label.setStyleSheet("color: #666;"))
            
        except Exception as e:
            self.logger.error(f"Ошибка вставки: {e}")
            self.status_label.setText(f"❌ Ошибка: {str(e)[:50]}")
        finally:
            self.model.blockSignals(False)
            self.table.setUpdatesEnabled(True)
    
    def _undo_last_change(self):
        """Отменяет последнее изменение"""
        if not self._last_changes:
            self.status_label.setText("ℹ️ Нет действий для отмены")
            return
        
        try:
            changes = self._last_changes.pop()
            self._redo_stack.append(changes)
            
            for change in changes:
                item = None
                for i in self._filtered_items:
                    if i.id == change['item_id']:
                        item = i
                        break
                
                if item:
                    setattr(item, change['field'], change['old_value'])
                    self._dirty_ids.add(item.id)
            
            self._flush_changes()
            self._apply_filters()
            
            self.status_label.setText("↩️ Изменение отменено")
            self.status_label.setStyleSheet("color: #28a745;")
            QTimer.singleShot(2000, lambda: self.status_label.setStyleSheet("color: #666;"))
            
        except Exception as e:
            self.logger.error(f"Ошибка отмены: {e}")
            self.status_label.setText(f"❌ Ошибка: {str(e)[:30]}")
    
    def _on_table_clicked(self, index):
        """Обработчик клика по таблице"""
        if not index.isValid():
            return
        
        current = self.table.currentIndex()
        if current.isValid() and current.row() == index.row() and current.column() == index.column():
            self.table.edit(index)
    
    # ========== ОБРАБОТЧИКИ КОЛОНОК ==========
    
    def _on_column_moved(self, logical_index, old_visual_index, new_visual_index):
        self._save_column_state()
    
# ===== gui/widgets/base_tab.py =====
# ЗАМЕНИТЬ МЕТОД _on_column_resized

    def _on_column_resized(self, logical_index, old_size, new_size):
        """Обработчик изменения размера колонки"""
        try:
            if old_size == new_size:
                return
            self._save_column_state()
        except Exception as e:
            self.logger.debug(f"Ошибка при изменении размера колонки: {e}")