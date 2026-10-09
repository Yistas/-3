# -*- coding: utf-8 -*-

"""
Диалог для добавления новой страны
"""

from PySide6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QFormLayout,
                               QPushButton, QLineEdit, QComboBox, QCheckBox,
                               QLabel)
from PySide6.QtCore import Qt


class AddCountryDialog(QDialog):
    """Диалог для добавления новой страны"""
    
    def __init__(self, db_manager, parent=None, initial_name="", default_continent=None, is_extinct=False):
        super().__init__(parent)
        self.db_manager = db_manager
        self.country_name = initial_name
        self.default_continent = default_continent
        self.default_extinct = is_extinct
        self.setWindowTitle("Добавление новой страны")
        self.setMinimumWidth(400)
        
        layout = QVBoxLayout()
        self.setLayout(layout)
        
        # Заголовок
        title_label = QLabel("➕ Добавление новой страны")
        title_label.setStyleSheet("font-weight: bold; font-size: 14px; padding: 5px; background-color: #4a6fa5; color: white; border-radius: 3px;")
        title_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(title_label)
        
        # Форма
        form_layout = QFormLayout()
        
        # Название страны
        self.name_edit = QLineEdit()
        self.name_edit.setPlaceholderText("Введите название страны")
        self.name_edit.setMinimumHeight(30)
        self.name_edit.setText(initial_name)
        form_layout.addRow("Название страны:", self.name_edit)
        
        # Код страны (необязательно)
        self.code_edit = QLineEdit()
        self.code_edit.setPlaceholderText("например: RU, US, DE (необязательно)")
        self.code_edit.setMinimumHeight(30)
        self.code_edit.setMaxLength(2)
        form_layout.addRow("Код страны:", self.code_edit)
        
        # Континент
        self.continent_combo = QComboBox()
        self.continent_combo.addItems(["", "Европа", "Азия", "Америка", "Африка", "Океания"])
        self.continent_combo.setMinimumHeight(30)
        if default_continent:
            index = self.continent_combo.findText(default_continent)
            if index >= 0:
                self.continent_combo.setCurrentIndex(index)
        form_layout.addRow("Континент:", self.continent_combo)
        
        # Исчезнувшая страна?
        self.extinct_check = QCheckBox("Это исчезнувшая страна")
        if is_extinct:
            self.extinct_check.setChecked(True)
        form_layout.addRow("", self.extinct_check)
        
        layout.addLayout(form_layout)
        
        # Кнопки
        button_layout = QHBoxLayout()
        
        save_btn = QPushButton("💾 Сохранить")
        save_btn.clicked.connect(self.accept)
        save_btn.setMinimumHeight(35)
        save_btn.setStyleSheet("background-color: #4CAF50; color: white; font-weight: bold;")
        button_layout.addWidget(save_btn)
        
        cancel_btn = QPushButton("❌ Отмена")
        cancel_btn.clicked.connect(self.reject)
        cancel_btn.setMinimumHeight(35)
        button_layout.addWidget(cancel_btn)
        
        layout.addLayout(button_layout)
        
        # Подсказка
        hint_label = QLabel("💡 После добавления страны вы сможете установить для неё иконку через контекстное меню")
        hint_label.setStyleSheet("color: gray; font-size: 10px; margin-top: 10px;")
        hint_label.setWordWrap(True)
        layout.addWidget(hint_label)
    
    def get_country_data(self):
        """Возвращает данные о стране"""
        return {
            'name': self.name_edit.text().strip(),
            'code': self.code_edit.text().strip().upper(),
            'continent': self.continent_combo.currentText() or None,
            'is_extinct': self.extinct_check.isChecked()
        }