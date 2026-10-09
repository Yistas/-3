# -*- coding: utf-8 -*-

"""
Диалог для управления бекапами
"""

import sys
import os
from PySide6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QPushButton,
                               QListWidget, QListWidgetItem, QLabel, QMessageBox,
                               QRadioButton, QDialogButtonBox, QInputDialog)
from PySide6.QtCore import Qt


class BackupDialog(QDialog):
    """Диалог для управления бекапами"""
    
    def __init__(self, backup_manager, parent=None):
        super().__init__(parent)
        self.backup_manager = backup_manager
        self.selected_backup = None
        self.setWindowTitle("Управление резервными копиями")
        self.setMinimumWidth(600)
        self.setMinimumHeight(400)
        
        layout = QVBoxLayout()
        self.setLayout(layout)
        
        # Список бекапов
        self.backup_list = QListWidget()
        self.backup_list.setAlternatingRowColors(True)
        self.backup_list.itemDoubleClicked.connect(self.restore_selected)
        layout.addWidget(QLabel("Доступные резервные копии:"))
        layout.addWidget(self.backup_list)
        
        # Кнопки
        button_layout = QHBoxLayout()
        
        create_btn = QPushButton("📀 Создать бекап")
        create_btn.clicked.connect(self.create_backup)
        create_btn.setMinimumHeight(35)
        button_layout.addWidget(create_btn)
        
        button_layout.addStretch()
        
        restore_btn = QPushButton("♻️ Восстановить")
        restore_btn.clicked.connect(self.restore_selected)
        restore_btn.setMinimumHeight(35)
        button_layout.addWidget(restore_btn)
        
        close_btn = QPushButton("❌ Закрыть")
        close_btn.clicked.connect(self.accept)
        close_btn.setMinimumHeight(35)
        button_layout.addWidget(close_btn)
        
        layout.addLayout(button_layout)
        
        # Загружаем список бекапов
        self.load_backups()
    
    def load_backups(self):
        """Загружает список бекапов"""
        self.backup_list.clear()
        backups = self.backup_manager.list_backups()
        
        if not backups:
            item = QListWidgetItem("Нет доступных резервных копий")
            item.setFlags(item.flags() & ~Qt.ItemIsSelectable)
            item.setForeground(Qt.gray)
            self.backup_list.addItem(item)
            return
        
        for backup in backups:
            type_icon = "📀" if backup['type'] == 'full' else "📦"
            text = f"{type_icon} {backup['name']} - {backup['modified_str']} ({backup['size_str']})"
            item = QListWidgetItem(text)
            item.setData(Qt.UserRole, backup['path'])
            self.backup_list.addItem(item)
    
    def create_backup(self):
        """Создает новую резервную копию"""
        # Диалог выбора типа бекапа
        type_dialog = QDialog(self)
        type_dialog.setWindowTitle("Тип резервной копии")
        type_dialog.setMinimumWidth(400)
        
        type_layout = QVBoxLayout()
        type_dialog.setLayout(type_layout)
        
        type_layout.addWidget(QLabel("Выберите тип резервной копии:"))
        
        normal_radio = QRadioButton("📦 Обычный бекап (без логов и venv)")
        normal_radio.setChecked(True)
        type_layout.addWidget(normal_radio)
        
        full_radio = QRadioButton("📀 Полный бекап (включая логи и venv)")
        type_layout.addWidget(full_radio)
        
        type_layout.addWidget(QLabel("\n⚠️ Полный бекап может занимать много места!"))
        
        type_buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        type_buttons.accepted.connect(type_dialog.accept)
        type_buttons.rejected.connect(type_dialog.reject)
        type_layout.addWidget(type_buttons)
        
        if type_dialog.exec():
            backup_type = 'full' if full_radio.isChecked() else 'normal'
            
            # Предлагаем ввести имя для бекапа
            backup_name, ok = QInputDialog.getText(
                self, "Имя бекапа",
                "Введите имя для резервной копии (оставьте пустым для автоматического):"
            )
            
            if ok:
                if backup_name.strip():
                    backup_path = self.backup_manager.create_backup(backup_name.strip(), backup_type)
                else:
                    backup_path = self.backup_manager.create_backup(backup_type=backup_type)
                
                if backup_path:
                    QMessageBox.information(self, "Успех", f"Резервная копия создана:\n{backup_path}")
                    self.load_backups()
                else:
                    QMessageBox.critical(self, "Ошибка", "Не удалось создать резервную копию")
    
    def restore_selected(self):
        """Восстанавливает выбранную резервную копию"""
        current_item = self.backup_list.currentItem()
        if not current_item:
            QMessageBox.warning(self, "Предупреждение", "Выберите резервную копию для восстановления")
            return
        
        backup_path = current_item.data(Qt.UserRole)
        if not backup_path:
            return
        
        # Определяем тип восстановления по имени файла
        restore_type = 'normal'
        if 'full_' in str(backup_path):
            restore_type = 'full'
        
        # Подтверждение
        type_msg = "всех данных, включая логи и виртуальное окружение" if restore_type == 'full' else "основных данных (без логов)"
        reply = QMessageBox.question(
            self, "Подтверждение",
            f"Восстановление из резервной копии заменит текущие данные.\n"
            f"Будет выполнено восстановление {type_msg}.\n\n"
            f"Вы уверены, что хотите продолжить?",
            QMessageBox.Yes | QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            if self.backup_manager.restore_backup(backup_path, restore_type):
                QMessageBox.information(self, "Успех", "Данные успешно восстановлены.\nПрограмма будет перезапущена.")
                # Перезапускаем программу
                python = sys.executable
                os.execl(python, python, *sys.argv)
            else:
                QMessageBox.critical(self, "Ошибка", "Не удалось восстановить данные")