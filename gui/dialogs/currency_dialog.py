# -*- coding: utf-8 -*-

"""
Упрощенный диалог для добавления и редактирования валюты
"""

import logging
from PySide6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QFormLayout,
                               QPushButton, QLineEdit, QTextEdit, QDoubleSpinBox,
                               QLabel, QGroupBox, QMessageBox, QScrollArea,
                               QWidget, QCheckBox)
from PySide6.QtCore import Qt


class CurrencyDialog(QDialog):
    """Упрощенный диалог для добавления/редактирования валюты"""
    
    def __init__(self, db_manager, parent=None, currency_id=None):
        super().__init__(parent)
        self.logger = logging.getLogger('CoinCollector.GUI.CurrencyDialog')
        self.db_manager = db_manager
        self.currency_id = currency_id
        self.currency = None
        
        self.setWindowTitle("Добавление валюты" if not currency_id else "Редактирование валюты")
        self.setMinimumWidth(500)
        self.setMinimumHeight(400)
        
        self.init_ui()
        
        if currency_id:
            self.load_currency_data()
    
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
        main_group = QGroupBox("Информация о валюте")
        main_form = QFormLayout()
        
        # Название валюты (обязательное)
        self.name_edit = QLineEdit()
        self.name_edit.setPlaceholderText("например: Фунт стерлингов, Доллар США")
        self.name_edit.setMinimumHeight(30)
        main_form.addRow("Название*:", self.name_edit)
        
        # Код валюты (необязательно)
        self.code_edit = QLineEdit()
        self.code_edit.setPlaceholderText("например: GBP, USD, EUR")
        self.code_edit.setMinimumHeight(30)
        main_form.addRow("Код:", self.code_edit)
        
        # Символ валюты (необязательно)
        self.symbol_edit = QLineEdit()
        self.symbol_edit.setPlaceholderText("например: £, $, €")
        self.symbol_edit.setMinimumHeight(30)
        main_form.addRow("Символ:", self.symbol_edit)
        
        # Курс валюты (необязательно)
        self.has_rate_check = QCheckBox("Указать курс")
        self.has_rate_check.toggled.connect(self.on_rate_check_toggled)
        main_form.addRow("", self.has_rate_check)
        
        self.rate_spin = QDoubleSpinBox()
        self.rate_spin.setRange(0.0001, 1000000)
        self.rate_spin.setValue(1.0)
        self.rate_spin.setSuffix(" ₽")
        self.rate_spin.setDecimals(4)
        self.rate_spin.setEnabled(False)
        main_form.addRow("Курс к рублю:", self.rate_spin)
        
        main_group.setLayout(main_form)
        scroll_layout.addWidget(main_group)
        
        # === Группа: Описание ===
        desc_group = QGroupBox("Описание и примечания")
        desc_layout = QVBoxLayout()
        
        self.description_edit = QTextEdit()
        self.description_edit.setMaximumHeight(150)
        self.description_edit.setMinimumHeight(80)
        self.description_edit.setPlaceholderText("Дополнительная информация о валюте...")
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
        save_btn.clicked.connect(self.save_currency)
        save_btn.setMinimumHeight(35)
        save_btn.setStyleSheet("background-color: #4CAF50; color: white; font-weight: bold;")
        button_layout.addWidget(save_btn)
        
        cancel_btn = QPushButton("❌ Отмена")
        cancel_btn.clicked.connect(self.reject)
        cancel_btn.setMinimumHeight(35)
        button_layout.addWidget(cancel_btn)
        
        layout.addLayout(button_layout)
    
    def on_rate_check_toggled(self, checked):
        """Обработчик переключения чекбокса курса"""
        self.rate_spin.setEnabled(checked)
        if not checked:
            self.rate_spin.setValue(0)
    
    def collect_data(self):
        """Собирает данные из формы"""
        name = self.name_edit.text().strip()
        
        # Проверка обязательных полей
        if not name:
            QMessageBox.warning(self, "Предупреждение", "Введите название валюты")
            return None
        
        data = {
            'name': name,
            'code': self.code_edit.text().strip().upper() or None,
            'symbol': self.symbol_edit.text().strip() or None,
            'exchange_rate': self.rate_spin.value() if self.has_rate_check.isChecked() else None,
            'description': self.description_edit.toPlainText().strip() or None,
        }
        
        return data
    
    def save_currency(self):
        """Сохраняет валюту"""
        data = self.collect_data()
        if not data:
            return
        
        try:
            if self.currency_id:
                self.db_manager.update_currency(self.currency_id, data)
                QMessageBox.information(self, "Успех", "Валюта успешно обновлена")
            else:
                new_id = self.db_manager.add_currency(data)
                QMessageBox.information(self, "Успех", f"Валюта добавлена с ID {new_id}")
            
            self.accept()
            
        except Exception as e:
            self.logger.error(f"Ошибка при сохранении валюты: {e}")
            QMessageBox.critical(self, "Ошибка", f"Не удалось сохранить валюту: {e}")
    
    def load_currency_data(self):
        """Загружает данные валюты для редактирования"""
        try:
            self.currency = self.db_manager.get_currency(self.currency_id)
            if not self.currency:
                return
            
            self.name_edit.setText(self.currency.name or "")
            self.code_edit.setText(self.currency.code or "")
            self.symbol_edit.setText(self.currency.symbol or "")
            
            # Загрузка курса
            if self.currency.exchange_rate:
                self.has_rate_check.setChecked(True)
                self.rate_spin.setValue(self.currency.exchange_rate)
            else:
                self.has_rate_check.setChecked(False)
            
            self.description_edit.setText(self.currency.description or "")
            
        except Exception as e:
            self.logger.error(f"Ошибка при загрузке данных валюты: {e}")
            QMessageBox.critical(self, "Ошибка", f"Не удалось загрузить данные валюты: {e}")