# ===== gui/widgets/detail_panel/coin_edit.py =====
# ПОЛНОСТЬЮ ЗАМЕНИТЬ ФАЙЛ

# -*- coding: utf-8 -*-

"""
Режим редактирования монеты
"""

import os
import json
import logging
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QScrollArea, QLabel, 
                               QGroupBox, QGridLayout, QHBoxLayout, QPushButton, 
                               QDateEdit, QComboBox, QLineEdit, QSpinBox, 
                               QDoubleSpinBox, QSizePolicy, QFormLayout, 
                               QCheckBox, QTextEdit, QApplication)
from PySide6.QtCore import Qt, QDate
from .base_panel import ImageSelector, ClickableTextEdit


class CoinEditWidget(QWidget):
    """Виджет для редактирования монеты"""
    
    # Фиксированные размеры для всех полей
    FIELD_WIDTH = 142      # Ширина для обычных полей и комбобоксов без кнопки
    COMBO_WIDTH = 132      # Ширина для комбобоксов с кнопкой
    
    def __init__(self, db_manager, parent=None):
        super().__init__(parent)
        self.db_manager = db_manager
        self.parent_tab = parent
        self.logger = logging.getLogger('CoinCollector.GUI.CoinEditWidget')
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        self.setLayout(layout)
        
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        
        scroll_widget = QWidget()
        scroll_layout = QVBoxLayout()
        scroll_layout.setSpacing(4)
        scroll_layout.setContentsMargins(4, 4, 4, 4)
        scroll_widget.setLayout(scroll_layout)
        
        self.coin_edit_empty_label = QLabel("Выберите монету для редактирования")
        self.coin_edit_empty_label.setAlignment(Qt.AlignCenter)
        self.coin_edit_empty_label.setStyleSheet("color: gray; font-size: 11px; padding: 20px;")
        scroll_layout.addWidget(self.coin_edit_empty_label)
        
        self.coin_edit_form_container = QWidget()
        edit_form_layout = QVBoxLayout()
        edit_form_layout.setSpacing(6)
        edit_form_layout.setContentsMargins(0, 0, 0, 0)
        self.coin_edit_form_container.setLayout(edit_form_layout)
        
        # === 1. ФОТОГРАФИИ ===
        self._create_photos_section(edit_form_layout)
        
        # === 2. КОНТЕЙНЕР ДЛЯ ВСЕХ ПОЛЕЙ ===
        self.custom_fields_container = QWidget()
        self.custom_fields_layout = QVBoxLayout()
        self.custom_fields_layout.setSpacing(6)
        self.custom_fields_layout.setContentsMargins(0, 0, 0, 0)
        self.custom_fields_container.setLayout(self.custom_fields_layout)
        edit_form_layout.addWidget(self.custom_fields_container)
        
        edit_form_layout.addStretch()
        
        self.coin_edit_form_container.hide()
        scroll_layout.addWidget(self.coin_edit_form_container)
        scroll.setWidget(scroll_widget)
        layout.addWidget(scroll)
        
        from PySide6.QtCore import QTimer
        QTimer.singleShot(100, self.apply_small_height_to_all_fields)

# ===== gui/widgets/detail_panel/coin_edit.py =====
# МЕТОД: CoinEditWidget.rebuild_custom_fields (ПОЛНОСТЬЮ ЗАМЕНИТЬ)

    def rebuild_custom_fields(self):
        """Перестраивает все поля с группировкой по категориям (только show_in_edit)"""
        # Очищаем контейнер
        while self.custom_fields_layout.count():
            child = self.custom_fields_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()
        
        if not self.db_manager:
            print("❌ rebuild_custom_fields: db_manager is None")
            return
        
        # Загружаем настройки всех полей из БД
        field_settings = {f.field_key: f for f in self.db_manager.get_all_field_settings()}
        
        if hasattr(self.parent_tab, 'edit_fields'):
            pass
        else:
            print("  ❌ parent_tab.edit_fields does NOT exist!")
            return
        
        from gui.dialogs.column_selector import ColumnSelectorDialog
        
        # Группируем поля по категориям
        categories = {}
        
        # Список полей, которые НЕ нужно показывать в режиме редактирования
        skip_fields = [
            'flag',          # Флаг страны — не редактируется
            'select',        # Чекбокс выделения — не нужен в форме
            'id',            # ID — не редактируется
        ]
        
        # === ПРИНУДИТЕЛЬНО ДОБАВЛЯЕМ СТРАНУ ПЕРВОЙ ===
        if 'Основные' not in categories:
            categories['Основные'] = []
        
        categories['Основные'].insert(0, {
            "field_key": "country",
            "edit_key": "country",
            "name": "Страна",
            "field_type": "text",
            "is_standard": True,
            "sort_order": -100
        })
        
        # Добавляем ВСЕ стандартные поля, которые show_in_edit=True
        fields_added = 1  # Начинаем с 1 (страна уже добавлена)
        for col in ColumnSelectorDialog.STANDARD_COLUMNS:
            if col["key"] == "select":
                continue
            
            # Пропускаем поля из списка исключений
            if col["key"] in skip_fields:
                continue
            
            # Пропускаем country — уже добавлен принудительно
            if col["key"] == "country":
                continue
            
            # Получаем настройки из БД
            settings = field_settings.get(col["key"])
            
            # Проверяем, нужно ли показывать поле в режиме редактирования
            if settings:
                if not getattr(settings, 'show_in_edit', True):
                    continue
                if not settings.show_in_form:
                    continue
            else:
                if not col.get("show_in_form", True):
                    continue
            
            field_name = settings.name if settings else col["name"]
            category = settings.category if settings else col.get("category", "Основные")
            field_type = col["field_type"]
            
            # key_mapping для всех полей
            key_mapping = {
                'catalog_number': 'catalog_number',
                'denomination_value': 'denomination_value',
                'currency': 'currency',
                'year': 'year',
                'century': 'century',
                'mint': 'mint',
                'mint_mark': 'mint_mark',
                'metal': 'metal',
                'weight': 'weight',
                'diameter': 'diameter',
                'shape': 'shape',
                'edge': 'edge',
                'edge_description': 'edge_description',
                'condition': 'condition',
                'rarity': 'rarity',
                'storage_location': 'storage_location',
                'issue_type': 'issue_type',
                'avrev': 'avrev',
                'status': 'status',
                'purchase_date': 'purchase_date',
                'purchase_price': 'purchase_price',
                'purchase_where': 'purchase_where',
                'purchase_country': 'purchase_country',
                'purchase_info': 'purchase_info',
                'acquisition_type': 'acquisition_type',
                'sale_price': 'sale_price',
                'coin_info': 'coin_info',
                'ucoin_url': 'ucoin_url',
                'meshok_url': 'meshok_url',
                'market_price': 'market_price',
                'market_price_date': 'market_price_date',
                'period': 'period_id',
            }
            
            edit_key = key_mapping.get(col["key"], col["key"])
            
            if edit_key not in self.parent_tab.edit_fields:
                continue
            
            if category not in categories:
                categories[category] = []
            
            categories[category].append({
                "field_key": col["key"],
                "edit_key": edit_key,
                "name": field_name,
                "field_type": field_type,
                "is_standard": True,
                "sort_order": settings.sort_order if settings else col.get("sort_order", 0)
            })
            fields_added += 1
        
        # Добавляем пользовательские поля (show_in_edit=True)
        custom_added = 0
        if hasattr(self.parent_tab, 'custom_fields'):
            for field_dict in self.parent_tab.custom_fields:
                # field_dict теперь словарь, а не объект
                if not field_dict.get('show_in_form', True):
                    continue
                if not field_dict.get('show_in_edit', True):
                    continue
                
                category = field_dict.get('category', 'Дополнительные')
                if category not in categories:
                    categories[category] = []
                
                categories[category].append({
                    "field_key": field_dict['field_key'],
                    "edit_key": f"custom_{field_dict['field_key']}",
                    "name": field_dict['name'],
                    "field_type": field_dict['field_type'],
                    "is_standard": False,
                    "sort_order": field_dict.get('sort_order', 0),
                    "options": field_dict.get('options'),
                    "default_value": field_dict.get('default_value')
                })
                custom_added += 1
        
        # Сортируем категории
        category_order = ["Основные", "Монетный двор", "Характеристики", "Гурт", "Состояние", "Покупка", "Рыночная цена", "Ссылки", "Информация", "Дополнительные"]
        
        for category in category_order:
            if category in categories:
                self._add_category_group(category, categories[category])
        
        for category, fields in categories.items():
            if category not in category_order:
                self._add_category_group(category, fields)
        
        self.custom_fields_container.updateGeometry()
        self.coin_edit_form_container.updateGeometry()
        self.updateGeometry()

    def _add_category_group(self, category_name, fields):
        """Добавляет группу полей для категории"""
        if not fields:
            return
        
        group = QGroupBox(category_name)
        group.setStyleSheet("""
            QGroupBox {
                font-weight: bold;
                font-size: 10px;
                margin-top: 3px;
                padding-top: 2px;
                border: 1px solid #d0d0d0;
                border-radius: 4px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 8px;
                padding: 0 4px 0 4px;
            }
        """)
        
        grid_layout = QGridLayout()
        grid_layout.setSpacing(2)
        grid_layout.setHorizontalSpacing(6)
        grid_layout.setVerticalSpacing(2)
        grid_layout.setContentsMargins(6, 6, 6, 6)
        
        sorted_fields = sorted(fields, key=lambda f: f.get("sort_order", 0))
        
        row = 0
        for field in sorted_fields:
            field_key = field["field_key"]
            edit_key = field.get("edit_key", field_key)
            field_name = field["name"]
            is_standard = field.get("is_standard", True)
            
            label = QLabel(f"{field_name}:")
            label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
            label.setMinimumWidth(87)
            label.setMaximumWidth(87)
            label.setStyleSheet("font-size: 10px; color: #333;")
            grid_layout.addWidget(label, row, 0)
            
            if is_standard and edit_key in self.parent_tab.edit_fields:
                widget = self.parent_tab.edit_fields[edit_key]
                
                # Проверяем, нужна ли кнопка справочника
                ref_types = {
                    'currency': self.parent_tab.REF_CURRENCY,
                    'mint': self.parent_tab.REF_MINT,
                    'metal': self.parent_tab.REF_METAL,
                    'edge': self.parent_tab.REF_EDGE,
                    'purchase_country': self.parent_tab.REF_PURCHASE_COUNTRY,
                    'period_id': self.parent_tab.REF_PERIOD,
                    'status': self.parent_tab.REF_STATUS,
                    'condition': self.parent_tab.REF_CONDITION,
                    'rarity': self.parent_tab.REF_RARITY,
                    'shape': self.parent_tab.REF_SHAPE,
                    'issue_type': self.parent_tab.REF_ISSUE_TYPE,
                    'avrev': self.parent_tab.REF_AVREV,
                    'acquisition_type': self.parent_tab.REF_ACQUISITION_TYPE,
                    'storage_location': self.parent_tab.REF_STORAGE_LOCATION,
                }
                
                if edit_key in ref_types:
                    # Комбобокс с кнопкой справочника
                    container = QWidget()
                    container_layout = QHBoxLayout(container)
                    container_layout.setContentsMargins(0, 0, 0, 0)
                    container_layout.setSpacing(2)
                    
                    widget.setMinimumWidth(140)
                    widget.setMaximumWidth(140)
                    widget.setFixedHeight(18)
                    container_layout.addWidget(widget, 1)
                    
                    ref_btn = QPushButton("📚")
                    ref_btn.setFixedSize(20, 18)
                    ref_btn.setCursor(Qt.PointingHandCursor)
                    ref_btn.setToolTip("Открыть справочник")
                    ref_btn.setStyleSheet("""
                        QPushButton {
                            background-color: #e0e0e0;
                            border: 1px solid #aaa;
                            border-radius: 3px;
                            font-size: 9px;
                        }
                        QPushButton:hover {
                            background-color: #4a6fa5;
                            color: white;
                        }
                    """)
                    ref_btn.clicked.connect(lambda checked, rt=ref_types[edit_key]: self.parent_tab.open_references(rt))
                    container_layout.addWidget(ref_btn, 0)
                    
                    grid_layout.addWidget(container, row, 1)
                else:
                    # Обычное поле (LineEdit, SpinBox и т.д.)
                    widget.setMinimumWidth(165)
                    widget.setMaximumWidth(165)
                    widget.setFixedHeight(18)
                    grid_layout.addWidget(widget, row, 1)
            else:
                # Пользовательское поле
                if not is_standard:
                    if field_key in self.parent_tab.custom_edit_fields:
                        widget = self.parent_tab.custom_edit_fields[field_key]
                        widget.setMinimumWidth(165)
                        widget.setMaximumWidth(165)
                        if hasattr(widget, 'setFixedHeight'):
                            widget.setFixedHeight(18)
                        grid_layout.addWidget(widget, row, 1)
                    else:
                        empty_label = QLabel("—")
                        empty_label.setStyleSheet("color: #999; font-size: 10px;")
                        grid_layout.addWidget(empty_label, row, 1)
                else:
                    empty_label = QLabel("—")
                    empty_label.setStyleSheet("color: #999; font-size: 10px;")
                    grid_layout.addWidget(empty_label, row, 1)
            
            row += 1
        
        group.setLayout(grid_layout)
        self.custom_fields_layout.addWidget(group)

    def open_custom_reference(self, field_key, field_name):
        """Открывает диалог управления пользовательским справочником"""
        from gui.dialogs.custom_reference_dialog import CustomReferenceDialog
        
        dialog = CustomReferenceDialog(self.db_manager, field_key, field_name, self)
        dialog.data_changed.connect(lambda: self.refresh_custom_combo(field_key))
        dialog.exec()
    
    def refresh_custom_combo(self, field_key):
        """Обновляет комбобокс пользовательского справочника"""
        if field_key in self.parent_tab.custom_edit_fields:
            widget = self.parent_tab.custom_edit_fields[field_key]
            if isinstance(widget, QComboBox):
                current_value = widget.currentData()
                widget.clear()
                widget.addItem("—", None)
                
                ref_items = self.db_manager.get_custom_references(field_key)
                for ref in ref_items:
                    widget.addItem(ref.name, ref.value)
                
                if current_value:
                    idx = widget.findData(current_value)
                    if idx >= 0:
                        widget.setCurrentIndex(idx)
    
    def _disable_mouse_wheel(self):
        """Отключает колесико мыши для всех полей ввода"""
        for key, field in self.parent_tab.edit_fields.items():
            if field:
                try:
                    field.wheelEvent = lambda event: None
                except:
                    pass
        
        if hasattr(self.parent_tab, 'custom_edit_fields'):
            for field in self.parent_tab.custom_edit_fields.values():
                if field:
                    try:
                        field.wheelEvent = lambda event: None
                    except:
                        pass

    def apply_small_height_to_all_fields(self):
        """Принудительно применяет маленькую высоту ко всем полям ввода и отключает колесико"""
        small_height = 17
        text_height = 25
        date_height = 24
        
        for group in self.findChildren(QGroupBox):
            group.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Minimum)
            group.setMaximumWidth(380)
        
        button_style = """
            QPushButton {
                background-color: #f8f9fa;
                border: 1px solid #ced4da;
                border-radius: 4px;
                font-size: 10px;
                padding: 0px;
                margin: 0px;
            }
            QPushButton:hover {
                background-color: #e9ecef;
                border-color: #4a6fa5;
            }
            QPushButton:pressed {
                background-color: #dee2e6;
                border-color: #4a6fa5;
            }
        """
        
        for key, field in self.parent_tab.edit_fields.items():
            try:
                field.wheelEvent = lambda event: None
                
                if key == 'purchase_date':
                    field.setFixedHeight(date_height)
                    field.setMinimumHeight(date_height)
                    field.setMaximumHeight(date_height)
                elif key in ['coin_info', 'purchase_info', 'edge_description']:
                    field.setFixedHeight(text_height)
                    field.setMinimumHeight(text_height)
                    field.setMaximumHeight(text_height)
                else:
                    field.setFixedHeight(small_height)
                    field.setMinimumHeight(small_height)
                    field.setMaximumHeight(small_height)
                field.updateGeometry()
            except Exception as e:
                pass
        
        if hasattr(self.parent_tab, 'custom_edit_fields'):
            for field_key, field in self.parent_tab.custom_edit_fields.items():
                try:
                    field.wheelEvent = lambda event: None
                    if isinstance(field, QDateEdit):
                        field.setFixedHeight(date_height)
                    elif isinstance(field, (QTextEdit,)):
                        field.setFixedHeight(text_height)
                    elif isinstance(field, (QLineEdit, QComboBox, QDoubleSpinBox)):
                        field.setFixedHeight(small_height)
                    field.updateGeometry()
                except:
                    pass
        
        for btn in self.findChildren(QPushButton):
            if btn.text() == "📚" or btn.toolTip() == "Открыть справочник":
                btn.setStyleSheet(button_style)
                btn.setCursor(Qt.PointingHandCursor)
        
        # ИСПРАВЛЕНО: перебираем каждый тип отдельно
        for widget in self.findChildren(QLabel):
            try:
                font = widget.font()
                if font.pointSize() <= 0:
                    font.setPointSize(9)
                    widget.setFont(font)
            except:
                pass
        
        for widget in self.findChildren(QPushButton):
            try:
                font = widget.font()
                if font.pointSize() <= 0:
                    font.setPointSize(9)
                    widget.setFont(font)
            except:
                pass
        
        for widget in self.findChildren(QLineEdit):
            try:
                font = widget.font()
                if font.pointSize() <= 0:
                    font.setPointSize(9)
                    widget.setFont(font)
            except:
                pass
        
        for widget in self.findChildren(QComboBox):
            try:
                font = widget.font()
                if font.pointSize() <= 0:
                    font.setPointSize(9)
                    widget.setFont(font)
            except:
                pass

    def _create_photos_section(self, parent_layout):
        photos_group = QGroupBox("📷 Фотографии")
        photos_group.setFixedHeight(160)
        photos_group.setStyleSheet("""
            QGroupBox {
                font-weight: bold;
                font-size: 10px;
                margin-top: 6px;
                padding-top: 6px;
                border: 1px solid #d0d0d0;
                border-radius: 4px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 8px;
                padding: 0 4px 0 4px;
            }
        """)
        
        photos_layout = QHBoxLayout()
        photos_layout.setSpacing(15)
        photos_layout.setContentsMargins(15, 5, 15, 5)
        
        # Аверс
        obverse_layout = QVBoxLayout()
        obverse_layout.setSpacing(3)
        obverse_label = QLabel("Аверс")
        obverse_label.setAlignment(Qt.AlignCenter)
        obverse_label.setStyleSheet("font-weight: bold; font-size: 10px; color: #4a6fa5;")
        obverse_layout.addWidget(obverse_label)
        
        self.edit_obverse_image = ImageSelector(self, "аверса", editable=True)
        self.edit_obverse_image.setFixedSize(100, 100)
        self.edit_obverse_image.setCursor(Qt.PointingHandCursor)
        obverse_layout.addWidget(self.edit_obverse_image, 0, Qt.AlignCenter)
        
        self.clear_obverse_btn = QPushButton("Очистить")
        self.clear_obverse_btn.setFixedSize(70, 22)
        self.clear_obverse_btn.setStyleSheet("""
            QPushButton {
                background-color: #f0f0f0;
                border: 1px solid #ccc;
                border-radius: 3px;
                font-size: 9px;
            }
            QPushButton:hover {
                background-color: #e0e0e0;
            }
        """)
        self.clear_obverse_btn.clicked.connect(self.clear_obverse_image)
        obverse_layout.addWidget(self.clear_obverse_btn, 0, Qt.AlignCenter)
        
        photos_layout.addLayout(obverse_layout)
        
        # Реверс
        reverse_layout = QVBoxLayout()
        reverse_layout.setSpacing(3)
        reverse_label = QLabel("Реверс")
        reverse_label.setAlignment(Qt.AlignCenter)
        reverse_label.setStyleSheet("font-weight: bold; font-size: 10px; color: #4a6fa5;")
        reverse_layout.addWidget(reverse_label)
        
        self.edit_reverse_image = ImageSelector(self, "реверса", editable=True)
        self.edit_reverse_image.setFixedSize(100, 100)
        self.edit_reverse_image.setCursor(Qt.PointingHandCursor)
        reverse_layout.addWidget(self.edit_reverse_image, 0, Qt.AlignCenter)
        
        self.clear_reverse_btn = QPushButton("Очистить")
        self.clear_reverse_btn.setFixedSize(70, 22)
        self.clear_reverse_btn.setStyleSheet("""
            QPushButton {
                background-color: #f0f0f0;
                border: 1px solid #ccc;
                border-radius: 3px;
                font-size: 9px;
            }
            QPushButton:hover {
                background-color: #e0e0e0;
            }
        """)
        self.clear_reverse_btn.clicked.connect(self.clear_reverse_image)
        reverse_layout.addWidget(self.clear_reverse_btn, 0, Qt.AlignCenter)
        
        photos_layout.addLayout(reverse_layout)
        
        photos_layout.addStretch()
        photos_group.setLayout(photos_layout)
        parent_layout.addWidget(photos_group)

    def clear_obverse_image(self):
        """Очищает изображение аверса"""
        self.edit_obverse_image.clear_image()
        self.edit_obverse_image.image_path = None
        self.edit_obverse_image.current_pixmap = None
        self.edit_obverse_image.update_display()
    
    def clear_reverse_image(self):
        """Очищает изображение реверса"""
        self.edit_reverse_image.clear_image()
        self.edit_reverse_image.image_path = None
        self.edit_reverse_image.current_pixmap = None
        self.edit_reverse_image.update_display()
    
    def clear_edit_form(self):
        """Очищает форму редактирования полностью"""
        # Очищаем стандартные поля
        for key, field in self.parent_tab.edit_fields.items():
            if field is None:
                continue
            try:
                if hasattr(field, 'isValid') and not field.isValid():
                    continue
                if isinstance(field, (QComboBox,)):
                    field.setCurrentIndex(0)
                elif isinstance(field, (QLineEdit,)):
                    field.clear()
                elif isinstance(field, (QSpinBox, QDoubleSpinBox)):
                    field.setValue(0)
                elif isinstance(field, QDateEdit):
                    field.setDate(QDate.currentDate())
                    field.setSpecialValueText("Не указана")
                elif isinstance(field, ClickableTextEdit):
                    field.clear()
                # === ДОБАВЛЯЕМ ОЧИСТКУ ТЕКСТОВЫХ ПОЛЕЙ QTextEdit ===
                elif isinstance(field, QTextEdit):
                    field.clear()
            except RuntimeError:
                continue
        
        # Очищаем пользовательские поля
        if hasattr(self.parent_tab, 'custom_edit_fields'):
            for field_key, field in self.parent_tab.custom_edit_fields.items():
                if field is None:
                    continue
                try:
                    if hasattr(field, 'isValid') and not field.isValid():
                        continue
                    if isinstance(field, QLineEdit):
                        field.clear()
                    elif isinstance(field, QDoubleSpinBox):
                        field.setValue(0)
                    elif isinstance(field, QDateEdit):
                        field.setDate(QDate.currentDate())
                        field.setSpecialValueText("Не указана")
                    elif isinstance(field, QCheckBox):
                        field.setChecked(False)
                    elif isinstance(field, QComboBox):
                        field.setCurrentIndex(0)
                    elif isinstance(field, QTextEdit):
                        field.clear()
                except RuntimeError:
                    continue
        
        # Очищаем изображения
        try:
            self.clear_obverse_image()
        except RuntimeError:
            pass
        try:
            self.clear_reverse_image()
        except RuntimeError:
            pass
        
        # Скрываем контейнер формы, показываем пустое состояние
        try:
            self.coin_edit_empty_label.show()
            self.coin_edit_form_container.hide()
        except RuntimeError:
            pass

    def load_coin_to_form(self, coin):
        """Загружает данные монеты в форму редактирования"""
        if not coin:
            return
        
        # Перестраиваем пользовательские поля
        self.rebuild_custom_fields()
        
        self.clear_edit_form()
        
        try:
            self.coin_edit_empty_label.hide()
            self.coin_edit_form_container.show()
        except RuntimeError:
            pass
        
        self._disable_mouse_wheel()
        
        from PySide6.QtCore import QTimer
        QTimer.singleShot(50, self.apply_small_height_to_all_fields)
        
        # СТРАНА
        if coin.country:
            try:
                idx = self.parent_tab.edit_fields['country'].findData(coin.country.id)
                if idx >= 0:
                    self.parent_tab.edit_fields['country'].setCurrentIndex(idx)
            except (RuntimeError, KeyError):
                pass
        
        # ТЕКСТОВЫЕ ПОЛЯ
        try:
            self.parent_tab.edit_fields['catalog_number'].setText(coin.catalog_number or "")
        except (RuntimeError, KeyError):
            pass
        
        try:
            self.parent_tab.edit_fields['denomination_value'].setText(coin.denomination_value or "")
        except (RuntimeError, KeyError):
            pass
        
        try:
            self.parent_tab.edit_fields['mint_mark'].setText(coin.mint_mark or "")
        except (RuntimeError, KeyError):
            pass
        
        # ВАЛЮТА
        if coin.currency_id:
            try:
                idx = self.parent_tab.edit_fields['currency'].findData(coin.currency_id)
                if idx >= 0:
                    self.parent_tab.edit_fields['currency'].setCurrentIndex(idx)
            except (RuntimeError, KeyError):
                pass
        
        # МОНЕТНЫЙ ДВОР
        if coin.mint_id:
            try:
                idx = self.parent_tab.edit_fields['mint'].findData(coin.mint_id)
                if idx >= 0:
                    self.parent_tab.edit_fields['mint'].setCurrentIndex(idx)
            except (RuntimeError, KeyError):
                pass
        
        # ГУРТ
        if hasattr(coin, 'edge_id') and coin.edge_id:
            try:
                idx = self.parent_tab.edit_fields['edge'].findData(coin.edge_id)
                if idx >= 0:
                    self.parent_tab.edit_fields['edge'].setCurrentIndex(idx)
            except (RuntimeError, KeyError):
                pass
        
        # МЕТАЛЛ
        if coin.metal_id:
            try:
                idx = self.parent_tab.edit_fields['metal'].findData(coin.metal_id)
                if idx >= 0:
                    self.parent_tab.edit_fields['metal'].setCurrentIndex(idx)
            except (RuntimeError, KeyError):
                pass
        
        # ПЕРИОД
        if hasattr(coin, 'period_id') and coin.period_id:
            try:
                idx = self.parent_tab.edit_fields['period_id'].findData(coin.period_id)
                if idx >= 0:
                    self.parent_tab.edit_fields['period_id'].setCurrentIndex(idx)
            except (RuntimeError, KeyError):
                pass
        
        # ВЕК
        if hasattr(coin, 'century') and coin.century:
            try:
                idx = self.parent_tab.edit_fields['century'].findText(coin.century)
                if idx >= 0:
                    self.parent_tab.edit_fields['century'].setCurrentIndex(idx)
            except (RuntimeError, KeyError):
                pass
        
        # ФОРМА
        if hasattr(coin, 'shape_id') and coin.shape_id:
            try:
                idx = self.parent_tab.edit_fields['shape'].findData(coin.shape_id)
                if idx >= 0:
                    self.parent_tab.edit_fields['shape'].setCurrentIndex(idx)
            except (RuntimeError, KeyError):
                pass
        elif hasattr(coin, 'shape') and coin.shape:
            try:
                idx = self.parent_tab.edit_fields['shape'].findText(coin.shape)
                if idx >= 0:
                    self.parent_tab.edit_fields['shape'].setCurrentIndex(idx)
            except (RuntimeError, KeyError):
                pass
        
        # СОХРАННОСТЬ (condition)
        if hasattr(coin, 'condition_id') and coin.condition_id:
            try:
                idx = self.parent_tab.edit_fields['condition'].findData(coin.condition_id)
                if idx >= 0:
                    self.parent_tab.edit_fields['condition'].setCurrentIndex(idx)
            except (RuntimeError, KeyError):
                pass
        elif coin.condition:
            try:
                idx = self.parent_tab.edit_fields['condition'].findText(coin.condition)
                if idx >= 0:
                    self.parent_tab.edit_fields['condition'].setCurrentIndex(idx)
            except (RuntimeError, KeyError):
                pass
        
        # РЕДКОСТЬ (rarity)
        if hasattr(coin, 'rarity_id') and coin.rarity_id:
            try:
                idx = self.parent_tab.edit_fields['rarity'].findData(coin.rarity_id)
                if idx >= 0:
                    self.parent_tab.edit_fields['rarity'].setCurrentIndex(idx)
            except (RuntimeError, KeyError):
                pass
        elif hasattr(coin, 'rarity') and coin.rarity:
            try:
                idx = self.parent_tab.edit_fields['rarity'].findText(coin.rarity)
                if idx >= 0:
                    self.parent_tab.edit_fields['rarity'].setCurrentIndex(idx)
            except (RuntimeError, KeyError):
                pass
        
        # ТИП ВЫПУСКА (issue_type)
        if hasattr(coin, 'issue_type_id') and coin.issue_type_id:
            try:
                idx = self.parent_tab.edit_fields['issue_type'].findData(coin.issue_type_id)
                if idx >= 0:
                    self.parent_tab.edit_fields['issue_type'].setCurrentIndex(idx)
            except (RuntimeError, KeyError):
                pass
        elif hasattr(coin, 'issue_type') and coin.issue_type:
            try:
                idx = self.parent_tab.edit_fields['issue_type'].findText(coin.issue_type)
                if idx >= 0:
                    self.parent_tab.edit_fields['issue_type'].setCurrentIndex(idx)
            except (RuntimeError, KeyError):
                pass
        
        # АВ/РЕВ (avrev)
        if hasattr(coin, 'avrev_id') and coin.avrev_id:
            try:
                idx = self.parent_tab.edit_fields['avrev'].findData(coin.avrev_id)
                if idx >= 0:
                    self.parent_tab.edit_fields['avrev'].setCurrentIndex(idx)
            except (RuntimeError, KeyError):
                pass
        elif hasattr(coin, 'avrev') and coin.avrev:
            try:
                idx = self.parent_tab.edit_fields['avrev'].findText(coin.avrev)
                if idx >= 0:
                    self.parent_tab.edit_fields['avrev'].setCurrentIndex(idx)
            except (RuntimeError, KeyError):
                pass
        
        # СТАТУС
        if hasattr(coin, 'status_id') and coin.status_id:
            try:
                idx = self.parent_tab.edit_fields['status'].findData(coin.status_id)
                if idx >= 0:
                    self.parent_tab.edit_fields['status'].setCurrentIndex(idx)
            except (RuntimeError, KeyError):
                pass
        
        # ТИП ПРИОБРЕТЕНИЯ (acquisition_type)
        if hasattr(coin, 'acquisition_type_id') and coin.acquisition_type_id:
            try:
                idx = self.parent_tab.edit_fields['acquisition_type'].findData(coin.acquisition_type_id)
                if idx >= 0:
                    self.parent_tab.edit_fields['acquisition_type'].setCurrentIndex(idx)
            except (RuntimeError, KeyError):
                pass
        elif hasattr(coin, 'acquisition_type') and coin.acquisition_type:
            try:
                idx = self.parent_tab.edit_fields['acquisition_type'].findText(coin.acquisition_type)
                if idx >= 0:
                    self.parent_tab.edit_fields['acquisition_type'].setCurrentIndex(idx)
            except (RuntimeError, KeyError):
                pass
        
        # МЕСТО ХРАНЕНИЯ (storage_location)
        if hasattr(coin, 'storage_location_id') and coin.storage_location_id:
            try:
                idx = self.parent_tab.edit_fields['storage_location'].findData(coin.storage_location_id)
                if idx >= 0:
                    self.parent_tab.edit_fields['storage_location'].setCurrentIndex(idx)
            except (RuntimeError, KeyError):
                pass
        elif hasattr(coin, 'storage_location') and coin.storage_location:
            try:
                idx = self.parent_tab.edit_fields['storage_location'].findText(coin.storage_location)
                if idx >= 0:
                    self.parent_tab.edit_fields['storage_location'].setCurrentIndex(idx)
            except (RuntimeError, KeyError):
                pass
        
        # ГДЕ КУПЛЕНА
        if hasattr(coin, 'purchase_where') and coin.purchase_where:
            try:
                idx = self.parent_tab.edit_fields['purchase_where'].findText(coin.purchase_where)
                if idx >= 0:
                    self.parent_tab.edit_fields['purchase_where'].setCurrentIndex(idx)
            except (RuntimeError, KeyError):
                pass
        
        # СТРАНА ПОКУПКИ
        if hasattr(coin, 'purchase_country_obj') and coin.purchase_country_obj:
            try:
                idx = self.parent_tab.edit_fields['purchase_country'].findData(coin.purchase_country_obj.id)
                if idx >= 0:
                    self.parent_tab.edit_fields['purchase_country'].setCurrentIndex(idx)
            except (RuntimeError, KeyError):
                pass
        
        # ЧИСЛОВЫЕ ПОЛЯ
        try:
            if coin.year:
                self.parent_tab.edit_fields['year'].setValue(coin.year)
            if coin.weight:
                self.parent_tab.edit_fields['weight'].setValue(coin.weight)
            if coin.diameter:
                self.parent_tab.edit_fields['diameter'].setValue(coin.diameter)
            if coin.purchase_price:
                self.parent_tab.edit_fields['purchase_price'].setValue(coin.purchase_price)
            if coin.sale_price:
                self.parent_tab.edit_fields['sale_price'].setValue(coin.sale_price)
        except (RuntimeError, KeyError):
            pass
        
        # ДАТА ПОКУПКИ
        if hasattr(coin, 'purchase_date') and coin.purchase_date:
            try:
                self.parent_tab.edit_fields['purchase_date'].setDate(coin.purchase_date)
            except (RuntimeError, KeyError):
                pass
        
        # РЫНОЧНАЯ ЦЕНА
        if hasattr(coin, 'market_price') and coin.market_price:
            try:
                self.parent_tab.edit_fields['market_price'].setValue(coin.market_price)
            except (RuntimeError, KeyError):
                pass
        
        if hasattr(coin, 'market_price_date') and coin.market_price_date:
            try:
                self.parent_tab.edit_fields['market_price_date'].setDate(coin.market_price_date)
            except (RuntimeError, KeyError):
                pass
        
        # ТЕКСТОВЫЕ ПОЛЯ
        if hasattr(coin, 'edge_description'):
            try:
                self.parent_tab.edit_fields['edge_description'].setText(coin.edge_description or "")
            except (RuntimeError, KeyError):
                pass
        
        if hasattr(coin, 'purchase_info'):
            try:
                self.parent_tab.edit_fields['purchase_info'].setText(coin.purchase_info or "")
            except (RuntimeError, KeyError):
                pass
        
        # === ИНФОРМАЦИЯ О МОНЕТЕ (coin_info) - ОЧИЩАЕМ ПЕРЕД УСТАНОВКОЙ ===
        info_text = getattr(coin, 'coin_info', None)
        if info_text is None:
            info_text = getattr(coin, 'notes', None)
        try:
            # Принудительно очищаем поле перед установкой
            self.parent_tab.edit_fields['coin_info'].clear()
            self.parent_tab.edit_fields['coin_info'].setText(info_text or "")
        except (RuntimeError, KeyError):
            pass
        
        # ССЫЛКИ
        try:
            self.parent_tab.edit_fields['ucoin_url'].setText(getattr(coin, 'ucoin_url', '') or "")
            self.parent_tab.edit_fields['meshok_url'].setText(getattr(coin, 'meshok_url', '') or "")
        except (RuntimeError, KeyError):
            pass
        
        # ИЗОБРАЖЕНИЯ
        try:
            if hasattr(coin, 'obverse_image') and coin.obverse_image and os.path.exists(coin.obverse_image):
                self.edit_obverse_image.set_image_from_path(coin.obverse_image)
            else:
                self.clear_obverse_image()
        except RuntimeError:
            pass
        
        try:
            if hasattr(coin, 'reverse_image') and coin.reverse_image and os.path.exists(coin.reverse_image):
                self.edit_reverse_image.set_image_from_path(coin.reverse_image)
            else:
                self.clear_reverse_image()
        except RuntimeError:
            pass
        
        # Загружаем пользовательские значения
        if hasattr(self.parent_tab, 'load_custom_values_to_form'):
            self.parent_tab.load_custom_values_to_form(coin)
        
        # Принудительно обновляем все виджеты
        QApplication.processEvents()
        
        
    def _fit_fields_to_width(self):
        """Растягивает поля редактирования на всю ширину панели (убирает ограничение ширины)"""
        from PySide6.QtWidgets import QSizePolicy, QGroupBox
        # Снимаем ограничение ширины с групп
        for group in self.coin_edit_form_container.findChildren(QGroupBox):
            group.setMaximumWidth(16777215)
            group.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        # Растягиваем все поля ввода
        for key, widget in self.parent_tab.edit_fields.items():
            if widget is not None:
                widget.setMaximumWidth(16777215)
                widget.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        if hasattr(self.parent_tab, 'custom_edit_fields'):
            for key, widget in self.parent_tab.custom_edit_fields.items():
                if widget is not None:
                    widget.setMaximumWidth(16777215)
                    widget.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.coin_edit_form_container.updateGeometry()
        self.updateGeometry()