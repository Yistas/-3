# ===== gui/widgets/exchange_tab/sales_tab.py =====
# ПОЛНОСТЬЮ ЗАМЕНИТЬ ФАЙЛ

# -*- coding: utf-8 -*-

"""
Вкладка "Общие продажи" для учёта продаж монет
С полной поддержкой редактирования, фильтрации, сортировки,
цветовой заливки ячеек и сводной статистикой в шапке
"""

import logging
import re
import json
from datetime import datetime
from pathlib import Path

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTableView, QHeaderView, QAbstractItemView,
    QPushButton, QLabel, QMessageBox, QMenu, QApplication, QComboBox,
    QFrame, QProgressBar, QInputDialog, QLineEdit, QDialog, QScrollArea, QCheckBox,
    QColorDialog, QGridLayout, QSizePolicy, QStyledItemDelegate
)
from PySide6.QtCore import Qt, QSettings, QTimer, QPoint, QModelIndex, Signal, QAbstractTableModel, QSortFilterProxyModel
from PySide6.QtGui import QAction, QKeySequence, QColor, QBrush

from sqlalchemy.orm import joinedload
from database.models import Sale


class SalesDelegate(QStyledItemDelegate):
    """Делегат для редактирования ячеек таблицы продаж"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self._parent_tab = None
    
    def set_parent_tab(self, tab):
        self._parent_tab = tab
    
    def createEditor(self, parent, option, index):
        editor = QLineEdit(parent)
        text = index.data(Qt.DisplayRole) or ""
        editor.setText(text)
        editor.selectAll()
        editor.setFocus()
        return editor
    
    def setEditorData(self, editor, index):
        text = index.data(Qt.DisplayRole) or ""
        editor.setText(text)
    
    def setModelData(self, editor, model, index):
        new_value = editor.text().strip()
        old_value = index.data(Qt.DisplayRole) or ""
        
        if new_value != old_value and self._parent_tab:
            row = index.row()
            col = index.column()
            source_row = self._parent_tab._get_source_row(row)
            
            if source_row < len(self._parent_tab._filtered_sales):
                sale = self._parent_tab._filtered_sales[source_row]
                if sale:
                    column_key = self._parent_tab.model.COLUMN_KEYS[col] if col < len(self._parent_tab.model.COLUMN_KEYS) else None
                    if column_key and column_key != 'id':
                        self._parent_tab._on_cell_edited(sale, column_key, new_value)
        
        super().setModelData(editor, model, index)


class SalesTableModel(QAbstractTableModel):
    """Модель данных для таблицы продаж"""
    
    data_changed = Signal()
    
    HEADERS = [
        "ID", "ГОД", "Сумма+", "ЛОМ+", "AG+", 
        "Бонусы+", "Бонусы-", "Почта+", "Почта-",
        "Закупки", "Закупка AG", "ТРАТЫ",
        "Итог", "Тип", "№№Сделки", "Примечание", "Баланс"
    ]
    
    COLUMN_KEYS = [
        'id', 'year', 'total_sum', 'lom_plus', 'ag_plus',
        'bonus_plus', 'bonus_minus', 'post_plus', 'post_minus',
        'purchases', 'purchase_ag', 'costs',
        'total', 'sale_type', 'deal_number', 'notes', 'balance'
    ]
    
    def __init__(self, parent=None, db_manager=None):
        super().__init__(parent)
        self._data = []
        self.db_manager = db_manager
        
    def set_data(self, data):
        self.beginResetModel()
        self._data = data
        self.endResetModel()
    
    def get_sale(self, row):
        if 0 <= row < len(self._data):
            return self._data[row]
        return None
    
    def rowCount(self, parent=QModelIndex()):
        return len(self._data)
    
    def columnCount(self, parent=QModelIndex()):
        return len(self.HEADERS)
    
    def headerData(self, section, orientation, role=Qt.DisplayRole):
        if orientation == Qt.Horizontal and role == Qt.DisplayRole:
            if 0 <= section < len(self.HEADERS):
                return self.HEADERS[section]
        return super().headerData(section, orientation, role)
    
    def flags(self, index):
        if not index.isValid():
            return Qt.NoItemFlags
        
        if index.column() == 0:
            return Qt.ItemIsEnabled | Qt.ItemIsSelectable
        
        return Qt.ItemIsEditable | Qt.ItemIsEnabled | Qt.ItemIsSelectable
    
    def data(self, index, role=Qt.DisplayRole):
        if not index.isValid():
            return None
        row = index.row()
        col = index.column()
        if row < 0 or row >= len(self._data):
            return None
        
        sale = self._data[row]
        key = self.COLUMN_KEYS[col] if col < len(self.COLUMN_KEYS) else ""

        # --- ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ДЛЯ БЕЗОПАСНОГО ПОЛУЧЕНИЯ ЗНАЧЕНИЙ ---
        def safe_float(value, default=0):
            if value is None:
                return default
            try:
                return float(value)
            except (ValueError, TypeError):
                return default

        def safe_str(value, default=""):
            if value is None:
                return default
            return str(value)

        def safe_get_attr(obj, attr, default=None):
            """Безопасно получает атрибут, обрабатывая DetachedInstanceError"""
            try:
                return getattr(obj, attr, default)
            except Exception as e:
                # Если объект отсоединен или произошла другая ошибка — возвращаем default
                if 'DetachedInstanceError' in str(type(e)):
                    return default
                raise

        if role == Qt.DisplayRole:
            try:
                if key == 'id':
                    return safe_str(safe_get_attr(sale, 'id', None))
                elif key == 'year':
                    return safe_str(safe_get_attr(sale, 'year', None))
                elif key == 'total_sum':
                    lom = safe_float(safe_get_attr(sale, 'lom_plus', None))
                    ag = safe_float(safe_get_attr(sale, 'ag_plus', None))
                    total_sum = lom + ag
                    return f"{total_sum:.2f}" if total_sum != 0 else ""
                elif key == 'lom_plus':
                    value = safe_float(safe_get_attr(sale, 'lom_plus', None))
                    return f"{value:.2f}" if value != 0 else ""
                elif key == 'ag_plus':
                    value = safe_float(safe_get_attr(sale, 'ag_plus', None))
                    return f"{value:.2f}" if value != 0 else ""
                elif key == 'bonus_plus':
                    value = safe_float(safe_get_attr(sale, 'bonus_plus', None))
                    return f"{value:.2f}" if value != 0 else ""
                elif key == 'bonus_minus':
                    value = safe_float(safe_get_attr(sale, 'bonus_minus', None))
                    return f"{value:.2f}" if value != 0 else ""
                elif key == 'post_plus':
                    value = safe_float(safe_get_attr(sale, 'post_plus', None))
                    return f"{value:.2f}" if value != 0 else ""
                elif key == 'post_minus':
                    value = safe_float(safe_get_attr(sale, 'post_minus', None))
                    return f"{value:.2f}" if value != 0 else ""
                elif key == 'purchases':
                    value = safe_float(safe_get_attr(sale, 'purchases', None))
                    return f"{value:.2f}" if value != 0 else ""
                elif key == 'purchase_ag':
                    value = safe_float(safe_get_attr(sale, 'purchase_ag', None))
                    return f"{value:.2f}" if value != 0 else ""
                elif key == 'costs':
                    value = safe_float(safe_get_attr(sale, 'costs', None))
                    return f"{value:.2f}" if value != 0 else ""
                elif key == 'total':
                    lom = safe_float(safe_get_attr(sale, 'lom_plus', None))
                    ag = safe_float(safe_get_attr(sale, 'ag_plus', None))
                    bonus_plus = safe_float(safe_get_attr(sale, 'bonus_plus', None))
                    bonus_minus = safe_float(safe_get_attr(sale, 'bonus_minus', None))
                    post_plus = safe_float(safe_get_attr(sale, 'post_plus', None))
                    post_minus = safe_float(safe_get_attr(sale, 'post_minus', None))
                    purchases = safe_float(safe_get_attr(sale, 'purchases', None))
                    purchase_ag = safe_float(safe_get_attr(sale, 'purchase_ag', None))
                    costs = safe_float(safe_get_attr(sale, 'costs', None))
                    total = lom + ag + bonus_plus + bonus_minus + post_plus + post_minus + purchases + purchase_ag + costs
                    return f"{total:,.2f}" if total != 0 else ""
                elif key == 'sale_type':
                    return safe_str(safe_get_attr(sale, 'sale_type', "Продажа"))
                elif key == 'deal_number':
                    return safe_str(safe_get_attr(sale, 'deal_number', None))
                elif key == 'notes':
                    return safe_str(safe_get_attr(sale, 'notes', None))
                elif key == 'balance':
                    value = safe_float(safe_get_attr(sale, 'balance', None))
                    return f"{value:.2f}" if value != 0 else ""
                return ""
            except Exception as e:
                # Если произошла любая ошибка — возвращаем пустую строку
                self.logger.debug(f"Ошибка в data() для {key}: {e}")
                return ""

        elif role == Qt.TextAlignmentRole:
            if col == 0:
                return Qt.AlignCenter
            elif col in [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 16]:
                return Qt.AlignRight | Qt.AlignVCenter
            return Qt.AlignLeft | Qt.AlignVCenter

        elif role == Qt.UserRole:
            try:
                value = self.data(index, Qt.DisplayRole)
                if value:
                    import re
                    cleaned = re.sub(r'[^\d.-]', '', str(value))
                    if cleaned:
                        return float(cleaned)
            except:
                pass
            return None

        elif role == Qt.ForegroundRole:
            if col == 12:
                try:
                    lom = safe_float(safe_get_attr(sale, 'lom_plus', None))
                    ag = safe_float(safe_get_attr(sale, 'ag_plus', None))
                    bonus_plus = safe_float(safe_get_attr(sale, 'bonus_plus', None))
                    bonus_minus = safe_float(safe_get_attr(sale, 'bonus_minus', None))
                    post_plus = safe_float(safe_get_attr(sale, 'post_plus', None))
                    post_minus = safe_float(safe_get_attr(sale, 'post_minus', None))
                    purchases = safe_float(safe_get_attr(sale, 'purchases', None))
                    purchase_ag = safe_float(safe_get_attr(sale, 'purchase_ag', None))
                    costs = safe_float(safe_get_attr(sale, 'costs', None))
                    total = lom + ag + bonus_plus + bonus_minus + post_plus + post_minus + purchases + purchase_ag + costs
                    if total < 0:
                        from PySide6.QtGui import QColor
                        return QColor("#dc3545")
                    elif total > 0:
                        from PySide6.QtGui import QColor
                        return QColor("#28a745")
                except:
                    pass
            return None

        elif role == Qt.BackgroundRole:
            try:
                return sale.get_cell_color(col)
            except:
                pass
            return None

        return None

    def setData(self, index, value, role=Qt.EditRole):
        if not index.isValid():
            return False
        
        row = index.row()
        col = index.column()
        
        if row < 0 or row >= len(self._data):
            return False
        
        sale = self._data[row]
        key = self.COLUMN_KEYS[col] if col < len(self.COLUMN_KEYS) else ""
        
        if key == 'id':
            return False
        
        if key == 'year':
            try:
                sale.year = int(value) if value else None
            except:
                return False
        elif key == 'sale_type':
            sale.sale_type = value if value else "Продажа"
        elif key == 'deal_number':
            try:
                sale.deal_number = int(float(value)) if value else None
            except:
                return False
        elif key == 'notes':
            sale.notes = value if value else None
        elif key in ['lom_plus', 'ag_plus', 'bonus_plus', 'bonus_minus',
                     'post_plus', 'post_minus', 'purchases', 'purchase_ag', 'costs']:
            try:
                setattr(sale, key, float(value.replace(',', '.')) if value else 0)
            except:
                return False
        else:
            return False
        
        sale.calculate_total()
        sale.updated_at = datetime.now()
        
        self.dataChanged.emit(index, index, [Qt.DisplayRole, Qt.ForegroundRole])
        self.data_changed.emit()
        
        return True


class SortFilterProxyModel(QSortFilterProxyModel):
    """Прокси-модель для сортировки"""
    
    def lessThan(self, left, right):
        left_data = left.data(Qt.UserRole)
        right_data = right.data(Qt.UserRole)
        try:
            left_num = float(left_data)
            right_num = float(right_data)
            return left_num < right_num
        except (ValueError, TypeError):
            pass
        return str(left_data).lower() < str(right_data).lower()


class SalesTab(QWidget):
    """Вкладка "Общие продажи" с полным функционалом"""
    
    COLUMN_SETTINGS_FILE = Path("data/sales_tab_column_settings.json")
    
    def __init__(self, db_manager, parent=None):
        super().__init__(parent)
        self.db_manager = db_manager
        self.logger = logging.getLogger('CoinCollector.GUI.SalesTab')
        self.settings = QSettings('CoinCollector', 'SalesTab')
        
        self._all_sales = []
        self._filtered_sales = []
        self._dirty_ids = set()
        self._column_filters = {}
        self._disabled_filters = {}
        self._copied_cells_data = None
        self._copied_row_data = None
        self._last_changes = []
        
        self._save_timer = QTimer()
        self._save_timer.setSingleShot(True)
        self._save_timer.timeout.connect(self._flush_changes)
        
        self.init_ui()
        self._restore_column_state()
        self._load_column_filters_from_json()
        
        QTimer.singleShot(100, self.load_data)
        
        self.setFocusPolicy(Qt.StrongFocus)
        
    def init_ui(self):
        layout = QVBoxLayout()
        layout.setContentsMargins(5, 5, 5, 5)
        layout.setSpacing(5)
        self.setLayout(layout)
        
        self.stats_frame = self._create_stats_frame()
        layout.addWidget(self.stats_frame)
        
        toolbar = self._create_toolbar()
        layout.addWidget(toolbar)
        
        self.filter_label = QLabel("")
        self.filter_label.setStyleSheet("color: #dc3545; font-size: 9px; padding: 0px 2px;")
        self.filter_label.setVisible(False)
        self.filter_label.setCursor(Qt.PointingHandCursor)
        self.filter_label.mousePressEvent = lambda e: self._clear_all_filters()
        layout.addWidget(self.filter_label)
        
        self.model = SalesTableModel(self, self.db_manager)
        self.model.data_changed.connect(self._on_data_changed)
        
        self.proxy_model = SortFilterProxyModel(self)
        self.proxy_model.setSourceModel(self.model)
        self.proxy_model.setSortRole(Qt.UserRole)
        
        self.sales_table = QTableView()
        self.sales_table.setModel(self.proxy_model)
        self.sales_table.setAlternatingRowColors(True)
        self.sales_table.setSelectionBehavior(QAbstractItemView.SelectItems)
        self.sales_table.setSelectionMode(QAbstractItemView.ExtendedSelection)
        
        self.sales_table.setEditTriggers(
            QAbstractItemView.CurrentChanged |
            QAbstractItemView.EditKeyPressed
        )
        
        self.sales_table.setSortingEnabled(True)
        self.sales_table.horizontalHeader().setSortIndicatorShown(True)
        
        self.sales_table.clicked.connect(self._on_table_clicked)
        
        self.sales_delegate = SalesDelegate(self)
        self.sales_delegate.set_parent_tab(self)
        self.sales_table.setItemDelegate(self.sales_delegate)
        
        header = self.sales_table.horizontalHeader()
        header.setSectionsMovable(True)
        header.setContextMenuPolicy(Qt.CustomContextMenu)
        header.customContextMenuRequested.connect(self._show_header_filter_menu)
        header.sectionMoved.connect(self._on_column_moved)
        header.sectionResized.connect(self._on_column_resized)
        
        v_header = self.sales_table.verticalHeader()
        v_header.setContextMenuPolicy(Qt.CustomContextMenu)
        v_header.customContextMenuRequested.connect(self._show_row_context_menu)
        
        self.sales_table.setContextMenuPolicy(Qt.CustomContextMenu)
        self.sales_table.customContextMenuRequested.connect(self._show_cell_context_menu)
        
        default_widths = [40, 60, 80, 70, 70, 70, 70, 70, 70, 80, 80, 80, 100, 80, 70, 150, 100]
        for i, width in enumerate(default_widths):
            if i < len(self.model.HEADERS):
                self.sales_table.setColumnWidth(i, width)
                header.setSectionResizeMode(i, QHeaderView.Interactive)
        
        self.sales_table.sortByColumn(0, Qt.DescendingOrder)
        
        layout.addWidget(self.sales_table)
        
        self.status_bar = self._create_status_bar()
        layout.addWidget(self.status_bar)
    
    def _create_stats_frame(self):
        frame = QFrame()
        frame.setFrameShape(QFrame.StyledPanel)
        frame.setStyleSheet("""
            QFrame {
                background-color: #f8f9fa;
                border: 1px solid #dee2e6;
                border-radius: 5px;
                padding: 5px;
                margin-bottom: 5px;
            }
        """)
        
        layout = QGridLayout()
        layout.setSpacing(3)
        layout.setContentsMargins(8, 5, 8, 5)
        frame.setLayout(layout)
        
        self.balance_label = QLabel("Баланс: 0.00 ₽")
        self.balance_label.setStyleSheet("""
            font-weight: bold;
            font-size: 28px;
            color: #4a6fa5;
        """)
        layout.addWidget(self.balance_label, 0, 0, 2, 1)
        
        self.purchase_ag_label = QLabel("Закупка AG: 0.00 ₽")
        self.purchase_ag_label.setStyleSheet("color: #6c757d; font-size: 12px;")
        layout.addWidget(self.purchase_ag_label, 0, 1)
        
        self.sales_ag_label = QLabel("Продажа AG: 0.00 ₽")
        self.sales_ag_label.setStyleSheet("color: #28a745; font-size: 12px;")
        layout.addWidget(self.sales_ag_label, 0, 2)
        
        self.percent_ag_label = QLabel("AG %: 0%")
        self.percent_ag_label.setStyleSheet("font-weight: bold; color: #17a2b8; font-size: 12px;")
        layout.addWidget(self.percent_ag_label, 0, 3)
        
        self.purchases_label = QLabel("Закупки: 0.00 ₽")
        self.purchases_label.setStyleSheet("color: #6c757d; font-size: 12px;")
        layout.addWidget(self.purchases_label, 1, 1)
        
        self.sales_lom_label = QLabel("Продажа ЛОМ: 0.00 ₽")
        self.sales_lom_label.setStyleSheet("color: #28a745; font-size: 12px;")
        layout.addWidget(self.sales_lom_label, 1, 2)
        
        self.percent_lom_label = QLabel("ЛОМ %: 0%")
        self.percent_lom_label.setStyleSheet("font-weight: bold; color: #17a2b8; font-size: 12px;")
        layout.addWidget(self.percent_lom_label, 1, 3)
        
        layout.setColumnStretch(0, 1)
        layout.setColumnStretch(1, 1)
        layout.setColumnStretch(2, 1)
        layout.setColumnStretch(3, 1)
        
        return frame
    
    def _create_toolbar(self):
        toolbar = QFrame()
        toolbar.setFixedHeight(40)
        toolbar.setStyleSheet("""
            QFrame {
                background-color: #f5f5f5;
                border: 1px solid #ddd;
                border-radius: 3px;
            }
        """)
        
        layout = QHBoxLayout()
        layout.setContentsMargins(5, 2, 5, 2)
        layout.setSpacing(8)
        toolbar.setLayout(layout)
        
        add_btn = QPushButton("➕ Добавить")
        add_btn.clicked.connect(self._add_sale)
        add_btn.setFixedHeight(32)
        add_btn.setMinimumWidth(90)
        layout.addWidget(add_btn)
        
        del_btn = QPushButton("🗑️ Удалить")
        del_btn.clicked.connect(self._delete_selected)
        del_btn.setFixedHeight(32)
        del_btn.setMinimumWidth(90)
        del_btn.setStyleSheet("background-color: #dc3545; color: white; font-weight: bold; border-radius: 3px;")
        layout.addWidget(del_btn)
        
        separator = QFrame()
        separator.setFrameShape(QFrame.VLine)
        separator.setFrameShadow(QFrame.Sunken)
        separator.setFixedSize(2, 28)
        layout.addWidget(separator)
        
        self.top_btn = QPushButton("▲")
        self.top_btn.setFixedSize(32, 32)
        self.top_btn.setToolTip("Перейти к первой строке")
        self.top_btn.clicked.connect(self._scroll_to_top)
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
        layout.addWidget(self.top_btn)
        
        self.bottom_btn = QPushButton("▼")
        self.bottom_btn.setFixedSize(32, 32)
        self.bottom_btn.setToolTip("Перейти к последней строке")
        self.bottom_btn.clicked.connect(self._scroll_to_bottom)
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
        layout.addWidget(self.bottom_btn)
        
        self.purchase_count_label = QLabel("Записей: 0")
        self.purchase_count_label.setStyleSheet("color: #666; font-size: 11px; padding: 0 10px;")
        layout.addWidget(self.purchase_count_label)
        
        layout.addStretch()
        
        clear_btn = QPushButton("🗑️ Очистить всё")
        clear_btn.clicked.connect(self._clear_all)
        clear_btn.setFixedHeight(32)
        clear_btn.setMinimumWidth(100)
        clear_btn.setStyleSheet("background-color: #dc3545; color: white; font-weight: bold; border-radius: 3px;")
        layout.addWidget(clear_btn)
        
        refresh_btn = QPushButton("🔄 Обновить")
        refresh_btn.clicked.connect(self.load_data)
        refresh_btn.setFixedHeight(32)
        refresh_btn.setMinimumWidth(90)
        refresh_btn.setStyleSheet("background-color: #6c757d; color: white; font-weight: bold; border-radius: 3px;")
        layout.addWidget(refresh_btn)
        
        return toolbar

    def _create_status_bar(self):
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
        
        self.count_label = QLabel("Записей: 0")
        self.count_label.setStyleSheet("color: #666; font-size: 11px;")
        layout.addWidget(self.count_label)
        
        status_bar.setLayout(layout)
        return status_bar
    
# ===== ФАЙЛ: gui/widgets/exchange_tab/sales_tab.py =====
# ЗАМЕНИТЬ МЕТОД load_data

    def load_data(self):
        try:
            # Отключаем авто-коммит для предотвращения проблем с сессией
            self.db_manager.session.autocommit = False
            
            # Загружаем данные с принудительным присоединением к сессии
            sales = self.db_manager.session.query(Sale).order_by(Sale.id.desc()).all()
            
            # Обновляем _all_sales
            self._all_sales = sales
            self.logger.info(f"Загружено продаж: {len(self._all_sales)}")
            
            # Применяем фильтры
            self._apply_filters()
            
            # Обновляем статистику
            self.update_statistics()
            
            # Обновляем статус
            self.status_label.setText(f"✅ Загружено: {len(self._all_sales)}")
            self.status_label.setStyleSheet("color: #28a745;")
            
            # Обновляем отображение
            self.sales_table.viewport().update()
            self.sales_table.updateGeometry()
            
            # Возвращаем авто-коммит
            self.db_manager.session.autocommit = True
            
            QTimer.singleShot(2000, lambda: self.status_label.setStyleSheet("color: #666;"))
            
        except Exception as e:
            self.db_manager.session.rollback()
            self.logger.error(f"Ошибка загрузки продаж: {e}")
            import traceback
            traceback.print_exc()
            self.status_label.setText("❌ Ошибка загрузки")
            self.status_label.setStyleSheet("color: #dc3545;")

    def _apply_filters(self):
        if not self._all_sales:
            self.model.set_data([])
            if hasattr(self, 'purchase_count_label'):
                self.purchase_count_label.setText("Записей: 0")
            return
        
        filtered = list(self._all_sales)
        
        if self._column_filters:
            filtered = self._apply_column_filters_to_list(filtered)
        
        self._filtered_sales = filtered
        self.model.set_data(filtered)
        
        if hasattr(self, 'purchase_count_label'):
            self.purchase_count_label.setText(f"Записей: {len(filtered)}")
    
    def _apply_column_filters_to_list(self, sales):
        filtered = []
        for sale in sales:
            match = True
            for col, filter_vals in self._column_filters.items():
                if col < len(self.model.COLUMN_KEYS):
                    key = self.model.COLUMN_KEYS[col]
                    actual_val = str(getattr(sale, key, '') or '')
                    if isinstance(filter_vals, set):
                        if not actual_val.strip():
                            if "__EMPTY__" not in filter_vals:
                                match = False
                                break
                        elif actual_val not in filter_vals:
                            match = False
                            break
            if match:
                filtered.append(sale)
        return filtered
    
    def update_statistics(self):
        total_purchase_ag = 0
        total_purchases = 0
        total_ag_plus = 0
        total_lom_plus = 0
        
        last_sale = self.db_manager.session.query(Sale).order_by(Sale.id.desc()).first()
        if last_sale and last_sale.balance is not None:
            total_balance = last_sale.balance
        else:
            total_balance = 0
        
        for sale in self._filtered_sales:
            total_purchase_ag += abs(sale.purchase_ag or 0)
            total_purchases += abs(sale.purchases or 0)
            total_ag_plus += sale.ag_plus or 0
            total_lom_plus += sale.lom_plus or 0
        
        if total_balance >= 0:
            bal_text = f"Баланс: +{total_balance:,.2f} ₽".replace(',', ' ')
            bal_color = "#28a745"
        else:
            bal_text = f"Баланс: {total_balance:,.2f} ₽".replace(',', ' ')
            bal_color = "#dc3545"
        
        self.balance_label.setText(bal_text)
        self.balance_label.setStyleSheet(f"font-weight: bold; font-size: 18px; color: {bal_color};")
        
        self.purchase_ag_label.setText(f"Закупка AG: {total_purchase_ag:,.2f} ₽".replace(',', ' '))
        self.purchases_label.setText(f"Закупки: {total_purchases:,.2f} ₽".replace(',', ' '))
        self.sales_ag_label.setText(f"Продажа AG: {total_ag_plus:,.2f} ₽".replace(',', ' '))
        self.sales_lom_label.setText(f"Продажа ЛОМ: {total_lom_plus:,.2f} ₽".replace(',', ' '))
        
        if total_purchase_ag > 0:
            ag_percent = (total_ag_plus / total_purchase_ag) * 100
        elif total_ag_plus > 0:
            ag_percent = 100
        else:
            ag_percent = 0
        
        if total_purchases > 0:
            lom_percent = (total_lom_plus / total_purchases) * 100
        elif total_lom_plus > 0:
            lom_percent = 100
        else:
            lom_percent = 0
        
        percent_ag_color = "#28a745" if ag_percent > 0 else "#666"
        percent_lom_color = "#28a745" if lom_percent > 0 else "#666"
        
        self.percent_ag_label.setText(f"AG %: {ag_percent:.1f}%")
        self.percent_ag_label.setStyleSheet(f"font-weight: bold; color: {percent_ag_color}; font-size: 12px;")
        
        self.percent_lom_label.setText(f"ЛОМ %: {lom_percent:.1f}%")
        self.percent_lom_label.setStyleSheet(f"font-weight: bold; color: {percent_lom_color}; font-size: 12px;")
    
    def _scroll_to_top(self):
        if not hasattr(self, 'sales_table') or self.sales_table is None:
            return
        
        model = self.sales_table.model()
        if not model or model.rowCount() == 0:
            return
        
        first_index = model.index(0, 0)
        if first_index.isValid():
            self.sales_table.scrollTo(first_index, QAbstractItemView.PositionAtTop)
            self.sales_table.setCurrentIndex(first_index)
            self.sales_table.selectRow(first_index.row())
    
    def _scroll_to_bottom(self):
        if not hasattr(self, 'sales_table') or self.sales_table is None:
            return
        
        model = self.sales_table.model()
        if not model or model.rowCount() == 0:
            return
        
        last_row = model.rowCount() - 1
        last_index = model.index(last_row, 0)
        if last_index.isValid():
            self.sales_table.scrollTo(last_index, QAbstractItemView.PositionAtBottom)
            self.sales_table.setCurrentIndex(last_index)
            self.sales_table.selectRow(last_index.row())
    
    def _flush_changes(self):
        if not self._dirty_ids:
            return
        
        try:
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
    
    def _on_data_changed(self):
        self.update_statistics()
        
        for sale in self._filtered_sales:
            if hasattr(sale, 'id') and sale.id:
                self._dirty_ids.add(sale.id)
        
        self._save_timer.start(2000)
        
        self.status_label.setText("📝 Есть несохранённые изменения...")
        self.status_label.setStyleSheet("color: #ffc107; font-size: 11px;")

    def _add_sale(self):
        try:
            new_sale = Sale()
            new_sale.year = datetime.now().year
            new_sale.sale_type = "Продажа"
            self.db_manager.session.add(new_sale)
            self.db_manager.session.commit()
            
            self._recalculate_balance()
            
            self._all_sales = self.db_manager.session.query(Sale).order_by(Sale.id.desc()).all()
            self._apply_filters()
            
            self.sales_table.scrollToTop()
            
            self.status_label.setText(f"✅ Добавлена запись (ID: {new_sale.id})")
            self.status_label.setStyleSheet("color: #28a745;")
            QTimer.singleShot(2000, lambda: self.status_label.setStyleSheet("color: #666;"))
            
        except Exception as e:
            self.db_manager.session.rollback()
            self.logger.error(f"Ошибка добавления: {e}")
            self.status_label.setText(f"❌ Ошибка: {str(e)[:30]}")
            self.status_label.setStyleSheet("color: #dc3545;")
    
    def _recalculate_balance(self):
        try:
            sales = self.db_manager.session.query(Sale).order_by(Sale.id).all()
            balance = 0
            for sale in sales:
                sale.calculate_total()
                balance += sale.total
                sale.balance = balance
            self.db_manager.session.commit()
            self.logger.info("✅ Баланс пересчитан")
            
            self._all_sales = self.db_manager.session.query(Sale).order_by(Sale.id.desc()).all()
            self._apply_filters()
            self.update_statistics()
            self.sales_table.viewport().update()
            
        except Exception as e:
            self.logger.error(f"Ошибка пересчёта баланса: {e}")
            self.db_manager.session.rollback()

    def _on_cell_edited(self, sale, column_key, new_value):
        if column_key == 'year':
            try:
                sale.year = int(new_value) if new_value else None
            except:
                return
        elif column_key == 'sale_type':
            sale.sale_type = new_value if new_value else "Продажа"
        elif column_key == 'deal_number':
            try:
                sale.deal_number = int(float(new_value)) if new_value else None
            except:
                return
        elif column_key == 'notes':
            sale.notes = new_value if new_value else None
        elif column_key in ['lom_plus', 'ag_plus', 'bonus_plus', 'bonus_minus',
                             'post_plus', 'post_minus', 'purchases', 'purchase_ag', 'costs']:
            try:
                setattr(sale, column_key, float(new_value.replace(',', '.')) if new_value else 0)
            except:
                return
        else:
            return
        
        sale.calculate_total()
        sale.updated_at = datetime.now()
        self._dirty_ids.add(sale.id)
        self._save_timer.start(2000)
        self.status_label.setText("📝 Есть несохранённые изменения...")
        
        self._recalculate_balance()
        self.update_statistics()
    
    def _get_selected_rows(self):
        selected_rows = set()
        for idx in self.sales_table.selectionModel().selectedRows():
            selected_rows.add(idx.row())
        
        if not selected_rows:
            for idx in self.sales_table.selectionModel().selectedIndexes():
                selected_rows.add(idx.row())
        
        return sorted(selected_rows, reverse=True)
    
    def _get_source_row(self, proxy_row):
        model = self.sales_table.model()
        proxy_index = model.index(proxy_row, 0)
        if hasattr(model, 'mapToSource'):
            source_index = model.mapToSource(proxy_index)
            return source_index.row()
        return proxy_row
    
    def _delete_selected(self):
        selected_rows = self._get_selected_rows()
        if not selected_rows:
            QMessageBox.warning(self, "Предупреждение", "Выделите строки для удаления")
            return
        
        source_rows = []
        for row in selected_rows:
            source_rows.append(self._get_source_row(row))
        
        source_rows = sorted(set(source_rows), reverse=True)
        count = len(source_rows)
        
        reply = QMessageBox.question(
            self, "Подтверждение",
            f"Удалить {count} строк(и)?\n\nЭто действие нельзя отменить!",
            QMessageBox.Yes | QMessageBox.No
        )
        
        if reply != QMessageBox.Yes:
            return
        
        try:
            for row in source_rows:
                if row < len(self._filtered_sales):
                    sale = self._filtered_sales[row]
                    if sale and sale.id:
                        db_sale = self.db_manager.session.query(Sale).get(sale.id)
                        if db_sale:
                            self.db_manager.session.delete(db_sale)
            
            self.db_manager.session.commit()
            
            for row in sorted(source_rows, reverse=True):
                if row < len(self._filtered_sales):
                    sale = self._filtered_sales.pop(row)
                    if sale in self._all_sales:
                        self._all_sales.remove(sale)
            
            self._recalculate_balance()
            
            self.model.set_data(self._filtered_sales)
            self.update_statistics()
            
            self.status_label.setText(f"🗑️ Удалено {count} строк")
            self.status_label.setStyleSheet("color: #dc3545;")
            QTimer.singleShot(2000, lambda: self.status_label.setStyleSheet("color: #666;"))
            
        except Exception as e:
            self.db_manager.session.rollback()
            self.logger.error(f"Ошибка удаления: {e}")
            self.status_label.setText(f"❌ Ошибка: {str(e)[:30]}")
            self.status_label.setStyleSheet("color: #dc3545;")
    
    def _clear_all(self):
        reply = QMessageBox.question(
            self, "Подтверждение",
            "Удалить ВСЕ записи из таблицы продаж?\n\nЭто действие нельзя отменить!",
            QMessageBox.Yes | QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            try:
                self.db_manager.session.query(Sale).delete()
                self.db_manager.session.commit()
                self._all_sales.clear()
                self._filtered_sales.clear()
                self.model.set_data([])
                self.update_statistics()
                
                self.balance_label.setText("Баланс: 0.00 ₽")
                
                self.status_label.setText("🗑️ Все записи удалены")
                self.status_label.setStyleSheet("color: #dc3545;")
                QTimer.singleShot(2000, lambda: self.status_label.setStyleSheet("color: #666;"))
            except Exception as e:
                self.db_manager.session.rollback()
                self.logger.error(f"Ошибка очистки: {e}")
                self.status_label.setText(f"❌ Ошибка: {str(e)[:30]}")
    
    def _copy_selected_cells(self):
        selected_indexes = self.sales_table.selectionModel().selectedIndexes()
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
        clipboard = QApplication.clipboard()
        text = clipboard.text()
        if not text:
            return
        
        rows_data = [line.split("\t") for line in text.strip().split("\n")]
        if not rows_data:
            return
        
        selected_indexes = self.sales_table.selectionModel().selectedIndexes()
        if not selected_indexes:
            current = self.sales_table.currentIndex()
            if current.isValid():
                selected_indexes = [current]
        
        if not selected_indexes:
            return
        
        selected_indexes.sort(key=lambda x: (x.row(), x.column()))
        
        source_rows = len(rows_data)
        source_cols = len(rows_data[0]) if source_rows > 0 else 0
        
        if source_rows == 0 or source_cols == 0:
            return
        
        self.sales_table.setUpdatesEnabled(False)
        self.model.blockSignals(True)
        
        try:
            for i, target_idx in enumerate(selected_indexes):
                source_row = i % source_rows
                source_col = (i // source_rows) % source_cols
                value = rows_data[source_row][source_col] if source_col < len(rows_data[source_row]) else ""
                
                row = target_idx.row()
                col = target_idx.column()
                source_row_idx = self._get_source_row(row)
                
                if source_row_idx < len(self._filtered_sales):
                    sale = self._filtered_sales[source_row_idx]
                    if sale:
                        field_name = self.model.COLUMN_KEYS[col] if col < len(self.model.COLUMN_KEYS) else None
                        if field_name and field_name != 'id':
                            self._on_cell_edited(sale, field_name, value)
            
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
            self.status_label.setStyleSheet("color: #dc3545;")
        finally:
            self.model.blockSignals(False)
            self.sales_table.setUpdatesEnabled(True)
    
    def _undo_last_change(self):
        if not self._last_changes:
            self.status_label.setText("ℹ️ Нет действий для отмены")
            return
        
        try:
            changes = self._last_changes.pop()
            for change in changes:
                sale = self.db_manager.session.query(Sale).get(change['sale_id'])
                if sale:
                    setattr(sale, change['field'], change['old_value'])
            
            self.db_manager.session.commit()
            self.load_data()
            
            self.status_label.setText("↩️ Изменение отменено")
            self.status_label.setStyleSheet("color: #28a745;")
            QTimer.singleShot(2000, lambda: self.status_label.setStyleSheet("color: #666;"))
            
        except Exception as e:
            self.logger.error(f"Ошибка отмены: {e}")
            self.status_label.setText(f"❌ Ошибка: {str(e)[:30]}")
    
    def _save_column_state(self):
        header = self.sales_table.horizontalHeader()
        order = [header.logicalIndex(vp) for vp in range(header.count())]
        self.settings.setValue('sales_column_order', order)
        
        widths = []
        for li in range(len(self.model.HEADERS)):
            vi = header.visualIndex(li)
            w = self.sales_table.columnWidth(vi)
            widths.append(w)
        self.settings.setValue('sales_column_widths', widths)
    
    def _restore_column_state(self):
        header = self.sales_table.horizontalHeader()
        
        saved_order = self.settings.value('sales_column_order')
        if saved_order and isinstance(saved_order, list):
            for vi, li in enumerate(saved_order):
                li = int(li)
                if li < len(self.model.HEADERS):
                    cv = header.visualIndex(li)
                    if cv != vi:
                        header.moveSection(cv, vi)
        
        saved_widths = self.settings.value('sales_column_widths')
        if saved_widths and isinstance(saved_widths, list):
            for li, w in enumerate(saved_widths):
                if li < len(self.model.HEADERS) and isinstance(w, (int, float)) and w > 0:
                    vi = header.visualIndex(li)
                    self.sales_table.setColumnWidth(vi, int(w))
    
    def _on_column_moved(self, logical_index, old_visual_index, new_visual_index):
        self._save_column_state()
    
    def _on_column_resized(self, logical_index, old_size, new_size):
        self._save_column_state()
    
    def _set_cell_color(self):
        selected_indexes = self.sales_table.selectionModel().selectedIndexes()
        if not selected_indexes:
            QMessageBox.warning(self, "Предупреждение", "Выделите ячейки для заливки")
            return
        
        color = QColorDialog.getColor(QColor("#ffffff"), self, "Выберите цвет")
        if not color.isValid():
            return
        
        for idx in selected_indexes:
            row = idx.row()
            col = idx.column()
            source_row = self._get_source_row(row)
            
            if source_row < len(self._filtered_sales):
                sale = self._filtered_sales[source_row]
                if sale:
                    sale.set_cell_color(col, color.name())
                    self._dirty_ids.add(sale.id)
                    
                    model_index = self.model.index(source_row, col)
                    self.model.dataChanged.emit(model_index, model_index, [Qt.BackgroundRole])
        
        self._save_timer.start(2000)
        self.status_label.setText(f"🎨 Цвет установлен для {len(selected_indexes)} ячеек")
        self.status_label.setStyleSheet("color: #28a745;")
        QTimer.singleShot(2000, lambda: self.status_label.setStyleSheet("color: #666;"))
    
    def _clear_cell_color(self):
        selected_indexes = self.sales_table.selectionModel().selectedIndexes()
        if not selected_indexes:
            QMessageBox.warning(self, "Предупреждение", "Выделите ячейки для очистки")
            return
        
        for idx in selected_indexes:
            row = idx.row()
            col = idx.column()
            source_row = self._get_source_row(row)
            
            if source_row < len(self._filtered_sales):
                sale = self._filtered_sales[source_row]
                if sale:
                    sale.set_cell_color(col, None)
                    self._dirty_ids.add(sale.id)
                    
                    model_index = self.model.index(source_row, col)
                    self.model.dataChanged.emit(model_index, model_index, [Qt.BackgroundRole])
        
        self._save_timer.start(2000)
        self.status_label.setText(f"🧹 Цвет очищен для {len(selected_indexes)} ячеек")
        self.status_label.setStyleSheet("color: #28a745;")
        QTimer.singleShot(2000, lambda: self.status_label.setStyleSheet("color: #666;"))

# ===== В МЕТОДЕ _save_column_filters_to_json =====
    def _save_column_filters_to_json(self):
        """Сохраняет фильтры колонок в ConfigDB"""
        try:
            from database.config_db import get_config_db
            config_db = get_config_db()
            filters_to_save = {}
            for k, v in self._column_filters.items():
                if isinstance(v, set):
                    filters_to_save[str(k)] = list(v)
                else:
                    filters_to_save[str(k)] = v
            config_db.set('sales_tab_filters', filters_to_save, 'filters')
        except Exception as e:
            self.logger.error(f"Ошибка сохранения фильтров: {e}")

# ===== В МЕТОДЕ _load_column_filters_from_json =====
    def _load_column_filters_from_json(self):
        """Загружает фильтры колонок из ConfigDB"""
        try:
            from database.config_db import get_config_db
            config_db = get_config_db()
            saved = config_db.get('sales_tab_filters')
            if saved:
                for k, v in saved.items():
                    self._column_filters[int(k)] = set(v) if isinstance(v, list) else v
                self._update_filter_label()
        except Exception as e:
            self.logger.error(f"Ошибка загрузки фильтров: {e}")

    def _update_filter_label(self):
        if not self._column_filters:
            self.filter_label.setVisible(False)
            return
        self.filter_label.setVisible(True)
        parts = []
        for col, val in sorted(self._column_filters.items()):
            col_name = self.model.HEADERS[col] if col < len(self.model.HEADERS) else str(col)
            if isinstance(val, set):
                parts.append(f"{col_name}: {len(val)} знач.")
        self.filter_label.setText("🔍 Фильтры: " + " | ".join(parts) + "  [нажмите для сброса]")
    
    def _clear_all_filters(self):
        self._column_filters.clear()
        self.filter_label.setVisible(False)
        self._save_column_filters_to_json()
        self._apply_filters()
    
    def _show_cell_context_menu(self, position):
        index = self.sales_table.indexAt(position)
        if not index.isValid():
            return
        
        source_index = self.proxy_model.mapToSource(index)
        row = source_index.row()
        col = index.column()
        
        if row < 0 or row >= len(self._filtered_sales):
            return
        
        value = self.model.data(source_index, Qt.DisplayRole)
        col_name = self.model.HEADERS[col] if col < len(self.model.HEADERS) else ""
        
        menu = QMenu(self)
        
        title = QAction(f"📌 Колонка: {col_name}", menu)
        title.setEnabled(False)
        menu.addAction(title)
        menu.addSeparator()
        
        menu.addAction("🎨 Заливка цветом", self._set_cell_color)
        menu.addAction("🧹 Очистить заливку", self._clear_cell_color)
        menu.addSeparator()
        
        if value and str(value).strip():
            filter_action = QAction(f"🔍 Показать только «{value}»", menu)
            filter_action.triggered.connect(lambda: self._filter_by_value(col, value))
            menu.addAction(filter_action)
            
            exclude_action = QAction(f"🚫 Скрыть «{value}»", menu)
            exclude_action.triggered.connect(lambda: self._filter_exclude_value(col, value))
            menu.addAction(exclude_action)
            
            menu.addSeparator()
        
        copy_action = QAction("📋 Копировать ячейку", menu)
        copy_action.setShortcut(QKeySequence.Copy)
        copy_action.triggered.connect(self._copy_selected_cells)
        menu.addAction(copy_action)
        
        paste_action = QAction("📌 Вставить", menu)
        paste_action.setShortcut(QKeySequence.Paste)
        paste_action.triggered.connect(self._paste_to_selected_cells)
        menu.addAction(paste_action)
        
        menu.addSeparator()
        
        undo_action = QAction("↩ Отменить", menu)
        undo_action.setShortcut(QKeySequence.Undo)
        undo_action.triggered.connect(self._undo_last_change)
        menu.addAction(undo_action)
        
        menu.exec(self.sales_table.viewport().mapToGlobal(position))
    
    def _show_row_context_menu(self, position):
        row = self.sales_table.verticalHeader().logicalIndexAt(position)
        if row < 0 or row >= self.proxy_model.rowCount():
            return
        
        selected_rows = set()
        for idx in self.sales_table.selectionModel().selectedRows():
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
        
        menu.exec(self.sales_table.verticalHeader().mapToGlobal(position))
    
    def _show_header_filter_menu(self, position):
        header = self.sales_table.horizontalHeader()
        logical_index = header.logicalIndexAt(position)
        
        if logical_index < 0 or logical_index >= len(self.model.HEADERS):
            return
        
        column_name = self.model.HEADERS[logical_index]
        
        all_values = set()
        for sale in self._all_sales:
            key = self.model.COLUMN_KEYS[logical_index]
            if key == 'id':
                continue
            val = str(getattr(sale, key, '') or '').strip()
            if val:
                all_values.add(val)
        
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
    
    def _filter_by_value(self, col, value):
        self._column_filters[col] = {value}
        self._update_filter_label()
        self._save_column_filters_to_json()
        self._apply_filters()
    
    def _filter_exclude_value(self, col, value):
        all_vals = set()
        for sale in self._all_sales:
            key = self.model.COLUMN_KEYS[col]
            if key == 'id':
                continue
            val = str(getattr(sale, key, '') or '').strip()
            if val:
                all_vals.add(val)
        
        filtered = all_vals - {value}
        if filtered:
            self._column_filters[col] = filtered
        else:
            self._column_filters.pop(col, None)
        
        self._update_filter_label()
        self._save_column_filters_to_json()
        self._apply_filters()
    
    def _insert_empty_row(self, row):
        try:
            new_sale = Sale()
            new_sale.year = datetime.now().year
            new_sale.sale_type = "Продажа"
            self.db_manager.session.add(new_sale)
            self.db_manager.session.commit()
            
            self._recalculate_balance()
            
            self._all_sales = self.db_manager.session.query(Sale).order_by(Sale.id.desc()).all()
            self._apply_filters()
            
            self.status_label.setText(f"✅ Добавлена строка")
            self.status_label.setStyleSheet("color: #28a745;")
            QTimer.singleShot(2000, lambda: self.status_label.setStyleSheet("color: #666;"))
            
        except Exception as e:
            self.db_manager.session.rollback()
            self.logger.error(f"Ошибка вставки строки: {e}")
            self.status_label.setText(f"❌ Ошибка: {str(e)[:50]}")
    
    def _insert_n_rows(self, row, n):
        if n is None:
            n, ok = QInputDialog.getInt(self, "Вставить строки", "Количество строк:", 5, 1, 100, 1)
            if not ok:
                return
        
        try:
            for _ in range(n):
                new_sale = Sale()
                new_sale.year = datetime.now().year
                new_sale.sale_type = "Продажа"
                self.db_manager.session.add(new_sale)
            self.db_manager.session.commit()
            
            self._recalculate_balance()
            
            self.load_data()
            
            self.status_label.setText(f"✅ Добавлено {n} строк")
            self.status_label.setStyleSheet("color: #28a745;")
            QTimer.singleShot(2000, lambda: self.status_label.setStyleSheet("color: #666;"))
            
        except Exception as e:
            self.db_manager.session.rollback()
            self.logger.error(f"Ошибка вставки строк: {e}")
            self.status_label.setText(f"❌ Ошибка: {str(e)[:50]}")
    
    def _copy_row(self, rows):
        if not rows:
            return
        
        if isinstance(rows, int):
            rows = [rows]
        
        self._copied_row_data = []
        for row in rows:
            source_row = self._get_source_row(row)
            if source_row < len(self._filtered_sales):
                sale = self._filtered_sales[source_row]
                if sale:
                    data = {}
                    for key in self.model.COLUMN_KEYS:
                        if key != 'id':
                            value = getattr(sale, key, None)
                            data[key] = value
                    self._copied_row_data.append(data)
        
        count = len(self._copied_row_data)
        self.status_label.setText(f"📝 Скопировано {count} строк")
        self.status_label.setStyleSheet("color: #28a745;")
        QTimer.singleShot(2000, lambda: self.status_label.setStyleSheet("color: #666;"))
    
    def _on_table_clicked(self, index):
        if not index.isValid():
            return
        
        current = self.sales_table.currentIndex()
        if current.isValid() and current.row() == index.row() and current.column() == index.column():
            self.sales_table.edit(index)
    
    def closeEvent(self, event):
        self._save_column_state()
        self._save_column_filters_to_json()
        super().closeEvent(event)
    
    def _recalculate_balance(self):
        try:
            sales = self.db_manager.session.query(Sale).order_by(Sale.id.asc()).all()
            
            balance = 0.0
            
            for sale in sales:
                sale.calculate_total()
                balance += sale.total
                sale.balance = balance
            
            self.db_manager.session.commit()
            self.logger.info(f"✅ Баланс пересчитан. Финальный баланс: {balance:.2f} ₽")
            
        except Exception as e:
            self.logger.error(f"Ошибка пересчёта баланса: {e}")
            self.db_manager.session.rollback()
    
    def _update_balance_display(self):
        try:
            last_sale = self.db_manager.session.query(Sale).order_by(Sale.id.desc()).first()
            
            if last_sale and last_sale.balance is not None:
                final_balance = last_sale.balance
                if hasattr(self, 'balance_label'):
                    self.balance_label.setText(f"Баланс: {final_balance:,.2f} ₽".replace(',', ' '))
            
            self.load_data()
            
        except Exception as e:
            self.logger.error(f"Ошибка обновления отображения баланса: {e}")
    
    def _on_sales_table_clicked(self, index):
        if not index.isValid():
            return
        
        current = self.sales_table.currentIndex()
        if current.isValid() and current.row() == index.row() and current.column() == index.column():
            self.sales_table.edit(index)
    
    def keyPressEvent(self, event):
        focused_widget = QApplication.focusWidget()
        if isinstance(focused_widget, QLineEdit):
            super().keyPressEvent(event)
            return
        
        if event.modifiers() & Qt.ControlModifier:
            if event.key() == Qt.Key_C:
                self._copy_selected_cells()
                event.accept()
                return
            elif event.key() == Qt.Key_V:
                self._paste_to_selected_cells()
                event.accept()
                return
            elif event.key() == Qt.Key_A:
                self.sales_table.selectAll()
                event.accept()
                return
            elif event.key() == Qt.Key_Z:
                self._undo_last_change()
                event.accept()
                return
        elif event.key() == Qt.Key_F2:
            current = self.sales_table.currentIndex()
            if current.isValid():
                self.sales_table.edit(current)
            event.accept()
            return
        elif event.key() == Qt.Key_Delete:
            self._clear_selected_cells()
            event.accept()
            return
        
        super().keyPressEvent(event)
    
    def _clear_selected_cells(self):
        selected_indexes = self.sales_table.selectionModel().selectedIndexes()
        if not selected_indexes:
            return
        
        changes = []
        
        for idx in selected_indexes:
            row = idx.row()
            col = idx.column()
            source_row = self._get_source_row(row)
            
            if source_row < len(self._filtered_sales):
                sale = self._filtered_sales[source_row]
                if sale:
                    field_name = self.model.COLUMN_KEYS[col] if col < len(self.model.COLUMN_KEYS) else None
                    if field_name and field_name != 'id':
                        old_value = getattr(sale, field_name, None)
                        if old_value:
                            changes.append({
                                'sale_id': sale.id,
                                'field': field_name,
                                'old_value': old_value,
                                'new_value': ""
                            })
                            setattr(sale, field_name, None)
                            self._dirty_ids.add(sale.id)
        
        if changes:
            self._last_changes.append(changes)
            if len(self._last_changes) > 50:
                self._last_changes.pop(0)
        
        self.model.dataChanged.emit(
            self.model.index(0, 0),
            self.model.index(self.model.rowCount() - 1, self.model.columnCount() - 1),
            [Qt.DisplayRole]
        )
        
        self.status_label.setText(f"🧹 Очищено {len(selected_indexes)} ячеек")
        self.status_label.setStyleSheet("color: #28a745;")
        QTimer.singleShot(2000, lambda: self.status_label.setStyleSheet("color: #666;"))
        
        
    def _flush_changes(self):
        """Сохраняет все несохранённые изменения в БД"""
        if not hasattr(self, '_dirty_ids') or not self._dirty_ids:
            return
        
        try:
            self.db_manager.session.commit()
            self._dirty_ids.clear()
            self.logger.info(f"  ✅ Сохранено продаж: {len(self._filtered_sales)}")
        except Exception as e:
            self.db_manager.session.rollback()
            self.logger.error(f"Ошибка сохранения продаж: {e}")
            raise
            
# ===== ФАЙЛ: gui/widgets/exchange_tab/sales_tab.py =====
# ДОБАВИТЬ МЕТОД В КЛАСС SalesTab

    def _safe_get_attr(self, obj, attr_name, default=0):
        """
        Безопасно получает атрибут объекта, обрабатывая DetachedInstanceError
        """
        try:
            return getattr(obj, attr_name, default)
        except Exception as e:
            if 'DetachedInstanceError' in str(type(e)):
                self.logger.debug(f"DetachedInstanceError при доступе к {attr_name}, возвращаем значение по умолчанию")
                return default
            raise
            
# ===== ФАЙЛ: gui/widgets/exchange_tab/sales_tab.py =====
# ДОБАВИТЬ МЕТОД В КЛАСС SalesTableModel

    def _safe_float(self, value, default=0):
        """
        Безопасно преобразует значение в float.
        Если значение None или не конвертируется, возвращает default.
        """
        if value is None:
            return default
        try:
            return float(value)
        except (ValueError, TypeError):
            return default

    def _safe_str(self, value, default=""):
        """
        Безопасно преобразует значение в строку.
        Если значение None, возвращает default.
        """
        if value is None:
            return default
        return str(value)