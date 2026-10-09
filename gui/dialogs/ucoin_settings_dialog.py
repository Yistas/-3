# ===== gui/dialogs/ucoin_settings_dialog.py =====
# СОЗДАТЬ НОВЫЙ ФАЙЛ

# -*- coding: utf-8 -*-

"""
Диалог настроек UCOIN
"""

from PySide6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QFormLayout,
                               QPushButton, QLineEdit, QLabel, QMessageBox,
                               QCheckBox)
from PySide6.QtCore import Qt


class UcoinSettingsDialog(QDialog):
    """Диалог для настройки учетных данных UCOIN"""
    
    def __init__(self, password_manager, parent=None):
        super().__init__(parent)
        self.password_manager = password_manager
        self.setWindowTitle("Настройки UCOIN")
        self.setMinimumWidth(450)
        
        layout = QVBoxLayout()
        self.setLayout(layout)
        
        # Заголовок
        title = QLabel("🔑 Настройки учетной записи UCOIN")
        title.setStyleSheet("font-weight: bold; font-size: 14px; padding: 5px; background-color: #4a6fa5; color: white; border-radius: 3px;")
        title.setAlignment(Qt.AlignCenter)
        layout.addWidget(title)
        
        # Пояснение
        info = QLabel(
            "Введите ваши учетные данные для автоматического входа на UCOIN.net\n"
            "Пароль будет сохранен в зашифрованном виде."
        )
        info.setWordWrap(True)
        info.setStyleSheet("color: #666; padding: 5px;")
        layout.addWidget(info)
        
        # Форма
        form = QFormLayout()
        
        self.login_edit = QLineEdit()
        self.login_edit.setPlaceholderText("Ваш email на UCOIN")
        form.addRow("Логин (email):", self.login_edit)
        
        self.password_edit = QLineEdit()
        self.password_edit.setPlaceholderText("Ваш пароль")
        self.password_edit.setEchoMode(QLineEdit.Password)
        form.addRow("Пароль:", self.password_edit)
        
        self.show_password_check = QCheckBox("Показать пароль")
        self.show_password_check.toggled.connect(self.toggle_password_visibility)
        form.addRow("", self.show_password_check)
        
        layout.addLayout(form)
        
        # Загружаем сохраненные данные
        self.load_saved_data()
        
        # Кнопки
        button_layout = QHBoxLayout()
        
        save_btn = QPushButton("💾 Сохранить")
        save_btn.clicked.connect(self.save_settings)
        save_btn.setMinimumHeight(35)
        save_btn.setStyleSheet("background-color: #4CAF50; color: white; font-weight: bold;")
        button_layout.addWidget(save_btn)
        
        clear_btn = QPushButton("🗑️ Очистить")
        clear_btn.clicked.connect(self.clear_settings)
        clear_btn.setMinimumHeight(35)
        button_layout.addWidget(clear_btn)
        
        button_layout.addStretch()
        
        cancel_btn = QPushButton("❌ Отмена")
        cancel_btn.clicked.connect(self.reject)
        cancel_btn.setMinimumHeight(35)
        button_layout.addWidget(cancel_btn)
        
        layout.addLayout(button_layout)
    
    def toggle_password_visibility(self, checked):
        """Переключает видимость пароля"""
        if checked:
            self.password_edit.setEchoMode(QLineEdit.Normal)
        else:
            self.password_edit.setEchoMode(QLineEdit.Password)
    
    def load_saved_data(self):
        """Загружает сохраненные данные"""
        username, password = self.password_manager.get_password('ucoin')
        if username:
            self.login_edit.setText(username)
        if password:
            self.password_edit.setText(password)
    
    def save_settings(self):
        """Сохраняет настройки"""
        login = self.login_edit.text().strip()
        password = self.password_edit.text().strip()
        
        if not login:
            QMessageBox.warning(self, "Предупреждение", "Введите логин")
            return
        
        if not password:
            QMessageBox.warning(self, "Предупреждение", "Введите пароль")
            return
        
        if self.password_manager.save_password('ucoin', login, password):
            QMessageBox.information(self, "Успех", "Настройки сохранены")
            self.accept()
        else:
            QMessageBox.critical(self, "Ошибка", "Не удалось сохранить настройки")
    
    def clear_settings(self):
        """Очищает сохраненные настройки"""
        reply = QMessageBox.question(
            self, "Подтверждение",
            "Очистить сохраненные данные для входа на UCOIN?",
            QMessageBox.Yes | QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            if self.password_manager.delete_password('ucoin'):
                self.login_edit.clear()
                self.password_edit.clear()
                QMessageBox.information(self, "Успех", "Данные очищены")
            else:
                QMessageBox.critical(self, "Ошибка", "Не удалось очистить данные")