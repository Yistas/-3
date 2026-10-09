# -*- coding: utf-8 -*-

"""
Диалог для добавления и редактирования страны приобретения
"""

import logging
from datetime import datetime
from PySide6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QFormLayout,
                               QPushButton, QLineEdit, QTextEdit,
                               QLabel, QGroupBox, QMessageBox, QScrollArea,
                               QWidget)
from PySide6.QtCore import Qt


class PurchaseCountryDialog(QDialog):
    """Диалог для добавления/редактирования страны приобретения"""
    
    def __init__(self, db_manager, parent=None, country_id=None):
        super().__init__(parent)
        self.logger = logging.getLogger('CoinCollector.GUI.PurchaseCountryDialog')
        self.db_manager = db_manager
        self.country_id = country_id
        self.country = None
        
        self.setWindowTitle("Добавление страны приобретения" if not country_id else "Редактирование страны приобретения")
        self.setMinimumWidth(500)
        self.setMinimumHeight(400)
        
        self.init_ui()
        
        if country_id:
            self.load_country_data()
    
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
        main_group = QGroupBox("Информация о стране")
        main_form = QFormLayout()
        
        # Название страны (обязательное)
        self.name_edit = QLineEdit()
        self.name_edit.setPlaceholderText("например: Германия, США, Франция")
        self.name_edit.setMinimumHeight(30)
        main_form.addRow("Страна*:", self.name_edit)
        
        main_group.setLayout(main_form)
        scroll_layout.addWidget(main_group)
        
        # === Группа: Описание ===
        desc_group = QGroupBox("Описание и примечания")
        desc_layout = QVBoxLayout()
        
        self.description_edit = QTextEdit()
        self.description_edit.setMaximumHeight(150)
        self.description_edit.setMinimumHeight(80)
        self.description_edit.setPlaceholderText("Дополнительная информация о стране...")
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
        save_btn.clicked.connect(self.save_country)
        save_btn.setMinimumHeight(35)
        save_btn.setStyleSheet("background-color: #4CAF50; color: white; font-weight: bold;")
        button_layout.addWidget(save_btn)
        
        cancel_btn = QPushButton("❌ Отмена")
        cancel_btn.clicked.connect(self.reject)
        cancel_btn.setMinimumHeight(35)
        button_layout.addWidget(cancel_btn)
        
        layout.addLayout(button_layout)
    
    def collect_data(self):
        """Собирает данные из формы"""
        name = self.name_edit.text().strip()
        
        # Проверка обязательных полей
        if not name:
            QMessageBox.warning(self, "Предупреждение", "Введите название страны")
            return None
        
        data = {
            'name': name,
            'description': self.description_edit.toPlainText().strip() or None,
        }
        
        return data
    
    def save_country(self):
        """Сохраняет страну приобретения"""
        data = self.collect_data()
        if not data:
            return
        
        try:
            from database.models import PurchaseCountry
            
            if self.country_id:
                # Обновление
                country = self.db_manager.session.query(PurchaseCountry).get(self.country_id)
                if country:
                    for key, value in data.items():
                        setattr(country, key, value)
                    country.updated_at = datetime.now()
                    self.db_manager.session.commit()
                    QMessageBox.information(self, "Успех", "Страна приобретения обновлена")
            else:
                # Добавление
                country = PurchaseCountry(**data)
                self.db_manager.session.add(country)
                self.db_manager.session.commit()
                QMessageBox.information(self, "Успех", f"Страна приобретения добавлена с ID {country.id}")
            
            self.accept()
            
        except Exception as e:
            self.logger.error(f"Ошибка при сохранении: {e}")
            self.db_manager.session.rollback()
            QMessageBox.critical(self, "Ошибка", f"Не удалось сохранить: {e}")
    
    def load_country_data(self):
        """Загружает данные для редактирования"""
        try:
            from database.models import PurchaseCountry
            self.country = self.db_manager.session.query(PurchaseCountry).get(self.country_id)
            if not self.country:
                return
            
            self.name_edit.setText(self.country.name or "")
            self.description_edit.setText(self.country.description or "")
            
        except Exception as e:
            self.logger.error(f"Ошибка при загрузке данных: {e}")
            QMessageBox.critical(self, "Ошибка", f"Не удалось загрузить данные: {e}")