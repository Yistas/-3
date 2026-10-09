# -*- coding: utf-8 -*-

"""
Диалог для управления странами
"""

import logging
import os
import re
from datetime import datetime
from pathlib import Path
from PySide6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QPushButton,
                               QTableWidget, QTableWidgetItem, QHeaderView,
                               QMessageBox, QLabel, QSplitter, QGroupBox,
                               QAbstractItemView, QWidget, QFormLayout,
                               QScrollArea, QApplication, QLineEdit, QTextEdit,
                               QFileDialog, QGridLayout, QFrame, QSizePolicy,
                               QProgressDialog)
from PySide6.QtCore import Qt, Signal, QSettings, QTimer, QUrl
from PySide6.QtGui import QPixmap, QFont, QResizeEvent
from PySide6.QtNetwork import QNetworkAccessManager, QNetworkRequest, QNetworkReply

from database.models import Country
from gui.dialogs.add_country_dialog import AddCountryDialog
from utils.wikipedia_api import WikipediaAPI


class ImageLabel(QLabel):
    """Кастомный QLabel для изображений с автоматическим масштабированием"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.original_pixmap = None
        self.setAlignment(Qt.AlignCenter)
        self.setMinimumSize(40, 40)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.setStyleSheet("""
            background-color: #f8f9fa;
            border: 1px solid #dee2e6;
            border-radius: 2px;
        """)
    
    def setPixmap(self, pixmap):
        self.original_pixmap = pixmap
        self.update_display()
    
    def update_display(self):
        if self.original_pixmap and not self.original_pixmap.isNull():
            scaled = self.original_pixmap.scaled(
                self.width() - 4, self.height() - 4,
                Qt.KeepAspectRatio,
                Qt.SmoothTransformation
            )
            super().setPixmap(scaled)
    
    def resizeEvent(self, event: QResizeEvent):
        super().resizeEvent(event)
        self.update_display()


class CountryReferenceDialog(QDialog):
    """Диалог для управления странами"""
    
    data_updated = Signal()
    
    def __init__(self, db_manager, parent=None):
        super().__init__(parent)
        self.logger = logging.getLogger('CoinCollector.GUI.CountryReferenceDialog')
        self.db_manager = db_manager
        self.wiki_api = WikipediaAPI()
        self.current_country_id = None
        
        # Директория для пользовательских изображений
        self.custom_images_dir = Path("custom_images")
        self.custom_images_dir.mkdir(exist_ok=True)
        
        # Для загрузки изображений
        self.network_manager = QNetworkAccessManager()
        self.network_manager.finished.connect(self.on_image_loaded)
        self.loading_images = {}
        
        # Загружаем настройки
        self.settings = QSettings('CoinCollector', 'CountryReference')
        
        self.setWindowTitle("🌍 Справочник стран")
        self.setMinimumSize(1000, 700)
        
        self.init_ui()
        self.load_column_widths()
        
        # Подключаем сигнал выбора в таблице
        self.country_table.itemSelectionChanged.connect(self.on_country_selected)
        
        # Загружаем страны
        QTimer.singleShot(100, self.load_countries)
        
        self.logger.info("CountryReferenceDialog инициализирован")
    
    def init_ui(self):
        """Инициализация интерфейса"""
        layout = QVBoxLayout()
        layout.setContentsMargins(2, 2, 2, 2)
        layout.setSpacing(2)
        self.setLayout(layout)
        
        # Панель инструментов
        toolbar = self.create_toolbar()
        layout.addWidget(toolbar)
        
        # Основной сплиттер
        splitter = QSplitter(Qt.Horizontal)
        splitter.setHandleWidth(2)
        
        # Левая панель - список стран
        left_panel = self.create_country_list_panel()
        splitter.addWidget(left_panel)
        
        # Правая панель с информацией
        right_panel = self.create_detail_panel()
        splitter.addWidget(right_panel)
        
        # Устанавливаем соотношение размеров (40% - таблица, 60% - информация)
        splitter.setSizes([400, 600])
        layout.addWidget(splitter)
        
        # Кнопка закрытия
        close_layout = QHBoxLayout()
        close_layout.addStretch()
        
        close_btn = QPushButton("❌ Закрыть")
        close_btn.clicked.connect(self.accept)
        close_btn.setMinimumHeight(30)
        close_btn.setMinimumWidth(100)
        close_layout.addWidget(close_btn)
        
        layout.addLayout(close_layout)
    
    def create_toolbar(self):
        """Создает панель инструментов"""
        toolbar = QWidget()
        toolbar.setMaximumHeight(40)
        
        layout = QHBoxLayout()
        layout.setContentsMargins(2, 2, 2, 2)
        toolbar.setLayout(layout)
        
        self.add_btn = QPushButton("➕ Добавить")
        self.add_btn.clicked.connect(self.add_country)
        layout.addWidget(self.add_btn)
        
        self.edit_btn = QPushButton("✏️ Правка")
        self.edit_btn.clicked.connect(self.edit_country)
        self.edit_btn.setEnabled(False)
        layout.addWidget(self.edit_btn)
        
        self.delete_btn = QPushButton("🗑️ Удалить")
        self.delete_btn.clicked.connect(self.delete_country)
        self.delete_btn.setEnabled(False)
        layout.addWidget(self.delete_btn)
        
        layout.addStretch()
        
        # Кнопка загрузки из Wikipedia
        self.wiki_load_btn = QPushButton("📥 Загрузить из Wikipedia")
        self.wiki_load_btn.clicked.connect(self.load_from_wikipedia)
        self.wiki_load_btn.setEnabled(False)
        self.wiki_load_btn.setStyleSheet("""
            QPushButton {
                background-color: #4a6fa5;
                color: white;
                font-weight: bold;
                border-radius: 3px;
            }
            QPushButton:hover {
                background-color: #5a7fb5;
            }
        """)
        layout.addWidget(self.wiki_load_btn)
        
        # Кнопка открыть в Wikipedia
        self.wiki_open_btn = QPushButton("🌐 Открыть в Wikipedia")
        self.wiki_open_btn.clicked.connect(self.open_in_wikipedia)
        self.wiki_open_btn.setEnabled(False)
        self.wiki_open_btn.setStyleSheet("""
            QPushButton {
                background-color: #27ae60;
                color: white;
                font-weight: bold;
                border-radius: 3px;
            }
            QPushButton:hover {
                background-color: #2ecc71;
            }
        """)
        layout.addWidget(self.wiki_open_btn)
        
        self.save_btn = QPushButton("💾 Сохранить")
        self.save_btn.clicked.connect(self.save_country_changes)
        self.save_btn.setEnabled(False)
        layout.addWidget(self.save_btn)
        
        return toolbar
    
    def create_country_list_panel(self):
        """Создает панель со списком стран"""
        panel = QWidget()
        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        panel.setLayout(layout)
        
        # Заголовок
        title = QLabel("📋 Список стран")
        title.setStyleSheet("font-weight: bold; font-size: 12px; padding: 2px; background-color: #4a6fa5; color: white; border-radius: 2px;")
        title.setAlignment(Qt.AlignCenter)
        layout.addWidget(title)
        
        # Таблица
        self.country_table = QTableWidget()
        self.country_table.setColumnCount(3)
        self.country_table.setHorizontalHeaderLabels(["Страна", "Континент", "Монет"])
        self.country_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.country_table.setAlternatingRowColors(True)
        self.country_table.setSortingEnabled(True)
        
        # Настройка ширины колонок: страна - шире, континент и монеты - фиксированные
        header = self.country_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.Stretch)  # Страна - растягивается (шире)
        header.setSectionResizeMode(1, QHeaderView.Fixed)    # Континент - фиксированная ширина
        header.setSectionResizeMode(2, QHeaderView.Fixed)    # Монет - фиксированная ширина
        self.country_table.setColumnWidth(1, 80)            # Ширина колонки Континент
        self.country_table.setColumnWidth(2, 60)            # Ширина колонки Монет
        
        header.sectionResized.connect(self.save_column_widths)
        
        layout.addWidget(self.country_table)
        
        return panel
    
    def create_detail_panel(self):
        """Создает панель с информацией о стране с прокруткой"""
        panel = QWidget()
        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        panel.setLayout(layout)
        
        # Заголовок
        title = QLabel("ℹ️ Информация о стране")
        title.setStyleSheet("font-weight: bold; font-size: 12px; padding: 2px; background-color: #4a6fa5; color: white; border-radius: 2px;")
        title.setAlignment(Qt.AlignCenter)
        layout.addWidget(title)
        
        # Создаем область прокрутки для правой панели
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setFrameShape(QScrollArea.NoFrame)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        
        # Контейнер для содержимого
        content_widget = QWidget()
        content_layout = QVBoxLayout()
        content_layout.setContentsMargins(5, 5, 5, 5)
        content_layout.setSpacing(10)
        content_widget.setLayout(content_layout)
        
        # Название страны
        self.info_name = QLabel()
        self.info_name.setStyleSheet("font-weight: bold; font-size: 14px; color: #4a6fa5;")
        self.info_name.setAlignment(Qt.AlignCenter)
        content_layout.addWidget(self.info_name)
        
        # Карта
        map_group = QGroupBox("🗺️ Карта")
        map_group.setStyleSheet("QGroupBox { font-weight: bold; margin-top: 5px; padding-top: 5px; }")
        map_layout = QVBoxLayout()
        map_layout.setSpacing(5)
        
        self.map_label = ImageLabel()
        self.map_label.setMinimumHeight(150)
        map_layout.addWidget(self.map_label)
        
        self.load_map_btn = QPushButton("📁 Загрузить карту")
        self.load_map_btn.clicked.connect(lambda: self.load_image("map"))
        map_layout.addWidget(self.load_map_btn)
        
        map_group.setLayout(map_layout)
        content_layout.addWidget(map_group)
        
        # Флаг и герб (горизонтально)
        symbols_layout = QHBoxLayout()
        symbols_layout.setSpacing(10)
        
        # Флаг
        flag_group = QGroupBox("🏁 Флаг")
        flag_group.setStyleSheet("QGroupBox { font-weight: bold; }")
        flag_layout = QVBoxLayout()
        flag_layout.setSpacing(5)
        
        self.flag_label = ImageLabel()
        self.flag_label.setMinimumHeight(100)
        flag_layout.addWidget(self.flag_label)
        
        self.load_flag_btn = QPushButton("📁 Загрузить")
        self.load_flag_btn.clicked.connect(lambda: self.load_image("flag"))
        flag_layout.addWidget(self.load_flag_btn)
        
        flag_group.setLayout(flag_layout)
        symbols_layout.addWidget(flag_group)
        
        # Герб
        coat_group = QGroupBox("🛡️ Герб")
        coat_group.setStyleSheet("QGroupBox { font-weight: bold; }")
        coat_layout = QVBoxLayout()
        coat_layout.setSpacing(5)
        
        self.coat_label = ImageLabel()
        self.coat_label.setMinimumHeight(100)
        coat_layout.addWidget(self.coat_label)
        
        self.load_coat_btn = QPushButton("📁 Загрузить")
        self.load_coat_btn.clicked.connect(lambda: self.load_image("coat"))
        coat_layout.addWidget(self.load_coat_btn)
        
        coat_group.setLayout(coat_layout)
        symbols_layout.addWidget(coat_group)
        
        content_layout.addLayout(symbols_layout)
        
        # ===== ПАРАМЕТРЫ С ПРОКРУТКОЙ =====
        params_group = QGroupBox("📋 Параметры")
        params_group.setStyleSheet("QGroupBox { font-weight: bold; margin-top: 5px; padding-top: 5px; }")
        
        # Создаем форму с прокруткой внутри
        params_scroll = QScrollArea()
        params_scroll.setWidgetResizable(True)
        params_scroll.setFrameShape(QScrollArea.NoFrame)
        params_scroll.setMaximumHeight(300)
        params_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        
        params_widget = QWidget()
        params_layout = QFormLayout()
        params_layout.setSpacing(8)
        params_layout.setContentsMargins(10, 10, 10, 10)
        
        # Столица
        self.info_capital = QLineEdit()
        params_layout.addRow("Столица:", self.info_capital)
        
        # Континент
        self.info_continent = QLineEdit()
        self.info_continent.setReadOnly(True)
        params_layout.addRow("Континент:", self.info_continent)
        
        # Форма правления
        self.info_government = QLineEdit()
        params_layout.addRow("Форма правления:", self.info_government)
        
        # Валюта
        self.info_currency = QLineEdit()
        params_layout.addRow("Валюта:", self.info_currency)
        
        # Язык
        self.info_language = QLineEdit()
        params_layout.addRow("Язык:", self.info_language)
        
        # Религия
        self.info_religion = QLineEdit()
        params_layout.addRow("Религия:", self.info_religion)
        
        # Территория
        self.info_area = QLineEdit()
        params_layout.addRow("Территория (км²):", self.info_area)
        
        # Население
        self.info_population = QLineEdit()
        params_layout.addRow("Население:", self.info_population)
        
        # Код МОК
        self.info_ioc = QLineEdit()
        params_layout.addRow("Код МОК:", self.info_ioc)
        
        # ISO коды
        self.info_iso2 = QLineEdit()
        params_layout.addRow("ISO 3166-1 alpha-2:", self.info_iso2)
        
        self.info_iso3 = QLineEdit()
        params_layout.addRow("ISO 3166-1 alpha-3:", self.info_iso3)
        
        params_widget.setLayout(params_layout)
        params_scroll.setWidget(params_widget)
        
        params_group.setLayout(QVBoxLayout())
        params_group.layout().addWidget(params_scroll)
        content_layout.addWidget(params_group)
        # ===================================
        
        # Статус (исчезнувшая)
        self.extinct_check = QLabel()
        self.extinct_check.setStyleSheet("color: #dc3545; font-weight: bold;")
        content_layout.addWidget(self.extinct_check)
        
        scroll_area.setWidget(content_widget)
        layout.addWidget(scroll_area)
        
        return panel
    
    def save_column_widths(self):
        """Сохраняет ширину колонок"""
        for i in range(self.country_table.columnCount()):
            self.settings.setValue(f'column_width_{i}', self.country_table.columnWidth(i))
    
    def load_column_widths(self):
        """Загружает ширину колонок"""
        for i in range(self.country_table.columnCount()):
            width = self.settings.value(f'column_width_{i}', type=int)
            if width:
                self.country_table.setColumnWidth(i, width)
    

    # ================= ФЛАГ СТРАНЫ =================
    
    def get_image_path(self, country_id, image_type):
        """Путь к изображению страны в custom_images (герб, карта, копия флага)"""
        from utils.paths import paths
        custom_images_dir = paths.get_data_dir() / "custom_images"
        custom_images_dir.mkdir(parents=True, exist_ok=True)
        return custom_images_dir / f"country_{country_id}_{image_type}.png"

    def load_image(self, image_type):
        """Загружает изображение с диска.
        ФЛАГ сохраняется в оба хранилища и сразу обновляется везде."""
        if not self.current_country_id:
            QMessageBox.warning(self, "Предупреждение", "Сначала выберите страну")
            return
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Выберите изображение", "",
            "Изображения (*.png *.jpg *.jpeg *.webp *.bmp *.gif);;Все файлы (*.*)")
        if not file_path:
            return
        pixmap = QPixmap(file_path)
        if pixmap.isNull():
            QMessageBox.warning(self, "Ошибка", "Не удалось открыть изображение")
            return
        if image_type == "flag":
            from utils.flag_storage import save_flag_from_file
            save_flag_from_file(self.current_country_id, file_path)
        dest_path = self.get_image_path(self.current_country_id, image_type)
        pixmap.save(str(dest_path))
        self.logger.info(f"Загружено изображение: {dest_path}")
        if image_type == "map":
            self.map_label.setPixmap(pixmap)
        elif image_type == "flag":
            self.flag_label.setPixmap(pixmap)
            self._refresh_flags_everywhere()
        elif image_type == "coat":
            self.coat_label.setPixmap(pixmap)

    def _refresh_flags_everywhere(self):
        """Обновляет флаги в дереве, таблице и карточке страны"""
        from PySide6.QtWidgets import QApplication
        for w in QApplication.topLevelWidgets():
            if w.__class__.__name__ == 'MainWindow':
                tree = getattr(w, 'country_tree', None)
                if tree is not None and hasattr(tree, 'refresh_flags'):
                    tree.refresh_flags()
                tp = getattr(w, 'table_panel', None)
                if tp is not None:
                    if hasattr(tp, '_flag_icon_cache'):
                        tp._flag_icon_cache = {}
                    if hasattr(tp, '_render_page'):
                        tp._render_page()
                dp = getattr(w, 'detail_panel', None)
                ct = getattr(dp, 'country_tab', None) if dp else None
                if ct is not None and hasattr(ct, 'load_country_flag') and ct.current_country:
                    ct.load_country_flag(ct.current_country)
                break

    def load_country_flag(self, country):
        """Показывает флаг страны в диалоге: сначала data/country_flags, потом custom_images"""
        if not hasattr(self, 'flag_label'):
            return
        self.flag_label.clear()
        pix = None
        try:
            from utils.flag_manager import flag_manager
            pix = flag_manager.get_pixmap(country.id, 120, 80)
        except Exception:
            pix = None
        if pix is None:
            flag_path = self.get_image_path(country.id, "flag")
            if flag_path.exists():
                p = QPixmap(str(flag_path))
                if not p.isNull():
                    pix = p
        if pix is not None and not pix.isNull():
            self.flag_label.setPixmap(pix)
        else:
            self.flag_label.setText("🏳️")
            
    def _flags_dir(self):
        """Папка флагов: data/country_flags (синхронизируется с Google Drive)"""
        from utils.paths import paths
        d = paths.get_data_dir() / "country_flags"
        d.mkdir(parents=True, exist_ok=True)
        return d

    def _load_pixmap_any(self, path):
        """Загружает QPixmap из файла любого формата (PNG/JPG/SVG).
        SVG конвертирует в растр через QSvgRenderer."""
        pixmap = QPixmap(str(path))
        if pixmap.isNull():
            try:
                from PySide6.QtSvg import QSvgRenderer
                from PySide6.QtGui import QPainter
                from PySide6.QtCore import Qt as QtCore_Qt
                renderer = QSvgRenderer(str(path))
                if renderer.isValid():
                    pixmap = QPixmap(120, 80)
                    pixmap.fill(QtCore_Qt.transparent)
                    painter = QPainter(pixmap)
                    renderer.render(painter)
                    painter.end()
            except Exception as e:
                self.logger.debug(f"SVG-конвертация не удалась: {e}")
        return pixmap

    def _get_current_country_id(self):
        """Возвращает ID текущей выбранной страны диалога (любым из способов)"""
        # 1) атрибут current_country
        c = getattr(self, 'current_country', None)
        if c is not None and getattr(c, 'id', None):
            return c.id
        # 2) выделенный пункт списка
        lst = getattr(self, 'country_list', None) or getattr(self, 'list_widget', None)
        if lst is not None and hasattr(lst, 'currentItem'):
            item = lst.currentItem()
            if item is not None:
                cid = item.data(Qt.UserRole)
                if cid:
                    return cid
        # 3) выделенная строка таблицы
        tbl = getattr(self, 'table', None) or getattr(self, 'country_table', None)
        if tbl is not None and hasattr(tbl, 'currentRow'):
            row = tbl.currentRow()
            if row >= 0:
                it = tbl.item(row, 0)
                if it is not None:
                    cid = it.data(Qt.UserRole)
                    if cid:
                        return cid
        return None

    def _on_load_flag_clicked(self):
        """Кнопка «🏳️ Загрузить флаг»: выбирает файл из любого места,
        СОХРАНЯЕТ его в data/country_flags/{id}.png (основной файл, Google Drive),
        дублирует в custom_images, показывает превью и обновляет дерево/таблицу."""
        cid = self._get_current_country_id()
        if not cid:
            QMessageBox.warning(self, "Флаг страны", "Сначала выберите страну в списке")
            return

        path, _ = QFileDialog.getOpenFileName(
            self, "Выберите файл флага страны", str(self._flags_dir()),
            "Изображения (*.png *.jpg *.jpeg *.webp *.bmp *.gif);;Все файлы (*)")
        if not path:
            return

        pix = QPixmap(path)
        if pix.isNull():
            QMessageBox.warning(self, "Флаг страны", "Не удалось открыть файл изображения")
            return

        # === 1) СОХРАНЯЕМ в data/country_flags/{id}.png ===
        flags_path = self._flags_dir() / f"{cid}.png"
        ok = pix.save(str(flags_path), "PNG")
        if ok:
            self.logger.info(f"✅ Флаг страны {cid} сохранён: {flags_path}")
        else:
            self.logger.error(f"❌ Не удалось сохранить флаг: {flags_path}")

        # === 2) Копия в custom_images (превью диалога, обратная совместимость) ===
        try:
            custom_dir = Path("custom_images")
            custom_dir.mkdir(parents=True, exist_ok=True)
            custom_path = custom_dir / f"country_{cid}_flag.png"
            pix.save(str(custom_path), "PNG")
            self.logger.info(f"Загружено изображение: {custom_path}")
        except Exception as e:
            self.logger.debug(f"Не удалось сохранить копию в custom_images: {e}")

        if not ok:
            QMessageBox.warning(self, "Флаг страны", "Не удалось сохранить флаг в data/country_flags")
            return

        # === 3) Превью в диалоге ===
        if hasattr(self, 'flag_label'):
            self.flag_label.setPixmap(
                pix.scaled(60, 40, Qt.KeepAspectRatio, Qt.SmoothTransformation))

        # === 4) Обновляем дерево, таблицу и карточку страны ===
        self._refresh_flag_everywhere(cid)


    def load_countries(self):
        """Загружает список стран"""
        try:
            from database.models import Coin
            
            self.country_table.setSortingEnabled(False)
            
            countries = self.db_manager.get_all_countries()
            self.country_table.setRowCount(len(countries))
            
            for row, country in enumerate(countries):
                name_item = QTableWidgetItem(country.name)
                name_item.setData(Qt.UserRole, country.id)
                self.country_table.setItem(row, 0, name_item)
                
                continent_item = QTableWidgetItem(country.continent or "")
                self.country_table.setItem(row, 1, continent_item)
                
                coin_count = self.db_manager.session.query(Coin).filter_by(country_id=country.id).count()
                coin_item = QTableWidgetItem(str(coin_count))
                coin_item.setTextAlignment(Qt.AlignCenter)
                self.country_table.setItem(row, 2, coin_item)
            
            self.country_table.setSortingEnabled(True)
            
            # Настройка ширины колонок: страна - шире, континент и монеты - фиксированные
            header = self.country_table.horizontalHeader()
            header.setSectionResizeMode(0, QHeaderView.Stretch)  # Страна - растягивается
            header.setSectionResizeMode(1, QHeaderView.Fixed)    # Континент - фиксированная ширина
            header.setSectionResizeMode(2, QHeaderView.Fixed)    # Монет - фиксированная ширина
            self.country_table.setColumnWidth(1, 80)            # Ширина колонки Континент
            self.country_table.setColumnWidth(2, 60)            # Ширина колонки Монет
            
            if countries:
                self.country_table.selectRow(0)
            
        except Exception as e:
            self.logger.error(f"Ошибка при загрузке стран: {e}")
    
    def on_country_selected(self):
        """Обработчик выбора страны"""
        current_row = self.country_table.currentRow()
        if current_row < 0:
            return
        
        item = self.country_table.item(current_row, 0)
        if not item:
            return
        
        country_id = item.data(Qt.UserRole)
        if not country_id:
            return
        
        self.current_country_id = country_id
        
        self.edit_btn.setEnabled(True)
        self.delete_btn.setEnabled(True)
        self.wiki_load_btn.setEnabled(True)
        self.wiki_open_btn.setEnabled(True)
        self.save_btn.setEnabled(True)
        
        self.load_country_details(country_id)
    
    def load_country_details(self, country_id):
        """Загружает детали страны"""
        try:
            country = self.db_manager.session.query(Country).get(country_id)
            if not country:
                return
            
            self.info_name.setText(country.name)
            self.info_capital.setText(country.capital or "")
            self.info_continent.setText(country.continent or "")
            self.info_government.setText(country.government_type or "")
            
            currency_text = []
            if country.currency_name:
                currency_text.append(country.currency_name)
            if country.currency_code:
                currency_text.append(f"({country.currency_code})")
            self.info_currency.setText(" ".join(currency_text))
            
            self.info_language.setText(country.language or "")
            self.info_religion.setText(country.religion or "")
            self.info_area.setText(str(country.area) if country.area else "")
            self.info_population.setText(str(country.population) if country.population else "")
            self.info_ioc.setText(country.ioc_code or "")
            self.info_iso2.setText(country.iso2 or "")
            self.info_iso3.setText(country.iso3 or "")
            
            if country.is_extinct:
                self.extinct_check.setText("💀 Исчезнувшая страна")
                self.extinct_check.show()
            else:
                self.extinct_check.hide()
            
            self.load_saved_images(country_id)
            
        except Exception as e:
            self.logger.error(f"Ошибка при загрузке деталей: {e}")
    
    def load_saved_images(self, country_id):
        """Загружает сохранённые изображения страны.
        ФЛАГ: сначала data/country_flags/{id}.png (основное хранилище,
        туда сохраняет Wikipedia), затем custom_images/country_{id}_flag.png.
        Карта и герб — из custom_images."""
        # === КАРТА ===
        map_path = self.get_image_path(country_id, "map")
        if map_path.exists():
            pixmap = self._load_pixmap_any(map_path)
            if not pixmap.isNull():
                self.map_label.setPixmap(pixmap)
            else:
                self.map_label.setText("🗺️")
        else:
            self.map_label.setText("🗺️")

        # === ФЛАГ: основное хранилище → резервное ===
        flag_path = self._flags_dir() / f"{country_id}.png"
        if not flag_path.exists():
            flag_path = self.get_image_path(country_id, "flag")
        if flag_path.exists():
            pixmap = self._load_pixmap_any(flag_path)
            if not pixmap.isNull():
                self.flag_label.setPixmap(pixmap)
            else:
                self.flag_label.setText("🏳️")
        else:
            self.flag_label.setText("🏳️")

        # === ГЕРБ ===
        coat_path = self.get_image_path(country_id, "coat")
        if coat_path.exists():
            pixmap = self._load_pixmap_any(coat_path)
            if not pixmap.isNull():
                self.coat_label.setPixmap(pixmap)
            else:
                self.coat_label.setText("🛡️")
        else:
            self.coat_label.setText("🛡️")

    def save_country_changes(self):
        """Сохраняет изменения"""
        if not self.current_country_id:
            return
        
        try:
            country = self.db_manager.session.query(Country).get(self.current_country_id)
            if not country:
                return
            
            country.capital = self.info_capital.text() or None
            country.government_type = self.info_government.text() or None
            
            currency_text = self.info_currency.text()
            if currency_text:
                code_match = re.search(r'\(([A-Z]{3})\)', currency_text)
                if code_match:
                    country.currency_code = code_match.group(1)
                    country.currency_name = currency_text.replace(f"({country.currency_code})", "").strip()
                else:
                    country.currency_name = currency_text
                    country.currency_code = None
            else:
                country.currency_name = None
                country.currency_code = None
            
            country.language = self.info_language.text() or None
            country.religion = self.info_religion.text() or None
            
            try:
                country.area = int(self.info_area.text()) if self.info_area.text() else None
            except:
                country.area = None
            
            try:
                country.population = int(self.info_population.text()) if self.info_population.text() else None
            except:
                country.population = None
            
            country.ioc_code = self.info_ioc.text().upper() or None
            country.iso2 = self.info_iso2.text().upper() or None
            country.iso3 = self.info_iso3.text().upper() or None
            country.updated_at = datetime.now()
            
            self.db_manager.session.commit()
            QMessageBox.information(self, "Успех", "Изменения сохранены")
            
            # Обновляем таблицу
            self.load_countries()
            
        except Exception as e:
            self.logger.error(f"Ошибка при сохранении: {e}")
            QMessageBox.critical(self, "Ошибка", f"Не удалось сохранить изменения: {e}")
    
    def load_from_wikipedia(self):
        """Загрузка из Wikipedia:
        1) вся текстовая информация (столица, население, валюта и т.д.) — как раньше;
        2) флаг, герб и карта — автоматически;
        3) если что-то не нашлось — ручные кнопки «📁 Загрузить» остаются."""
        if not self.current_country_id:
            QMessageBox.warning(self, "Предупреждение", "Сначала выберите страну в списке")
            return
        from database.models import Country
        from utils.paths import paths
        from PySide6.QtCore import Qt as QConst
        from PySide6.QtWidgets import QApplication

        country = self.db_manager.session.query(Country).get(self.current_country_id)
        if not country:
            QMessageBox.warning(self, "Предупреждение", "Страна не найдена")
            return

        QApplication.setOverrideCursor(QConst.WaitCursor)
        try:
            info = self.wiki_api.get_country_info(country.name)
            media = self.wiki_api.get_country_media(country.name)
        except Exception as e:
            self.logger.error(f"Ошибка Wikipedia: {e}")
            info, media = None, None
        finally:
            QApplication.restoreOverrideCursor()

        loaded, failed = [], []

        # ---------- 1) ТЕКСТОВАЯ ИНФОРМАЦИЯ (как раньше) ----------
        if info:
            update = {}
            if info.get('capital'):      update['capital'] = info['capital']
            if info.get('government'):   update['government_type'] = info['government']
            if info.get('languages'):    update['language'] = info['languages']
            if info.get('religion'):     update['religion'] = info['religion']
            if info.get('area'):         update['area'] = info['area']
            if info.get('population'):   update['population'] = info['population']
            if info.get('ioc_code'):     update['ioc_code'] = info['ioc_code']
            if isinstance(info.get('currency'), dict):
                if info['currency'].get('name'): update['currency_name'] = info['currency']['name']
                if info['currency'].get('code'): update['currency_code'] = info['currency']['code']
            if update:
                try:
                    self.db_manager.update_country(country.id, update)
                    self.db_manager.session.refresh(country)
                    loaded.append('информация')
                except Exception as e:
                    self.logger.error(f"Ошибка сохранения информации: {e}")
            self._fill_country_fields(info)
        else:
            failed.append('информация')

        # ---------- 2) ФЛАГ / ГЕРБ / КАРТА ----------
        media = media or {}

        # ФЛАГ → data/country_flags/{id}.png (подхватывают дерево и таблица)
        if media.get('flag'):
            pix = self._download_pixmap(media['flag'])
            if pix and not pix.isNull():
                dest = paths.get_data_dir() / 'country_flags' / f'{country.id}.png'
                pix.save(str(dest), 'PNG')
                if hasattr(self, 'flag_label'):
                    self.flag_label.setPixmap(pix.scaled(
                        140, 100, QConst.KeepAspectRatio, QConst.SmoothTransformation))
                if hasattr(self, '_refresh_flags_everywhere'):
                    self._refresh_flags_everywhere()
                loaded.append('флаг')
                self.logger.info(f"🏳️ Флаг загружен из Wikipedia: {country.name}")
            else:
                failed.append('флаг')
        else:
            failed.append('флаг')

        # ГЕРБ → custom_images/country_{id}_coat.png
        if media.get('coat'):
            pix = self._download_pixmap(media['coat'])
            if pix and not pix.isNull():
                dest = self.get_image_path(country.id, 'coat')
                pix.save(str(dest), 'PNG')
                if hasattr(self, 'coat_label'):
                    self.coat_label.setPixmap(pix.scaled(
                        140, 100, QConst.KeepAspectRatio, QConst.SmoothTransformation))
                loaded.append('герб')
                self.logger.info(f"🛡️ Герб загружен из Wikipedia: {country.name}")
            else:
                failed.append('герб')
        else:
            failed.append('герб')

        # КАРТА → custom_images/country_{id}_map.png
        if media.get('map'):
            pix = self._download_pixmap(media['map'])
            if pix and not pix.isNull():
                dest = self.get_image_path(country.id, 'map')
                pix.save(str(dest), 'PNG')
                if hasattr(self, 'map_label'):
                    self.map_label.setPixmap(pix.scaled(
                        400, 260, QConst.KeepAspectRatio, QConst.SmoothTransformation))
                loaded.append('карта')
                self.logger.info(f"🗺️ Карта загружена из Wikipedia: {country.name}")
            else:
                failed.append('карта')
        else:
            failed.append('карта')

        # ---------- 3) ИТОГ ----------
        msg = f"🌍 {country.name}\n\n✅ Загружено: {', '.join(loaded) if loaded else 'ничего'}"
        if failed:
            msg += f"\n⚠️ Не загрузилось: {', '.join(failed)}\n(можно загрузить вручную кнопками «📁 Загрузить»)"
        QMessageBox.information(self, "Загрузка из Wikipedia", msg)
        # Обновить карточку (флаг/герб/карта) после загрузки
        self.load_saved_images(self.current_country_id)
    # ---------- помощники ----------
    def _download_pixmap(self, url):
        """Скачивает изображение по ссылке и возвращает QPixmap"""
        from PySide6.QtGui import QPixmap
        data = self.wiki_api.download_image_bytes(url)
        if not data:
            return None
        pix = QPixmap()
        pix.loadFromData(data)
        return pix

    def _fill_country_fields(self, info):
        """Заполняет видимые поля диалога (защищённо — только существующие виджеты)"""
        if not info:
            return
        cur = info.get('currency')
        currency_text = ''
        if isinstance(cur, dict):
            currency_text = f"{cur.get('name') or ''} ({cur.get('code') or ''})".strip(' ()')
        pairs = [
            ('capital', info.get('capital')),
            ('government', info.get('government')),
            ('language', info.get('languages')),
            ('religion', info.get('religion')),
            ('area', info.get('area')),
            ('population', info.get('population')),
            ('ioc', info.get('ioc_code')),
            ('currency', currency_text),
        ]
        for key, value in pairs:
            if value in (None, ''):
                continue
            for attr in (f'info_{key}', f'{key}_edit', f'{key}_label',
                         f'info_{key}_edit'):
                w = getattr(self, attr, None)
                if w is not None and hasattr(w, 'setText'):
                    w.setText(str(value))
                    break

    def open_in_wikipedia(self):
        """Открывает страницу страны в Wikipedia"""
        if not self.current_country_id:
            return
        
        country = self.db_manager.session.query(Country).get(self.current_country_id)
        if not country:
            return
        
        import webbrowser
        # Формируем URL для Wikipedia
        search_name = country.name.replace(' ', '_')
        url = f"https://ru.wikipedia.org/wiki/{search_name}"
        webbrowser.open(url)
        
        self.logger.info(f"Открыта страница Wikipedia: {url}")
    
    def add_country(self):
        """Добавляет страну"""
        dialog = AddCountryDialog(self.db_manager, self)
        if dialog.exec():
            self.load_countries()
            self.data_updated.emit()
    
    def edit_country(self):
        """Редактирует страну"""
        if not self.current_country_id:
            return
        
        country = self.db_manager.session.query(Country).get(self.current_country_id)
        if not country:
            return
        
        dialog = AddCountryDialog(
            self.db_manager, self,
            initial_name=country.name,
            default_continent=country.continent,
            is_extinct=country.is_extinct
        )
        
        if dialog.exec():
            self.load_countries()
            self.load_country_details(self.current_country_id)
            self.data_updated.emit()
    
    def delete_country(self):
        """Удаляет страну"""
        if not self.current_country_id:
            return
        
        country = self.db_manager.session.query(Country).get(self.current_country_id)
        if not country:
            return
        
        from database.models import Coin
        coin_count = self.db_manager.session.query(Coin).filter_by(country_id=self.current_country_id).count()
        
        if coin_count > 0:
            reply = QMessageBox.question(
                self, "Подтверждение",
                f"У страны '{country.name}' есть {coin_count} монет. Удалить?",
                QMessageBox.Yes | QMessageBox.No
            )
            
            if reply == QMessageBox.Yes:
                self.db_manager.delete_country(self.current_country_id)
                self.load_countries()
                self.data_updated.emit()
        else:
            reply = QMessageBox.question(
                self, "Подтверждение",
                f"Удалить страну '{country.name}'?",
                QMessageBox.Yes | QMessageBox.No
            )
            
            if reply == QMessageBox.Yes:
                self.db_manager.delete_country_without_coins(self.current_country_id)
                self.load_countries()
                self.data_updated.emit()
    
    def on_image_loaded(self, reply):
        """Обработчик загрузки изображения"""
        if reply in self.loading_images:
            label = self.loading_images[reply]
            
            if reply.error() == QNetworkReply.NoError:
                data = reply.readAll()
                pixmap = QPixmap()
                pixmap.loadFromData(data)
                
                if not pixmap.isNull():
                    label.setPixmap(pixmap)
            
            reply.deleteLater()
            del self.loading_images[reply]
            
            
