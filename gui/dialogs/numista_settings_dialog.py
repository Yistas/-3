# -*- coding: utf-8 -*-

from PySide6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QFormLayout,
                               QPushButton, QLineEdit, QLabel, QMessageBox)
from PySide6.QtCore import Qt


class NumistaSettingsDialog(QDialog):
    def __init__(self, settings_manager, parent=None):
        super().__init__(parent)
        self.settings_manager = settings_manager
        self.setWindowTitle("Настройки Numista API")
        self.setMinimumWidth(450)
        
        layout = QVBoxLayout()
        self.setLayout(layout)
        
        # Заголовок
        title = QLabel("🔑 Настройки API Numista")
        title.setStyleSheet("font-weight: bold; font-size: 14px; padding: 5px; background-color: #4a6fa5; color: white; border-radius: 3px;")
        title.setAlignment(Qt.AlignCenter)
        layout.addWidget(title)
        
        # Пояснение
        info = QLabel(
            "Для использования поиска на Numista введите ваши API ключи.\n"
            "Получить ключи можно на сайте numista.com в настройках аккаунта."
        )
        info.setWordWrap(True)
        info.setStyleSheet("color: #666; padding: 5px;")
        layout.addWidget(info)
        
        # Форма
        form = QFormLayout()
        
        self.api_key_edit = QLineEdit()
        self.api_key_edit.setText(settings_manager.get_numista_api_key())
        self.api_key_edit.setPlaceholderText("Ваш API ключ")
        form.addRow("API Key:", self.api_key_edit)
        
        self.client_id_edit = QLineEdit()
        self.client_id_edit.setText(settings_manager.get_numista_client_id())
        self.client_id_edit.setPlaceholderText("Client ID")
        form.addRow("Client ID:", self.client_id_edit)
        
        self.client_name_edit = QLineEdit()
        self.client_name_edit.setText(settings_manager.get_numista_client_name())
        self.client_name_edit.setPlaceholderText("Client Name")
        form.addRow("Client Name:", self.client_name_edit)
        
        layout.addLayout(form)
        
        # Кнопки
        button_layout = QHBoxLayout()
        
        save_btn = QPushButton("💾 Сохранить")
        save_btn.clicked.connect(self.save_settings)
        save_btn.setMinimumHeight(35)
        button_layout.addWidget(save_btn)
        
        cancel_btn = QPushButton("❌ Отмена")
        cancel_btn.clicked.connect(self.reject)
        cancel_btn.setMinimumHeight(35)
        button_layout.addWidget(cancel_btn)
        
        layout.addLayout(button_layout)
    
    def save_settings(self):
        api_key = self.api_key_edit.text().strip()
        client_id = self.client_id_edit.text().strip()
        client_name = self.client_name_edit.text().strip()
        
        if api_key and client_id:
            self.settings_manager.set_numista_credentials(api_key, client_id, client_name)
            QMessageBox.information(self, "Успех", "Настройки сохранены")
            self.accept()
        else:
            QMessageBox.warning(self, "Предупреждение", "Заполните API Key и Client ID")