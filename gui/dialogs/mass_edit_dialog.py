# ===== gui/dialogs/mass_edit_dialog.py =====
# ПОЛНОСТЬЮ ЗАМЕНИТЬ ФАЙЛ

# -*- coding: utf-8 -*-

"""
Диалог для массового изменения параметров монет
"""

from PySide6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QFormLayout,
                               QPushButton, QLabel, QGroupBox, QCheckBox,
                               QComboBox, QLineEdit, QSpinBox, QDoubleSpinBox,
                               QDateEdit, QMessageBox, QScrollArea, QWidget)
from PySide6.QtCore import Qt, QDate
from PySide6.QtGui import QFont

from database.models import StandardReference


class MassEditDialog(QDialog):
    """Диалог для массового изменения параметров монет"""
    
    def __init__(self, db_manager, coins, parent=None):
        super().__init__(parent)
        self.db_manager = db_manager
        self.coins = coins
        self.setWindowTitle(f"Массовое изменение ({len(coins)} монет)")
        self.setMinimumWidth(550)
        self.setMinimumHeight(650)
        
        self.changes = {}
        self.checkboxes = {}
        self.period_combo = None
        
        self.init_ui()
    
    def init_ui(self):
        layout = QVBoxLayout()
        self.setLayout(layout)
        
        # Заголовок
        title_label = QLabel(f"✏️ Массовое изменение ({len(self.coins)} монет)")
        title_label.setStyleSheet("""
            font-weight: bold;
            font-size: 14px;
            padding: 8px;
            background-color: #4a6fa5;
            color: white;
            border-radius: 3px;
        """)
        title_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(title_label)
        
        # Информация о выбранных монетах
        countries_text = ", ".join(set(c.country.name if c.country else '?' for c in self.coins[:5]))
        if len(self.coins) > 5:
            countries_text += "..."
        
        info_label = QLabel(f"Выбрано монет: {len(self.coins)}\n"
                           f"Страны: {countries_text}")
        info_label.setWordWrap(True)
        info_label.setStyleSheet("color: #666; padding: 5px; background-color: #f5f5f5; border-radius: 3px;")
        layout.addWidget(info_label)
        
        # Пояснение
        hint_label = QLabel("Отметьте параметры, которые хотите изменить, и укажите новые значения")
        hint_label.setWordWrap(True)
        hint_label.setStyleSheet("color: #666; font-size: 11px; padding: 5px;")
        layout.addWidget(hint_label)
        
        # Область прокрутки для полей
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.NoFrame)
        
        scroll_widget = QWidget()
        scroll_layout = QVBoxLayout()
        scroll_widget.setLayout(scroll_layout)
        
        # Создаем поля для каждого параметра
        self._create_field_group(scroll_layout, "Основные параметры", [
            ("country_id", "Страна", "combo_country"),
            ("catalog_number", "№ каталога", "line"),
            ("denomination_value", "Номинал", "line"),
            ("year", "Год", "spin", (-5000, 2100)),
            ("period_id", "Период", "combo_period"),
            ("century", "Век", "combo_century"),
        ])
        
        self._create_field_group(scroll_layout, "Монетный двор", [
            ("mint_id", "Монетный двор", "combo_mint"),
            ("mint_mark", "Знак МД", "line"),
        ])
        
        self._create_field_group(scroll_layout, "Характеристики", [
            ("metal_id", "Металл", "combo_metal"),
            ("weight", "Вес (г)", "double", (0, 10000, 2)),
            ("diameter", "Размер (мм)", "double", (0, 500, 1)),
            ("shape_id", "Форма", "combo_shape"),
            ("edge_description", "Описание гурта", "text"),
        ])
        
        self._create_field_group(scroll_layout, "Состояние", [
            ("condition_id", "Сохранность", "combo_condition"),
            ("rarity_id", "Редкость", "combo_rarity"),
            ("storage_location_id", "Альбом", "combo_storage_location"),
            ("issue_type_id", "Тип выпуска", "combo_issue_type"),
            ("avrev_id", "АВ/РЕВ", "combo_avrev"),
            ("status_id", "Статус", "combo_status"),
        ])
        
        self._create_field_group(scroll_layout, "Покупка", [
            ("purchase_date", "Дата покупки", "date"),
            ("purchase_price", "Цена покупки", "double", (0, 10000000, 2)),
            ("purchase_place", "Место покупки", "line"),
            ("purchase_where", "Где куплена", "combo_purchase_where"),
            ("purchase_country_id", "Страна покупки", "combo_purchase_country"),
            ("acquisition_type_id", "Тип приобретения", "combo_acquisition_type"),
            ("purchase_info", "Информация о покупке", "text"),
        ])
        
        self._create_field_group(scroll_layout, "Информация", [
            ("coin_info", "Информация о монете", "text"),
            ("notes", "Заметки", "text"),
        ])
        
        scroll.setWidget(scroll_widget)
        layout.addWidget(scroll)
        
        # Кнопки
        button_layout = QHBoxLayout()
        
        apply_btn = QPushButton("✅ Применить изменения")
        apply_btn.clicked.connect(self.apply_changes)
        apply_btn.setMinimumHeight(35)
        apply_btn.setStyleSheet("background-color: #4CAF50; color: white; font-weight: bold;")
        button_layout.addWidget(apply_btn)
        
        cancel_btn = QPushButton("❌ Отмена")
        cancel_btn.clicked.connect(self.reject)
        cancel_btn.setMinimumHeight(35)
        button_layout.addWidget(cancel_btn)
        
        layout.addLayout(button_layout)
    
    def _create_field_group(self, parent_layout, title, fields):
        """Создает группу полей"""
        group = QGroupBox(title)
        form_layout = QFormLayout()
        form_layout.setSpacing(5)
        
        for field_info in fields:
            field_key = field_info[0]
            field_label = field_info[1]
            field_type = field_info[2]
            
            # Чекбокс для включения изменения
            checkbox = QCheckBox()
            checkbox.setChecked(False)
            self.checkboxes[field_key] = checkbox
            
            # Создаем поле ввода
            if field_type == "line":
                widget = QLineEdit()
                widget.setEnabled(False)
                widget.setPlaceholderText("Новое значение")
            elif field_type == "text":
                widget = QLineEdit()
                widget.setEnabled(False)
                widget.setPlaceholderText("Новое значение")
            elif field_type == "spin":
                min_val, max_val = field_info[3]
                widget = QSpinBox()
                widget.setRange(min_val, max_val)
                widget.setSpecialValueText("—")
                widget.setEnabled(False)
            elif field_type == "double":
                min_val, max_val, decimals = field_info[3]
                widget = QDoubleSpinBox()
                widget.setRange(min_val, max_val)
                widget.setDecimals(decimals)
                widget.setSpecialValueText("—")
                widget.setEnabled(False)
            elif field_type == "date":
                widget = QDateEdit()
                widget.setCalendarPopup(True)
                widget.setDate(QDate.currentDate())
                widget.setSpecialValueText("Не указана")
                widget.setEnabled(False)
            elif field_type == "combo_country":
                widget = QComboBox()
                widget.setEnabled(False)
                self._load_countries(widget)
                # Подключаем сигнал для обновления периодов
                widget.currentIndexChanged.connect(self.update_periods_by_country)
            elif field_type == "combo_mint":
                widget = QComboBox()
                widget.setEnabled(False)
                self._load_mints(widget)
            elif field_type == "combo_metal":
                widget = QComboBox()
                widget.setEnabled(False)
                self._load_metals(widget)
            elif field_type == "combo_period":
                widget = QComboBox()
                widget.setEnabled(False)
                self.period_combo = widget
                self._load_periods(widget)
            elif field_type == "combo_century":
                widget = QComboBox()
                widget.setEnabled(False)
                widget.addItems(["", "XXI", "XX", "XIX", "XVIII", "XVII", "XVI", "XV", "XIV", "XIII", "XII", "XI", 
                               "X", "IX", "VIII", "VII", "VI", "V", "IV", "III", "II", "I", "до н.э."])
            elif field_type == "combo_shape":
                widget = QComboBox()
                widget.setEnabled(False)
                self._load_shape(widget)
            elif field_type == "combo_condition":
                widget = QComboBox()
                widget.setEnabled(False)
                self._load_condition(widget)
            elif field_type == "combo_rarity":
                widget = QComboBox()
                widget.setEnabled(False)
                self._load_rarity(widget)
            elif field_type == "combo_storage_location":
                widget = QComboBox()
                widget.setEnabled(False)
                self._load_storage_location(widget)
            elif field_type == "combo_issue_type":
                widget = QComboBox()
                widget.setEnabled(False)
                self._load_issue_type(widget)
            elif field_type == "combo_avrev":
                widget = QComboBox()
                widget.setEnabled(False)
                self._load_avrev(widget)
            elif field_type == "combo_status":
                widget = QComboBox()
                widget.setEnabled(False)
                self._load_status(widget)
            elif field_type == "combo_purchase_where":
                widget = QComboBox()
                widget.setEnabled(False)
                widget.addItems(["", "EBAY", "Lave.ru", "UCOIN", "Авито", "БАНК", "Подарок", "Магазин", "Мешок", "Молоток"])
            elif field_type == "combo_purchase_country":
                widget = QComboBox()
                widget.setEnabled(False)
                self._load_purchase_countries(widget)
            elif field_type == "combo_acquisition_type":
                widget = QComboBox()
                widget.setEnabled(False)
                self._load_acquisition_type(widget)
            else:
                continue
            
            # Сохраняем виджет
            setattr(self, f"widget_{field_key}", widget)
            
            # Соединяем чекбокс с включением виджета
            checkbox.toggled.connect(widget.setEnabled)
            
            # Добавляем в форму
            row_layout = QHBoxLayout()
            row_layout.addWidget(checkbox)
            row_layout.addWidget(widget, 1)
            form_layout.addRow(field_label, row_layout)
        
        group.setLayout(form_layout)
        parent_layout.addWidget(group)
    
    # ========== ЗАГРУЗКА СПРАВОЧНИКОВ С СОРТИРОВКОЙ ==========
    
    def _load_countries(self, combo):
        """Загружает страны в комбобокс с сортировкой"""
        combo.addItem("—", None)
        countries = self.db_manager.get_all_countries()
        # Сортируем страны по названию
        sorted_countries = sorted(countries, key=lambda x: x.name)
        for country in sorted_countries:
            combo.addItem(country.name, country.id)
    
    def _load_mints(self, combo):
        """Загружает монетные дворы в комбобокс с сортировкой"""
        combo.addItem("—", None)
        mints = self.db_manager.get_all_mints()
        # Сортируем по названию
        sorted_mints = sorted(mints, key=lambda x: x.name)
        for mint in sorted_mints:
            combo.addItem(mint.get_display_text(), mint.id)
    
    def _load_metals(self, combo):
        """Загружает металлы в комбобокс с сортировкой"""
        combo.addItem("—", None)
        from database.models import Metal
        metals = self.db_manager.session.query(Metal).order_by(Metal.name).all()
        # Уже отсортировано по имени в запросе
        for metal in metals:
            combo.addItem(metal.get_display_text(), metal.id)
    
    def _load_periods(self, combo):
        """Загружает периоды в комбобокс с отображением страны и сортировкой"""
        combo.blockSignals(True)
        combo.clear()
        combo.addItem("—", None)
        
        # Получаем выбранную страну
        selected_country_id = None
        if hasattr(self, 'widget_country_id') and self.widget_country_id:
            selected_country_id = self.widget_country_id.currentData()
        
        if selected_country_id:
            # Если страна выбрана, показываем периоды только для этой страны
            periods = self.db_manager.get_periods_by_country(selected_country_id)
            # Сортируем периоды по начальному году
            sorted_periods = sorted(periods, key=lambda x: x.start_year if x.start_year else 0)
            for period in sorted_periods:
                display_text = period.get_display_text()
                combo.addItem(display_text, period.id)
        else:
            # Если страна не выбрана, показываем все периоды с указанием страны
            periods = self.db_manager.get_all_periods()
            # Сортируем сначала по стране, потом по начальному году
            sorted_periods = sorted(periods, key=lambda x: (x.country.name if x.country else "", x.start_year if x.start_year else 0))
            for period in sorted_periods:
                country_name = period.country.name if period.country else "—"
                display_text = f"{country_name}: {period.get_display_text()}"
                combo.addItem(display_text, period.id)
        
        combo.blockSignals(False)
    
    def _load_purchase_countries(self, combo):
        """Загружает страны приобретения в комбобокс с сортировкой"""
        combo.addItem("—", None)
        countries = self.db_manager.get_all_purchase_countries()
        # Сортируем по названию
        sorted_countries = sorted(countries, key=lambda x: x.name)
        for country in sorted_countries:
            combo.addItem(country.name, country.id)
    
    def _load_condition(self, combo):
        """Загружает справочник сохранности с сортировкой"""
        combo.addItem("—", None)
        refs = self.db_manager.session.query(StandardReference).filter_by(
            field_key='condition'
        ).order_by(StandardReference.sort_order).all()
        for ref in refs:
            combo.addItem(ref.name, ref.id)
    
    def _load_rarity(self, combo):
        """Загружает справочник редкости с сортировкой"""
        combo.addItem("—", None)
        refs = self.db_manager.session.query(StandardReference).filter_by(
            field_key='rarity'
        ).order_by(StandardReference.sort_order).all()
        for ref in refs:
            combo.addItem(ref.name, ref.id)
    
    def _load_shape(self, combo):
        """Загружает справочник форм с сортировкой"""
        combo.addItem("—", None)
        refs = self.db_manager.session.query(StandardReference).filter_by(
            field_key='shape'
        ).order_by(StandardReference.sort_order).all()
        for ref in refs:
            combo.addItem(ref.name, ref.id)
    
    def _load_issue_type(self, combo):
        """Загружает справочник типов выпуска с сортировкой"""
        combo.addItem("—", None)
        refs = self.db_manager.session.query(StandardReference).filter_by(
            field_key='issue_type'
        ).order_by(StandardReference.sort_order).all()
        for ref in refs:
            combo.addItem(ref.name, ref.id)
    
    def _load_avrev(self, combo):
        """Загружает справочник АВ/РЕВ с сортировкой"""
        combo.addItem("—", None)
        refs = self.db_manager.session.query(StandardReference).filter_by(
            field_key='avrev'
        ).order_by(StandardReference.sort_order).all()
        for ref in refs:
            combo.addItem(ref.name, ref.id)
    
    def _load_status(self, combo):
        """Загружает справочник статусов с сортировкой"""
        combo.addItem("—", None)
        refs = self.db_manager.session.query(StandardReference).filter_by(
            field_key='status'
        ).order_by(StandardReference.sort_order).all()
        for ref in refs:
            combo.addItem(ref.name, ref.id)
    
    def _load_acquisition_type(self, combo):
        """Загружает справочник типов приобретения с сортировкой"""
        combo.addItem("—", None)
        refs = self.db_manager.session.query(StandardReference).filter_by(
            field_key='acquisition_type'
        ).order_by(StandardReference.sort_order).all()
        for ref in refs:
            combo.addItem(ref.name, ref.id)
    
    def _load_storage_location(self, combo):
        """Загружает справочник мест хранения с сортировкой"""
        combo.addItem("—", None)
        refs = self.db_manager.session.query(StandardReference).filter_by(
            field_key='storage_location'
        ).order_by(StandardReference.sort_order).all()
        for ref in refs:
            combo.addItem(ref.name, ref.id)
    
    # ========== ОБНОВЛЕНИЕ ПЕРИОДОВ ==========
    
    def update_periods_by_country(self):
        """Обновляет список периодов при изменении страны"""
        if self.period_combo:
            current_value = self.period_combo.currentData()
            self._load_periods(self.period_combo)
            # Восстанавливаем выбранное значение, если оно еще актуально
            if current_value:
                idx = self.period_combo.findData(current_value)
                if idx >= 0:
                    self.period_combo.setCurrentIndex(idx)
    
    # ========== СБОР И ПРИМЕНЕНИЕ ИЗМЕНЕНИЙ ==========
    
    def _get_widget_value(self, widget):
        """Получает значение из виджета"""
        if isinstance(widget, QLineEdit):
            val = widget.text().strip()
            return val if val else None
        elif isinstance(widget, QSpinBox):
            return widget.value() if widget.value() != 0 else None
        elif isinstance(widget, QDoubleSpinBox):
            return widget.value() if widget.value() != 0 else None
        elif isinstance(widget, QDateEdit):
            return widget.date().toPython() if widget.date() else None
        elif isinstance(widget, QComboBox):
            # Для комбобокса возвращаем ID (если есть) или текст
            data = widget.currentData()
            if data is not None:
                return data
            text = widget.currentText().strip()
            return text if text else None
        return None
    
    def apply_changes(self):
        """Собирает изменения и закрывает диалог"""
        changes = {}
        
        print("=" * 50)
        print("Сбор изменений для массового редактирования")
        
        for field_key, checkbox in self.checkboxes.items():
            if checkbox.isChecked():
                widget = getattr(self, f"widget_{field_key}", None)
                if widget:
                    value = self._get_widget_value(widget)
                    print(f"  {field_key}: {value} (тип: {type(value).__name__})")
                    if value is not None:
                        changes[field_key] = value
                    else:
                        print(f"    ⚠️ Значение None, пропускаем")
        
        print(f"Итого изменений: {len(changes)}")
        print("=" * 50)
        
        if not changes:
            QMessageBox.warning(self, "Предупреждение", 
                "Не выбрано ни одного параметра для изменения\n"
                "или выбранные параметры имеют пустые значения.")
            return
        
        self.changes = changes
        self.accept()
    
    def get_changes(self):
        """Возвращает словарь изменений"""
        return self.changes