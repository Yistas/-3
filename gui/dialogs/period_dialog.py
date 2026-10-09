# ===== gui/dialogs/period_dialog.py =====
# СОЗДАТЬ НОВЫЙ ФАЙЛ

# -*- coding: utf-8 -*-

"""
Диалог для добавления и редактирования периода
"""

import logging
from datetime import datetime
from PySide6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QFormLayout,
                               QPushButton, QLineEdit, QTextEdit, QSpinBox,
                               QLabel, QGroupBox, QMessageBox, QScrollArea,
                               QWidget, QComboBox)
from PySide6.QtCore import Qt


class PeriodDialog(QDialog):
    """Диалог для добавления/редактирования периода"""
    
    def __init__(self, db_manager, parent=None, period_id=None):
        super().__init__(parent)
        self.logger = logging.getLogger('CoinCollector.GUI.PeriodDialog')
        self.db_manager = db_manager
        self.period_id = period_id
        self.period = None
        
        self.setWindowTitle("Добавление периода" if not period_id else "Редактирование периода")
        self.setMinimumWidth(500)
        self.setMinimumHeight(400)
        
        self.init_ui()
        
        if period_id:
            self.load_period_data()
    
    def init_ui(self):
        """Инициализация интерфейса"""
        layout = QVBoxLayout()
        self.setLayout(layout)
        
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.NoFrame)
        
        scroll_widget = QWidget()
        scroll_layout = QVBoxLayout()
        scroll_widget.setLayout(scroll_layout)
        
        # === Группа: Основная информация ===
        main_group = QGroupBox("Информация о периоде")
        main_form = QFormLayout()
        
        # Название периода (обязательное)
        self.name_edit = QLineEdit()
        self.name_edit.setPlaceholderText("например: Российская Империя, СССР, Современная Россия")
        self.name_edit.setMinimumHeight(30)
        main_form.addRow("Название*:", self.name_edit)
        
        # Страна
        self.country_combo = QComboBox()
        self.country_combo.setMinimumHeight(30)
        self.load_countries()
        main_form.addRow("Страна*:", self.country_combo)
        
        # Годы
        year_layout = QHBoxLayout()
        
        self.start_year_spin = QSpinBox()
        self.start_year_spin.setRange(-5000, 2100)
        self.start_year_spin.setSpecialValueText("Не указан")
        self.start_year_spin.setMinimumHeight(30)
        year_layout.addWidget(self.start_year_spin)
        
        year_layout.addWidget(QLabel("—"))
        
        self.end_year_spin = QSpinBox()
        self.end_year_spin.setRange(-5000, 2100)
        self.end_year_spin.setSpecialValueText("Не указан")
        self.end_year_spin.setMinimumHeight(30)
        year_layout.addWidget(self.end_year_spin)
        
        main_form.addRow("Годы:", year_layout)
        
        main_group.setLayout(main_form)
        scroll_layout.addWidget(main_group)
        
        # === Группа: Описание ===
        desc_group = QGroupBox("Описание и примечания")
        desc_layout = QVBoxLayout()
        
        self.description_edit = QTextEdit()
        self.description_edit.setMaximumHeight(150)
        self.description_edit.setMinimumHeight(80)
        self.description_edit.setPlaceholderText("Историческая информация о периоде...")
        desc_layout.addWidget(self.description_edit)
        
        desc_group.setLayout(desc_layout)
        scroll_layout.addWidget(desc_group)
        
        scroll.setWidget(scroll_widget)
        layout.addWidget(scroll)
        
        info_label = QLabel("* - обязательные поля")
        info_label.setStyleSheet("color: gray; font-size: 10px;")
        layout.addWidget(info_label)
        
        # Кнопки
        button_layout = QHBoxLayout()
        
        save_btn = QPushButton("💾 Сохранить")
        save_btn.clicked.connect(self.save_period)
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
        country_id = self.country_combo.currentData()
        
        if not name:
            QMessageBox.warning(self, "Предупреждение", "Введите название периода")
            return None
        
        if not country_id:
            QMessageBox.warning(self, "Предупреждение", "Выберите страну")
            return None
        
        data = {
            'name': name,
            'country_id': country_id,
            'start_year': self.start_year_spin.value() if self.start_year_spin.value() != 0 else None,
            'end_year': self.end_year_spin.value() if self.end_year_spin.value() != 0 else None,
            'description': self.description_edit.toPlainText().strip() or None,
        }
        
        return data
    
    def save_period(self):
        """Сохраняет период"""
        data = self.collect_data()
        if not data:
            return
        
        try:
            if self.period_id:
                self.db_manager.update_period(self.period_id, data)
                QMessageBox.information(self, "Успех", "Период успешно обновлен")
            else:
                new_id = self.db_manager.add_period(data)
                QMessageBox.information(self, "Успех", f"Период добавлен с ID {new_id}")
            
            self.accept()
            
        except Exception as e:
            self.logger.error(f"Ошибка при сохранении периода: {e}")
            QMessageBox.critical(self, "Ошибка", f"Не удалось сохранить период: {e}")
    
    def load_period_data(self):
        """Загружает данные периода для редактирования"""
        try:
            self.period = self.db_manager.get_period(self.period_id)
            if not self.period:
                return
            
            self.name_edit.setText(self.period.name or "")
            
            if self.period.country_id:
                idx = self.country_combo.findData(self.period.country_id)
                if idx >= 0:
                    self.country_combo.setCurrentIndex(idx)
            
            if self.period.start_year:
                self.start_year_spin.setValue(self.period.start_year)
            
            if self.period.end_year:
                self.end_year_spin.setValue(self.period.end_year)
            
            self.description_edit.setText(self.period.description or "")
            
        except Exception as e:
            self.logger.error(f"Ошибка при загрузке данных периода: {e}")
            QMessageBox.critical(self, "Ошибка", f"Не удалось загрузить данные периода: {e}")