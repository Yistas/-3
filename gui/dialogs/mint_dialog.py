# -*- coding: utf-8 -*-

"""
Диалог для добавления и редактирования монетного двора
"""

import logging
from PySide6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QFormLayout,
                               QPushButton, QLineEdit, QTextEdit, QSpinBox,
                               QLabel, QGroupBox, QMessageBox, QScrollArea,
                               QWidget, QComboBox)
from PySide6.QtCore import Qt


class MintDialog(QDialog):
    """Диалог для добавления/редактирования монетного двора"""
    
    def __init__(self, db_manager, parent=None, mint_id=None):
        super().__init__(parent)
        self.logger = logging.getLogger('CoinCollector.GUI.MintDialog')
        self.db_manager = db_manager
        self.mint_id = mint_id
        self.mint = None
        
        self.setWindowTitle("Добавление монетного двора" if not mint_id else "Редактирование монетного двора")
        self.setMinimumWidth(600)
        self.setMinimumHeight(500)
        
        self.init_ui()
        
        if mint_id:
            self.load_mint_data()
    
    def init_ui(self):
        """Инициализация интерфейса"""
        layout = QVBoxLayout()
        self.setLayout(layout)
        
        # Создаем область с прокруткой
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.NoFrame)
        
        scroll_widget = QWidget()
        scroll_layout = QVBoxLayout()
        scroll_widget.setLayout(scroll_layout)
        
        # === Группа: Основная информация ===
        main_group = QGroupBox("Основная информация")
        main_form = QFormLayout()
        
        # Название монетного двора (обязательное)
        self.name_edit = QLineEdit()
        self.name_edit.setPlaceholderText("например: Московский монетный двор")
        self.name_edit.setMinimumHeight(30)
        main_form.addRow("Название*:", self.name_edit)
        
        # Краткое название
        self.short_name_edit = QLineEdit()
        self.short_name_edit.setPlaceholderText("например: ММД, СПМД, P, S")
        self.short_name_edit.setMinimumHeight(30)
        main_form.addRow("Краткое название:", self.short_name_edit)
        
        # Знак/обозначение на монетах
        self.mark_edit = QLineEdit()
        self.mark_edit.setPlaceholderText("например: ММД, СПМД, S, P")
        self.mark_edit.setMinimumHeight(30)
        main_form.addRow("Знак на монетах:", self.mark_edit)
        
        main_group.setLayout(main_form)
        scroll_layout.addWidget(main_group)
        
        # === Группа: Расположение ===
        location_group = QGroupBox("Расположение")
        location_form = QFormLayout()
        
        # Страна
        self.country_combo = QComboBox()
        self.country_combo.addItem("— Не выбрано —", None)
        self.country_combo.setMinimumHeight(30)
        self.load_countries()
        location_form.addRow("Страна:", self.country_combo)
        
        # Город
        self.city_edit = QLineEdit()
        self.city_edit.setPlaceholderText("например: Москва, Санкт-Петербург")
        self.city_edit.setMinimumHeight(30)
        location_form.addRow("Город:", self.city_edit)
        
        location_group.setLayout(location_form)
        scroll_layout.addWidget(location_group)
        
        # === Группа: История ===
        history_group = QGroupBox("История")
        history_form = QFormLayout()
        
        # Год основания
        self.founded_year_spin = QSpinBox()
        self.founded_year_spin.setRange(-5000, 2100)
        self.founded_year_spin.setSpecialValueText("Не указан")
        self.founded_year_spin.setMinimumHeight(30)
        history_form.addRow("Год основания:", self.founded_year_spin)
        
        # Год закрытия
        self.closed_year_spin = QSpinBox()
        self.closed_year_spin.setRange(-5000, 2100)
        self.closed_year_spin.setSpecialValueText("Действующий")
        self.closed_year_spin.setMinimumHeight(30)
        history_form.addRow("Год закрытия:", self.closed_year_spin)
        
        history_group.setLayout(history_form)
        scroll_layout.addWidget(history_group)
        
        # === Группа: Дополнительно ===
        extra_group = QGroupBox("Дополнительно")
        extra_form = QFormLayout()
        
        # Веб-сайт
        self.website_edit = QLineEdit()
        self.website_edit.setPlaceholderText("например: https://www.mint.ru")
        self.website_edit.setMinimumHeight(30)
        extra_form.addRow("Веб-сайт:", self.website_edit)
        
        extra_group.setLayout(extra_form)
        scroll_layout.addWidget(extra_group)
        
        # === Группа: Описание ===
        desc_group = QGroupBox("Описание и примечания")
        desc_layout = QVBoxLayout()
        
        self.description_edit = QTextEdit()
        self.description_edit.setMaximumHeight(150)
        self.description_edit.setMinimumHeight(80)
        self.description_edit.setPlaceholderText("Историческая информация, особенности и т.д.")
        desc_layout.addWidget(self.description_edit)
        
        desc_group.setLayout(desc_layout)
        scroll_layout.addWidget(desc_group)
        
        # Добавляем прокрутку
        scroll.setWidget(scroll_widget)
        layout.addWidget(scroll)
        
        # Информационное сообщение
        info_label = QLabel("* - обязательные поля")
        info_label.setStyleSheet("color: gray; font-size: 10px;")
        layout.addWidget(info_label)
        
        # Кнопки
        button_layout = QHBoxLayout()
        
        save_btn = QPushButton("💾 Сохранить")
        save_btn.clicked.connect(self.save_mint)
        save_btn.setMinimumHeight(35)
        save_btn.setStyleSheet("background-color: #4CAF50; color: white; font-weight: bold;")
        button_layout.addWidget(save_btn)
        
        cancel_btn = QPushButton("❌ Отмена")
        cancel_btn.clicked.connect(self.reject)
        cancel_btn.setMinimumHeight(35)
        button_layout.addWidget(cancel_btn)
        
        layout.addLayout(button_layout)
    
    def load_countries(self):
        """Загружает список стран в комбобокс"""
        countries = self.db_manager.get_all_countries()
        for country in countries:
            self.country_combo.addItem(country.name, country.id)
    
    def collect_data(self):
        """Собирает данные из формы"""
        name = self.name_edit.text().strip()
        
        # Проверка обязательных полей
        if not name:
            QMessageBox.warning(self, "Предупреждение", "Введите название монетного двора")
            return None
        
        data = {
            'name': name,
            'short_name': self.short_name_edit.text().strip() or None,
            'mark': self.mark_edit.text().strip() or None,
            'country_id': self.country_combo.currentData(),
            'city': self.city_edit.text().strip() or None,
            'founded_year': self.founded_year_spin.value() if self.founded_year_spin.value() != 0 else None,
            'closed_year': self.closed_year_spin.value() if self.closed_year_spin.value() != 0 else None,
            'website': self.website_edit.text().strip() or None,
            'description': self.description_edit.toPlainText().strip() or None,
        }
        
        return data
    
    def save_mint(self):
        """Сохраняет монетный двор"""
        data = self.collect_data()
        if not data:
            return
        
        try:
            if self.mint_id:
                self.db_manager.update_mint(self.mint_id, data)
                QMessageBox.information(self, "Успех", "Монетный двор успешно обновлен")
            else:
                new_id = self.db_manager.add_mint(data)
                QMessageBox.information(self, "Успех", f"Монетный двор добавлен с ID {new_id}")
            
            self.accept()
            
        except Exception as e:
            self.logger.error(f"Ошибка при сохранении монетного двора: {e}")
            QMessageBox.critical(self, "Ошибка", f"Не удалось сохранить монетный двор: {e}")
    
    def load_mint_data(self):
        """Загружает данные монетного двора для редактирования"""
        try:
            self.mint = self.db_manager.get_mint(self.mint_id)
            if not self.mint:
                return
            
            self.name_edit.setText(self.mint.name or "")
            self.short_name_edit.setText(self.mint.short_name or "")
            self.mark_edit.setText(self.mint.mark or "")
            
            if self.mint.country_id:
                index = self.country_combo.findData(self.mint.country_id)
                if index >= 0:
                    self.country_combo.setCurrentIndex(index)
            
            self.city_edit.setText(self.mint.city or "")
            
            if self.mint.founded_year:
                self.founded_year_spin.setValue(self.mint.founded_year)
            
            if self.mint.closed_year:
                self.closed_year_spin.setValue(self.mint.closed_year)
            
            self.website_edit.setText(self.mint.website or "")
            self.description_edit.setText(self.mint.description or "")
            
        except Exception as e:
            self.logger.error(f"Ошибка при загрузке данных монетного двора: {e}")
            QMessageBox.critical(self, "Ошибка", f"Не удалось загрузить данные монетного двора: {e}")