# -*- coding: utf-8 -*-

"""
Интерфейс для вкладки продажи серебра
"""

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel,
    QFrame, QComboBox, QLineEdit, QScrollArea, QSizePolicy,
    QTableView, QHeaderView, QSplitter
)
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QColor

from .silver_model import SilverTableModel
from .silver_delegate import SilverDelegate


class SilverUIMixin:
    """Примесь с методами создания UI для серебра"""

    def _create_stats_header(self):
        """Создает современную шапку статистики (тёмная тема)"""
        stats_frame = QFrame()
        stats_frame.setFrameShape(QFrame.StyledPanel)
        stats_frame.setStyleSheet("""
            QFrame {
                background-color: #16213e;
                border: 1px solid #2a2a4a;
                border-radius: 6px;
                padding: 0px;
                margin-bottom: 5px;
            }
        """)
        main_layout = QHBoxLayout()
        main_layout.setSpacing(6)
        main_layout.setContentsMargins(10, 6, 10, 6)
        stats_frame.setLayout(main_layout)

        # БЛОК 1: Количество
        block1 = self._create_stats_block([
            ("Куплено", "total_purchased_label", "7c74ff"),
            ("Остаток", "total_remaining_label", "a8a8d0"),
            ("Продано", "total_sold_count_label", "28a745"),
        ])
        main_layout.addWidget(block1)

        # БЛОК 2: В коллекцию
        block2 = self._create_stats_block([
            ("В коллекцию", "total_collection_count_label", "ff9800"),
            ("Сумма в коллекцию", "total_collection_sum_label", "ff9800"),
        ])
        main_layout.addWidget(block2)

        # БЛОК 3: Суммы
        block3 = self._create_stats_block([
            ("Сумма закупки", "total_purchase_sum_label", "ff6b6b"),
            ("Сумма продаж", "total_sales_sum_label", "28a745"),
        ])
        main_layout.addWidget(block3)

        # БЛОК 4: Проценты
        block4 = self._create_stats_block([
            ("Прибыль от продаж", "sales_percent_label", "28a745"),
            ("Общая прибыль", "total_percent_label", "28a745"),
            ("Доля коллекции", "collection_percent_label", "ff9800"),
        ])
        main_layout.addWidget(block4)

        # Растягиваем блоки
        main_layout.setStretchFactor(block1, 1)
        main_layout.setStretchFactor(block2, 1)
        main_layout.setStretchFactor(block3, 1)
        main_layout.setStretchFactor(block4, 2)
        return stats_frame

    def _create_stats_block(self, items):
        """Создает блок статистики (тёмная тема)"""
        block = QWidget()
        block.setStyleSheet("""
            QWidget {
                background-color: rgba(255, 255, 255, 0.05);
                border-radius: 4px;
                padding: 2px 8px;
            }
        """)
        layout = QHBoxLayout()
        layout.setSpacing(15)
        layout.setContentsMargins(5, 2, 5, 2)
        block.setLayout(layout)

        for label_text, attr_name, color in items:
            widget = QWidget()
            widget_layout = QVBoxLayout()
            widget_layout.setSpacing(0)
            widget_layout.setContentsMargins(0, 0, 0, 0)
            widget.setLayout(widget_layout)

            label = QLabel(label_text)
            label.setStyleSheet("color: #8888aa; font-size: 10px; letter-spacing: 0.5px;")
            widget_layout.addWidget(label)

            value_label = QLabel("0")
            value_label.setStyleSheet(f"font-weight: bold; color: #{color}; font-size: 20px;")
            setattr(self, attr_name, value_label)
            widget_layout.addWidget(value_label)
            layout.addWidget(widget)

            # Разделитель
            sep = QFrame()
            sep.setFrameShape(QFrame.VLine)
            sep.setFrameShadow(QFrame.Sunken)
            sep.setFixedWidth(2)
            sep.setStyleSheet("background-color: #2a2a4a;")
            layout.addWidget(sep)
        return block

    def _get_theme(self):
        """Возвращает словарь текущей темы (поднимаясь к главному окну)"""
        try:
            w = self.parent()
            while w is not None:
                tm = getattr(w, 'theme_manager', None)
                if tm is not None:
                    return tm.current_theme
                w = w.parent()
        except Exception:
            pass
        return {}

    def _create_toolbar(self):
        """Создает панель инструментов (тёмная тема)"""
        toolbar = QFrame()
        toolbar.setFrameShape(QFrame.StyledPanel)
        toolbar.setStyleSheet("""
            QFrame {
                background-color: #16213e;
                border: 1px solid #2a2a4a;
                border-radius: 6px;
                padding: 3px;
            }
            QLabel { color: #e4e4ef; }
        """)
        self.toolbar_layout = QHBoxLayout()
        self.toolbar_layout.setContentsMargins(5, 3, 5, 3)
        self.toolbar_layout.setSpacing(3)

        btn_style = """
            QPushButton {
                background-color: #262640;
                color: #e4e4ef;
                border: 1px solid #3d3d5c;
                border-radius: 6px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #6c63ff;
                color: #ffffff;
                border-color: #6c63ff;
            }
        """

        # Кнопки действий
        self.add_btn = QPushButton("➕ Новая закупка")
        self.add_btn.clicked.connect(self.add_purchase)
        self.add_btn.setMinimumHeight(30)
        self.add_btn.setStyleSheet(btn_style)
        self.toolbar_layout.addWidget(self.add_btn)

        self.delete_btn = QPushButton("🗑️ Удалить")
        self.delete_btn.clicked.connect(self.delete_selected_purchase)
        self.delete_btn.setMinimumHeight(30)
        self.delete_btn.setStyleSheet(btn_style.replace('#6c63ff', '#dc3545'))
        self.toolbar_layout.addWidget(self.delete_btn)

        sep = QFrame()
        sep.setFrameShape(QFrame.VLine)
        sep.setFrameShadow(QFrame.Sunken)
        sep.setFixedSize(2, 28)
        self.toolbar_layout.addWidget(sep)

        # Фильтр
        self.toolbar_layout.addWidget(QLabel("Фильтр:"))
        self.filter_combo = QComboBox()
        self.filter_combo.addItem("📊 Все монеты", "all")
        self.filter_combo.addItem("🏷️ В продаже", "in_sale")
        self.filter_combo.addItem("✅ Продано", "sold")
        self.filter_combo.addItem("📦 В коллекции", "in_collection")
        self.filter_combo.setMinimumWidth(120)
        self.filter_combo.setMinimumHeight(30)
        self.filter_combo.currentIndexChanged.connect(self._on_filter_changed)
        self.toolbar_layout.addWidget(self.filter_combo)

        sep2 = QFrame()
        sep2.setFrameShape(QFrame.VLine)
        sep2.setFrameShadow(QFrame.Sunken)
        sep2.setFixedSize(2, 28)
        self.toolbar_layout.addWidget(sep2)

        # Поиск
        self.toolbar_layout.addWidget(QLabel("🔍"))
        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText("Страна, год, номинал...")
        self.search_edit.setMinimumWidth(200)
        self.search_edit.setMinimumHeight(30)
        self.search_edit.setStyleSheet("""
            QLineEdit {
                background-color: #16213e;
                color: #e4e4ef;
                border: 1px solid #2a2a4a;
                border-radius: 6px;
                padding: 3px 8px;
            }
            QLineEdit:focus { border-color: #6c63ff; }
        """)
        self.search_edit.textChanged.connect(self._on_search_changed)
        self.toolbar_layout.addWidget(self.search_edit)

        self.clear_search_btn = QPushButton("✕")
        self.clear_search_btn.setFixedSize(28, 28)
        self.clear_search_btn.setToolTip("Очистить поиск")
        self.clear_search_btn.clicked.connect(self._clear_search)
        self.clear_search_btn.setStyleSheet(btn_style)
        self.toolbar_layout.addWidget(self.clear_search_btn)

        sep3 = QFrame()
        sep3.setFrameShape(QFrame.VLine)
        sep3.setFrameShadow(QFrame.Sunken)
        sep3.setFixedSize(2, 28)
        self.toolbar_layout.addWidget(sep3)

        # Развернуть/Свернуть
        self.expand_all_btn = QPushButton("📂 Развернуть всё")
        self.expand_all_btn.clicked.connect(self.expand_all)
        self.expand_all_btn.setMinimumHeight(30)
        self.expand_all_btn.setStyleSheet(btn_style)
        self.toolbar_layout.addWidget(self.expand_all_btn)

        self.collapse_all_btn = QPushButton("📁 Свернуть всё")
        self.collapse_all_btn.clicked.connect(self.collapse_all)
        self.collapse_all_btn.setMinimumHeight(30)
        self.collapse_all_btn.setStyleSheet(btn_style)
        self.toolbar_layout.addWidget(self.collapse_all_btn)

        # Навигация
        self.top_btn = QPushButton("▲")
        self.top_btn.clicked.connect(self.scroll_to_top)
        self.top_btn.setFixedSize(28, 30)
        self.top_btn.setToolTip("Перейти к первой строке")
        self.top_btn.setStyleSheet(btn_style)
        self.toolbar_layout.addWidget(self.top_btn)

        self.bottom_btn = QPushButton("▼")
        self.bottom_btn.clicked.connect(self.scroll_to_bottom)
        self.bottom_btn.setFixedSize(28, 30)
        self.bottom_btn.setToolTip("Перейти к последней строке")
        self.bottom_btn.setStyleSheet(btn_style)
        self.toolbar_layout.addWidget(self.bottom_btn)

        self.toolbar_layout.addStretch()

        # Индикатор загрузки
        self.loading_label = QLabel("")
        self.loading_label.setStyleSheet("color: #7c74ff; font-size: 10px;")
        self.toolbar_layout.addWidget(self.loading_label)

        # Информация о размере
        self.size_label = QLabel("Размер: 10x5")
        self.size_label.setStyleSheet("color: #8888aa; padding: 5px; font-size: 10px;")
        self.toolbar_layout.addWidget(self.size_label)

        toolbar.setLayout(self.toolbar_layout)
        return toolbar

    # Алиас для совместимости с silver_sales_tab.py
    create_toolbar = _create_toolbar

    def create_toolbar(self):
        """Создает панель инструментов вкладки «Продажа серебра» (без лишних кнопок погодовки)"""
        toolbar = QFrame()
        toolbar.setFrameShape(QFrame.StyledPanel)
        toolbar.setStyleSheet("""
            QFrame {
                background-color: #16213e;
                border: 1px solid #2a2a4a;
                border-radius: 6px;
                padding: 3px;
            }
        """)
        self.toolbar_layout = QHBoxLayout()
        self.toolbar_layout.setContentsMargins(5, 3, 5, 3)
        self.toolbar_layout.setSpacing(3)
        toolbar.setLayout(self.toolbar_layout)

        btn_style = """
            QPushButton {
                background-color: #262640;
                color: #e4e4ef;
                border: 1px solid #3d3d5c;
                border-radius: 6px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #6c63ff;
                color: #ffffff;
                border-color: #6c63ff;
            }
        """

        # ➕ Новая закупка
        add_btn = QPushButton("➕ Новая закупка")
        add_btn.clicked.connect(self.add_purchase)
        add_btn.setMinimumHeight(28)
        add_btn.setStyleSheet(btn_style)
        self.toolbar_layout.addWidget(add_btn)

        # 🗑️ Удалить выбранную закупку
        delete_btn = QPushButton("🗑️ Удалить")
        delete_btn.clicked.connect(self.delete_selected_purchase)
        delete_btn.setMinimumHeight(28)
        delete_btn.setStyleSheet(btn_style)
        self.toolbar_layout.addWidget(delete_btn)

        sep1 = QFrame()
        sep1.setFrameShape(QFrame.VLine)
        sep1.setFrameShadow(QFrame.Sunken)
        sep1.setFixedSize(2, 24)
        self.toolbar_layout.addWidget(sep1)

        # Фильтр по статусу
        filter_label = QLabel("Фильтр:")
        filter_label.setStyleSheet("color: #e4e4ef;")
        self.toolbar_layout.addWidget(filter_label)
        self.filter_combo = QComboBox()
        self.filter_combo.addItem("📊 Все монеты", "all")
        self.filter_combo.addItem("🏷️ В продаже", "in_sale")
        self.filter_combo.addItem("✅ Продано", "sold")
        self.filter_combo.addItem("📦 В коллекции", "in_collection")
        self.filter_combo.setMinimumWidth(120)
        self.filter_combo.setMinimumHeight(28)
        self.filter_combo.currentIndexChanged.connect(self._on_filter_changed)
        self.toolbar_layout.addWidget(self.filter_combo)

        # Поиск
        search_label = QLabel("🔍")
        search_label.setStyleSheet("color: #e4e4ef;")
        self.toolbar_layout.addWidget(search_label)
        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText("Страна, год, номинал...")
        self.search_edit.setMinimumWidth(180)
        self.search_edit.setMinimumHeight(28)
        self.search_edit.setStyleSheet("""
            QLineEdit {
                background-color: #16213e;
                color: #e4e4ef;
                border: 1px solid #2a2a4a;
                border-radius: 6px;
                padding: 3px 8px;
            }
            QLineEdit:focus {
                border-color: #6c63ff;
            }
        """)
        self.search_edit.textChanged.connect(self._on_search_changed)
        self.toolbar_layout.addWidget(self.search_edit)

        clear_btn = QPushButton("✕")
        clear_btn.setFixedSize(28, 28)
        clear_btn.setToolTip("Очистить поиск")
        clear_btn.setStyleSheet(btn_style)
        clear_btn.clicked.connect(self._clear_search)
        self.toolbar_layout.addWidget(clear_btn)

        sep2 = QFrame()
        sep2.setFrameShape(QFrame.VLine)
        sep2.setFrameShadow(QFrame.Sunken)
        sep2.setFixedSize(2, 24)
        self.toolbar_layout.addWidget(sep2)

        # Развернуть / свернуть
        expand_all_btn = QPushButton("📂 Развернуть всё")
        expand_all_btn.clicked.connect(self.expand_all)
        expand_all_btn.setMinimumHeight(28)
        expand_all_btn.setStyleSheet(btn_style)
        self.toolbar_layout.addWidget(expand_all_btn)

        collapse_all_btn = QPushButton("📁 Свернуть всё")
        collapse_all_btn.clicked.connect(self.collapse_all)
        collapse_all_btn.setMinimumHeight(28)
        collapse_all_btn.setStyleSheet(btn_style)
        self.toolbar_layout.addWidget(collapse_all_btn)

        # Навигация
        top_btn = QPushButton("▲")
        top_btn.setFixedSize(28, 28)
        top_btn.setToolTip("К первой закупке")
        top_btn.setStyleSheet(btn_style)
        top_btn.clicked.connect(self.scroll_to_top)
        self.toolbar_layout.addWidget(top_btn)

        bottom_btn = QPushButton("▼")
        bottom_btn.setFixedSize(28, 28)
        bottom_btn.setToolTip("К последней закупке")
        bottom_btn.setStyleSheet(btn_style)
        bottom_btn.clicked.connect(self.scroll_to_bottom)
        self.toolbar_layout.addWidget(bottom_btn)

        self.toolbar_layout.addStretch()

        # Обновить
        refresh_btn = QPushButton("🔄 Обновить")
        refresh_btn.clicked.connect(self.load_data_from_db)
        refresh_btn.setMinimumHeight(28)
        refresh_btn.setStyleSheet(btn_style)
        self.toolbar_layout.addWidget(refresh_btn)

        return toolbar

    def _create_main_container(self):
        """Создает основной контейнер с прокруткой"""
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setFrameShape(QScrollArea.NoFrame)
        self.scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)

        self.main_container = QWidget()
        self.main_layout = QVBoxLayout()
        self.main_layout.setSpacing(5)
        self.main_layout.setContentsMargins(0, 0, 0, 0)
        self.main_layout.addStretch()
        self.main_container.setLayout(self.main_layout)

        self.scroll_area.setWidget(self.main_container)

    def _create_purchase_container(self, purchase):
        """Создает контейнер для закупки"""
        container = QWidget()
        container.setProperty('purchase_id', purchase['id'])
        container.setObjectName(f"purchase_container_{purchase['id']}")

        layout = QVBoxLayout()
        layout.setSpacing(2)
        layout.setContentsMargins(0, 0, 0, 0)
        container.setLayout(layout)

        # Шапка
        header = self._create_purchase_header(purchase)
        layout.addWidget(header)
        container.header = header

        # Таблица монет
        table = self._create_coin_table(purchase)
        if table:
            table.setVisible(False)
            layout.addWidget(table)
            container.coin_table = table
        else:
            container.coin_table = None

        return container

    def _create_purchase_header(self, purchase):
        """Создает шапку закупки"""
        header = QFrame()
        header.setFrameShape(QFrame.StyledPanel)

        purchase_sum = purchase.get('purchase_sum', 0)
        sales_sum = 0
        for coin in purchase['coins']:
            if coin['status'] == 'sold':
                sales_sum += coin.get('sale_price', 0)
        if purchase_sum > 0:
            percent = ((sales_sum - purchase_sum) / purchase_sum) * 100
        else:
            percent = 0

        header_color, border_color = self._header_colors(percent)
        header.setStyleSheet(f"""
            QFrame {{
                background-color: {header_color};
                border: 1px solid {border_color};
                border-radius: 3px;
                padding: 5px;
                margin: 0px;
            }}
        """)
        header.setFixedHeight(50)
        layout = QHBoxLayout()
        layout.setContentsMargins(10, 5, 10, 5)
        layout.setSpacing(10)
        header.setLayout(layout)

        info_widget = QWidget()
        info_layout = QHBoxLayout()
        info_layout.setContentsMargins(0, 0, 0, 0)
        info_layout.setSpacing(15)
        info_widget.setLayout(info_layout)

        date_str = purchase['date'].strftime("%d.%m.%Y") if purchase['date'] else "—"
        info_layout.addWidget(QLabel(f"📅 {date_str}"))
        info_layout.addWidget(QLabel(f"🔢 №{purchase['number']}"))
        info_layout.addWidget(QLabel(f"🏷️ {purchase['number_ag']}"))
        info_layout.addWidget(QLabel(f"💰 {purchase['purchase_sum']:.2f} ₽"))
        info_layout.addWidget(QLabel(f"📊 {purchase['quantity']} монет"))
        layout.addWidget(info_widget, 1)

        stats_widget = self._create_stats_widget(purchase)
        layout.addWidget(stats_widget, 0)

        btn = QPushButton("▶ Показать монеты")
        btn.setFixedSize(140, 32)
        btn.setCursor(Qt.PointingHandCursor)
        btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {self._get_theme().get('accent', '#4a6fa5')};
                color: white;
                font-weight: bold;
                border-radius: 3px;
            }}
            QPushButton:hover {{
                background-color: {self._get_theme().get('accent_hover', '#5a7fb5')};
            }}
        """)
        from functools import partial
        btn.clicked.connect(partial(self.toggle_purchase, purchase['id']))
        layout.addWidget(btn)
        header.btn = btn
        header.purchase_id = purchase['id']
        return header

    def _create_stats_widget(self, purchase):
        """Создает виджет статистики для закупки"""
        widget = QWidget()
        layout = QHBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)
        widget.setLayout(layout)

        all_coins = purchase['coins']
        sold_count = 0
        in_collection_count = 0
        in_sale_count = 0
        total_sale_price = 0.0
        purchase_sum = purchase.get('purchase_sum', 0)

        for coin in all_coins:
            if coin['status'] == 'sold':
                sold_count += 1
                total_sale_price += coin.get('sale_price', 0)
            elif coin['status'] == 'in_collection':
                in_collection_count += 1
            elif coin['status'] == 'in_sale':
                in_sale_count += 1

        total = len(all_coins)

        # Процент
        if purchase_sum > 0:
            percent = ((total_sale_price - purchase_sum) / purchase_sum) * 100
        else:
            percent = 0

        if percent > 0:
            percent_color = "#28a745"
            percent_text = f"📈 +{percent:.1f}%"
        elif percent < 0:
            percent_color = "#dc3545"
            percent_text = f"📉 {percent:.1f}%"
        else:
            percent_color = "#6c757d"
            percent_text = "0%"

        layout.addWidget(QLabel(f"📊 Всего: {total}"))
        layout.addWidget(QLabel(f"💰 Продано: {sold_count}"))
        layout.addWidget(QLabel(f"📦 В коллекции: {in_collection_count}"))
        layout.addWidget(QLabel(f"🏷️ В продаже: {in_sale_count}"))

        percent_label = QLabel(f"💹 {percent_text}")
        percent_label.setStyleSheet(f"""
            font-weight: bold;
            color: {percent_color};
            background-color: rgba({255 if percent > 0 else 0 if percent < 0 else 128},
                                  {128 if percent > 0 else 0 if percent < 0 else 128},
                                  {128 if percent > 0 else 0 if percent < 0 else 128}, 30);
            padding: 2px 8px;
            border-radius: 10px;
        """)
        layout.addWidget(percent_label)

        sale_sum_label = QLabel(f"💰 {total_sale_price:.2f} ₽")
        sale_sum_label.setStyleSheet("font-weight: bold; color: #28a745;")
        layout.addWidget(sale_sum_label)

        return widget


    def _create_coin_table(self, purchase):
        """Создает таблицу монет с моделью (тёмная тема)"""
        from PySide6.QtCore import QTimer
        from .silver_table import SilverTableView

        # Создаем таблицу
        table = SilverTableView(self)
        table._parent_tab = self
        table.setObjectName(f"coin_table_{purchase['id']}")
        # ОТКЛЮЧАЕМ черезстрочную заливку — заливка строки целиком по статусу
        table.setAlternatingRowColors(False)
        table.setSortingEnabled(True)
        table.setSelectionBehavior(QTableView.SelectItems)
        table.setSelectionMode(QTableView.ExtendedSelection)

        # Тёмный стиль таблицы
        table.setStyleSheet("""
            QTableView {
                background-color: #1a1a2e;
                color: #e4e4ef;
                gridline-color: #2a2a4a;
                selection-background-color: #6c63ff;
                selection-color: #ffffff;
            }
            QTableView::item:selected {
                background-color: #6c63ff;
                color: #ffffff;
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

        # Создаем модель
        model = SilverTableModel(table)
        model.set_purchase_id(purchase['id'])
        table.setModel(model)

        # Применяем отфильтрованные монеты
        filtered_coins = purchase.get('_filtered_coins', purchase['coins'])
        model.set_data(filtered_coins)

        # Подключаем сигнал изменения данных для сохранения
        model.data_changed.connect(lambda: self._on_silver_data_changed(purchase['id']))

        # Делегат
        delegate = SilverDelegate(table)
        delegate.set_parent_tab(self)
        table.setItemDelegate(delegate)

        # Настройка ширины колонок
        header = table.horizontalHeader()
        header.setStretchLastSection(False)
        default_widths = [80, 100, 80, 60, 150, 50, 80, 80, 50, 50, 50, 50, 60, 60]
        for col, width in enumerate(default_widths):
            if col < len(default_widths):
                table.setColumnWidth(col, width)
            header.setSectionResizeMode(col, QHeaderView.Interactive)

        # Подключаем сигнал изменения ширины колонок
        header.sectionResized.connect(
            lambda logical, old, new, pid=purchase['id']: self._on_column_resized(pid, logical, old, new)
        )

        # Отключаем вертикальную прокрутку (используем общий scroll_area)
        table.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        table.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)

        # Вычисляем высоту таблицы
        row_count = len(filtered_coins)
        row_height = 25
        header_height = 30
        total_height = row_count * row_height + header_height + 10
        final_height = min(total_height, 800)
        table.setMinimumHeight(final_height)
        table.setMaximumHeight(final_height)

        # Применяем сохраненные ширины колонок
        QTimer.singleShot(100, lambda: self._apply_column_settings(table, purchase['id']))
        return table      

    def _is_dark(self):
        """Возвращает True, если текущая тема тёмная"""
        return self._get_theme().get('type', 'dark') == 'dark'

    def _header_colors(self, percent):
        """Возвращает (фон, граница) для шапки закупки по проценту прибыли"""
        if self._is_dark():
            if percent > 0:
                return "#123524", "#28a745"
            elif percent < 0:
                return "#3a1515", "#dc3545"
            return "#16213e", "#4a6fa5"
        else:
            if percent > 0:
                return "#d4edda", "#28a745"
            elif percent < 0:
                return "#f8d7da", "#dc3545"
            return "#e8f0fe", "#4a6fa5"


    def _ensure_color_settings(self):
        """Создаёт настройки цветов, если их ещё нет"""
        if not hasattr(self, 'color_settings') or self.color_settings is None:
            from gui.widgets.yearly_table.color_settings import ColorSettings
            self.color_settings = ColorSettings()

    def open_color_settings(self):
        """Открывает диалог настройки цветов заливки"""
        from gui.widgets.yearly_table.color_settings_dialog import ColorSettingsDialog
        self._ensure_color_settings()
        dialog = ColorSettingsDialog(self.color_settings, self)
        dialog.colors_changed.connect(self.refresh_color_buttons)
        dialog.exec()
        # После закрытия диалога обновляем кнопки цветов
        self.refresh_color_buttons()

    def refresh_color_buttons(self):
        """Пересоздаёт виджет с кнопками цветов после изменения настроек"""
        self._ensure_color_settings()
        old_widget = getattr(self, '_color_widget', None)
        if old_widget is None:
            return
        parent_layout = old_widget.parentLayout()
        new_widget = self.create_color_buttons()
        if parent_layout is not None:
            idx = parent_layout.indexOf(old_widget)
            if idx >= 0:
                parent_layout.replaceWidget(idx, new_widget)
                old_widget.deleteLater()            
            
    def create_color_buttons(self):
        """Создает кнопки для выбора цвета заливки"""
        self._ensure_color_settings()
        color_widget = QWidget()
        color_layout = QHBoxLayout()
        color_layout.setContentsMargins(0, 0, 0, 0)
        color_layout.setSpacing(2)
        # Кнопка настройки цветов (шестеренка)
        settings_btn = QPushButton("⚙️")
        settings_btn.setFixedSize(28, 28)
        settings_btn.setToolTip("Настройка цветов")
        settings_btn.clicked.connect(self.open_color_settings)
        color_layout.addWidget(settings_btn)
        # Разделитель
        sep = QFrame()
        sep.setFrameShape(QFrame.VLine)
        sep.setFrameShadow(QFrame.Sunken)
        sep.setFixedSize(2, 24)
        color_layout.addWidget(sep)
        # Метка "Заливка:"
        label = QLabel("🎨")
        label.setStyleSheet("font-size: 14px; padding: 0 2px;")
        label.setToolTip("Заливка ячеек")
        color_layout.addWidget(label)
        # Кнопки для каждого включенного цвета
        enabled_colors = self.color_settings.get_enabled_colors()
        for color_name, color_data in enabled_colors.items():
            color_code = color_data["code"]
            description = color_data.get("description", color_name)
            btn = QPushButton()
            btn.setFixedSize(24, 24)
            btn.setToolTip(f"{color_name}: {description}")
            btn.setCursor(Qt.PointingHandCursor)
            btn.setStyleSheet(f"""
QPushButton {{
background-color: {color_code};
border: 1px solid #999;
border-radius: 3px;
}}
QPushButton:hover {{
border: 2px solid #000;
}}
""")
            btn.clicked.connect(lambda checked, c=color_code: self.set_selected_cells_color(c))
            color_layout.addWidget(btn)
        # Кнопка сброса цвета
        clear_btn = QPushButton("✖")
        clear_btn.setFixedSize(24, 24)
        clear_btn.setToolTip("Убрать заливку")
        clear_btn.setCursor(Qt.PointingHandCursor)
        clear_btn.setStyleSheet("""
QPushButton {
background-color: #f0f0f0;
border: 1px solid #999;
border-radius: 3px;
font-size: 12px;
}
QPushButton:hover {
border: 2px solid #000;
background-color: #e0e0e0;
}
""")
        clear_btn.clicked.connect(lambda: self.set_selected_cells_color(None))
        color_layout.addWidget(clear_btn)
        color_layout.addStretch()
        color_widget.setLayout(color_layout)
        # Сохраняем ссылку для последующей замены при обновлении
        self._color_widget = color_widget
        return color_widget