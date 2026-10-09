# -*- coding: utf-8 -*-

"""
Вкладка "Обмен/Продажа" с подвкладками
"""

import logging
import re
import json
from pathlib import Path
from datetime import datetime
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTableView, QHeaderView, QAbstractItemView,
    QPushButton, QLabel, QMessageBox, QMenu, QApplication, QComboBox,
    QFrame, QProgressBar, QTabWidget, QProgressDialog, QInputDialog,
    QCheckBox, QDialog, QListWidget, QDialogButtonBox, QListWidgetItem,
    QLineEdit, QSplitter, QSizePolicy, QStyledItemDelegate, QStyle
)
from PySide6.QtCore import Qt, QSettings, QTimer, QPoint, QModelIndex, QUrl
from PySide6.QtGui import QAction, QKeySequence, QColor

from sqlalchemy.orm import joinedload

from database.models import Purchase, ImportCountry, PurchaseArchive

from .purchases_model import PurchasesTableModel
from .purchases_delegate import PurchaseDelegate
from .purchases_io import ImportPurchasesThread
from .purchases_filters import PurchasesFiltersMixin
from .purchases_actions import PurchasesActionsMixin
from .purchases_autofill import PurchasesAutofillMixin
from .purchases_sorting import PurchasesSortingMixin
from .purchases_navigation import PurchasesNavigationMixin
from .purchases_paste import PurchasesPasteMixin
from .purchases_table import PurchasesTableView
from .silver import SilverSalesTab
from gui.widgets.deals_tab.deals_tab import DealsTab
from .sales_tab import SalesTab
from .balance_chart_tab import BalanceChartTab

class AgColumnDelegate(QStyledItemDelegate):
    """Делегат колонки AG: рисует ✅/❌ напрямую из purchase.ag,
    НЕ зависимо от data() модели таблицы. Редактора нет —
    переключение выполняется кликом (и пробелом) по ячейке."""

    def _get_purchase(self, index):
        model = index.model()
        if model is None:
            return None
        row = index.row()
        if hasattr(model, 'mapToSource'):
            row = model.mapToSource(index).row()
        getter = getattr(model, 'get_purchase', None)
        if callable(getter):
            return getter(row)
        data = getattr(model, '_data', None)
        if isinstance(data, list) and 0 <= row < len(data):
            return data[row]
        return None

    def paint(self, painter, option, index):
        purchase = self._get_purchase(index)
        value = bool(getattr(purchase, 'ag', False)) \
            if purchase is not None else False
        painter.save()
        try:
            if option.state & QStyle.State_Selected:
                painter.fillRect(option.rect, option.palette.highlight())
            if value:
                font = painter.font()
                font.setPointSize(11)
                painter.setFont(font)
                painter.setPen(QColor('#28a745'))
                painter.drawText(option.rect, Qt.AlignCenter, "✅")
            else:
                painter.setPen(QColor('#3a3a5a'))
                painter.drawText(option.rect, Qt.AlignCenter, "—")
        finally:
            painter.restore()

    def createEditor(self, parent, option, index):
        return None   # редактирования нет: переключение кликом

class ExchangeTab(QWidget, 
                  PurchasesFiltersMixin, 
                  PurchasesActionsMixin,
                  PurchasesAutofillMixin, 
                  PurchasesSortingMixin, 
                  PurchasesNavigationMixin,
                  PurchasesPasteMixin):
    """Вкладка "Обмен/Продажа" с подвкладками"""
    
    COLUMN_KEYS = [
        'in_collection', 'collection_price', 'purchase_number', 'purchase_batch',
        'country', 'continent', 'denomination', 'currency', 'year',
        'location_found', 'quantity', 'comments', 'ucoin_exchange',
        'sold_count', 'sold_sum', 'ag'
    ]
    COLUMN_HEADERS = [
        "КОЛ", "ЦК", "№Зак", "№Пок", "Страна", "Континент", "Номинал", "Валюта",
        "ГОД", "МЕСТО", "КОЛ", "КОМЕНТЫ", "Обмен", "Продано", "Сумма", "AG"
    ]
    DEFAULT_COLUMN_WIDTHS = [20, 30, 45, 48, 150, 68, 65, 80, 50, 70, 50, 150,
                             50, 70, 70, 40]
                             
    def __init__(self, db_manager, parent=None):
        super().__init__(parent)
        self.db_manager = db_manager
        self.logger = logging.getLogger('CoinCollector.GUI.ExchangeTab')
        self.settings = QSettings('CoinCollector', 'ExchangeTab')
        self._check_obmen_file_timer = None
        self._check_start_time = None        
        # Данные
        self._all_purchases = []
        self._all_data = []
        self._purchase_cache = {}
        self._filtered_purchases = []
        self._dirty_ids = set()
        self._deleted_ids = set()
        
        # Флаг показа архива
        self._show_archive = False
        
        # Фильтры
        self._column_filters = {}
        self._disabled_filters = {}
        self._copied_cells_data = None
        self._copied_row_data = None
        
        # Undo/Redo
        self._last_changes = []
        self._redo_stack = []
        
        # Таймер сохранения
        self._save_timer = QTimer()
        self._save_timer.setSingleShot(True)
        self._save_timer.timeout.connect(self._flush_changes)
        
        # Переменные для автозаполнения
        self._autofill_nickname = None
        self._autofill_download_dir = None
        self._autofill_processed = False
        self._autofill_check_timer = None
        self._nick_data = {}
        self._autofill_deal_number = None
        self._purchases_cols_ready = False        
        self.init_ui()
        self._restore_column_state()
        self.table = None
        # ===== Сохранение ширины/порядка колонок на подвкладках =====
        from utils.column_state import ColumnStateHelper
        for tbl, key in (
            (getattr(self.deals_tab, 'table', None), 'deals_columns'),
            (getattr(self.statistics_tab, 'table', None), 'exchange_statistics_columns'),
            (getattr(self, 'purchases_table', None), 'purchases_columns'),
            (getattr(self.sales_tab, 'sales_table', None), 'sales_columns'),
        ):
            if tbl is not None:
                try:
                    ColumnStateHelper.attach(tbl, key)
                except Exception as e:
                    self.logger.error(f"ColumnState {key}: {e}")
        self._restore_column_state()
        self._load_column_filters_from_json()
        
        saved_country = self.settings.value('purchases_country_filter')
        if saved_country:
            idx = self.country_filter.findData(saved_country)
            if idx >= 0:
                self.country_filter.setCurrentIndex(idx)
        
        # Загружаем данные после инициализации UI
        QTimer.singleShot(100, self.load_data)
        
        self.setFocusPolicy(Qt.StrongFocus)
    
    def init_ui(self):
        """Инициализация интерфейса"""
        layout = QVBoxLayout()
        layout.setContentsMargins(5, 5, 5, 5)
        layout.setSpacing(5)
        self.setLayout(layout)

        # Создаём вкладки
        self.tab_widget = QTabWidget()
        self.tab_widget.setDocumentMode(True)
        
        # === ВКЛАДКА 1: СДЕЛКИ ===
        self.deals_tab = DealsTab(self.db_manager, self)
        self.tab_widget.addTab(self.deals_tab, "📋 Сделки")
        
        # === ВКЛАДКА 2: СТАТИСТИКА ===
        from .statistics_tab import StatisticsTab
        self.statistics_tab = StatisticsTab(self.db_manager, self)
        self.tab_widget.addTab(self.statistics_tab, "📊 Статистика")
        
        # === ВКЛАДКА 3: ЗАКУПКИ ===
        self.tab_widget.addTab(self._create_purchases_tab(), "📦 Закупки")
         # === НОВАЯ ВКЛАДКА: статистика продаж по закупкам (актив + архив) ===
        from gui.widgets.exchange_tab.sales_stats_tab import SalesStatsTab
        self.sales_stats_tab = SalesStatsTab(self.db_manager, self)
        self.tab_widget.addTab(self.sales_stats_tab, "📊 Статистика продаж")       
        # === ВКЛАДКА 4: ОБЩИЕ ПРОДАЖИ ===
        self.sales_tab = SalesTab(self.db_manager, self)
        self.tab_widget.addTab(self.sales_tab, "💰 Общие продажи")
        
        # === ВКЛАДКА 5: ГРАФИК БАЛАНСА ===
        self.balance_chart_tab = BalanceChartTab(self.db_manager, self)
        self.tab_widget.addTab(self.balance_chart_tab, "📈 График баланса")
        
        # === ВКЛАДКА 6: ПРОДАЖА СЕРЕБРА ===
        self.silver_sales_tab = SilverSalesTab(self.db_manager, self)
        self.tab_widget.addTab(self.silver_sales_tab, "🥈 Продажа серебра")
        
        layout.addWidget(self.tab_widget)

    def _rewrite_stylesheet(self, ss):
        """Заменяет светлые цвета в stylesheet виджета на тёмные эквиваленты"""
        import re
        if not ss:
            return ss
        # Белый фон -> тёмный (только для background, не трогаем color: white)
        ss = re.sub(
            r'(background(?:-color)?:\s*)white\b',
            lambda m: m.group(1) + '#1a1a2e',
            ss, flags=re.IGNORECASE
        )
        # Светлые фоны
        for light, dark in [
            ('#f8f9fa', '#1a1a2e'), ('#f5f5f5', '#1a1a2e'), ('#f0f0f0', '#1a1a2e'),
            ('#fafafa', '#16213e'), ('#e9ecef', '#16213e'), ('#e8f0fe', '#1f2b47'),
            ('#e0e0e0', '#262640'),
        ]:
            ss = ss.replace(light, dark)
        # Светлые границы и сетки
        for light, dark in [
            ('#d0d0d0', '#2a2a4a'), ('#dee2e6', '#2a2a4a'),
            ('#dddddd', '#2a2a4a'), ('#cccccc', '#2a2a4a'),
        ]:
            ss = ss.replace(light, dark)
        # Короткие формы (с границей, чтобы не задеть длинные коды)
        for light, dark in [
            (r'#ddd\b', '#2a2a4a'), (r'#ccc\b', '#2a2a4a'),
            (r'#999\b', '#a8a8d0'), (r'#666\b', '#a8a8d0'),
            (r'#333\b', '#e4e4ef'),
        ]:
            ss = re.sub(light, dark, ss, flags=re.IGNORECASE)
        return ss

    def update_style(self):
        """Переводит все дочерние виджеты вкладки в тёмную тему"""
        from PySide6.QtWidgets import QApplication, QWidget
        main_window = None
        for w in QApplication.topLevelWidgets():
            if w.__class__.__name__ == 'MainWindow':
                main_window = w
                break
        if not main_window or not hasattr(main_window, 'theme_manager'):
            return
        if not main_window.theme_manager.is_dark():
            return
        for widget in self.findChildren(QWidget):
            ss = widget.styleSheet()
            if ss:
                new_ss = self._rewrite_stylesheet(ss)
                if new_ss != ss:
                    widget.setStyleSheet(new_ss)

    def showEvent(self, event):
        """При показе вкладки применяем тёмную тему ко всем дочерним виджетам"""
        from PySide6.QtCore import QTimer
        super().showEvent(event)
        QTimer.singleShot(0, self.update_style)
        # При переключении подвкладок тоже перекрашиваем (виджеты могут создаваться лениво)
        if hasattr(self, 'tab_widget') and not getattr(self, '_style_hooked', False):
            self._style_hooked = True
            self.tab_widget.currentChanged.connect(
                lambda idx: QTimer.singleShot(0, self.update_style)
            )
    
    def _create_purchases_tab(self):
        """Создает вкладку закупок с правой панелью браузера"""
        from PySide6.QtWidgets import QSizePolicy
        
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        
        # === ВЕРХНЯЯ ПАНЕЛЬ ИНСТРУМЕНТОВ ===
        toolbar_widget = QWidget()
        toolbar_widget.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        toolbar_widget.setMinimumHeight(75)  # Увеличиваем высоту для двухстрочных кнопок
        toolbar_widget.setStyleSheet("background-color: #f5f5f5; border-bottom: 1px solid #ddd;")
        
        toolbar = QHBoxLayout(toolbar_widget)
        toolbar.setContentsMargins(5, 2, 5, 2)
        toolbar.setSpacing(4)
        
        # === ЛЕВАЯ ЧАСТЬ: Навигация и страна ===
        left_widget = QWidget()
        left_layout = QHBoxLayout(left_widget)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(3)
        
        # Кнопка "Перейти к первой строке"
        self.top_btn = QPushButton("▲\nВверх")
        self.top_btn.setFixedSize(42, 38)
        self.top_btn.setToolTip("Перейти к первой строке")
        self.top_btn.setStyleSheet("""
            QPushButton {
                background-color: #4a6fa5;
                color: white;
                font-weight: bold;
                border-radius: 3px;
                font-size: 10px;
                padding: 1px;
            }
            QPushButton:hover {
                background-color: #5a7fb5;
            }
        """)
        self.top_btn.clicked.connect(self._scroll_to_top)
        left_layout.addWidget(self.top_btn)
        
        # Кнопка "Перейти к последней строке"
        self.bottom_btn = QPushButton("▼\nВниз")
        self.bottom_btn.setFixedSize(42, 38)
        self.bottom_btn.setToolTip("Перейти к последней строке")
        self.bottom_btn.setStyleSheet("""
            QPushButton {
                background-color: #4a6fa5;
                color: white;
                font-weight: bold;
                border-radius: 3px;
                font-size: 10px;
                padding: 1px;
            }
            QPushButton:hover {
                background-color: #5a7fb5;
            }
        """)
        self.bottom_btn.clicked.connect(self._scroll_to_bottom)
        left_layout.addWidget(self.bottom_btn)
        
        # Кнопка "Обновить"
        self.refresh_btn = QPushButton("🔄\nОбновить")
        self.refresh_btn.setFixedSize(50, 38)
        self.refresh_btn.clicked.connect(self._full_reload)
        self.refresh_btn.setToolTip("Обновить данные")
        self.refresh_btn.setStyleSheet("""
            QPushButton {
                background-color: #6c757d;
                color: white;
                font-weight: bold;
                border-radius: 3px;
                font-size: 10px;
                padding: 1px;
            }
            QPushButton:hover {
                background-color: #5a6268;
            }
        """)
        left_layout.addWidget(self.refresh_btn)
        
        # Разделитель
        sep1 = QFrame()
        sep1.setFrameShape(QFrame.VLine)
        sep1.setFrameShadow(QFrame.Sunken)
        sep1.setFixedSize(2, 32)
        left_layout.addWidget(sep1)
        
        # Страна
        country_label = QLabel("Страна:")
        country_label.setFixedHeight(22)
        left_layout.addWidget(country_label)
        
        self.country_filter = QComboBox()
        self.country_filter.setStyleSheet("""
            QComboBox {
                background-color: #16213e;
                color: #e4e4ef;
                border: 1px solid #2a2a4a;
                border-radius: 6px;
                padding: 2px 8px;
            }
            QComboBox QAbstractItemView {
                background-color: #1a1a2e;
                color: #e4e4ef;
                border: 1px solid #3d3d5c;
                selection-background-color: #6c63ff;
                selection-color: #ffffff;
            }
        """)
        self.country_filter.addItem("Все страны", None)
        self.country_filter.currentIndexChanged.connect(self._apply_filters)
        self.country_filter.setMinimumWidth(140)
        self.country_filter.setFixedHeight(22)
        # Увеличиваем максимальную ширину для длинных названий стран
        self.country_filter.setMaximumWidth(250)
        # Настройка выпадающего списка - ширина по содержимому
        self.country_filter.setSizeAdjustPolicy(QComboBox.AdjustToContents)
        left_layout.addWidget(self.country_filter)
        
        # Счётчик записей
        self.purchase_count_label = QLabel("Сумма: 0")
        self.purchase_count_label.setStyleSheet("color: #666; font-size: 11px; padding: 0 8px;")
        self.purchase_count_label.setFixedHeight(22)
        left_layout.addWidget(self.purchase_count_label)
        
        left_layout.addStretch()
        toolbar.addWidget(left_widget, 1)
        
        # === ПРАВАЯ ЧАСТЬ: КНОПКИ ДЕЙСТВИЙ ===
        right_widget = QWidget()
        right_layout = QHBoxLayout(right_widget)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(3)
        
        # Вернуть в продажу
        self.return_to_sale_btn = QPushButton("🔄\nВернуть\nв продажу")
        self.return_to_sale_btn.clicked.connect(self._return_to_sale)
        self.return_to_sale_btn.setFixedSize(55, 45)
        self.return_to_sale_btn.setStyleSheet("""
            QPushButton {
                background-color: #28a745;
                color: white;
                font-weight: bold;
                border-radius: 3px;
                padding: 1px;
                font-size: 9px;
            }
            QPushButton:hover {
                background-color: #218838;
            }
        """)
        self.return_to_sale_btn.setToolTip("Вернуть выделенные закупки в продажу")
        right_layout.addWidget(self.return_to_sale_btn)
        
        # Добавить к заказу
        self.add_to_order_btn = QPushButton("➕\nДобавить\nк заказу")
        self.add_to_order_btn.clicked.connect(self._add_to_order)
        self.add_to_order_btn.setFixedSize(55, 45)
        self.add_to_order_btn.setStyleSheet("""
            QPushButton {
                background-color: #17a2b8;
                color: white;
                font-weight: bold;
                border-radius: 3px;
                padding: 1px;
                font-size: 9px;
            }
            QPushButton:hover {
                background-color: #138496;
            }
        """)
        self.add_to_order_btn.setToolTip("Добавить выделенные закупки к заказу")
        right_layout.addWidget(self.add_to_order_btn)
        
        # Выставить на обмен
        self.set_exchange_btn = QPushButton("🔄\nВыставить\nна обмен")
        self.set_exchange_btn.clicked.connect(self._set_exchange_selected)
        self.set_exchange_btn.setFixedSize(55, 45)
        self.set_exchange_btn.setStyleSheet("""
            QPushButton {
                background-color: #ffc107;
                color: #333;
                font-weight: bold;
                border-radius: 3px;
                padding: 1px;
                font-size: 9px;
            }
            QPushButton:hover {
                background-color: #e0a800;
            }
        """)
        self.set_exchange_btn.setToolTip("Выставить выделенные закупки на обмен")
        right_layout.addWidget(self.set_exchange_btn)
        
        # Отложено
        self.set_delayed_btn = QPushButton("⏸️\nОтложено")
        self.set_delayed_btn.clicked.connect(self._set_delayed_selected)
        self.set_delayed_btn.setFixedSize(50, 45)
        self.set_delayed_btn.setStyleSheet("""
            QPushButton {
                background-color: #6c757d;
                color: white;
                font-weight: bold;
                border-radius: 3px;
                padding: 1px;
                font-size: 9px;
            }
            QPushButton:hover {
                background-color: #5a6268;
            }
        """)
        self.set_delayed_btn.setToolTip("Отметить выделенные закупки как отложенные")
        right_layout.addWidget(self.set_delayed_btn)
        
        # Переместить в мусор
        self.move_to_trash_btn = QPushButton("🗑️\nМусор")
        self.move_to_trash_btn.clicked.connect(self._move_to_trash)
        self.move_to_trash_btn.setFixedSize(45, 45)
        self.move_to_trash_btn.setStyleSheet("""
            QPushButton {
                background-color: #dc3545;
                color: white;
                font-weight: bold;
                border-radius: 3px;
                padding: 1px;
                font-size: 9px;
            }
            QPushButton:hover {
                background-color: #c82333;
            }
        """)
        self.move_to_trash_btn.setToolTip("Переместить выделенные закупки в мусор")
        right_layout.addWidget(self.move_to_trash_btn)
        
        # Продать мусор
        self.sell_trash_btn = QPushButton("💰\nПродать\nмусор")
        self.sell_trash_btn.clicked.connect(self._sell_trash)
        self.sell_trash_btn.setFixedSize(55, 45)
        self.sell_trash_btn.setStyleSheet("""
            QPushButton {
                background-color: #e67e22;
                color: white;
                font-weight: bold;
                border-radius: 3px;
                padding: 1px;
                font-size: 9px;
            }
            QPushButton:hover {
                background-color: #d35400;
            }
        """)
        self.sell_trash_btn.setToolTip("Продать мусорные монеты")
        right_layout.addWidget(self.sell_trash_btn)
        
        # Показать дубли
        self.show_duplicates_btn = QPushButton("🔍\nДубли")
        self.show_duplicates_btn.clicked.connect(self._show_duplicates)
        self.show_duplicates_btn.setFixedSize(45, 45)
        self.show_duplicates_btn.setStyleSheet("""
            QPushButton {
                background-color: #9b59b6;
                color: white;
                font-weight: bold;
                border-radius: 3px;
                padding: 1px;
                font-size: 9px;
            }
            QPushButton:hover {
                background-color: #8e44ad;
            }
        """)
        self.show_duplicates_btn.setToolTip("Показать дубликаты для выделенной монеты")
        right_layout.addWidget(self.show_duplicates_btn)
        
        # Открыть на Мешке
        self.open_meshok_btn = QPushButton("📦\nМешок")
        self.open_meshok_btn.clicked.connect(self._open_meshok_for_selected)
        self.open_meshok_btn.setFixedSize(45, 45)
        self.open_meshok_btn.setStyleSheet("""
            QPushButton {
                background-color: #2ecc71;
                color: white;
                font-weight: bold;
                border-radius: 3px;
                padding: 1px;
                font-size: 9px;
            }
            QPushButton:hover {
                background-color: #27ae60;
            }
        """)
        self.open_meshok_btn.setToolTip("Открыть поиск на Мешке для выделенной закупки")
        right_layout.addWidget(self.open_meshok_btn)
        
        # Разделитель перед архивом
        sep_archive = QFrame()
        sep_archive.setFrameShape(QFrame.VLine)
        sep_archive.setFrameShadow(QFrame.Sunken)
        sep_archive.setFixedSize(2, 32)
        right_layout.addWidget(sep_archive)
        
        # Архив
        self.show_archive_check = QCheckBox("📦\nАрхив")
        self.show_archive_check.setToolTip("Показывать архивированные закупки вместе с активными")
        self.show_archive_check.stateChanged.connect(self._on_show_archive_changed)
        self.show_archive_check.setFixedSize(45, 45)
        self.show_archive_check.setStyleSheet("""
            QCheckBox {
                font-weight: bold;
                color: #6c757d;
                font-size: 9px;
                text-align: center;
            }
            QCheckBox:checked {
                color: #dc3545;
            }
        """)
        # Переопределяем отображение чекбокса с текстом в две строки
        self.show_archive_check.setStyleSheet("""
            QCheckBox {
                font-weight: bold;
                color: #6c757d;
                font-size: 9px;
                spacing: 2px;
            }
            QCheckBox::indicator {
                width: 16px;
                height: 16px;
            }
            QCheckBox:checked {
                color: #dc3545;
            }
        """)
        right_layout.addWidget(self.show_archive_check)
        
        # Автозаполнение
        self.autofill_btn = QPushButton("🔄\nАвто-\nзаполнение")
        self.autofill_btn.clicked.connect(self._show_autofill_dialog)
        self.autofill_btn.setFixedSize(55, 45)
        self.autofill_btn.setStyleSheet("""
            QPushButton {
                background-color: #17a2b8;
                color: white;
                font-weight: bold;
                border-radius: 3px;
                padding: 1px;
                font-size: 9px;
            }
            QPushButton:hover {
                background-color: #138496;
            }
        """)
        right_layout.addWidget(self.autofill_btn)
        
        # Браузер - кнопка переключения
        self.toggle_panel_btn = QPushButton("🌐\nПоказать\nбраузер")
        self.toggle_panel_btn.clicked.connect(self._toggle_browser_panel)
        self.toggle_panel_btn.setFixedSize(55, 45)
        self.toggle_panel_btn.setStyleSheet("""
            QPushButton {
                background-color: #4a6fa5;
                color: white;
                font-weight: bold;
                border-radius: 3px;
                padding: 1px;
                font-size: 9px;
            }
            QPushButton:hover {
                background-color: #5a7fb5;
            }
        """)
        right_layout.addWidget(self.toggle_panel_btn)
        
        right_layout.addStretch()
        toolbar.addWidget(right_widget, 0)
        
        layout.addWidget(toolbar_widget)
        
        # Метка фильтров
        self.filter_label = QLabel("")
        self.filter_label.setStyleSheet("color: #dc3545; font-size: 9px; padding: 0px 2px;")
        self.filter_label.setVisible(False)
        self.filter_label.setCursor(Qt.PointingHandCursor)
        self.filter_label.mousePressEvent = lambda e: self._clear_all_filters()
        layout.addWidget(self.filter_label)
        
        # === ОСНОВНОЙ СПЛИТТЕР ===
        self.right_splitter = QSplitter(Qt.Horizontal)
        self.right_splitter.setHandleWidth(3)
        self.right_splitter.setChildrenCollapsible(False)
        self.right_splitter.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        
        # Левая часть — таблица закупок
        left_widget = QWidget()
        left_layout = QVBoxLayout(left_widget)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(0)
        
        # Модель
        self.model = PurchasesTableModel(self, self.db_manager)
        self.model.data_changed.connect(self._on_purchase_data_changed)
        
        # Делегат
        self.delegate = PurchaseDelegate(self)
        self.delegate.set_parent_tab(self)
        
        # Кастомная таблица
        self.purchases_table = PurchasesTableView(self)
        self.table = self.purchases_table
        self.purchases_table.setModel(self.model)
        self.purchases_table.setItemDelegate(self.delegate)
        # === КОЛОНКА AG: гарантируем 16-ю колонку в модели и свой делегат ===
        self._ensure_ag_column_in_model()
        ag_col = self._ag_column_index()
        if ag_col >= 0:
            self.purchases_table.setItemDelegateForColumn(
                ag_col, AgColumnDelegate(self.purchases_table))
        # === ОДИН КЛИК ПО ЯЧЕЙКЕ AG = ПЕРЕКЛЮЧЕНИЕ МЕТКИ ✅/❌ ===
        self.purchases_table.clicked.connect(self._on_purchases_cell_clicked)
        self.purchases_table.setAlternatingRowColors(True)
        self.purchases_table.setSelectionBehavior(QAbstractItemView.SelectItems)
        self.purchases_table.setSelectionMode(QAbstractItemView.ExtendedSelection)
        
        self.purchases_table.setStyleSheet("""
        QTableView {
            background-color: #1a1a2e;
            color: #e4e4ef;
            selection-background-color: #6c63ff;
            selection-color: #ffffff;
            gridline-color: #2a2a4a;
            alternate-background-color: #16213e;
        }
        QTableView::item:selected {
            background-color: #6c63ff;
            color: #ffffff;
        }
        QTableView::item:selected:!active {
            background-color: #5a52e0;
        }
        QTableView::item:hover {
            background-color: #1f2b47;
        }
        QHeaderView::section {
            background-color: #16213e;
            color: #a8a8d0;
            padding: 4px;
            border: none;
            border-right: 1px solid #2a2a4a;
            border-bottom: 2px solid #6c63ff;
            font-weight: bold;
        }
        QHeaderView::section:hover {
            background-color: #1f2b47;
        }
        """)
        
        self.purchases_table.setEditTriggers(QAbstractItemView.DoubleClicked)
        self.purchases_table.setSortingEnabled(False)
        self.purchases_table.horizontalHeader().setSortIndicatorShown(True)
        self.purchases_table.setAcceptDrops(True)
        
        # Настройка заголовков
        header = self.purchases_table.horizontalHeader()
        header.setSectionsMovable(True)
        header.setContextMenuPolicy(Qt.CustomContextMenu)
        header.customContextMenuRequested.connect(self._show_header_filter_menu)
        header.sectionMoved.connect(self._on_column_moved)
        header.sectionResized.connect(self._on_column_resized)
        
        v_header = self.purchases_table.verticalHeader()
        v_header.setContextMenuPolicy(Qt.CustomContextMenu)
        v_header.customContextMenuRequested.connect(self._show_row_context_menu)
        
        self.purchases_table.setContextMenuPolicy(Qt.CustomContextMenu)
        self.purchases_table.customContextMenuRequested.connect(self._show_cell_context_menu)
        
        # Устанавливаем ширину колонок по умолчанию
        for i, width in enumerate(self.DEFAULT_COLUMN_WIDTHS):
            self.purchases_table.setColumnWidth(i, width)
        for i in range(len(self.COLUMN_HEADERS)):
            header.setSectionResizeMode(i, QHeaderView.Interactive)
        
        left_layout.addWidget(self.purchases_table)
        
        # Статус сохранения
        self.save_status_label = QLabel("")
        self.save_status_label.setStyleSheet("color: #666; font-size: 10px; padding: 2px 4px;")
        self.save_status_label.setFixedHeight(18)
        left_layout.addWidget(self.save_status_label)
        
        self.right_splitter.addWidget(left_widget)
        
        # Правая часть — браузер (СКРЫТ ПО УМОЛЧАНИЮ)
        self.browser_panel = self._create_browser_panel()
        self.browser_panel.setVisible(False)
        self.right_splitter.addWidget(self.browser_panel)
        
        layout.addWidget(self.right_splitter)
        
        QTimer.singleShot(100, self._set_initial_splitter_sizes)
        
        return widget

    def _create_browser_panel(self):
        """Создаёт панель с браузером для закупок"""
        from gui.widgets.exchange_browser import ExchangeBrowser
        
        panel = QWidget()
        panel.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        
        title_frame = QFrame()
        title_frame.setStyleSheet("background-color: #4a6fa5; border: none;")
        title_frame.setFixedHeight(28)
        title_layout = QHBoxLayout(title_frame)
        title_layout.setContentsMargins(6, 2, 6, 2)
        
        title_label = QLabel("🌐 Поиск и отметка монет")
        title_label.setStyleSheet("color: white; font-weight: bold; font-size: 11px;")
        title_layout.addWidget(title_label)
        title_layout.addStretch()
        
        self.browser_info_label = QLabel("ПКМ → фоновая вкладка | ЛКМ → текущая вкладка")
        self.browser_info_label.setStyleSheet("color: #ffd966; font-size: 9px;")
        title_layout.addWidget(self.browser_info_label)
        
        close_btn = QPushButton("✕")
        close_btn.setFixedSize(22, 22)
        close_btn.setCursor(Qt.PointingHandCursor)
        close_btn.setStyleSheet("""
            QPushButton {
                background-color: transparent;
                color: white;
                border: none;
                font-size: 12px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #dc3545;
                border-radius: 3px;
            }
        """)
        close_btn.clicked.connect(self._toggle_browser_panel)
        title_layout.addWidget(close_btn)
        
        layout.addWidget(title_frame)
        
        try:
            self.embedded_browser = ExchangeBrowser(self, profile_name="exchange_tab")
            
            # Устанавливаем ссылку на текущую вкладку
            self.embedded_browser.set_parent_tab(self)
            layout.addWidget(self.embedded_browser)
            self.logger.info("✅ Браузер для вкладки закупок создан (ExchangeBrowser)")
        except Exception as e:
            self.logger.error(f"Ошибка создания браузера: {e}")
            error_label = QLabel(f"❌ Ошибка: {str(e)[:100]}\n\nУстановите PySide6-WebEngine")
            error_label.setAlignment(Qt.AlignCenter)
            error_label.setStyleSheet("color: red; padding: 20px;")
            layout.addWidget(error_label)
            self.embedded_browser = None
        
        return panel
    
    def _set_initial_splitter_sizes(self):
        """Устанавливает начальные размеры сплиттера"""
        if not self.right_splitter:
            return
        total_width = self.right_splitter.width()
        if total_width <= 0:
            QTimer.singleShot(100, self._set_initial_splitter_sizes)
            return
        self.right_splitter.setSizes([total_width, 0])
    
    def _toggle_browser_panel(self):
        """Показывает или скрывает правую панель с браузером"""
        if not hasattr(self, 'right_panel_visible'):
            self.right_panel_visible = False
        self.right_panel_visible = not self.right_panel_visible
        
        if self.right_panel_visible:
            self.browser_panel.setVisible(True)
            self.toggle_panel_btn.setText("🌐\nСкрыть\nбраузер")
            self.toggle_panel_btn.setStyleSheet("""
                QPushButton {
                    background-color: #dc3545;
                    color: white;
                    font-weight: bold;
                    border-radius: 3px;
                    padding: 1px;
                    font-size: 9px;
                }
                QPushButton:hover {
                    background-color: #c82333;
                }
            """)
            total_width = self.right_splitter.width()
            if total_width > 0:
                self.right_splitter.setSizes([int(total_width * 0.55), int(total_width * 0.45)])
            else:
                self.right_splitter.setSizes([600, 100])
        else:
            self.browser_panel.setVisible(False)
            self.toggle_panel_btn.setText("🌐\nПоказать\nбраузер")
            self.toggle_panel_btn.setStyleSheet("""
                QPushButton {
                    background-color: #4a6fa5;
                    color: white;
                    font-weight: bold;
                    border-radius: 3px;
                    padding: 1px;
                    font-size: 9px;
                }
                QPushButton:hover {
                    background-color: #5a7fb5;
                }
            """)
    
    # ========== ЗАГРУЗКА ДАННЫХ ==========
    
    def load_data(self):
        """Загружает данные из БД (только активные).
        Первым делом гарантирует наличие колонки 'ag' в purchases /
        purchases_archive (авто-миграция, идемпотентна)."""
        # === ГАРАНТИРОВАННАЯ МИГРАЦИЯ КОЛОНКИ 'ag' ===
        try:
            from database.models import ensure_ag_column
            ensure_ag_column(self.db_manager)
            self.db_manager.session.rollback()
        except Exception as e:
            self.logger.debug(f"Миграция колонки 'ag': {e}")
        try:
            self.db_manager.session.rollback()
        except:
            pass
        if hasattr(self, 'purchases_table'):
            self.purchases_table.setSortingEnabled(False)
        try:
            self._all_purchases = self.db_manager.session.query(Purchase).options(
                joinedload(Purchase.import_country)
            ).all()
            self.logger.info(f"Загружено активных закупок: {len(self._all_purchases)}")
            self.refresh_data()
            if hasattr(self, 'purchases_table'):
                self.purchases_table.setSortingEnabled(True)
            self.save_status_label.setText(f"✅ Активных закупок: {len(self._all_purchases)}")
            self.save_status_label.setStyleSheet("color: #28a745; font-size: 11px;")
            QTimer.singleShot(2000, lambda: self.save_status_label.setStyleSheet("color: #666; font-size: 11px;"))
        except Exception as e:
            self.logger.error(f"Ошибка загрузки закупок: {e}")
            import traceback
            traceback.print_exc()
            self.save_status_label.setText("❌ Ошибка загрузки")
            self.save_status_label.setStyleSheet("color: #dc3545; font-size: 11px;")
        finally:
            if hasattr(self, 'purchases_table'):
                self.purchases_table.setSortingEnabled(True)
    
    def refresh_data(self):
        """Обновляет данные в зависимости от состояния чекбокса 'Показать архив'"""
        if self.show_archive_check.isChecked():
            archived = self.load_archive_data()
            self._all_data = self._all_purchases + archived
            self.logger.info(f"Всего записей (активные + архив): {len(self._all_data)}")
        else:
            self._all_data = self._all_purchases
            self.logger.info(f"Всего активных записей: {len(self._all_data)}")
        
        self._apply_filters()
        self.load_country_filter()
        
        # Обновляем сумму по колонке "КОЛ" (quantity)
        self._update_total_quantity()
    
    def _update_total_quantity(self):
        """Обновляет сумму по колонке 'КОЛ' (quantity)"""
        if not hasattr(self, '_filtered_purchases'):
            return
        total_quantity = 0
        for purchase in self._filtered_purchases:
            if purchase:
                try:
                    total_quantity += purchase.quantity or 1
                except Exception:
                    total_quantity += getattr(purchase, '_frozen_quantity', 1)
        if hasattr(self, 'purchase_count_label'):
            self.purchase_count_label.setText(f"Сумма: {total_quantity}")

    def load_archive_data(self):
        """Загружает архивные закупки из таблицы purchases_archive.
        Поле 'ag' переносится во временный объект, чтобы фильтр AG
        и колонка AG работали и на архивных строках."""
        try:
            self.db_manager.session.rollback()
            archive_purchases = self.db_manager.session.query(PurchaseArchive).options(
                joinedload(PurchaseArchive.import_country)
            ).all()
            archive_data = []
            for arch in archive_purchases:
                class TempPurchase:
                    pass
                temp = TempPurchase()
                temp.id = arch.id
                temp.in_collection = arch.in_collection
                temp.collection_price = arch.collection_price
                temp.purchase_number = arch.purchase_number
                temp.purchase_batch = arch.purchase_batch
                temp.import_country_id = arch.import_country_id
                temp.import_country = arch.import_country
                temp.continent = arch.continent
                temp.denomination_value = arch.denomination_value
                temp.currency = arch.currency
                temp.year = arch.year
                temp.location_found = arch.location_found
                temp.quantity = arch.quantity
                temp.comments = arch.comments
                temp.ucoin_exchange = arch.ucoin_exchange
                temp.ucoin_exchange_count = arch.ucoin_exchange_count
                temp.sold_count = arch.sold_count
                temp.sold_sum = arch.sold_sum
                temp.total = arch.total
                # === ПРИЗНАК СЕРЕБРА ИЗ АРХИВА (для фильтра AG) ===
                temp.ag = bool(getattr(arch, 'ag', False) or False)
                temp._is_archived = True
                temp.archived_at = arch.archived_at
                archive_data.append(temp)
            self.logger.info(f"Загружено архивных закупок: {len(archive_data)}")
            return archive_data
        except Exception as e:
            self.logger.error(f"Ошибка загрузки архивных закупок: {e}")
            return []

    def _flush_changes(self):
        """Сохраняет изменения в БД"""
        if not self._dirty_ids:
            return
        
        try:
            self.db_manager.session.commit()
            self._dirty_ids.clear()
            self.save_status_label.setText("💾 Изменения сохранены")
            self.save_status_label.setStyleSheet("color: #28a745; font-size: 11px;")
            QTimer.singleShot(2000, lambda: self.save_status_label.setStyleSheet("color: #666; font-size: 11px;"))
        except Exception as e:
            self.db_manager.session.rollback()
            self.logger.error(f"Ошибка сохранения: {e}")
            self.save_status_label.setText(f"❌ Ошибка: {str(e)[:30]}")
            self.save_status_label.setStyleSheet("color: #dc3545; font-size: 11px;")
    
    def _on_purchase_data_changed(self):
        """Обработчик изменения данных в закупках"""
        if not hasattr(self, '_recalc_timer'):
            self._recalc_timer = QTimer()
            self._recalc_timer.setSingleShot(True)
            self._recalc_timer.timeout.connect(self._recalculate_deal_totals)
        self._recalc_timer.start(500)

    def _recalculate_deal_totals(self):
        """Пересчитывает суммы сделок ТОЛЬКО в колонке 'Сумма' (amount)"""
        try:
            from database.models import Deal, Purchase
            from collections import defaultdict
            batches = defaultdict(float)
            # === ГАРАНТИРОВАННАЯ МИГРАЦИЯ: колонка 'ag' в purchases ===
            # SQLite не умеет сам синхронизировать схему с моделями,
            # поэтому добавляем колонку до первого запроса к таблице.
            try:
                from database.models import ensure_ag_column
                ensure_ag_column(self.db_manager)
                self.db_manager.session.rollback()
            except Exception as e:
                self.logger.debug(f"Миграция колонки 'ag': {e}")
            purchases = self.db_manager.session.query(Purchase).all()
            for p in purchases:
                if p.purchase_batch and str(p.purchase_batch).strip() \
                        and str(p.purchase_batch).strip() != '0' and p.sold_sum:
                    try:
                        batches[str(p.purchase_batch)] += float(p.sold_sum)
                    except (TypeError, ValueError):
                        pass
            updated_count = 0
            for number, total in batches.items():
                deal = (self.db_manager.session.query(Deal)
                        .filter(Deal.number == number).first())
                if deal:
                    try:
                        current = float(deal.amount) if deal.amount is not None else None
                    except (TypeError, ValueError):
                        current = None
                    if current != total:
                        # ВАЖНО: только amount ("Сумма"), total не трогаем (там "📦")
                        deal.amount = total
                        deal.updated_at = datetime.now()
                        updated_count += 1
            if updated_count > 0:
                self.db_manager.session.commit()
                self.logger.info(f"💰 Пересчитаны суммы для {updated_count} сделок")
                main_window = self.window()
                if main_window and hasattr(main_window, 'exchange_tab'):
                    deals_tab = main_window.exchange_tab.deals_tab
                    if deals_tab:
                        deals_tab._refresh_all()
                        self.logger.info("🔄 Таблица сделок обновлена")
        except Exception as e:
            self.db_manager.session.rollback()
            self.logger.error(f"Ошибка пересчёта сумм сделок: {e}")

    def _on_show_archive_changed(self, state):
        """Обработчик переключения чекбокса 'Показать архив'"""
        self._show_archive = (state == Qt.Checked)
        self.logger.info(f"Переключение показа архива: {self._show_archive}")
        self.refresh_data()
    
    def _full_reload(self):
        """Полная перезагрузка данных"""
        self._flush_changes()
        self._all_purchases = []
        self._purchase_cache = {}
        self._filtered_purchases = []
        self.load_data()
    
    def _get_column_value(self, purchase, logical_index):
        """Возвращает текстовое значение колонки для фильтров.
        Защищено от удалённых из БД / откреплённых объектов SQLAlchemy."""
        try:
            if logical_index == 0:
                return "✅" if purchase.in_collection else ""
            elif logical_index == 1:
                return f"{purchase.collection_price:.0f}" if purchase.collection_price else ""
            elif logical_index == 2:
                return str(purchase.purchase_number or "")
            elif logical_index == 3:
                return purchase.purchase_batch or ""
            elif logical_index == 4:
                return purchase.import_country.name if purchase.import_country else "—"
            elif logical_index == 5:
                return purchase.continent or ""
            elif logical_index == 6:
                return purchase.denomination_value or ""
            elif logical_index == 7:
                return purchase.currency or ""
            elif logical_index == 8:
                return str(purchase.year) if purchase.year else ""
            elif logical_index == 9:
                return purchase.location_found or ""
            elif logical_index == 10:
                return str(purchase.quantity) if purchase.quantity else ""
            elif logical_index == 11:
                return purchase.comments or ""
            elif logical_index == 12:
                if purchase.ucoin_exchange:
                    return str(purchase.ucoin_exchange_count) if purchase.ucoin_exchange_count else "✅"
                elif purchase.ucoin_exchange_count == 0:
                    return "0"
                return ""
            elif logical_index == 13:
                return str(purchase.sold_count) if purchase.sold_count else ""
            elif logical_index == 14:
                return f"{purchase.sold_sum:.2f}" if purchase.sold_sum else ""
            elif logical_index == 15:
                # === AG: признак "закупка относится к серебру" ===
                return "✅" if getattr(purchase, 'ag', False) else ""
            return ""
        except Exception:
            return ""

    def _ag_column_index(self):
        """Логический индекс колонки AG (-1, если колонки нет)."""
        try:
            return self.COLUMN_KEYS.index('ag')
        except ValueError:
            return -1

    def _ensure_ag_column_in_model(self):
        """Гарантирует, что модель таблицы закупок видит 16-ю колонку AG.
        Интроспекция: ищем у модели списки/кортежи строк, длина которых равна
        текущему columnCount (это списки заголовков и ключей), и дописываем
        в них 'AG' / 'ag'. Работает ЛЮБЫЕ имена атрибутов в purchases_model.py,
        файл модели править не нужно."""
        model = self.model
        try:
            current = model.columnCount()
        except Exception:
            return False
        if current >= len(self.COLUMN_KEYS):
            return True
        patched = 0
        seen = set()
        names = list(vars(model).keys()) + \
            [n for n in dir(type(model)) if not n.startswith('__')]
        for name in names:
            if name in seen:
                continue
            seen.add(name)
            try:
                val = getattr(model, name)
            except Exception:
                continue
            if not isinstance(val, (list, tuple)) or len(val) != current:
                continue
            if not all(isinstance(x, str) for x in val):
                continue
            first = val[0] if val else ''
            is_keys = first.islower() and first.isascii()
            add = 'ag' if is_keys else 'AG'
            if add in val:
                continue
            if isinstance(val, list):
                val.append(add)
            else:
                setattr(model, name, val + (add,))
            patched += 1
        if patched:
            self.logger.info(
                f"✅ Модель закупок пропатчена для колонки AG: {patched} списк(а/ов)")
        return patched > 0

    def _on_purchases_cell_clicked(self, index):
        """Один клик по ячейке колонки AG переключает метку ✅/❌.
        ДЕБАУНС: двойной клик даёт два сигнала clicked — переключение
        откладывается на 250 мс и отменяется сигналом doubleClicked,
        поэтому двойной клик не переключает метку дважды."""
        if not index.isValid():
            return
        ag_col = self._ag_column_index()
        if ag_col < 0 or index.column() != ag_col:
            return
        if not hasattr(self, '_ag_click_timer'):
            self._ag_click_timer = QTimer()
            self._ag_click_timer.setSingleShot(True)
            self._ag_click_timer.timeout.connect(self._do_toggle_ag)
            self.purchases_table.doubleClicked.connect(
                lambda *a: self._ag_click_timer.stop())
        row = index.row()
        model = self.purchases_table.model()
        if model is not None and hasattr(model, 'mapToSource'):
            row = model.mapToSource(index).row()
        self._ag_click_pending_row = row
        self._ag_click_timer.start(250)

    def _do_toggle_ag(self):
        """Фактическое переключение AG после дебаунса одиночного клика."""
        row = getattr(self, '_ag_click_pending_row', -1)
        if not (0 <= row < len(self._filtered_purchases)):
            return
        purchase = self._filtered_purchases[row]
        if purchase is None:
            return
        self._set_purchase_ag(
            purchase, not bool(getattr(purchase, 'ag', False)))

    def _set_purchase_ag(self, purchase, value):
        """Пишет AG в БД (активная или архивная закупка), обновляет
        ячейку таблицы и показывает статус."""
        try:
            from database.models import Purchase, PurchaseArchive
            is_arch = bool(getattr(purchase, '_is_archived', False))
            model_cls = PurchaseArchive if is_arch else Purchase
            db_obj = self.db_manager.session.query(model_cls).get(purchase.id)
            if db_obj is not None:
                db_obj.ag = bool(value)
                self.db_manager.session.commit()
            try:
                purchase.ag = bool(value)
            except Exception:
                pass
            ag_col = self._ag_column_index()
            if ag_col >= 0:
                for row in range(self.model.rowCount()):
                    if self.model.get_purchase(row) is purchase:
                        idx = self.model.index(row, ag_col)
                        self.model.dataChanged.emit(
                            idx, idx, [Qt.DisplayRole])
                        break
            self.save_status_label.setText(
                f"🏷 AG для №Зак {getattr(purchase, 'purchase_number', '?')}: "
                f"{'✅' if value else '❌'}")
            self.save_status_label.setStyleSheet("color: #28a745; font-size: 11px;")
            QTimer.singleShot(
                2000,
                lambda: self.save_status_label.setStyleSheet(
                    "color: #666; font-size: 11px;"))
        except Exception as e:
            self.db_manager.session.rollback()
            self.logger.error(f"Ошибка сохранения AG: {e}")

    def _paste_to_selected_cells(self):
        """Вставка из буфера в выделенные ячейки таблицы закупок.
        Переопределяет версию mixin: сохранение идёт через _on_cell_edited
        (commit сразу, архивные строки пишутся в purchases_archive),
        сообщение КОМБИНИРОВАННОЕ — подтверждение сохранения не теряется."""
        table = getattr(self, 'purchases_table', None) or \
            getattr(self, 'table', None)
        if table is None:
            return
        clipboard = QApplication.clipboard()
        text = clipboard.text()
        if not text:
            return
        rows_data = []
        for line in text.strip().split("\n"):
            if "\t" in line:
                row = line.split("\t")
            else:
                row = line.split(",")
            rows_data.append([cell.strip() for cell in row])
        if not rows_data:
            return
        selected = table.selectionModel().selectedIndexes()
        if not selected:
            current = table.currentIndex()
            if current.isValid():
                selected = [current]
        if not selected:
            return
        selected = sorted(selected, key=lambda x: (x.row(), x.column()))
        start_row = min(i.row() for i in selected)
        start_col = min(i.column() for i in selected)
        source_rows = len(rows_data)
        source_cols = max(len(r) for r in rows_data) if rows_data else 0
        if source_rows == 0 or source_cols == 0:
            return
        model = table.model()
        for idx in selected:
            row = idx.row()
            col = idx.column()
            if model is not None and hasattr(model, 'mapToSource'):
                src = model.mapToSource(idx)
                row, col = src.row(), src.column()
            if not (0 <= row < len(self._filtered_purchases)):
                continue
            purchase = self._filtered_purchases[row]
            if purchase is None or col >= len(self.COLUMN_KEYS):
                continue
            column_key = self.COLUMN_KEYS[col]
            s_row = (idx.row() - start_row) % source_rows
            s_col = (idx.column() - start_col) % source_cols
            if s_col < len(rows_data[s_row]):
                value = rows_data[s_row][s_col]
            else:
                value = ""
            self._on_cell_edited(purchase, column_key, value)
        self.save_status_label.setText(
            f"📌 Вставлено в {len(selected)} ячеек | 💾 Сохранено в БД")
        self.save_status_label.setStyleSheet("color: #28a745; font-size: 11px;")
        QTimer.singleShot(
            3000,
            lambda: self.save_status_label.setStyleSheet(
                "color: #666; font-size: 11px;"))

    def _paste_single_value_to_selected(self, text):
        """Вставка ОДНОГО значения во все выделенные ячейки.
        Переопределяет mixin: сообщение комбинированное, сохранение
        через _on_cell_edited (включая архивные строки)."""
        table = getattr(self, 'purchases_table', None) or \
            getattr(self, 'table', None)
        if table is None:
            return
        selected = table.selectionModel().selectedIndexes()
        if not selected:
            current = table.currentIndex()
            if current.isValid():
                selected = [current]
        if not selected:
            return
        model = table.model()
        for idx in selected:
            row = idx.row()
            col = idx.column()
            if model is not None and hasattr(model, 'mapToSource'):
                src = model.mapToSource(idx)
                row, col = src.row(), src.column()
            if not (0 <= row < len(self._filtered_purchases)):
                continue
            purchase = self._filtered_purchases[row]
            if purchase is None or col >= len(self.COLUMN_KEYS):
                continue
            column_key = self.COLUMN_KEYS[col]
            self._on_cell_edited(purchase, column_key, text)
        self.save_status_label.setText(
            f"📌 Вставлено в {len(selected)} ячеек | 💾 Сохранено в БД")
        self.save_status_label.setStyleSheet("color: #28a745; font-size: 11px;")
        QTimer.singleShot(
            3000,
            lambda: self.save_status_label.setStyleSheet(
                "color: #666; font-size: 11px;"))

    def load_country_filter(self):
        """Загружает фильтр по странам"""
        try:
            current = self.country_filter.currentData()
            self.country_filter.blockSignals(True)
            self.country_filter.clear()
            self.country_filter.addItem("Все страны", None)
            
            country_ids = set()
            for purchase in self._filtered_purchases:
                if purchase and purchase.import_country_id:
                    country_ids.add(purchase.import_country_id)
            
            if country_ids:
                countries = self.db_manager.session.query(ImportCountry).filter(
                    ImportCountry.id.in_(country_ids)
                ).order_by(ImportCountry.name).all()
                for country in countries:
                    self.country_filter.addItem(country.name, country.id)
            
            if current:
                idx = self.country_filter.findData(current)
                if idx >= 0:
                    self.country_filter.setCurrentIndex(idx)
        except Exception as e:
            self.logger.error(f"Ошибка загрузки фильтра стран: {e}")
        finally:
            self.country_filter.blockSignals(False)
    
    def _restore_column_state(self):
        """Восстанавливает состояние колонок из настроек и разрешает дальнейшее сохранение"""
        try:
            header = self.purchases_table.horizontalHeader()
            saved_order = self.settings.value('purchases_column_order')
            if saved_order and isinstance(saved_order, list):
                for vi, li in enumerate(saved_order):
                    li = int(li)
                    if li < len(self.COLUMN_HEADERS):
                        cv = header.visualIndex(li)
                        if cv != vi:
                            header.moveSection(cv, vi)
            saved_widths = self.settings.value('purchases_column_widths')
            if saved_widths and isinstance(saved_widths, list):
                for li, w in enumerate(saved_widths):
                    if li < len(self.COLUMN_HEADERS) and isinstance(w, (int, float)) and w > 0:
                        vi = header.visualIndex(li)
                        self.purchases_table.setColumnWidth(vi, int(w))
        except Exception as e:
            self.logger.debug(f"Ошибка восстановления состояния колонок: {e}")
        # Разрешаем сохранение ТОЛЬКО после восстановления
        self._purchases_cols_ready = True
   
    def _on_column_moved(self, logical_index, old_visual_index, new_visual_index):
        """Обработчик перемещения колонки"""
        if not getattr(self, '_purchases_cols_ready', False):
            return
        header = self.purchases_table.horizontalHeader()
        order = [header.logicalIndex(vp) for vp in range(header.count())]
        self.settings.setValue('purchases_column_order', order)
    
    def _on_column_resized(self, logical_index, old_size, new_size):
        """Обработчик изменения размера колонки"""
        if not getattr(self, '_purchases_cols_ready', False):
            return  # защита от перезаписи дефолтами во время init_ui
        header = self.purchases_table.horizontalHeader()
        widths = []
        for li in range(len(self.COLUMN_HEADERS)):
            vi = header.visualIndex(li)
            w = self.purchases_table.columnWidth(vi)
            widths.append(w)
        self.settings.setValue('purchases_column_widths', widths)
    
    def _get_source_row(self, proxy_row):
        """Возвращает индекс в source модели"""
        model = self.purchases_table.model()
        proxy_index = model.index(proxy_row, 0)
        if hasattr(model, 'mapToSource'):
            source_index = model.mapToSource(proxy_index)
            return source_index.row()
        return proxy_row
    
    # ========== ОБРАБОТЧИК РЕДАКТИРОВАНИЯ ==========
    
    def _on_cell_edited(self, purchase, column_key, new_value):
        """Обработчик редактирования ячейки.
        ВАЖНО: архивные строки на закладке "Закупки" — временные объекты
        TempPurchase, не зарегистрированные в сессии SQLAlchemy: раньше
        правки в них НЕ писались в purchases_archive и исчезали при
        обновлении списка и перезапуске программы.
        Теперь: для архива загружается реальный объект PurchaseArchive,
        правка применяется к нему и коммитится; для активных строк —
        как раньше, правка ORM-объекта Purchase."""
        if new_value is None and column_key not in ['in_collection',
                                                    'ucoin_exchange', 'ag']:
            return
        old_value = getattr(purchase, column_key, None)
        str_old = str(old_value) if old_value is not None else ""
        str_new = str(new_value) if new_value is not None else ""
        if str_old == str_new:
            return
        self.logger.info(
            f"EDIT: column={column_key}, old='{str_old}', new='{str_new}'")
        is_arch = bool(getattr(purchase, '_is_archived', False))

        # ========== АРХИВНАЯ СТРОКА: пишем в purchases_archive ==========
        if is_arch:
            try:
                db_obj = self.db_manager.session.query(PurchaseArchive).get(
                    purchase.id)
                if db_obj is None:
                    self.logger.warning(
                        f"Архивная закупка ID {purchase.id} не найдена в БД")
                    return
                self._apply_edit_to_orm(db_obj, column_key, new_value)
                self.db_manager.session.commit()
                # Зеркалим в временный объект в памяти
                for attr in ('in_collection', 'collection_price',
                             'purchase_number', 'purchase_batch',
                             'import_country_id', 'continent',
                             'denomination_value', 'currency', 'year',
                             'location_found', 'quantity', 'comments',
                             'ucoin_exchange', 'ucoin_exchange_count',
                             'sold_count', 'sold_sum', 'total',
                             'manual_costs', 'ag'):
                    try:
                        setattr(purchase, attr, getattr(db_obj, attr))
                    except Exception:
                        pass
                try:
                    purchase.import_country = db_obj.import_country
                except Exception:
                    pass
                # Undo-стек
                self._last_changes.append([{
                    'purchase_id': purchase.id,
                    'field': column_key,
                    'old_value': old_value,
                    'new_value': new_value,
                    'archived': True,
                }])
                if len(self._last_changes) > 100:
                    self._last_changes.pop(0)
                self._redo_stack.clear()
                self.save_status_label.setText(
                    f"💾 Сохранено в архиве: {column_key}")
                self.save_status_label.setStyleSheet(
                    "color: #28a745; font-size: 11px;")
                QTimer.singleShot(
                    2000,
                    lambda: self.save_status_label.setStyleSheet(
                        "color: #666; font-size: 11px;"))
                self._refresh_edited_cell(purchase, column_key)
                self._update_total_quantity()
                return
            except Exception as e:
                self.db_manager.session.rollback()
                self.logger.error(f"Ошибка сохранения архивной правки: {e}")
                self.save_status_label.setText(f"❌ Ошибка: {str(e)[:30]}")
                self.save_status_label.setStyleSheet(
                    "color: #dc3545; font-size: 11px;")
                return

        # ========== АКТИВНАЯ СТРОКА: как раньше ==========
        self._apply_edit_to_orm(purchase, column_key, new_value)
        # Сохраняем в Undo стек
        change = {
            'purchase_id': purchase.id,
            'field': column_key,
            'old_value': old_value,
            'new_value': new_value
        }
        self._last_changes.append([change])
        if len(self._last_changes) > 100:
            self._last_changes.pop(0)
        self._redo_stack.clear()
        # Отмечаем как изменённое
        self._dirty_ids.add(purchase.id)
        # НЕМЕДЛЕННО СОХРАНЯЕМ В БД
        try:
            self.db_manager.session.commit()
            self._dirty_ids.clear()
            self.save_status_label.setText("💾 Изменения сохранены")
            self.save_status_label.setStyleSheet("color: #28a745; font-size: 11px;")
            QTimer.singleShot(2000, lambda: self.save_status_label.setStyleSheet("color: #666; font-size: 11px;"))
        except Exception as e:
            self.db_manager.session.rollback()
            self.logger.error(f"Ошибка сохранения: {e}")
            self.save_status_label.setText(f"❌ Ошибка: {str(e)[:30]}")
            self.save_status_label.setStyleSheet("color: #dc3545; font-size: 11px;")
        # Обновляем отображение ячейки
        self._refresh_edited_cell(purchase, column_key)
        # Обновляем сумму по колонке "КОЛ"
        self._update_total_quantity()

    def _apply_edit_to_orm(self, obj, column_key, new_value):
        """Применяет правку ячейки к ORM-объекту закупки.
        Работает и с Purchase, и с PurchaseArchive (наборы полей одинаковы)."""
        if column_key == 'in_collection':
            obj.in_collection = bool(new_value)
        elif column_key == 'collection_price':
            try:
                obj.collection_price = float(new_value) if new_value else None
            except (ValueError, TypeError):
                obj.collection_price = None
        elif column_key == 'purchase_number':
            obj.purchase_number = str(new_value) if new_value else None
        elif column_key == 'purchase_batch':
            obj.purchase_batch = str(new_value) if new_value else None
        elif column_key == 'country':
            if new_value and str(new_value).strip():
                country_name = str(new_value).strip()
                country = self.db_manager.session.query(ImportCountry).filter_by(
                    name=country_name).first()
                if not country:
                    country = ImportCountry(name=country_name)
                    self.db_manager.session.add(country)
                    self.db_manager.session.flush()
                obj.import_country_id = country.id
                obj.import_country = country
            else:
                obj.import_country_id = None
                obj.import_country = None
        elif column_key == 'continent':
            obj.continent = str(new_value) if new_value else None
        elif column_key == 'denomination':
            obj.denomination_value = str(new_value) if new_value else None
        elif column_key == 'currency':
            obj.currency = str(new_value) if new_value else None
        elif column_key == 'year':
            try:
                obj.year = int(new_value) if new_value else None
            except (ValueError, TypeError):
                obj.year = None
        elif column_key == 'location_found':
            obj.location_found = str(new_value) if new_value else None
        elif column_key == 'quantity':
            try:
                obj.quantity = int(new_value) if new_value else 1
            except (ValueError, TypeError):
                obj.quantity = 1
        elif column_key == 'comments':
            obj.comments = str(new_value) if new_value else None
        elif column_key == 'ucoin_exchange':
            try:
                num_value = int(new_value) if new_value else 0
                obj.ucoin_exchange = num_value > 0
                obj.ucoin_exchange_count = num_value
            except (ValueError, TypeError):
                obj.ucoin_exchange = False
                obj.ucoin_exchange_count = 0
        elif column_key == 'sold_count':
            obj.sold_count = str(new_value) if new_value else None
        elif column_key == 'sold_sum':
            try:
                obj.sold_sum = float(new_value) if new_value else None
            except (ValueError, TypeError):
                obj.sold_sum = None
        elif column_key == 'ag':
            if isinstance(new_value, bool):
                obj.ag = new_value
            else:
                s = str(new_value or '').strip().lower()
                obj.ag = s in ('1', 'true', '✅', 'да', 'yes', 'ag', '+')
        obj.updated_at = datetime.now()

    def _refresh_edited_cell(self, purchase, column_key):
        """Точечно перерисовывает отредактированную ячейку таблицы закупок."""
        try:
            col_index = self.COLUMN_KEYS.index(column_key)
        except ValueError:
            return
        for row in range(self.model.rowCount()):
            if self.model.get_purchase(row) is purchase:
                idx = self.model.index(row, col_index)
                self.model.dataChanged.emit(
                    idx, idx, [Qt.DisplayRole, Qt.ForegroundRole])
                break
   
    def closeEvent(self, event):
        """Обработчик закрытия"""
        self._save_column_filters_to_json()
        super().closeEvent(event)
        
    def _show_autofill_dialog(self):
        """Диалог автозаполнения из UCOIN с автоматическим получением URL из браузера"""
        
        # Получаем текущий URL из браузера закупок
        current_url = self._get_current_browser_url()
        
        dialog = QDialog(self)
        dialog.setWindowTitle("🔄 Автозаполнение из UCOIN")
        dialog.setMinimumWidth(500)
        dialog.setModal(True)
        
        layout = QVBoxLayout(dialog)
        layout.setContentsMargins(15, 15, 15, 15)
        layout.setSpacing(10)
        
        title = QLabel("📥 Заполнение поля «Продано» из обмена на UCOIN")
        title.setStyleSheet("font-weight: bold; font-size: 13px; color: #4a6fa5;")
        title.setWordWrap(True)
        layout.addWidget(title)
        
        info = QLabel(
            "1. URL подставляется автоматически из открытой вкладки браузера\n"
            "2. Выберите покупателя из списка (ники из незакрытых сделок)\n"
            "3. Монеты будут найдены по стране, году, номиналу\n"
            "4. В поле «Продано» будет записан НИК покупателя\n"
            "5. № из сделки будет записан в колонку №Пок закупки"
        )
        info.setStyleSheet("color: #666; font-size: 11px;")
        info.setWordWrap(True)
        layout.addWidget(info)
        
        # Никнейм с данными из незакрытых сделок
        layout.addWidget(QLabel("Покупатель (НИК):"))
        
        nick_layout = QHBoxLayout()
        self.autofill_nickname = QComboBox()
        self.autofill_nickname.setEditable(True)
        self.autofill_nickname.setMinimumHeight(30)
        self.autofill_nickname.setMinimumWidth(200)
        
        # Загружаем ники ТОЛЬКО из НЕЗАКРЫТЫХ СДЕЛОК (ВСЕ, без limit)
        nick_list = self._load_open_nicknames_from_deals()
        self._nick_data = {}
        
        for item in nick_list:
            display_text = f"{item['name']} (№{item['number']})"
            self.autofill_nickname.addItem(display_text, item['name'])
            self._nick_data[item['name']] = {
                'number': item['number'],
                'deal_id': item['deal_id']
            }
        
        # === ДОБАВЛЯЕМ ВСЕ СОХРАНЁННЫЕ НИКИ ИЗ ИСТОРИИ ===
        saved_nicks = self.settings.value('autofill_nicknames', [])
        if isinstance(saved_nicks, str):
            saved_nicks = [saved_nicks]
        
        # Добавляем только те ники, которых нет в списке
        existing_nicks = set(self._nick_data.keys())
        for nick in saved_nicks:
            if nick and nick not in existing_nicks:
                self.autofill_nickname.addItem(nick, nick)
                self._nick_data[nick] = {
                    'number': None,  # Нет номера сделки для сохранённых ников
                    'deal_id': None
                }
                self.logger.info(f"📋 Добавлен сохранённый ник: {nick}")
        
        # Если ников нет, добавляем пустую строку для ручного ввода
        if self.autofill_nickname.count() == 0:
            self.autofill_nickname.addItem("", "")
            self.autofill_nickname.setEditable(True)
            self.autofill_nickname.setPlaceholderText("введите ник вручную...")
        else:
            self.autofill_nickname.setCurrentIndex(0)
            self.autofill_nickname.setPlaceholderText("выберите покупателя")
        
        nick_layout.addWidget(self.autofill_nickname, 1)
        
        clear_history_btn = QPushButton("🗑️")
        clear_history_btn.setFixedSize(30, 30)
        clear_history_btn.setToolTip("Очистить историю ников")
        clear_history_btn.clicked.connect(self._clear_nick_history)
        nick_layout.addWidget(clear_history_btn)
        
        layout.addLayout(nick_layout)
        
        # Ссылка на обмен (автоматически из браузера)
        layout.addWidget(QLabel("Ссылка на обмен UCOIN (авто из браузера):"))
        
        url_layout = QHBoxLayout()
        self.autofill_url = QLineEdit()
        self.autofill_url.setMinimumHeight(30)
        self.autofill_url.setMinimumWidth(200)
        self.autofill_url.setReadOnly(True)
        
        if current_url:
            self.autofill_url.setText(current_url)
            self.autofill_url.setStyleSheet("background-color: #e8f0fe; color: #4a6fa5;")
        else:
            self.autofill_url.setPlaceholderText("❌ Не удалось получить URL из браузера. Откройте страницу обмена.")
            self.autofill_url.setStyleSheet("background-color: #ffe0e0; color: #dc3545;")
        
        url_layout.addWidget(self.autofill_url, 1)
        
        refresh_url_btn = QPushButton("🔄")
        refresh_url_btn.setFixedSize(30, 30)
        refresh_url_btn.setToolTip("Обновить URL из браузера")
        refresh_url_btn.clicked.connect(self._refresh_autofill_url)
        url_layout.addWidget(refresh_url_btn)
        
        layout.addLayout(url_layout)
        
        layout.addStretch()
        
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        
        cancel_btn = QPushButton("❌ Отмена")
        cancel_btn.setMinimumHeight(32)
        cancel_btn.setMinimumWidth(100)
        cancel_btn.clicked.connect(dialog.reject)
        btn_layout.addWidget(cancel_btn)
        
        ok_btn = QPushButton("✅ ОК")
        ok_btn.setMinimumHeight(32)
        ok_btn.setMinimumWidth(100)
        ok_btn.setStyleSheet("background-color: #4CAF50; color: white; font-weight: bold; border-radius: 3px;")
        
        if not current_url:
            ok_btn.setEnabled(False)
            ok_btn.setToolTip("Сначала откройте страницу обмена в браузере")
        
        ok_btn.clicked.connect(lambda: self._start_autofill(dialog))
        btn_layout.addWidget(ok_btn)
        
        layout.addLayout(btn_layout)
        
        dialog.exec()

    def _load_open_nicknames_from_deals(self):
        """Загружает ники из ВСЕХ НЕЗАКРЫТЫХ сделок (без ограничения)"""
        try:
            from database.models import Deal
            
            # Получаем ВСЕ НЕЗАКРЫТЫЕ сделки без limit()
            deals = self.db_manager.session.query(Deal).filter(
                Deal.buyer.isnot(None),
                Deal.buyer != "",
                Deal.number.isnot(None),
                Deal.number != "",
                (Deal.delivery.is_(None) | (Deal.delivery != '✅'))
            ).order_by(Deal.number.desc()).all()  # <-- БЕЗ limit()
            
            nick_list = []
            seen_nicks = set()
            
            for deal in deals:
                if deal.buyer and deal.buyer not in seen_nicks:
                    seen_nicks.add(deal.buyer)
                    try:
                        num_value = int(deal.number) if deal.number else 0
                    except (ValueError, TypeError):
                        num_value = 0
                    
                    nick_list.append({
                        'name': deal.buyer,
                        'number': deal.number,
                        'number_value': num_value,
                        'deal_id': deal.id
                    })
            
            nick_list.sort(key=lambda x: x['number_value'], reverse=True)
            self.logger.info(f"📋 Загружено {len(nick_list)} ников из незакрытых сделок")
            return nick_list
        except Exception as e:
            self.logger.error(f"Ошибка загрузки ников из сделок: {e}")
            return []

    def _refresh_autofill_url(self):
        """Обновляет URL из браузера в диалоге"""
        current_url = self._get_current_browser_url()
        
        if hasattr(self, 'autofill_url'):
            if current_url:
                self.autofill_url.setText(current_url)
                self.autofill_url.setStyleSheet("background-color: #e8f0fe; color: #4a6fa5;")
                
                # Включаем кнопку ОК
                for btn in self.autofill_url.parent().parent().findChildren(QPushButton):
                    if btn.text() == "✅ ОК":
                        btn.setEnabled(True)
                        btn.setToolTip("")
            else:
                self.autofill_url.setText("")
                self.autofill_url.setPlaceholderText("❌ Не удалось получить URL из браузера. Откройте страницу обмена.")
                self.autofill_url.setStyleSheet("background-color: #ffe0e0; color: #dc3545;")
                
                # Отключаем кнопку ОК
                for btn in self.autofill_url.parent().parent().findChildren(QPushButton):
                    if btn.text() == "✅ ОК":
                        btn.setEnabled(False)
                        btn.setToolTip("Сначала откройте страницу обмена в браузере")
    
    def _get_current_browser_url(self):
        """Возвращает текущий URL из браузера закупок"""
        try:
            if hasattr(self, 'embedded_browser') and self.embedded_browser:
                web_view = self.embedded_browser.get_current_web_view()
                if web_view:
                    url = web_view.url().toString()
                    if url and 'ucoin.net/swap-list' in url:
                        return url
            return None
        except Exception as e:
            self.logger.error(f"Ошибка получения URL из браузера: {e}")
            return None


    def _apply_filters(self):
        """Применяет фильтры с защитой от удалённых из БД объектов"""
        try:
            self._apply_filters_inner()
        except Exception as e:
            # В списке есть удалённые объекты — перезагружаем закупки из БД и повторяем
            self.logger.warning(f"_apply_filters: {e} — перезагружаю список закупок")
            try:
                from database.models import Purchase
                self._all_purchases = self.db_manager.session.query(Purchase).all()
                # ВАЖНО: пересобираем _all_data с учётом архива, иначе архив потеряется
                if self.show_archive_check.isChecked():
                    self._all_data = self._all_purchases + self.load_archive_data()
                else:
                    self._all_data = self._all_purchases
            except Exception:
                pass
            try:
                self._apply_filters_inner()
            except Exception as e2:
                self.logger.error(f"_apply_filters после перезагрузки: {e2}")

    def _apply_filters_inner(self):
        """Внутренняя реализация применения фильтров.
        ВАЖНО: источник данных — self._all_data (активные + архив при
        включённом чекбоксе), а НЕ self._all_purchases.
        НОВОЕ: после применения фильтров ВОССТАНАВЛИВАЕТСЯ выбранная
        ранее сортировка (сброс модели больше её не сбивает):
        1) до пересборки модели запоминаем индикатор сортировки шапки;
        2) после пересборки повторно применяем сортировку к
           отфильтрованному списку и возвращаем стрелку индикатора."""
        source = getattr(self, '_all_data', None)
        if source is None:
            source = self._all_purchases
        filtered = list(source)
        country_id = self.country_filter.currentData()
        if country_id:
            filtered = [p for p in filtered
                        if getattr(p, 'import_country_id', None) == country_id]
        # Фильтры по колонкам
        if self._column_filters:
            filtered = self._apply_column_filters_to_list(filtered)
        # === ЗАПОМИНАЕМ СОРТИРОВКУ ДО ПЕРЕСБОРКИ МОДЕЛИ ===
        header = self.purchases_table.horizontalHeader()
        saved_section = header.sortIndicatorSection()
        saved_order = header.sortIndicatorOrder()
        saved_shown = header.isSortIndicatorShown()
        self._filtered_purchases = filtered
        # Обновляем модель
        if hasattr(self.model, '_data'):
            self.model.beginResetModel()
            self.model._data = filtered
            self.model.endResetModel()
        else:
            self.model.set_data(filtered)
        # === ВОССТАНАВЛИВАЕМ СОРТИРОВКУ ПОСЛЕ ПЕРЕСБОРКИ ===
        self._reapply_current_sort(saved_section, saved_order, saved_shown)
        self.load_country_filter()
        # Обновляем сумму по колонке "КОЛ"
        self._update_total_quantity()

    def _reapply_current_sort(self, saved_section, saved_order, saved_shown):
        """Повторно применяет текущую сортировку после смены фильтра.
        ЗАЩИТА: если сортировку НИКОГДА не выбирали (стрелка не видна и
        состояния миксина нет) — ничего не применяем, иначе дефолтный
        sortIndicatorSection()=0 принимался за сортировку по колонке 0."""
        header = self.purchases_table.horizontalHeader()
        section = None
        order = saved_order
        # === 1) Состояние сортировки миксина (если есть) ===
        state = getattr(self, '_sort_state', None)
        if isinstance(state, (tuple, list)) and len(state) == 2:
            try:
                section = int(state[0])
                order = state[1]
            except (TypeError, ValueError):
                section = None
        else:
            for col_attr, ord_attr in (('_sort_column', '_sort_order'),
                                       ('_sort_col', '_sort_ord'),
                                       ('sort_column', 'sort_order'),
                                       ('_current_sort_column',
                                        '_current_sort_order')):
                if hasattr(self, col_attr) and hasattr(self, ord_attr):
                    try:
                        section = int(getattr(self, col_attr))
                        order = getattr(self, ord_attr)
                    except (TypeError, ValueError):
                        section = None
                    break
        # === 2) Нет состояния миксина — доверяем шапке, ТОЛЬКО если
        # стрелка сортировки реально отображалась ===
        if section is None:
            if saved_shown and saved_section is not None and saved_section >= 0:
                section = saved_section
                order = saved_order
            else:
                return   # сортировку не выбирали — не навязываем
        # === 3) Применяем сортировку методом миксина (если есть) ===
        applied = False
        for name in ('_apply_sorting', '_apply_sort', '_apply_current_sort',
                     '_reapply_sort', '_sort_filtered', '_sort_data'):
            fn = getattr(self, name, None)
            if callable(fn):
                try:
                    import inspect
                    params = [p for p in inspect.signature(fn).parameters
                              if p != 'self']
                    if len(params) >= 2:
                        fn(section, order)
                    elif len(params) == 1:
                        fn(section)
                    else:
                        fn()
                    applied = True
                    break
                except Exception:
                    continue
        # === 4) Фолбэк: штатный механизм view (работает, если модель
        # реализует sort()); иначе порядок оставит естественным ===
        if not applied:
            model = self.purchases_table.model()
            model_has_sort = model is not None and \
                'sort' in type(model).__dict__
            if model_has_sort:
                try:
                    if not self.purchases_table.isSortingEnabled():
                        self.purchases_table.setSortingEnabled(True)
                    self.purchases_table.sortByColumn(section, order)
                    applied = True
                except Exception:
                    pass
            else:
                self.logger.debug(
                    f"Сортировку не удалось восстановить автоматически "
                    f"(колонка {section}): модель не реализует sort(), "
                    f"метод миксина не найден")
        # === 5) Стрелку индикатора восстанавливаем всегда ===
        try:
            header.setSortIndicator(section, order)
            header.setSortIndicatorShown(True)
        except Exception:
            pass
      
    def scan_and_list_selected(self):
        """ПКМ → «📷 Сканировать и выставить на Meshok».
        Описание парсится из открытой вкладки браузера закупок.
        internalId = №Зак + МЕСТО (МЕСТО может быть пустым).
        ПОСЛЕ УСПЕШНОГО ВЫСТАВЛЕНИЯ: автоматически проставляет 'М' в колонке
        'Продано' (sold_count) у этой закупки."""
        try:
            table = getattr(self, 'purchases_table', None) or getattr(self, 'table', None)
            if table is None:
                QMessageBox.warning(self, 'Предупреждение',
                                    'Таблица закупок не инициализирована.')
                return
            index = table.currentIndex()
            if index is None or not index.isValid():
                QMessageBox.warning(self, 'Предупреждение',
                                    'Выделите строку закупки.')
                return
            row = index.row()
            source_row = row
            try:
                model = table.model()
                if model is not None and hasattr(model, 'mapToSource'):
                    source_row = model.mapToSource(index).row()
            except Exception:
                source_row = row
            purchases = getattr(self, '_filtered_purchases', None) or []
            if not (0 <= source_row < len(purchases)):
                QMessageBox.warning(self, 'Предупреждение',
                                    'Не удалось определить выбранную закупку.')
                return
            purchase = purchases[source_row]
            # === Артикул: №Зак + МЕСТО (МЕСТО может быть пустым) ===
            num = str(getattr(purchase, 'purchase_number', None) or '').strip()
            place = str(getattr(purchase, 'location_found', None) or '').strip()
            internal_id = f"{num}_{place}" if num and place else (num or place)
            source_data = {
                'country': (getattr(getattr(purchase, 'import_country', None),
                                    'name', '') or ''),
                'continent': getattr(purchase, 'continent', None) or '',
                'denomination': getattr(purchase, 'denomination_value', None) or '',
                'currency': getattr(purchase, 'currency', None) or '',
                'year': getattr(purchase, 'year', None) or '',
                'description': getattr(purchase, 'comments', None) or '',
                'price': (getattr(purchase, 'collection_price', None)
                          or getattr(purchase, 'sold_sum', None)
                          or getattr(purchase, 'total', None) or 0),
                'purchase_id': getattr(purchase, 'id', None),
                'purchase_number': num,
                'location_found': place,
                'internal_id': internal_id,
            }
            # Текущая вкладка браузера закупок (для парсинга описания)
            web_view = None
            try:
                eb = getattr(self, 'embedded_browser', None)
                if eb is not None and hasattr(eb, 'get_current_web_view'):
                    web_view = eb.get_current_web_view()
            except Exception:
                web_view = None
            from gui.widgets.coin_scanner.scan_list_dialog import ScanAndListDialog
            from PySide6.QtWidgets import QDialog
            dlg = ScanAndListDialog(None, self.db_manager, self.window(), self,
                                    source=source_data, web_view=web_view)
            result = dlg.exec()

            # === АВТОПРОСТАНОВКА 'М' В КОЛОНКЕ 'ПРОДАНО' ===
            if result == QDialog.Accepted:
                self._mark_as_sold_on_meshok(purchase)

        except Exception as e:
            self.logger.error(f"Ошибка scan_and_list_selected: {e}")
            import traceback
            traceback.print_exc()
            QMessageBox.critical(self, 'Ошибка', str(e))

    def _mark_as_sold_on_meshok(self, purchase):
        """Автоматически проставляет 'М' в колонку 'Продано' (sold_count)
        после успешного выставления на Meshok через сканирование листа.
        Сохраняет в БД и обновляет отображение в таблице закупок."""
        if not purchase or not getattr(purchase, 'id', None):
            return
        try:
            # 1) Находим свежий объект из БД (purchase из _filtered_purchases
            #    может быть откреплён от сессии после длительных операций)
            from database.models import Purchase
            db_purchase = self.db_manager.session.query(Purchase).get(purchase.id)
            if not db_purchase:
                self.logger.warning(
                    f"⚠️ Закупка ID {purchase.id} не найдена в БД для пометки 'М'")
                return
            # 2) Ставим 'М' только если колонка пустая —
            #    не перезатираем вручную введённые ники покупателей
            current = getattr(db_purchase, 'sold_count', None) or ''
            if current.strip():
                self.logger.info(
                    f"ℹ️ Колонка 'Продано' уже заполнена ({current!r}) — "
                    f"не перезаписываем для закупки ID {purchase.id}")
                return
            db_purchase.sold_count = 'М'
            db_purchase.updated_at = datetime.now()
            self.db_manager.session.commit()
            self.logger.info(
                f"✅ Закупка ID {purchase.id}: в колонку 'Продано' проставлено 'М'")

            # 3) Обновляем зеркало в _filtered_purchases (для корректной
            #    сортировки/фильтрации без перезагрузки всей таблицы)
            for p in self._filtered_purchases:
                if getattr(p, 'id', None) == purchase.id:
                    p.sold_count = 'М'
                    break
            for p in self._all_purchases:
                if getattr(p, 'id', None) == purchase.id:
                    p.sold_count = 'М'
                    break

            # 4) Обновляем только эту ячейку в таблице (без полной перерисовки)
            try:
                col_index = self.COLUMN_KEYS.index('sold_count')
                for r in range(self.model.rowCount()):
                    mp = self.model.get_purchase(r)
                    if mp and getattr(mp, 'id', None) == purchase.id:
                        idx = self.model.index(r, col_index)
                        self.model.dataChanged.emit(
                            idx, idx, [Qt.DisplayRole, Qt.ForegroundRole])
                        break
            except (ValueError, Exception) as e:
                self.logger.debug(f"Не удалось обновить ячейку точечно: {e}")

            # 5) Уведомление в статус-баре
            if hasattr(self, 'save_status_label'):
                self.save_status_label.setText(
                    f"✅ Выставлено на Meshok | 'Продано' = 'М' (ID {purchase.id})")
                self.save_status_label.setStyleSheet(
                    "color: #28a745; font-size: 11px;")
                QTimer.singleShot(
                    4000,
                    lambda: self.save_status_label.setStyleSheet(
                        "color: #666; font-size: 11px;"))
        except Exception as e:
            self.logger.error(f"Ошибка пометки 'М' для закупки {purchase.id}: {e}")
            try:
                self.db_manager.session.rollback()
            except Exception:
                pass