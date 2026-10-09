# -*- coding: utf-8 -*-

"""
Вкладка "Сделки" — основной класс
"""


import logging
import re
from datetime import datetime
from pathlib import Path

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTableView, QHeaderView, QAbstractItemView,
    QPushButton, QLabel, QMessageBox, QMenu, QApplication, QFrame,
    QLineEdit, QFileDialog, QProgressBar, QDialog, QScrollArea, QCheckBox,
    QInputDialog, QComboBox
)
from PySide6.QtCore import Qt, QTimer, QPoint
from PySide6.QtGui import QAction, QKeySequence

from database.models import Deal

from .deals_model import DealsTableModel
from .deals_proxy import DealsSortProxyModel
from .deals_delegate import DealsDelegate
from .deals_actions import DealsActionsMixin
from .deals_filters import DealsFiltersMixin
from .deals_clipboard import DealsClipboardMixin
from .deals_io import DealsIOMixin


class DealsTab(
    QWidget,
    DealsActionsMixin,
    DealsFiltersMixin,
    DealsClipboardMixin,
    DealsIOMixin
 ):
    """Вкладка "Сделки" — полная версия"""

    COLUMN_KEYS = DealsTableModel.COLUMN_KEYS
    HEADERS = DealsTableModel.HEADERS
    CHECKBOX_COLUMNS = DealsTableModel.CHECKBOX_COLUMNS

    def __init__(self, db_manager, parent=None):
        super().__init__(parent)
        self.db_manager = db_manager
        self.logger = logging.getLogger('CoinCollector.GUI.DealsTab')
        self.logger.info("=" * 60)
        self.logger.info("ИНИЦИАЛИЗАЦИЯ DealsTab")
        self.logger.info("=" * 60)

        self._all_deals = []
        self._filtered_deals = []
        self._column_filters = {}
        self._disabled_filters = {}
        self._frozen_deals = []
        self._dirty_ids = set()
        self._copied_row_data = None
        self._copied_cells_data = None
        self._last_changes = []
        self._redo_stack = []
        self._loading_data = False
        self._save_timer = QTimer()
        self._save_timer.setSingleShot(True)
        self._save_timer.timeout.connect(self._flush_changes)
        self._import_thread = None

        self.init_ui()
        # === АВТООБРЕЗКА СКАНОВ: перехват всех scan* методов ===
        try:
            self._hook_scan_methods_autocrop()
        except Exception as e:
            self.logger.debug(f"Автообрезка не подключена: {e}")
        QTimer.singleShot(100, self.load_data)

    def init_ui(self):
        """Инициализация интерфейса"""
        self.logger.debug("init_ui: создание интерфейса")

        layout = QVBoxLayout()
        layout.setContentsMargins(5, 5, 5, 5)
        layout.setSpacing(5)
        self.setLayout(layout)

        toolbar = self._create_toolbar()
        layout.addWidget(toolbar)

        self._create_filters(layout)

        self.filter_label = QLabel("")
        self.filter_label.setStyleSheet("color: #dc3545; font-size: 9px; padding: 0px 2px;")
        self.filter_label.setVisible(False)
        self.filter_label.setCursor(Qt.PointingHandCursor)
        self.filter_label.mousePressEvent = lambda e: self._clear_all_filters()
        layout.addWidget(self.filter_label)

        self.model = DealsTableModel(self)
        self.model.set_parent_tab(self)
        self.model.data_changed.connect(self._on_model_data_changed)



        self.proxy_model = DealsSortProxyModel(self)
        self.proxy_model.setSourceModel(self.model)
        self.proxy_model.setSortRole(Qt.UserRole)

        self.table = QTableView()
        self.table.setModel(self.proxy_model)
        self.table.setAlternatingRowColors(True)
        self.table.setSelectionBehavior(QAbstractItemView.SelectItems)
        self.table.setSelectionMode(QAbstractItemView.ExtendedSelection)

        # ВАЖНО: редактирование ТОЛЬКО по двойному клику или F2
        self.table.setEditTriggers(
            QAbstractItemView.DoubleClicked |
            QAbstractItemView.EditKeyPressed
        )

        self.table.setSortingEnabled(True)
        self.table.horizontalHeader().setSortIndicatorShown(True)

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

        self.delegate = DealsDelegate(self)
        self.delegate.set_parent_tab(self)
        self.table.setItemDelegate(self.delegate)

        default_widths = [30, 80, 80, 60, 80, 50, 50, 50, 50, 50, 50, 50, 50, 50, 50, 60, 80, 80]
        for i, width in enumerate(default_widths):
            if i < len(self.HEADERS):
                self.table.setColumnWidth(i, width)
                header.setSectionResizeMode(i, QHeaderView.Interactive)

        layout.addWidget(self.table)
        self._create_status_bar(layout)
        self._load_column_filters_from_json()
        self._restore_column_state()

        self.logger.info("DealsTab UI инициализирован")

    def _create_toolbar(self):
        """Создаёт панель инструментов"""
        self.logger.debug("_create_toolbar: создание панели инструментов")
        toolbar = QFrame()
        toolbar.setFixedHeight(45)
        toolbar.setStyleSheet("background-color: #f5f5f5; border-bottom: 1px solid #ddd;")
        layout = QHBoxLayout()
        layout.setContentsMargins(5, 1, 5, 1)
        layout.setSpacing(6)
        toolbar.setLayout(layout)
        add_btn = QPushButton("➕ Сделка")
        add_btn.clicked.connect(self._add_deal)
        add_btn.setMinimumHeight(30)
        layout.addWidget(add_btn)
        del_btn = QPushButton("🗑️ Удалить")
        del_btn.clicked.connect(self._delete_selected)
        del_btn.setMinimumHeight(30)
        del_btn.setStyleSheet("background-color: #dc3545; color: white; font-weight: bold; border-radius: 3px;")
        layout.addWidget(del_btn)
        sep = QFrame()
        sep.setFrameShape(QFrame.VLine)
        sep.setFrameShadow(QFrame.Sunken)
        sep.setFixedSize(2, 28)
        layout.addWidget(sep)
        import_btn = QPushButton("📥 Импорт")
        import_btn.clicked.connect(self._import_from_excel)
        import_btn.setMinimumHeight(30)
        import_btn.setStyleSheet("background-color: #e67e22; color: white; font-weight: bold; border-radius: 3px;")
        layout.addWidget(import_btn)
        clear_btn = QPushButton("🗑️ Очистить всё")
        clear_btn.clicked.connect(self._clear_all)
        clear_btn.setMinimumHeight(30)
        clear_btn.setStyleSheet("background-color: #dc3545; color: white; font-weight: bold; border-radius: 3px;")
        layout.addWidget(clear_btn)
        layout.addStretch()
        self.count_label = QLabel("Сделок: 0")
        layout.addWidget(self.count_label)
        nav_widget = self._create_navigation_panel()
        layout.addWidget(nav_widget)
        refresh_btn = QPushButton("🔄 Обновить")
        refresh_btn.clicked.connect(self._force_reload)
        refresh_btn.setMinimumHeight(30)
        refresh_btn.setStyleSheet("background-color: #6c757d; color: white; font-weight: bold; border-radius: 3px;")
        layout.addWidget(refresh_btn)
        # === КНОПКА СКАНА ЛИСТА СДЕЛКИ — ОБЯЗАТЕЛЬНО addWidget, иначе не видна ===
        self.scan_sheet_btn = QPushButton("📷 Скан листа сделки")
        self.scan_sheet_btn.setToolTip(
            "Сканировать полный лист A4 по выделенной сделке → "
            "data/temp/obmen_image/№ПОК_НИК_1.jpg")
        self.scan_sheet_btn.setMinimumHeight(30)
        self.scan_sheet_btn.setStyleSheet(
            "background-color: #4a6fa5; color: white; font-weight: bold; border-radius: 3px;")
        self.scan_sheet_btn.clicked.connect(self._scan_deal_sheet)
        layout.addWidget(self.scan_sheet_btn)
        return toolbar

    def _create_navigation_panel(self):
        """Создаёт панель навигации"""
        nav_widget = QWidget()
        nav_layout = QHBoxLayout()
        nav_layout.setContentsMargins(0, 0, 0, 0)
        nav_layout.setSpacing(2)
        nav_widget.setLayout(nav_layout)

        self.top_btn = QPushButton("▲")
        self.top_btn.setFixedSize(28, 28)
        self.top_btn.setToolTip("Перейти к первой строке")
        self.top_btn.setStyleSheet("""
            QPushButton {
                background-color: #4a6fa5;
                color: white;
                font-weight: bold;
                border-radius: 3px;
                font-size: 14px;
            }
            QPushButton:hover {
                background-color: #5a7fb5;
            }
        """)
        self.top_btn.clicked.connect(self._scroll_to_top)
        nav_layout.addWidget(self.top_btn)

        self.bottom_btn = QPushButton("▼")
        self.bottom_btn.setFixedSize(28, 28)
        self.bottom_btn.setToolTip("Перейти к последней строке")
        self.bottom_btn.setStyleSheet("""
            QPushButton {
                background-color: #4a6fa5;
                color: white;
                font-weight: bold;
                border-radius: 3px;
                font-size: 14px;
            }
            QPushButton:hover {
                background-color: #5a7fb5;
            }
        """)
        self.bottom_btn.clicked.connect(self._scroll_to_bottom)
        nav_layout.addWidget(self.bottom_btn)

        self.count_label = QLabel("Сделок: 0")
        self.count_label.setStyleSheet("color: #666; font-size: 11px;")
        nav_layout.addWidget(self.count_label)

        return nav_widget

    def _create_filters(self, parent_layout):
        """Создаёт фильтры"""
        filter_layout = QHBoxLayout()
        filter_layout.setContentsMargins(5, 2, 5, 2)
        filter_layout.setSpacing(5)

        filter_layout.addWidget(QLabel("Фильтр по нику:"))
        self.nick_filter_combo = QComboBox()
        self.nick_filter_combo.setEditable(False)
        self.nick_filter_combo.setMinimumWidth(150)
        self.nick_filter_combo.addItem("— Все ники —", None)
        self.nick_filter_combo.currentIndexChanged.connect(self._on_nick_filter_changed)
        filter_layout.addWidget(self.nick_filter_combo)

        filter_layout.addStretch()
        parent_layout.insertLayout(parent_layout.count() - 1, filter_layout)

    def _create_status_bar(self, parent_layout):
        """Создаёт статус-бар"""
        self.status_label = QLabel("Готово")
        self.status_label.setStyleSheet("color: #666; font-size: 11px;")
        parent_layout.addWidget(self.status_label)

    # ========== ЗАГРУЗКА ДАННЫХ ==========

    def load_data(self):
        """Загружает данные из БД"""
        self.logger.info("load_data: начало загрузки")
        try:
            # Откатываем сессию для свежих данных
            try:
                self.db_manager.session.rollback()
            except:
                pass

            # Загружаем сделки
            try:
                self._all_deals = self.db_manager.session.query(Deal).all()
            except OverflowError as e:
                self.logger.warning(f"OverflowError при загрузке: {e}, загружаем с ограничением")
                self._all_deals = self.db_manager.session.query(Deal).limit(10000).all()

            self.logger.info(f"Загружено сделок из БД: {len(self._all_deals)}")

            # Сохраняем замороженные данные для фильтрации
            self._frozen_deals = []
            for deal in self._all_deals:
                try:
                    frozen = {'id': deal.id}
                    for key in self.COLUMN_KEYS:
                        if key != 'id':
                            try:
                                value = getattr(deal, key, None)
                                if key in ['number', 'amount', 'total'] and isinstance(value, (int, float)):
                                    if abs(value) > 1e15:
                                        value = str(value)
                                frozen[key] = value
                            except (OverflowError, ValueError, TypeError) as e:
                                self.logger.debug(f"Ошибка получения {key} для сделки {deal.id}: {e}")
                                frozen[key] = None
                    self._frozen_deals.append(frozen)
                except Exception as e:
                    self.logger.warning(f"Ошибка при обработке сделки {deal.id}: {e}")
                    continue

            # Очищаем сессию, чтобы избежать проблем с отсоединёнными объектами
            try:
                self.db_manager.session.expunge_all()
            except:
                pass

            # === ГЛАВНОЕ ИСПРАВЛЕНИЕ: ОБНОВЛЯЕМ МОДЕЛЬ ===
            self._apply_filters()
            self.load_nicknames_combo()
            self.update_statistics()
            self.count_label.setText(f"Сделок: {len(self._filtered_deals)}")

            # Принудительно обновляем таблицу
            self.model.set_data(self._filtered_deals)
            self.table.viewport().update()

            self.status_label.setText(f"✅ Загружено сделок: {len(self._all_deals)}")
            self.status_label.setStyleSheet("color: #28a745; font-size: 11px;")
            QTimer.singleShot(3000, lambda: self.status_label.setStyleSheet("color: #666; font-size: 11px;"))

            self.logger.info("load_data: загрузка завершена")

        except Exception as e:
            self.logger.error(f"Ошибка загрузки сделок: {e}")
            import traceback
            traceback.print_exc()
            self.status_label.setText("❌ Ошибка загрузки")
            self.status_label.setStyleSheet("color: #dc3545; font-size: 11px;")
            # Создаём пустую модель, чтобы не было ошибок
            self._filtered_deals = []
            self.model.set_data([])

    def _refresh_all(self):
        """Обновляет все данные"""
        self.logger.debug("_refresh_all: обновление всех данных")
        self._apply_filters_to_frozen()
        self.load_nicknames_combo()
        self.update_statistics()
        self.count_label.setText(f"Сделок: {len(self._filtered_deals)}")
        self.status_label.setText(f"✅ Загружено сделок: {len(self._all_deals)}")
        self.status_label.setStyleSheet("color: #28a745; font-size: 11px;")
        self.table.viewport().update()

    def _apply_filters_to_frozen(self):
        """Применяет фильтры к frozen данным"""
        self.logger.debug("_apply_filters_to_frozen: применение фильтров")

        if not self._frozen_deals:
            self.model.set_data([])
            self.count_label.setText("Сделок: 0")
            self.update_statistics()
            return

        filtered = list(self._frozen_deals)

        if hasattr(self, '_current_nick_filter') and self._current_nick_filter:
            filtered = [d for d in filtered if str(d.get('buyer', '')) == str(self._current_nick_filter)]

        if self._column_filters:
            filtered = self._apply_column_filters_to_frozen_list(filtered)

        temp_deals = []
        for frozen in filtered:
            try:
                deal = Deal()
                for key, value in frozen.items():
                    if key != 'id':
                        try:
                            if key in ['number', 'amount', 'total'] and isinstance(value, (int, float)):
                                if abs(value) > 1e15:
                                    value = str(value)
                            setattr(deal, key, value)
                        except (OverflowError, ValueError, TypeError) as e:
                            self.logger.debug(f"Ошибка установки {key}: {e}")
                            setattr(deal, key, None)
                deal.id = frozen.get('id')
                temp_deals.append(deal)
            except Exception as e:
                self.logger.warning(f"Ошибка при создании сделки из frozen: {e}")
                continue

        self._filtered_deals = temp_deals

        try:
            self.model.set_data(temp_deals)
        except OverflowError as e:
            self.logger.warning(f"OverflowError при установке данных: {e}")
            self.table.setSortingEnabled(False)
            self.model.set_data(temp_deals)
            self.table.setSortingEnabled(True)

        sort_column = self.table.horizontalHeader().sortIndicatorSection()
        sort_order = self.table.horizontalHeader().sortIndicatorOrder()
        if sort_column >= 0:
            try:
                self.table.sortByColumn(sort_column, sort_order)
            except OverflowError as e:
                self.logger.warning(f"OverflowError при сортировке: {e}")
                self.table.setSortingEnabled(False)

        self.count_label.setText(f"Сделок: {len(filtered)}")
        self.update_statistics()
        self.logger.debug(f"_apply_filters_to_frozen: отфильтровано {len(filtered)} записей")

    def _apply_column_filters_to_frozen_list(self, deals):
        """Применяет фильтры по колонкам к frozen списку"""
        filtered = []
        for deal in deals:
            match = True
            for col, filter_vals in self._column_filters.items():
                if col < len(self.COLUMN_KEYS):
                    key = self.COLUMN_KEYS[col]
                    if key == 'id':
                        continue
                    try:
                        value = deal.get(key, '')
                        if isinstance(value, (int, float)):
                            if abs(value) > 1e15:
                                actual_val = str(value)
                            else:
                                actual_val = str(value)
                        else:
                            actual_val = str(value or '')
                    except (OverflowError, ValueError, TypeError):
                        actual_val = ""

                    if isinstance(filter_vals, set):
                        if not actual_val.strip():
                            if "__EMPTY__" not in filter_vals:
                                match = False
                                break
                        elif actual_val not in filter_vals:
                            match = False
                            break
            if match:
                filtered.append(deal)
        return filtered

    def _on_deal_edited(self, deal, column_key, new_value):
        """Обработчик редактирования ячейки"""
        if not deal or not deal.id:
            return

        self.logger.info(f"Deal {deal.id}: {column_key} = '{new_value}'")

        try:
            # Проверяем, существует ли ещё сделка в БД
            db_deal = self.db_manager.session.query(Deal).get(deal.id)
            if not db_deal:
                self.logger.warning(f"Сделка {deal.id} уже удалена, пропускаем сохранение")
                return

            # Сохраняем в БД
            setattr(db_deal, column_key, new_value)
            db_deal.updated_at = datetime.now()
            self.db_manager.session.commit()

            # Обновляем данные в модели (в _filtered_deals)
            for d in self._filtered_deals:
                if d.id == deal.id:
                    setattr(d, column_key, new_value)
                    break

            # Обновляем отображение ячейки без полной перезагрузки таблицы
            col_index = self.COLUMN_KEYS.index(column_key) if column_key in self.COLUMN_KEYS else -1
            if col_index >= 0:
                # Находим строку в модели
                for row, d in enumerate(self._filtered_deals):
                    if d.id == deal.id:
                        model_index = self.model.index(row, col_index)
                        self.model.dataChanged.emit(model_index, model_index, [Qt.DisplayRole, Qt.ForegroundRole])
                        break

            self.status_label.setText("✅ Сохранено")
            self.status_label.setStyleSheet("color: #28a745; font-size: 11px;")
            QTimer.singleShot(2000, lambda: self.status_label.setStyleSheet("color: #666; font-size: 11px;"))

            self._dirty_ids.clear()

        except Exception as e:
            self.db_manager.session.rollback()
            self.logger.error(f"Ошибка сохранения: {e}")
            self.status_label.setText(f"❌ Ошибка: {str(e)[:30]}")
            self.status_label.setStyleSheet("color: #dc3545; font-size: 11px;")

    def _on_model_data_changed(self):
        """Обработчик изменения данных в модели"""
        self.logger.debug("_on_model_data_changed: данные модели изменились")
        self.status_label.setText("📝 Изменено")
        self.status_label.setStyleSheet("color: #ffc107; font-size: 11px;")
        QTimer.singleShot(2000, lambda: self.status_label.setStyleSheet("color: #666; font-size: 11px;"))

    def _flush_changes(self):
        """Сохраняет изменения в БД"""
        if not self._dirty_ids:
            return

        try:
            for deal_id in self._dirty_ids:
                db_deal = self.db_manager.session.query(Deal).get(deal_id)
                if db_deal:
                    # Обновляем из кэша
                    for deal in self._filtered_deals:
                        if deal.id == deal_id:
                            for key in self.COLUMN_KEYS:
                                if key != 'id':
                                    setattr(db_deal, key, getattr(deal, key, None))
                            break

            self.db_manager.session.commit()
            self._dirty_ids.clear()
            self.status_label.setText("💾 Изменения сохранены")
            self.status_label.setStyleSheet("color: #28a745; font-size: 11px;")
            QTimer.singleShot(2000, lambda: self.status_label.setStyleSheet("color: #666; font-size: 11px;"))
        except Exception as e:
            self.db_manager.session.rollback()
            self.logger.error(f"Ошибка сохранения: {e}")
            self.status_label.setText(f"❌ Ошибка: {str(e)[:30]}")
            self.status_label.setStyleSheet("color: #dc3545; font-size: 11px;")

    # ========== КОНТЕКСТНЫЕ МЕНЮ ==========

    def _show_cell_context_menu(self, position):
        """Показывает контекстное меню для ячейки"""
        self.logger.debug(f"_show_cell_context_menu: позиция {position}")

        try:
            index = self.table.indexAt(position)
            if not index.isValid():
                self.logger.debug("  Индекс невалидный")
                return

            source_index = self.proxy_model.mapToSource(index)
            row = source_index.row()
            col = index.column()

            if row < 0 or row >= len(self._filtered_deals):
                self.logger.debug(f"  Строка {row} вне диапазона")
                return

            value = self.model.data(source_index, Qt.DisplayRole)
            col_name = self.HEADERS[col] if col < len(self.HEADERS) else ""

            self.logger.debug(f"  Показано меню для строки {row}, колонки {col} (\"{col_name}\")")

            menu = QMenu(self)

            # Заголовок
            title = QAction(f"📌 Колонка: {col_name}", menu)
            title.setEnabled(False)
            menu.addAction(title)
            menu.addSeparator()

            # === ФИЛЬТРАЦИЯ ===
            if value and value != "":
                try:
                    filter_action = QAction(f"🔍 Показать только «{value}»", menu)
                    filter_action.triggered.connect(lambda: self._filter_by_value(col, value))
                    menu.addAction(filter_action)

                    exclude_action = QAction(f"🚫 Скрыть «{value}»", menu)
                    exclude_action.triggered.connect(lambda: self._filter_exclude_value(col, value))
                    menu.addAction(exclude_action)

                    menu.addSeparator()
                except Exception as e:
                    self.logger.error(f"Ошибка добавления фильтров: {e}")

            # === КОПИРОВАТЬ/ВСТАВИТЬ ===
            try:
                copy_action = QAction("📋 Копировать ячейку", menu)
                copy_action.setShortcut(QKeySequence.Copy)
                copy_action.triggered.connect(self._copy_selected_cells)
                menu.addAction(copy_action)

                paste_action = QAction("📌 Вставить", menu)
                paste_action.setShortcut(QKeySequence.Paste)
                paste_action.triggered.connect(self._paste_to_selected_cells)
                menu.addAction(paste_action)

                menu.addSeparator()
            except Exception as e:
                self.logger.error(f"Ошибка добавления копирования/вставки: {e}")

            # === ДЕЙСТВИЯ ДЛЯ КОЛОНКИ №ПОК (колонка 15) ===
            if col == 15:
                try:
                    goto_action = QAction(f"🔗 Перейти к закупке №{value}", menu)
                    goto_action.triggered.connect(self._goto_purchase_by_number)
                    menu.addAction(goto_action)

                    archive_action = QAction(f"📦 Перенести в архив закупки №{value}", menu)
                    archive_action.triggered.connect(lambda: self._archive_purchases_by_number(value))
                    menu.addAction(archive_action)

                    close_action = QAction("💰 Закрыть сделку", menu)
                    close_action.triggered.connect(self._close_deal)
                    menu.addAction(close_action)

                    menu.addSeparator()
                except Exception as e:
                    self.logger.error(f"Ошибка добавления действий для №ПОК: {e}")

            # === МАССОВАЯ АРХИВАЦИЯ ===
            try:
                selected_rows = set()
                for idx in self.table.selectionModel().selectedRows():
                    selected_rows.add(idx.row())
                if not selected_rows:
                    for idx in self.table.selectionModel().selectedIndexes():
                        selected_rows.add(idx.row())

                selected_count = len(selected_rows)

                if selected_count > 1:
                    archive_multi_action = QAction(f"📦 Архивировать закупки для {selected_count} выделенных сделок", self)
                    archive_multi_action.triggered.connect(self._archive_multiple_deals)
                    menu.addAction(archive_multi_action)
            except Exception as e:
                self.logger.error(f"Ошибка добавления массовой архивации: {e}")

            # === РАЗМНОЖЕНИЕ МОНЕТ ===
            try:
                remove_duplicates_action = QAction("🔄 Удалить дубли (размножить монеты)", self)
                remove_duplicates_action.triggered.connect(self._remove_duplicates)
                menu.addAction(remove_duplicates_action)
            except Exception as e:
                self.logger.error(f"Ошибка добавления размножения: {e}")

            menu.addSeparator()

            # === ОТМЕНА ===
            try:
                undo_action = QAction("↩ Отменить", menu)
                undo_action.setShortcut(QKeySequence.Undo)
                undo_action.triggered.connect(self._undo_last_change)
                menu.addAction(undo_action)
            except Exception as e:
                self.logger.error(f"Ошибка добавления отмены: {e}")

            menu.exec(self.table.viewport().mapToGlobal(position))
            self.logger.debug("  Меню закрыто")

        except Exception as e:
            self.logger.error(f"Критическая ошибка в контекстном меню: {e}")
            import traceback
            traceback.print_exc()

    def _show_row_context_menu(self, position):
        """Показывает контекстное меню для строки"""
        self.logger.debug(f"_show_row_context_menu: позиция {position}")

        row = self.table.verticalHeader().logicalIndexAt(position)
        if row < 0 or row >= self.proxy_model.rowCount():
            self.logger.debug("  Строка вне диапазона")
            return

        selected_rows = set()
        for idx in self.table.selectionModel().selectedRows():
            selected_rows.add(idx.row())

        if not selected_rows:
            selected_rows.add(row)

        count = len(selected_rows)
        self.logger.debug(f"  Выделено {count} строк")

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
        self.logger.debug("  Меню строк закрыто")

    # ========== НАВИГАЦИЯ ==========

    def _scroll_to_top(self):
        """Прокручивает к первой строке"""
        self.logger.debug("_scroll_to_top: прокрутка к началу")
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
        self.logger.debug("_scroll_to_bottom: прокрутка к концу")
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

    def _save_column_state(self):
        """Сохраняет состояние колонок (только ПОСЛЕ восстановления)"""
        # Защита: не пишем дефолтные ширины во время инициализации
        if not getattr(self, '_cs_ready', False):
            return
        try:
            from database.config_db import get_config_db
            config_db = get_config_db()
            header = self.table.horizontalHeader()
            order = [header.logicalIndex(vp) for vp in range(header.count())]
            widths = []
            for li in range(len(self.COLUMN_KEYS)):
                vi = header.visualIndex(li)
                w = self.table.columnWidth(vi)
                widths.append(int(w) if w > 0 else 0)
            config_db.set('deals_tab_column_settings', {'order': order, 'widths': widths}, 'columns')
        except Exception as e:
            self.logger.debug(f"Ошибка сохранения состояния колонок: {e}")

    def _restore_column_state(self):
        """Восстанавливает состояние колонок и разрешает дальнейшее сохранение"""
        try:
            from database.config_db import get_config_db
            config_db = get_config_db()
            settings = config_db.get('deals_tab_column_settings')
            if settings:
                header = self.table.horizontalHeader()
                saved_order = settings.get('order')
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
                saved_widths = settings.get('widths')
                if saved_widths and isinstance(saved_widths, list):
                    for li, w in enumerate(saved_widths):
                        try:
                            width = int(w) if w is not None else 0
                            if li < len(self.HEADERS) and width > 0:
                                vi = header.visualIndex(li)
                                self.table.setColumnWidth(vi, width)
                        except (ValueError, TypeError):
                            continue
        except Exception as e:
            self.logger.debug(f"Ошибка восстановления состояния колонок: {e}")
        # Гарантируем подключение сигналов (без дублей)
        try:
            header = self.table.horizontalHeader()
            try:
                header.sectionResized.disconnect(self._on_column_resized)
            except Exception:
                pass
            header.sectionResized.connect(self._on_column_resized)
            try:
                header.sectionMoved.disconnect(self._on_column_moved)
            except Exception:
                pass
            header.sectionMoved.connect(self._on_column_moved)
        except Exception:
            pass
        # Разрешаем сохранение ТОЛЬКО после восстановления
        self._cs_ready = True

    def _on_column_moved(self, logical_index, old_visual_index, new_visual_index):
        """Обработчик перемещения колонки"""
        self.logger.debug(f"_on_column_moved: {logical_index} -> {new_visual_index}")
        self._save_column_state()

    def _on_column_resized(self, logical_index, old_size, new_size):
        """Обработчик изменения размера колонки"""
        try:
            if old_size == new_size:
                return
            self.logger.debug(f"_on_column_resized: {logical_index} {old_size}->{new_size}")
            self._save_column_state()
        except Exception as e:
            self.logger.debug(f"Ошибка при изменении размера колонки: {e}")

    # ========== ВСПОМОГАТЕЛЬНЫЕ МЕТОДЫ ==========

    def _get_deal_value(self, deal, col):
        """Возвращает значение для колонки"""
        if col < len(self.COLUMN_KEYS):
            key = self.COLUMN_KEYS[col]
            if key == 'id':
                return str(deal.id) if deal.id else ""
            try:
                value = getattr(deal, key, None)
                if value is None:
                    return ""
                if key in ['reserve', 'collect', 'scan', 'send', 'approve', 'payment', 'check', 'pack', 'post', 'arrived']:
                    return "✅" if value in [True, "True", "true", "1", "✅"] else "❌"
                if key in ['number', 'amount', 'total', 'id']:
                    try:
                        if isinstance(value, (int, float)):
                            if abs(value) > 1e15:
                                return str(value)
                            return value
                        return str(value)
                    except (OverflowError, ValueError, TypeError):
                        return str(value)
                return str(value)
            except (OverflowError, ValueError, TypeError, AttributeError):
                return ""
        return ""

    def _get_source_row(self, proxy_row):
        """Возвращает индекс в source модели"""
        model = self.table.model()
        if hasattr(model, 'mapToSource'):
            proxy_index = model.index(proxy_row, 0)
            source_index = model.mapToSource(proxy_index)
            return source_index.row()
        return proxy_row

    # ========== СТАТИСТИКА ==========

    def update_statistics(self):
        """Обновляет статистику"""
        if not hasattr(self, '_filtered_deals'):
            return

        total_sum = 0.0
        order_count = 0

        for deal in self._filtered_deals:
            amount_str = getattr(deal, 'amount', '')
            if amount_str:
                try:
                    num_match = re.search(r'[\d]+(?:[.,]\d+)?', str(amount_str))
                    if num_match:
                        amount = float(num_match.group().replace(',', '.'))
                        total_sum += amount
                        order_count += 1
                except (ValueError, TypeError):
                    pass

        if total_sum >= 15000:
            discount_percent = 10
        elif total_sum >= 8000:
            discount_percent = 7
        elif total_sum >= 5000:
            discount_percent = 5
        elif total_sum >= 2000:
            discount_percent = 3
        else:
            discount_percent = 0

        discount_amount = total_sum * discount_percent / 100

        if hasattr(self, 'stats_orders_label'):
            self.stats_orders_label.setText(f"📦 Заказов: {order_count}")
            self.stats_sum_label.setText(f"💰 Сумма: {total_sum:,.0f} ₽")
            self.stats_discount_label.setText(f"🏷️ Скидка: {discount_percent}% ({discount_amount:,.0f} ₽)")

    # ========== НИКНЕЙМЫ ==========

    def load_nicknames_combo(self):
        """Загружает ники в комбобокс"""
        self.logger.debug("load_nicknames_combo: загрузка ников")
        if not hasattr(self, 'nick_filter_combo'):
            return

        current_nick = self.nick_filter_combo.currentData()

        self.nick_filter_combo.blockSignals(True)
        self.nick_filter_combo.clear()
        self.nick_filter_combo.addItem("— Все ники —", None)

        unique_nicks = set()
        for deal in self._all_deals:
            buyer = getattr(deal, 'buyer', '')
            if buyer and str(buyer).strip():
                unique_nicks.add(str(buyer).strip())

        for nick in sorted(unique_nicks):
            self.nick_filter_combo.addItem(nick, nick)

        if current_nick:
            idx = self.nick_filter_combo.findData(current_nick)
            if idx >= 0:
                self.nick_filter_combo.setCurrentIndex(idx)

        self.nick_filter_combo.blockSignals(False)

    def _on_nick_filter_changed(self):
        """Обработчик изменения фильтра по нику"""
        self.logger.debug("_on_nick_filter_changed: фильтр по нику изменён")
        if not hasattr(self, 'nick_filter_combo'):
            return

        nick_data = self.nick_filter_combo.currentData()
        self._current_nick_filter = nick_data if nick_data is not None else None
        self._apply_filters_to_frozen()
        self.update_statistics()

    def _refresh_model_data(self):
        """Обновляет данные в модели без полной перезагрузки"""
        if hasattr(self, 'model') and self.model:
            self.model.layoutAboutToBeChanged.emit()
            self.model._data = self._filtered_deals
            self.model.layoutChanged.emit()
            self.table.viewport().update()

    # ========== ЗАКРЫТИЕ ==========

    def closeEvent(self, event):
        """Обработчик закрытия"""
        self.logger.info("closeEvent: закрытие вкладки")
        self._save_column_state()
        self._save_column_filters_to_json()
        super().closeEvent(event)
        
    def _get_selected_deal(self):
        """Возвращает объект выделенной сделки (устойчиво к прокси-модели
        и разным именам атрибутов таблицы/списков)."""
        table = getattr(self, 'table', None) or getattr(self, 'deals_table', None)
        if table is None:
            return None
        idx = table.currentIndex()
        if idx is None or not idx.isValid():
            return None
        row = idx.row()
        model = table.model()
        try:
            if model is not None and hasattr(model, 'mapToSource'):
                row = model.mapToSource(idx).row()
                model = model.sourceModel()
        except Exception:
            pass
        for container in (getattr(model, '_data', None),
                          getattr(model, '_deals', None),
                          getattr(self, '_filtered_deals', None),
                          getattr(self, '_deals', None),
                          getattr(self, '_all_deals', None)):
            if container and 0 <= row < len(container):
                return container[row]
        return None

    def _scan_deal_sheet(self):
        """Открывает диалог сканирования полного листа A4 по выделенной сделке.
        Файлы сохраняются как data/temp/obmen_image/№ПОК_НИК_1.jpg, _2.jpg, …"""
        deal = self._get_selected_deal()
        if deal is None:
            QMessageBox.warning(self, 'Предупреждение',
                                'Выделите строку сделки.')
            return
        from gui.widgets.deals_tab.deal_sheet_scanner import DealSheetScanDialog
        dlg = DealSheetScanDialog(deal, self)
        dlg.exec()
        
    def _autocrop_scanned_sheet(self, path):
        """Автообрезка белых полей скана листа сделки:
        остаётся заполненная область + 5 мм отступа по краям
        (отступ и включение настраиваются в ConfigDB,
        ключ 'scan_autocrop_settings')."""
        try:
            from utils.image_autocrop import autocrop_file, get_autocrop_settings
            st = get_autocrop_settings()
            if not st['enabled']:
                return False
            done = autocrop_file(path, margin_mm=st['margin_mm'],
                                 threshold=st['threshold'])
            if done:
                self.logger.info(
                    f"✂️ Скан листа обрезан по контенту "
                    f"+{st['margin_mm']:.0f} мм: {path}")
            return done
        except Exception as e:
            self.logger.debug(f"Автообрезка скана не выполнена: {e}")
            return False

    def _autocrop_watch_dirs(self):
        """Папки, в которых отслеживаем появление новых сканов."""
        dirs = []
        try:
            from utils.paths import paths_instance as paths
            for d in (paths.get_data_dir(),
                      paths.get_data_dir() / 'scans',
                      paths.get_root_dir() / 'scans',
                      paths.get_data_dir() / 'coin_images',
                      paths.get_data_dir() / 'deal_scans'):
                dirs.append(Path(d))
        except Exception:
            pass
        try:
            from PySide6.QtCore import QDir
            dirs.append(Path(QDir.tempPath()))
        except Exception:
            pass
        return [d for d in dirs if d is not None and Path(d).exists()]

    def _snapshot_scans(self):
        """Снимок {путь: mtime} по всем изображениям в отслеживаемых папках
        (без рекурсии — быстро даже при тысячах файлов)."""
        snap = {}
        for d in self._autocrop_watch_dirs():
            try:
                for p in Path(d).glob('*'):
                    if p.is_file() and p.suffix.lower() in (
                            '.jpg', '.jpeg', '.png', '.bmp', '.tif', '.tiff'):
                        snap[str(p)] = p.stat().st_mtime
            except Exception:
                pass
        return snap


    def _show_autocrop_settings_dialog(self):
        """Диалог настроек автообрезки: вкл/выкл, отступ мм, порог белизны."""
        from PySide6.QtWidgets import (QDialog, QFormLayout, QCheckBox,
                                       QDoubleSpinBox, QSpinBox,
                                       QDialogButtonBox)
        from utils.image_autocrop import get_autocrop_settings, set_autocrop_settings
        st = get_autocrop_settings()
        dlg = QDialog(self)
        dlg.setWindowTitle("✂️ Автообрезка сканов")
        form = QFormLayout(dlg)
        enabled_chk = QCheckBox("Обрезать белые поля автоматически")
        enabled_chk.setChecked(st['enabled'])
        form.addRow(enabled_chk)
        margin_spin = QDoubleSpinBox()
        margin_spin.setRange(0, 50)
        margin_spin.setDecimals(1)
        margin_spin.setSuffix(" мм")
        margin_spin.setValue(st['margin_mm'])
        margin_spin.setToolTip("Отступ вокруг заполненной области")
        form.addRow("Отступ вокруг контента:", margin_spin)
        thr_spin = QSpinBox()
        thr_spin.setRange(150, 255)
        thr_spin.setValue(st['threshold'])
        thr_spin.setToolTip("Пиксель ярче порога = пустой фон "
                            "(меньше значение — строже)")
        form.addRow("Порог белизны фона:", thr_spin)
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(dlg.accept)
        buttons.rejected.connect(dlg.reject)
        form.addRow(buttons)
        if dlg.exec() == QDialog.Accepted:
            set_autocrop_settings(enabled=enabled_chk.isChecked(),
                                  margin_mm=margin_spin.value(),
                                  threshold=thr_spin.value())
            self.logger.info("✅ Настройки автообрезки сохранены")