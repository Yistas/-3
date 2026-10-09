# ===== gui/add_coin_dialog.py =====
# ПОЛНОСТЬЮ ЗАМЕНИТЬ ФАЙЛ

# -*- coding: utf-8 -*-

"""
Диалог добавления/редактирования/копирования монеты - полная версия
"""

import logging
import traceback
import os
import shutil
from pathlib import Path
from datetime import datetime
from PySide6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QFormLayout,
                               QPushButton, QLineEdit, QComboBox, QSpinBox,
                               QDoubleSpinBox, QTextEdit, QLabel, QGroupBox,
                               QScrollArea, QMessageBox, QWidget, QFileDialog, QDateEdit)
from PySide6.QtCore import Qt, QTimer, QDate
from PySide6.QtGui import QPixmap

from database.models import Country, Currency, Mint, Edge, StandardReference
from gui.dialogs.references_dialog import ReferencesDialog
from utils.cache import ReferenceCache

class ImageSelector(QLabel):
    """Виджет для выбора и отображения изображения"""
    
    def __init__(self, parent=None, image_type=""):
        super().__init__(parent)
        self.image_type = image_type
        self.image_path = None
        self.current_pixmap = None
        self.setAlignment(Qt.AlignCenter)
        self.setMinimumSize(100, 100)
        self.setMaximumSize(100, 100)
        self.setStyleSheet("""
            QLabel {
                background-color: #f8f9fa;
                border: 2px dashed #ccc;
                border-radius: 5px;
                padding: 5px;
            }
        """)
        self.setText("📷\nНажмите\nдля загрузки")
        self.setToolTip(f"Нажмите для загрузки изображения {image_type}")
    
    def mousePressEvent(self, event):
        file_path, _ = QFileDialog.getOpenFileName(
            self, f"Выберите изображение {self.image_type}",
            "",
            "Изображения (*.png *.jpg *.jpeg *.bmp *.gif);;Все файлы (*.*)"
        )
        if file_path:
            self.load_image(file_path)
    
    def load_image(self, file_path):
        pixmap = QPixmap(file_path)
        if not pixmap.isNull():
            self.current_pixmap = pixmap
            self.image_path = file_path
            scaled_pixmap = pixmap.scaled(95, 95, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            self.setPixmap(scaled_pixmap)
            self.setToolTip(f"Изображение {self.image_type}\n{os.path.basename(file_path)}\nНажмите для замены")
    
    def clear_image(self):
        self.clear()
        self.current_pixmap = None
        self.image_path = None
        self.setText("📷\nНажмите\nдля загрузки")
        self.setToolTip(f"Нажмите для загрузки изображения {self.image_type}")
    
    def get_image_path(self):
        return self.image_path
    
    def set_image_from_path(self, image_path):
        if image_path and os.path.exists(image_path):
            pixmap = QPixmap(image_path)
            if not pixmap.isNull():
                self.current_pixmap = pixmap
                self.image_path = image_path
                scaled_pixmap = pixmap.scaled(95, 95, Qt.KeepAspectRatio, Qt.SmoothTransformation)
                self.setPixmap(scaled_pixmap)
                self.setToolTip(f"Изображение {self.image_type}\n{os.path.basename(image_path)}")
                return True
        return False


class AddCoinDialog(QDialog):
    """Диалог для добавления/редактирования/копирования монеты"""
    
    REF_CURRENCY = 0
    REF_MINT = 1
    REF_EDGE = 2
    REF_METAL = 4
    REF_PURCHASE_COUNTRY = 6
    
    def __init__(self, db_manager, parent=None, coin_id=None, copy_mode=False):
        super().__init__(parent)
        self.logger = logging.getLogger('CoinCollector.GUI.AddCoinDialog')
        self.db_manager = db_manager
        self.coin_id = coin_id
        self.copy_mode = copy_mode
        self.coin = None
        self._saving = False
        
        self.images_dir = Path("coin_images")
        self.images_dir.mkdir(exist_ok=True)
        
        if copy_mode:
            self.setWindowTitle("Копирование монеты")
        elif coin_id:
            self.setWindowTitle("Редактирование монеты")
        else:
            self.setWindowTitle("Добавление монеты")
        
        self.setMinimumWidth(750)
        self.setMinimumHeight(800)
        
        self.init_ui()
        
        if coin_id:
            QTimer.singleShot(100, self.load_coin_data)
    
    def init_ui(self):
        """Инициализация интерфейса"""
        layout = QVBoxLayout()
        layout.setSpacing(5)
        layout.setContentsMargins(8, 8, 8, 8)
        self.setLayout(layout)
        
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.NoFrame)
        
        scroll_widget = QWidget()
        scroll_layout = QVBoxLayout()
        scroll_layout.setSpacing(5)
        scroll_widget.setLayout(scroll_layout)
        
        # === Группа: Основная информация ===
        main_group = QGroupBox("📋 Основное")
        main_form = QFormLayout()
        main_form.setSpacing(3)
        main_form.setContentsMargins(5, 5, 5, 5)
        
        self.country_combo = QComboBox()
        self.country_combo.setEditable(True)
        self.load_countries()
        main_form.addRow("Страна:", self.country_combo)
        
        self.catalog_number_edit = QLineEdit()
        self.catalog_number_edit.setPlaceholderText("Y# 123, KM# 456")
        main_form.addRow("№ кат.:", self.catalog_number_edit)
        
        self.denomination_value_edit = QLineEdit()
        self.denomination_value_edit.setPlaceholderText("1, 2, 5, 10")
        main_form.addRow("Номинал:", self.denomination_value_edit)
        
        currency_layout = QHBoxLayout()
        self.currency_combo = QComboBox()
        self.currency_combo.setEditable(False)
        self.load_currencies()
        currency_layout.addWidget(self.currency_combo)
        self.currency_ref_btn = QPushButton("📚")
        self.currency_ref_btn.setMaximumWidth(30)
        self.currency_ref_btn.clicked.connect(lambda: self.open_references(self.REF_CURRENCY))
        currency_layout.addWidget(self.currency_ref_btn)
        main_form.addRow("Валюта:", currency_layout)
        
        self.year_spin = QSpinBox()
        self.year_spin.setRange(-5000, 2100)
        self.year_spin.setSpecialValueText("Не указан")
        main_form.addRow("Год:", self.year_spin)
        
        self.century_combo = QComboBox()
        self.century_combo.addItems(["", "XXI", "XX", "XIX", "XVIII", "XVII", "XVI", "XV", "XIV", "XIII", "XII", "XI", "X", "IX", "VIII", "VII", "VI", "V", "IV", "III", "II", "I", "до н.э."])
        main_form.addRow("Век:", self.century_combo)
        
        main_group.setLayout(main_form)
        scroll_layout.addWidget(main_group)
        
        # === Группа: Монетный двор ===
        mint_group = QGroupBox("🏭 Монетный двор")
        mint_form = QFormLayout()
        mint_form.setSpacing(3)
        mint_form.setContentsMargins(5, 5, 5, 5)
        
        mint_layout = QHBoxLayout()
        self.mint_combo = QComboBox()
        self.mint_combo.setEditable(False)
        self.load_mints()
        mint_layout.addWidget(self.mint_combo)
        self.mint_ref_btn = QPushButton("📚")
        self.mint_ref_btn.setMaximumWidth(30)
        self.mint_ref_btn.clicked.connect(lambda: self.open_references(self.REF_MINT))
        mint_layout.addWidget(self.mint_ref_btn)
        mint_form.addRow("Двор:", mint_layout)
        
        self.mint_mark_edit = QLineEdit()
        self.mint_mark_edit.setPlaceholderText("ММД, СПМД, S")
        mint_form.addRow("Знак:", self.mint_mark_edit)
        
        mint_group.setLayout(mint_form)
        scroll_layout.addWidget(mint_group)
        
        # === Группа: Характеристики ===
        tech_group = QGroupBox("⚙️ Характеристики")
        tech_form = QFormLayout()
        tech_form.setSpacing(3)
        tech_form.setContentsMargins(5, 5, 5, 5)
        
        metal_layout = QHBoxLayout()
        self.metal_combo = QComboBox()
        self.metal_combo.setEditable(False)
        self.load_metals()
        metal_layout.addWidget(self.metal_combo)
        self.metal_ref_btn = QPushButton("📚")
        self.metal_ref_btn.setMaximumWidth(30)
        self.metal_ref_btn.clicked.connect(lambda: self.open_references_metal())
        metal_layout.addWidget(self.metal_ref_btn)
        tech_form.addRow("Металл:", metal_layout)
        
        self.weight_spin = QDoubleSpinBox()
        self.weight_spin.setRange(0, 10000)
        self.weight_spin.setSuffix(" г")
        self.weight_spin.setSpecialValueText("Не указан")
        tech_form.addRow("Вес:", self.weight_spin)
        
        self.diameter_spin = QDoubleSpinBox()
        self.diameter_spin.setRange(0, 500)
        self.diameter_spin.setSuffix(" мм")
        self.diameter_spin.setSpecialValueText("Не указан")
        tech_form.addRow("Размер:", self.diameter_spin)
        
        self.shape_combo = QComboBox()
        self.load_shape_combo()
        tech_form.addRow("Форма:", self.shape_combo)
        
        tech_group.setLayout(tech_form)
        scroll_layout.addWidget(tech_group)
        
        # === Группа: Гурт ===
        edge_group = QGroupBox("⚙️ Гурт")
        edge_layout = QVBoxLayout()
        edge_layout.setSpacing(3)
        edge_layout.setContentsMargins(5, 5, 5, 5)
        
        edge_type_layout = QHBoxLayout()
        self.edge_combo = QComboBox()
        self.edge_combo.setEditable(False)
        self.load_edges()
        edge_type_layout.addWidget(self.edge_combo)
        
        self.edge_ref_btn = QPushButton("📚")
        self.edge_ref_btn.setMaximumWidth(30)
        self.edge_ref_btn.clicked.connect(lambda: self.open_references(self.REF_EDGE))
        edge_type_layout.addWidget(self.edge_ref_btn)
        edge_layout.addLayout(edge_type_layout)
        
        edge_layout.addWidget(QLabel("Описание гурта:"))
        self.edge_description_edit = QTextEdit()
        self.edge_description_edit.setMaximumHeight(60)
        self.edge_description_edit.setPlaceholderText("Рубчатый, гладкий, узорчатый...")
        edge_layout.addWidget(self.edge_description_edit)
        
        edge_group.setLayout(edge_layout)
        scroll_layout.addWidget(edge_group)
        
        # === Группа: Фотографии ===
        photos_group = QGroupBox("📷 Фотографии")
        photos_layout = QHBoxLayout()
        photos_layout.setSpacing(10)
        photos_layout.setContentsMargins(10, 10, 10, 10)
        
        obverse_layout = QVBoxLayout()
        obverse_layout.addWidget(QLabel("Аверс:"), 0, Qt.AlignCenter)
        self.obverse_image = ImageSelector(self, "аверса")
        obverse_layout.addWidget(self.obverse_image, 0, Qt.AlignCenter)
        
        self.clear_obverse_btn = QPushButton("❌ Очистить")
        self.clear_obverse_btn.setMaximumWidth(80)
        self.clear_obverse_btn.clicked.connect(self.clear_obverse_image)
        obverse_layout.addWidget(self.clear_obverse_btn, 0, Qt.AlignCenter)
        photos_layout.addLayout(obverse_layout)
        
        reverse_layout = QVBoxLayout()
        reverse_layout.addWidget(QLabel("Реверс:"), 0, Qt.AlignCenter)
        self.reverse_image = ImageSelector(self, "реверса")
        reverse_layout.addWidget(self.reverse_image, 0, Qt.AlignCenter)
        
        self.clear_reverse_btn = QPushButton("❌ Очистить")
        self.clear_reverse_btn.setMaximumWidth(80)
        self.clear_reverse_btn.clicked.connect(self.clear_reverse_image)
        reverse_layout.addWidget(self.clear_reverse_btn, 0, Qt.AlignCenter)
        photos_layout.addLayout(reverse_layout)
        
        photos_group.setLayout(photos_layout)
        scroll_layout.addWidget(photos_group)
        
        # === Группа: Состояние ===
        status_group = QGroupBox("📊 Состояние")
        status_form = QFormLayout()
        status_form.setSpacing(3)
        status_form.setContentsMargins(5, 5, 5, 5)
        
        self.condition_combo = QComboBox()
        self.load_condition_combo()
        status_form.addRow("Сохранность:", self.condition_combo)
        
        self.rarity_combo = QComboBox()
        self.load_rarity_combo()
        status_form.addRow("Редкость:", self.rarity_combo)
        
        self.storage_combo = QComboBox()
        self.load_storage_location_combo()
        status_form.addRow("Место хранения:", self.storage_combo)
        
        self.issue_type_combo = QComboBox()
        self.load_issue_type_combo()
        status_form.addRow("Тип выпуска:", self.issue_type_combo)
        
        self.avrev_combo = QComboBox()
        self.load_avrev_combo()
        status_form.addRow("АВ/РЕВ:", self.avrev_combo)
        
        self.status_combo = QComboBox()
        self.load_status_combo()
        status_form.addRow("Статус:", self.status_combo)
        
        self.quantity_spin = QSpinBox()
        self.quantity_spin.setRange(1, 1000)
        self.quantity_spin.setValue(1)
        status_form.addRow("Кол-во:", self.quantity_spin)
        
        status_group.setLayout(status_form)
        scroll_layout.addWidget(status_group)
        
        # === Группа: Покупка ===
        purchase_group = QGroupBox("💰 Покупка")
        purchase_form = QFormLayout()
        purchase_form.setSpacing(3)
        purchase_form.setContentsMargins(5, 5, 5, 5)
        
        self.purchase_date_edit = QDateEdit()
        self.purchase_date_edit.setCalendarPopup(True)
        self.purchase_date_edit.setDate(QDate.currentDate())
        self.purchase_date_edit.setSpecialValueText("Не указана")
        purchase_form.addRow("Дата покупки:", self.purchase_date_edit)
        
        self.purchase_price_spin = QDoubleSpinBox()
        self.purchase_price_spin.setRange(0, 10000000)
        self.purchase_price_spin.setSuffix(" ₽")
        self.purchase_price_spin.setSpecialValueText("Не указана")
        purchase_form.addRow("Цена покупки:", self.purchase_price_spin)
        
        purchase_layout = QHBoxLayout()
        self.purchase_where_combo = QComboBox()
        self.purchase_where_combo.setEditable(True)
        self.purchase_where_combo.setMinimumHeight(30)
        self.load_purchase_countries()
        purchase_layout.addWidget(self.purchase_where_combo)
        
        self.purchase_ref_btn = QPushButton("📚")
        self.purchase_ref_btn.setMaximumWidth(30)
        self.purchase_ref_btn.clicked.connect(lambda: self.open_purchase_reference())
        purchase_layout.addWidget(self.purchase_ref_btn)
        purchase_form.addRow("Где куплена:", purchase_layout)
        
        self.acquisition_type_combo = QComboBox()
        self.load_acquisition_type_combo()
        purchase_form.addRow("Тип приобретения:", self.acquisition_type_combo)
        
        purchase_form.addWidget(QLabel("Информация о покупке:"))
        self.purchase_info_edit = QTextEdit()
        self.purchase_info_edit.setMaximumHeight(60)
        self.purchase_info_edit.setPlaceholderText("Дополнительная информация о покупке...")
        purchase_form.addWidget(self.purchase_info_edit)
        
        purchase_group.setLayout(purchase_form)
        scroll_layout.addWidget(purchase_group)
        
        # === Группа: Рыночная цена ===
        market_group = QGroupBox("💰 Рыночная цена")
        market_form = QFormLayout()
        market_form.setSpacing(3)
        market_form.setContentsMargins(5, 5, 5, 5)
        
        self.market_price_spin = QDoubleSpinBox()
        self.market_price_spin.setRange(0, 10000000)
        self.market_price_spin.setSuffix(" ₽")
        self.market_price_spin.setSpecialValueText("Не указана")
        market_form.addRow("Рыночная цена:", self.market_price_spin)
        
        self.market_price_date_edit = QDateEdit()
        self.market_price_date_edit.setCalendarPopup(True)
        self.market_price_date_edit.setDate(QDate.currentDate())
        self.market_price_date_edit.setSpecialValueText("Не указана")
        market_form.addRow("Дата цены:", self.market_price_date_edit)
        
        market_group.setLayout(market_form)
        scroll_layout.addWidget(market_group)
        
        scroll.setWidget(scroll_widget)
        layout.addWidget(scroll)
        
        # Кнопки
        button_layout = QHBoxLayout()
        ok_btn = QPushButton("💾 Сохранить")
        ok_btn.clicked.connect(self.accept)
        ok_btn.setMinimumHeight(35)
        ok_btn.setStyleSheet("background-color: #4CAF50; color: white; font-weight: bold;")
        button_layout.addWidget(ok_btn)
        
        cancel_btn = QPushButton("❌ Отмена")
        cancel_btn.clicked.connect(self.reject)
        cancel_btn.setMinimumHeight(35)
        button_layout.addWidget(cancel_btn)
        
        if self.copy_mode:
            ok_btn.setText("📋 Создать копию")
        
        layout.addLayout(button_layout)
        
        # Отключаем колесико мыши для всех полей ввода
        for field in [self.country_combo, self.catalog_number_edit, self.denomination_value_edit,
                      self.currency_combo, self.year_spin, self.century_combo,
                      self.mint_combo, self.mint_mark_edit, self.metal_combo, self.weight_spin,
                      self.diameter_spin, self.shape_combo, self.edge_combo, self.edge_description_edit,
                      self.condition_combo, self.rarity_combo, self.storage_combo, self.issue_type_combo,
                      self.avrev_combo, self.status_combo, self.quantity_spin, self.purchase_date_edit,
                      self.purchase_price_spin, self.purchase_where_combo, self.purchase_info_edit,
                      self.market_price_spin, self.market_price_date_edit, self.acquisition_type_combo]:
            if field:
                field.wheelEvent = lambda event: None
    
    # ========== ЗАГРУЗКА СПРАВОЧНИКОВ ==========
    
    def load_countries(self):
        self.country_combo.clear()
        
        countries = ReferenceCache.get('countries', self.db_manager.get_all_countries)
        for country in countries:
            self.country_combo.addItem(country.name, country.id)
    
    def load_currencies(self):
        self.currency_combo.clear()
        self.currency_combo.addItem("— Выберите —", None)
        
        currencies = ReferenceCache.get('currencies', self.db_manager.get_all_currencies)
        for currency in currencies:
            self.currency_combo.addItem(currency.get_display_text(), currency.id)
    
    def load_mints(self):
        self.mint_combo.clear()
        self.mint_combo.addItem("— Не указан —", None)
        mints = self.db_manager.get_all_mints()
        for mint in mints:
            self.mint_combo.addItem(mint.get_display_text(), mint.id)
    
    def load_metals(self):
        self.metal_combo.clear()
        self.metal_combo.addItem("— Выберите —", None)
        from database.models import Metal
        metals = self.db_manager.session.query(Metal).order_by(Metal.name).all()
        for metal in metals:
            self.metal_combo.addItem(metal.get_display_text(), metal.id)
    
    def load_edges(self):
        self.edge_combo.clear()
        self.edge_combo.addItem("— Не указан —", None)
        edges = self.db_manager.session.query(Edge).order_by(Edge.name).all()
        for edge in edges:
            self.edge_combo.addItem(edge.name, edge.id)
    
    def load_purchase_countries(self):
        self.purchase_where_combo.clear()
        self.purchase_where_combo.addItem("— Выберите —", None)
        countries = self.db_manager.get_all_purchase_countries()
        for country in countries:
            self.purchase_where_combo.addItem(country.name, country.id)
    
    def load_condition_combo(self):
        """Загружает справочник сохранности"""
        self.condition_combo.clear()
        self.condition_combo.addItem("—", None)
        refs = self.db_manager.session.query(StandardReference).filter_by(field_key='condition').order_by(StandardReference.sort_order).all()
        for ref in refs:
            self.condition_combo.addItem(ref.name, ref.id)
    
    def load_rarity_combo(self):
        """Загружает справочник редкости"""
        self.rarity_combo.clear()
        self.rarity_combo.addItem("—", None)
        refs = self.db_manager.session.query(StandardReference).filter_by(field_key='rarity').order_by(StandardReference.sort_order).all()
        for ref in refs:
            self.rarity_combo.addItem(ref.name, ref.id)
    
    def load_shape_combo(self):
        """Загружает справочник форм"""
        self.shape_combo.clear()
        self.shape_combo.addItem("—", None)
        refs = self.db_manager.session.query(StandardReference).filter_by(field_key='shape').order_by(StandardReference.sort_order).all()
        for ref in refs:
            self.shape_combo.addItem(ref.name, ref.id)
    
    def load_issue_type_combo(self):
        """Загружает справочник типов выпуска"""
        self.issue_type_combo.clear()
        self.issue_type_combo.addItem("—", None)
        refs = self.db_manager.session.query(StandardReference).filter_by(field_key='issue_type').order_by(StandardReference.sort_order).all()
        for ref in refs:
            self.issue_type_combo.addItem(ref.name, ref.id)
    
    def load_avrev_combo(self):
        """Загружает справочник АВ/РЕВ"""
        self.avrev_combo.clear()
        self.avrev_combo.addItem("—", None)
        refs = self.db_manager.session.query(StandardReference).filter_by(field_key='avrev').order_by(StandardReference.sort_order).all()
        for ref in refs:
            self.avrev_combo.addItem(ref.name, ref.id)
    
    def load_status_combo(self):
        """Загружает справочник статусов"""
        self.status_combo.clear()
        self.status_combo.addItem("—", None)
        refs = self.db_manager.session.query(StandardReference).filter_by(field_key='status').order_by(StandardReference.sort_order).all()
        for ref in refs:
            self.status_combo.addItem(ref.name, ref.id)
    
    def load_acquisition_type_combo(self):
        """Загружает справочник типов приобретения"""
        self.acquisition_type_combo.clear()
        self.acquisition_type_combo.addItem("—", None)
        refs = self.db_manager.session.query(StandardReference).filter_by(field_key='acquisition_type').order_by(StandardReference.sort_order).all()
        for ref in refs:
            self.acquisition_type_combo.addItem(ref.name, ref.id)
    
    def load_storage_location_combo(self):
        """Загружает справочник мест хранения"""
        self.storage_combo.clear()
        self.storage_combo.addItem("—", None)
        refs = self.db_manager.session.query(StandardReference).filter_by(field_key='storage_location').order_by(StandardReference.sort_order).all()
        for ref in refs:
            self.storage_combo.addItem(ref.name, ref.id)
    
    # ========== МЕТОДЫ ДЛЯ ИЗОБРАЖЕНИЙ ==========
    
    def clear_obverse_image(self):
        self.obverse_image.clear_image()
    
    def clear_reverse_image(self):
        self.reverse_image.clear_image()
    
    # ========== ДИАЛОГИ СПРАВОЧНИКОВ ==========
    
    def open_references(self, ref_type):
        dialog = ReferencesDialog(self.db_manager, self, ref_type)
        if dialog.exec():
            current_currency_id = self.currency_combo.currentData()
            current_mint_id = self.mint_combo.currentData()
            current_edge_id = self.edge_combo.currentData()
            
            self.load_currencies()
            self.load_mints()
            self.load_edges()
            
            if current_currency_id:
                idx = self.currency_combo.findData(current_currency_id)
                if idx >= 0:
                    self.currency_combo.setCurrentIndex(idx)
            if current_mint_id:
                idx = self.mint_combo.findData(current_mint_id)
                if idx >= 0:
                    self.mint_combo.setCurrentIndex(idx)
            if current_edge_id:
                idx = self.edge_combo.findData(current_edge_id)
                if idx >= 0:
                    self.edge_combo.setCurrentIndex(idx)
    
    def open_references_metal(self):
        dialog = ReferencesDialog(self.db_manager, self, 4)
        if dialog.exec():
            current_metal_id = self.metal_combo.currentData()
            self.load_metals()
            if current_metal_id:
                idx = self.metal_combo.findData(current_metal_id)
                if idx >= 0:
                    self.metal_combo.setCurrentIndex(idx)
    
    def open_purchase_reference(self):
        from gui.dialogs.purchase_country_manager_dialog import PurchaseCountryManagerDialog
        dialog = PurchaseCountryManagerDialog(self.db_manager, self)
        if dialog.exec():
            current_id = self.purchase_where_combo.currentData()
            self.load_purchase_countries()
            if current_id:
                idx = self.purchase_where_combo.findData(current_id)
                if idx >= 0:
                    self.purchase_where_combo.setCurrentIndex(idx)
    
    # ========== СБОР ДАННЫХ ==========
    
    def collect_data(self):
        if not self.country_combo.currentText().strip():
            QMessageBox.warning(self, "Предупреждение", "Укажите страну")
            return None
        
        if not self.currency_combo.currentData():
            QMessageBox.warning(self, "Предупреждение", "Выберите валюту")
            return None
        
        country_text = self.country_combo.currentText().strip()
        if self.country_combo.currentData():
            country = self.db_manager.session.query(Country).get(self.country_combo.currentData())
        else:
            country = self.db_manager.get_or_create_country(country_text)
        
        if not country:
            QMessageBox.warning(self, "Ошибка", "Не удалось определить страну")
            return None
        
        currency_id = self.currency_combo.currentData()
        currency = self.db_manager.get_currency(currency_id)
        mint_id = self.mint_combo.currentData()
        metal_id = self.metal_combo.currentData()
        edge_id = self.edge_combo.currentData()
        
        # Получаем ID из справочников
        condition_id = self.condition_combo.currentData()
        rarity_id = self.rarity_combo.currentData()
        shape_id = self.shape_combo.currentData()
        issue_type_id = self.issue_type_combo.currentData()
        avrev_id = self.avrev_combo.currentData()
        status_id = self.status_combo.currentData()
        acquisition_type_id = self.acquisition_type_combo.currentData()
        storage_location_id = self.storage_combo.currentData()
        
        # Получаем строковые значения для обратной совместимости
        condition_name = self.condition_combo.currentText() if condition_id else None
        rarity_name = self.rarity_combo.currentText() if rarity_id else None
        shape_name = self.shape_combo.currentText() if shape_id else None
        issue_type_name = self.issue_type_combo.currentText() if issue_type_id else None
        avrev_name = self.avrev_combo.currentText() if avrev_id else None
        status_name = self.status_combo.currentText() if status_id else None
        acquisition_type_name = self.acquisition_type_combo.currentText() if acquisition_type_id else None
        storage_location_name = self.storage_combo.currentText() if storage_location_id else None
        
        data = {
            'country_id': country.id,
            'currency_id': currency_id,
            'currency': currency.name if currency else None,
            'mint_id': mint_id,
            'mint': None,
            'mint_mark': self.mint_mark_edit.text() or None,
            'metal_id': metal_id,
            'edge_id': edge_id,
            'edge_description': self.edge_description_edit.toPlainText().strip() or None,
            'catalog_number': self.catalog_number_edit.text() or None,
            'denomination_value': self.denomination_value_edit.text() or None,
            'century': self.century_combo.currentText() or None,
            'year': self.year_spin.value() if self.year_spin.value() != 0 else None,
            'weight': self.weight_spin.value() if self.weight_spin.value() != 0 else None,
            'diameter': self.diameter_spin.value() if self.diameter_spin.value() != 0 else None,
            'condition': condition_name,
            'rarity': rarity_name,
            'shape': shape_name,
            'issue_type': issue_type_name,
            'avrev': avrev_name,
            'storage_location': storage_location_name,
            'acquisition_type': acquisition_type_name,
            'status': status_name,
            'quantity': self.quantity_spin.value(),
            'purchase_date': self.purchase_date_edit.date().toPython() if self.purchase_date_edit.date() else None,
            'purchase_price': self.purchase_price_spin.value() if self.purchase_price_spin.value() != 0 else None,
            'purchase_where': self.purchase_where_combo.currentText() or None,
            'purchase_info': self.purchase_info_edit.toPlainText().strip() or None,
            'market_price': self.market_price_spin.value() if self.market_price_spin.value() != 0 else None,
            'market_price_date': self.market_price_date_edit.date().toPython() if self.market_price_date_edit.date() else None,
            # ID справочников
            'condition_id': condition_id,
            'rarity_id': rarity_id,
            'shape_id': shape_id,
            'issue_type_id': issue_type_id,
            'avrev_id': avrev_id,
            'status_id': status_id,
            'acquisition_type_id': acquisition_type_id,
            'storage_location_id': storage_location_id,
        }
        
        if mint_id:
            mint = self.db_manager.get_mint(mint_id)
            if mint:
                data['mint'] = mint.get_full_name()
        
        return data
    
    # ========== ЗАГРУЗКА ДАННЫХ МОНЕТЫ ==========
    
    def load_coin_data(self):
        try:
            self.coin = self.db_manager.get_coin(self.coin_id)
            if not self.coin:
                return
            
            # Страна
            if self.coin.country:
                idx = self.country_combo.findData(self.coin.country.id)
                if idx >= 0:
                    self.country_combo.setCurrentIndex(idx)
            
            # Основные поля
            self.catalog_number_edit.setText(self.coin.catalog_number or "")
            self.denomination_value_edit.setText(self.coin.denomination_value or "")
            
            # Валюта
            if self.coin.currency_id:
                idx = self.currency_combo.findData(self.coin.currency_id)
                if idx >= 0:
                    self.currency_combo.setCurrentIndex(idx)
            
            # Монетный двор
            if self.coin.mint_id:
                idx = self.mint_combo.findData(self.coin.mint_id)
                if idx >= 0:
                    self.mint_combo.setCurrentIndex(idx)
            
            # Металл
            if self.coin.metal_id:
                idx = self.metal_combo.findData(self.coin.metal_id)
                if idx >= 0:
                    self.metal_combo.setCurrentIndex(idx)
            
            # Гурт
            if hasattr(self.coin, 'edge_id') and self.coin.edge_id:
                idx = self.edge_combo.findData(self.coin.edge_id)
                if idx >= 0:
                    self.edge_combo.setCurrentIndex(idx)
            
            # Остальные поля
            self.mint_mark_edit.setText(self.coin.mint_mark or "")
            
            if self.coin.year:
                self.year_spin.setValue(self.coin.year)
            
            if hasattr(self.coin, 'century') and self.coin.century:
                idx = self.century_combo.findText(self.coin.century)
                if idx >= 0:
                    self.century_combo.setCurrentIndex(idx)
            
            if self.coin.weight:
                self.weight_spin.setValue(self.coin.weight)
            
            if self.coin.diameter:
                self.diameter_spin.setValue(self.coin.diameter)
            
            # Состояние - через ID справочников
            if hasattr(self.coin, 'condition_id') and self.coin.condition_id:
                idx = self.condition_combo.findData(self.coin.condition_id)
                if idx >= 0:
                    self.condition_combo.setCurrentIndex(idx)
            elif self.coin.condition:
                idx = self.condition_combo.findText(self.coin.condition)
                if idx >= 0:
                    self.condition_combo.setCurrentIndex(idx)
            
            if hasattr(self.coin, 'rarity_id') and self.coin.rarity_id:
                idx = self.rarity_combo.findData(self.coin.rarity_id)
                if idx >= 0:
                    self.rarity_combo.setCurrentIndex(idx)
            elif hasattr(self.coin, 'rarity') and self.coin.rarity:
                idx = self.rarity_combo.findText(self.coin.rarity)
                if idx >= 0:
                    self.rarity_combo.setCurrentIndex(idx)
            
            if hasattr(self.coin, 'shape_id') and self.coin.shape_id:
                idx = self.shape_combo.findData(self.coin.shape_id)
                if idx >= 0:
                    self.shape_combo.setCurrentIndex(idx)
            elif hasattr(self.coin, 'shape') and self.coin.shape:
                idx = self.shape_combo.findText(self.coin.shape)
                if idx >= 0:
                    self.shape_combo.setCurrentIndex(idx)
            
            if hasattr(self.coin, 'issue_type_id') and self.coin.issue_type_id:
                idx = self.issue_type_combo.findData(self.coin.issue_type_id)
                if idx >= 0:
                    self.issue_type_combo.setCurrentIndex(idx)
            elif hasattr(self.coin, 'issue_type') and self.coin.issue_type:
                idx = self.issue_type_combo.findText(self.coin.issue_type)
                if idx >= 0:
                    self.issue_type_combo.setCurrentIndex(idx)
            
            if hasattr(self.coin, 'avrev_id') and self.coin.avrev_id:
                idx = self.avrev_combo.findData(self.coin.avrev_id)
                if idx >= 0:
                    self.avrev_combo.setCurrentIndex(idx)
            elif hasattr(self.coin, 'avrev') and self.coin.avrev:
                idx = self.avrev_combo.findText(self.coin.avrev)
                if idx >= 0:
                    self.avrev_combo.setCurrentIndex(idx)
            
            # Статус - через ID
            if hasattr(self.coin, 'status_id') and self.coin.status_id:
                idx = self.status_combo.findData(self.coin.status_id)
                if idx >= 0:
                    self.status_combo.setCurrentIndex(idx)
            elif self.coin.status:
                idx = self.status_combo.findText(self.coin.status)
                if idx >= 0:
                    self.status_combo.setCurrentIndex(idx)
            
            # Место хранения
            if hasattr(self.coin, 'storage_location_id') and self.coin.storage_location_id:
                idx = self.storage_combo.findData(self.coin.storage_location_id)
                if idx >= 0:
                    self.storage_combo.setCurrentIndex(idx)
            elif hasattr(self.coin, 'storage_location') and self.coin.storage_location:
                idx = self.storage_combo.findText(self.coin.storage_location)
                if idx >= 0:
                    self.storage_combo.setCurrentIndex(idx)
            
            # Тип приобретения
            if hasattr(self.coin, 'acquisition_type_id') and self.coin.acquisition_type_id:
                idx = self.acquisition_type_combo.findData(self.coin.acquisition_type_id)
                if idx >= 0:
                    self.acquisition_type_combo.setCurrentIndex(idx)
            elif hasattr(self.coin, 'acquisition_type') and self.coin.acquisition_type:
                idx = self.acquisition_type_combo.findText(self.coin.acquisition_type)
                if idx >= 0:
                    self.acquisition_type_combo.setCurrentIndex(idx)
            
            # Покупка
            if hasattr(self.coin, 'purchase_date') and self.coin.purchase_date:
                self.purchase_date_edit.setDate(self.coin.purchase_date)
            
            if self.coin.purchase_price:
                self.purchase_price_spin.setValue(self.coin.purchase_price)
            
            if hasattr(self.coin, 'purchase_where') and self.coin.purchase_where:
                idx = self.purchase_where_combo.findText(self.coin.purchase_where)
                if idx >= 0:
                    self.purchase_where_combo.setCurrentIndex(idx)
            
            if hasattr(self.coin, 'purchase_info') and self.coin.purchase_info:
                self.purchase_info_edit.setText(self.coin.purchase_info)
            
            # Гурт описание
            if hasattr(self.coin, 'edge_description'):
                self.edge_description_edit.setText(self.coin.edge_description or "")
            
            # Рыночная цена
            if hasattr(self.coin, 'market_price') and self.coin.market_price:
                self.market_price_spin.setValue(self.coin.market_price)
            
            if hasattr(self.coin, 'market_price_date') and self.coin.market_price_date:
                self.market_price_date_edit.setDate(self.coin.market_price_date)
            
            # Изображения
            if hasattr(self.coin, 'obverse_image') and self.coin.obverse_image:
                if os.path.exists(self.coin.obverse_image):
                    self.obverse_image.set_image_from_path(self.coin.obverse_image)
            
            if hasattr(self.coin, 'reverse_image') and self.coin.reverse_image:
                if os.path.exists(self.coin.reverse_image):
                    self.reverse_image.set_image_from_path(self.coin.reverse_image)
            
            if self.copy_mode:
                self.setWindowTitle(f"Копирование монеты (оригинал ID: {self.coin_id})")
            
        except Exception as e:
            self.logger.error(f"Ошибка при загрузке данных монеты: {e}")
            QMessageBox.critical(self, "Ошибка", f"Не удалось загрузить данные монеты: {e}")
    
    def accept(self):
        if self._saving:
            return
        self._saving = True
        
        try:
            data = self.collect_data()
            if data:
                if self.coin_id and not self.copy_mode:
                    self.db_manager.update_coin(self.coin_id, data)
                    QMessageBox.information(self, "Успех", "Монета успешно обновлена")
                else:
                    new_id = self.db_manager.add_coin(data)
                    QMessageBox.information(self, "Успех", "Монета успешно добавлена")
                
                super().accept()
            else:
                self._saving = False
        except Exception as e:
            self.logger.error(f"Ошибка при сохранении: {e}")
            QMessageBox.critical(self, "Ошибка", f"Не удалось сохранить монету: {e}")
            self._saving = False