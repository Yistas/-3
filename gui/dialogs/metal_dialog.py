# -*- coding: utf-8 -*-

"""
Диалог для добавления и редактирования металла
"""

import logging
from datetime import datetime
from PySide6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QFormLayout,
                               QPushButton, QLineEdit, QTextEdit, QDoubleSpinBox,
                               QLabel, QGroupBox, QMessageBox, QScrollArea,
                               QWidget, QComboBox, QDateEdit, QCheckBox)  # Добавлен QCheckBox
from PySide6.QtCore import Qt, QDate


class MetalDialog(QDialog):
    """Диалог для добавления/редактирования металла"""
    
    def __init__(self, db_manager, parent=None, metal_id=None):
        super().__init__(parent)
        self.logger = logging.getLogger('CoinCollector.GUI.MetalDialog')
        self.db_manager = db_manager
        self.metal_id = metal_id
        self.metal = None
        
        self.setWindowTitle("Добавление металла" if not metal_id else "Редактирование металла")
        self.setMinimumWidth(500)
        self.setMinimumHeight(400)
        
        self.init_ui()
        
        if metal_id:
            self.load_metal_data()
    
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
        main_group = QGroupBox("Информация о металле")
        main_form = QFormLayout()
        
        # Название металла (обязательное)
        self.name_edit = QLineEdit()
        self.name_edit.setPlaceholderText("например: Золото, Серебро, Платина")
        self.name_edit.setMinimumHeight(30)
        main_form.addRow("Название*:", self.name_edit)
        
        self.ticker_edit = QLineEdit()
        self.ticker_edit.setPlaceholderText("например: SLVRUB_TOM, GLDRUB_TOM")
        self.ticker_edit.setMinimumHeight(30)
        main_form.addRow("Биржевой тикер:", self.ticker_edit)
        
        # Проба
        self.purity_edit = QLineEdit()
        self.purity_edit.setPlaceholderText("например: 999, 900, 585, 925")
        self.purity_edit.setMinimumHeight(30)
        main_form.addRow("Проба:", self.purity_edit)
        
        main_group.setLayout(main_form)
        scroll_layout.addWidget(main_group)
        
        # === Группа: Курс ===
        price_group = QGroupBox("Текущий курс")
        price_form = QFormLayout()
        
        # Включить курс
        self.has_price_check = QCheckBox("Указать текущий курс")
        self.has_price_check.toggled.connect(self.on_price_check_toggled)
        price_form.addRow("", self.has_price_check)
        
        # Цена за грамм
        self.price_spin = QDoubleSpinBox()
        self.price_spin.setRange(0, 10000000)
        self.price_spin.setSuffix(" за грамм")
        self.price_spin.setDecimals(2)
        self.price_spin.setEnabled(False)
        price_form.addRow("Цена:", self.price_spin)
        
        # Валюта
        self.currency_combo = QComboBox()
        self.currency_combo.addItems(["RUB", "USD", "EUR"])
        self.currency_combo.setEnabled(False)
        price_form.addRow("Валюта:", self.currency_combo)
        
        # Дата курса
        self.price_date_edit = QDateEdit()
        self.price_date_edit.setCalendarPopup(True)
        self.price_date_edit.setDate(QDate.currentDate())
        self.price_date_edit.setEnabled(False)
        price_form.addRow("Дата курса:", self.price_date_edit)
        
        price_group.setLayout(price_form)
        scroll_layout.addWidget(price_group)
        
        # === Группа: Описание ===
        desc_group = QGroupBox("Описание и примечания")
        desc_layout = QVBoxLayout()
        
        self.description_edit = QTextEdit()
        self.description_edit.setMaximumHeight(150)
        self.description_edit.setMinimumHeight(80)
        self.description_edit.setPlaceholderText("Дополнительная информация о металле...")
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
        save_btn.clicked.connect(self.save_metal)
        save_btn.setMinimumHeight(35)
        save_btn.setStyleSheet("background-color: #4CAF50; color: white; font-weight: bold;")
        button_layout.addWidget(save_btn)
        
        cancel_btn = QPushButton("❌ Отмена")
        cancel_btn.clicked.connect(self.reject)
        cancel_btn.setMinimumHeight(35)
        button_layout.addWidget(cancel_btn)
        
        layout.addLayout(button_layout)
    
    def on_price_check_toggled(self, checked):
        """Обработчик переключения чекбокса курса"""
        self.price_spin.setEnabled(checked)
        self.currency_combo.setEnabled(checked)
        self.price_date_edit.setEnabled(checked)
        if not checked:
            self.price_spin.setValue(0)
    
    def collect_data(self):
        """Собирает данные из формы"""
        name = self.name_edit.text().strip()
        
        # Проверка обязательных полей
        if not name:
            QMessageBox.warning(self, "Предупреждение", "Введите название металла")
            return None
        
        # Создаем словарь данных
        data = {
            'name': name,
            'purity': self.purity_edit.text().strip() or None,
            'description': self.description_edit.toPlainText().strip() or None,
        }
        
        # Добавляем ticker_moex
        data['ticker_moex'] = self.ticker_edit.text().strip() or None
        
        # Обработка курса
        if self.has_price_check.isChecked():
            data['current_price'] = self.price_spin.value()
            data['price_currency'] = self.currency_combo.currentText()
            data['price_date'] = self.price_date_edit.date().toPython()
        else:
            data['current_price'] = None
            data['price_currency'] = None
            data['price_date'] = None
        
        return data
    
    def save_metal(self):
        """Сохраняет металл"""
        data = self.collect_data()
        if not data:
            return
        
        try:
            from database.models import Metal
            
            if self.metal_id:
                # Обновление существующего металла
                metal = self.db_manager.session.query(Metal).get(self.metal_id)
                if metal:
                    for key, value in data.items():
                        setattr(metal, key, value)
                    metal.updated_at = datetime.now()
                    self.db_manager.session.commit()
                    QMessageBox.information(self, "Успех", "Металл успешно обновлен")
            else:
                # Добавление нового металла
                metal = Metal(**data)
                self.db_manager.session.add(metal)
                self.db_manager.session.commit()
                QMessageBox.information(self, "Успех", f"Металл добавлен с ID {metal.id}")
            
            self.accept()
            
        except Exception as e:
            self.logger.error(f"Ошибка при сохранении металла: {e}")
            self.db_manager.session.rollback()
            QMessageBox.critical(self, "Ошибка", f"Не удалось сохранить металл: {e}")
    
    def load_metal_data(self):
        """Загружает данные металла для редактирования"""
        try:
            from database.models import Metal
            self.metal = self.db_manager.session.query(Metal).get(self.metal_id)
            if not self.metal:
                return
            
            self.name_edit.setText(self.metal.name or "")
            self.purity_edit.setText(self.metal.purity or "")
            
            if self.metal.current_price:
                self.has_price_check.setChecked(True)
                self.price_spin.setValue(self.metal.current_price)
                if self.metal.price_currency:
                    index = self.currency_combo.findText(self.metal.price_currency)
                    if index >= 0:
                        self.currency_combo.setCurrentIndex(index)
                if self.metal.price_date:
                    self.price_date_edit.setDate(self.metal.price_date)
            else:
                self.has_price_check.setChecked(False)
            
            self.description_edit.setText(self.metal.description or "")
            self.ticker_edit.setText(self.metal.ticker_moex or "")
            
        except Exception as e:
            self.logger.error(f"Ошибка при загрузке данных металла: {e}")
            QMessageBox.critical(self, "Ошибка", f"Не удалось загрузить данные металла: {e}")