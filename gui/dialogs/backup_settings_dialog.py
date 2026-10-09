# -*- coding: utf-8 -*-

"""
Диалог для настройки параметров резервного копирования
"""

from PySide6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel,
                               QPushButton, QTabWidget, QWidget, QFormLayout,
                               QCheckBox, QSpinBox, QLineEdit, QGroupBox,
                               QListWidget, QListWidgetItem, QMessageBox,
                               QFileDialog, QInputDialog)
from PySide6.QtCore import Qt


class BackupSettingsDialog(QDialog):
    """Диалог для настройки параметров резервного копирования"""
    
    def __init__(self, settings, parent=None):
        super().__init__(parent)
        self.settings = settings
        self.setWindowTitle("Настройки резервного копирования")
        self.setMinimumWidth(500)
        self.setMinimumHeight(400)
        
        layout = QVBoxLayout()
        self.setLayout(layout)
        
        # Заголовок
        title_label = QLabel("⚙️ Настройки резервного копирования")
        title_label.setStyleSheet("font-weight: bold; font-size: 14px; padding: 5px; background-color: #4a6fa5; color: white; border-radius: 3px;")
        title_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(title_label)
        
        # Создаем вкладки
        tabs = QTabWidget()
        
        # Вкладка основных настроек
        main_tab = self.create_main_tab()
        tabs.addTab(main_tab, "Основные")
        
        # Вкладка содержимого
        content_tab = self.create_content_tab()
        tabs.addTab(content_tab, "Содержимое")
        
        # Вкладка уведомлений
        notifications_tab = self.create_notifications_tab()
        tabs.addTab(notifications_tab, "Уведомления")
        
        layout.addWidget(tabs)
        
        # Кнопки
        button_layout = QHBoxLayout()
        
        save_btn = QPushButton("💾 Сохранить")
        save_btn.clicked.connect(self.save_settings)
        save_btn.setMinimumHeight(35)
        save_btn.setStyleSheet("background-color: #4CAF50; color: white; font-weight: bold;")
        button_layout.addWidget(save_btn)
        
        reset_btn = QPushButton("🔄 Сбросить")
        reset_btn.clicked.connect(self.reset_settings)
        reset_btn.setMinimumHeight(35)
        button_layout.addWidget(reset_btn)
        
        cancel_btn = QPushButton("❌ Отмена")
        cancel_btn.clicked.connect(self.reject)
        cancel_btn.setMinimumHeight(35)
        button_layout.addWidget(cancel_btn)
        
        layout.addLayout(button_layout)
    
    def create_main_tab(self):
        """Создает вкладку основных настроек"""
        widget = QWidget()
        layout = QFormLayout()
        widget.setLayout(layout)
        
        # Автоматический бекап
        self.auto_backup_check = QCheckBox()
        self.auto_backup_check.setChecked(self.settings.get('auto_backup_enabled', True))
        layout.addRow("Автоматический бекап:", self.auto_backup_check)
        
        # Интервал бекапа
        self.interval_spin = QSpinBox()
        self.interval_spin.setRange(1, 30)
        self.interval_spin.setValue(self.settings.get('auto_backup_interval_days', 1))
        self.interval_spin.setSuffix(" дней")
        layout.addRow("Интервал:", self.interval_spin)
        
        # Папка для бекапов
        self.backup_dir_edit = QLineEdit()
        self.backup_dir_edit.setText(self.settings.get('backup_dir', 'backups'))
        self.backup_dir_edit.setMinimumHeight(30)
        
        dir_layout = QHBoxLayout()
        dir_layout.addWidget(self.backup_dir_edit)
        
        browse_btn = QPushButton("📁 Обзор")
        browse_btn.clicked.connect(self.browse_backup_dir)
        browse_btn.setMaximumWidth(80)
        dir_layout.addWidget(browse_btn)
        
        layout.addRow("Папка бекапов:", dir_layout)
        
        layout.addRow(QLabel(""))  # Отступ
        
        # Максимальное количество бекапов
        self.max_auto_spin = QSpinBox()
        self.max_auto_spin.setRange(1, 20)
        self.max_auto_spin.setValue(self.settings.get('max_auto_backups', 5))
        layout.addRow("Макс. авто-бекапов:", self.max_auto_spin)
        
        self.max_normal_spin = QSpinBox()
        self.max_normal_spin.setRange(1, 20)
        self.max_normal_spin.setValue(self.settings.get('max_normal_backups', 3))
        layout.addRow("Макс. обычных бекапов:", self.max_normal_spin)
        
        self.max_full_spin = QSpinBox()
        self.max_full_spin.setRange(1, 20)
        self.max_full_spin.setValue(self.settings.get('max_full_backups', 2))
        layout.addRow("Макс. полных бекапов:", self.max_full_spin)
        
        return widget
    
    def create_content_tab(self):
        """Создает вкладку настроек содержимого"""
        widget = QWidget()
        layout = QVBoxLayout()
        widget.setLayout(layout)
        
        # Обычный бекап
        normal_group = QGroupBox("Обычный бекап")
        normal_layout = QVBoxLayout()
        
        self.normal_folders_list = QListWidget()
        for folder in self.settings.get('normal_backup_folders', []):
            item = QListWidgetItem(folder)
            item.setFlags(item.flags() | Qt.ItemIsEditable)
            self.normal_folders_list.addItem(item)
        
        normal_layout.addWidget(QLabel("Папки для включения:"))
        normal_layout.addWidget(self.normal_folders_list)
        
        normal_btn_layout = QHBoxLayout()
        add_normal_btn = QPushButton("➕ Добавить")
        add_normal_btn.clicked.connect(lambda: self.add_folder(self.normal_folders_list))
        normal_btn_layout.addWidget(add_normal_btn)
        
        remove_normal_btn = QPushButton("➖ Удалить")
        remove_normal_btn.clicked.connect(lambda: self.remove_folder(self.normal_folders_list))
        normal_btn_layout.addWidget(remove_normal_btn)
        
        normal_layout.addLayout(normal_btn_layout)
        normal_group.setLayout(normal_layout)
        layout.addWidget(normal_group)
        
        # Полный бекап
        full_group = QGroupBox("Полный бекап")
        full_layout = QVBoxLayout()
        
        self.full_folders_list = QListWidget()
        for folder in self.settings.get('full_backup_folders', []):
            item = QListWidgetItem(folder)
            item.setFlags(item.flags() | Qt.ItemIsEditable)
            self.full_folders_list.addItem(item)
        
        full_layout.addWidget(QLabel("Папки для включения:"))
        full_layout.addWidget(self.full_folders_list)
        
        full_btn_layout = QHBoxLayout()
        add_full_btn = QPushButton("➕ Добавить")
        add_full_btn.clicked.connect(lambda: self.add_folder(self.full_folders_list))
        full_btn_layout.addWidget(add_full_btn)
        
        remove_full_btn = QPushButton("➖ Удалить")
        remove_full_btn.clicked.connect(lambda: self.remove_folder(self.full_folders_list))
        full_btn_layout.addWidget(remove_full_btn)
        
        full_layout.addLayout(full_btn_layout)
        full_group.setLayout(full_layout)
        layout.addWidget(full_group)
        
        return widget
    
    def create_notifications_tab(self):
        """Создает вкладку настроек уведомлений"""
        widget = QWidget()
        layout = QVBoxLayout()
        widget.setLayout(layout)
        
        group = QGroupBox("Уведомления")
        group_layout = QVBoxLayout()
        
        self.notify_backup_check = QCheckBox("Показывать уведомление о создании бекапа")
        self.notify_backup_check.setChecked(self.settings.get('notify_on_backup', True))
        group_layout.addWidget(self.notify_backup_check)
        
        self.notify_restore_check = QCheckBox("Показывать уведомление о восстановлении")
        self.notify_restore_check.setChecked(self.settings.get('notify_on_restore', True))
        group_layout.addWidget(self.notify_restore_check)
        
        group.setLayout(group_layout)
        layout.addWidget(group)
        
        layout.addStretch()
        return widget
    
    def browse_backup_dir(self):
        """Открывает диалог выбора папки для бекапов"""
        dir_path = QFileDialog.getExistingDirectory(
            self, "Выберите папку для бекапов",
            self.backup_dir_edit.text()
        )
        if dir_path:
            self.backup_dir_edit.setText(dir_path)
    
    def add_folder(self, list_widget):
        """Добавляет новую папку в список"""
        folder, ok = QInputDialog.getText(self, "Новая папка", "Введите название папки:")
        if ok and folder:
            list_widget.addItem(folder)
    
    def remove_folder(self, list_widget):
        """Удаляет выбранную папку из списка"""
        current = list_widget.currentItem()
        if current:
            list_widget.takeItem(list_widget.row(current))
    
    def save_settings(self):
        """Сохраняет настройки"""
        # Основные настройки
        self.settings.set('auto_backup_enabled', self.auto_backup_check.isChecked())
        self.settings.set('auto_backup_interval_days', self.interval_spin.value())
        self.settings.set('backup_dir', self.backup_dir_edit.text())
        self.settings.set('max_auto_backups', self.max_auto_spin.value())
        self.settings.set('max_normal_backups', self.max_normal_spin.value())
        self.settings.set('max_full_backups', self.max_full_spin.value())
        
        # Папки для обычного бекапа
        normal_folders = []
        for i in range(self.normal_folders_list.count()):
            normal_folders.append(self.normal_folders_list.item(i).text())
        self.settings.set('normal_backup_folders', normal_folders)
        
        # Папки для полного бекапа
        full_folders = []
        for i in range(self.full_folders_list.count()):
            full_folders.append(self.full_folders_list.item(i).text())
        self.settings.set('full_backup_folders', full_folders)
        
        # Уведомления
        self.settings.set('notify_on_backup', self.notify_backup_check.isChecked())
        self.settings.set('notify_on_restore', self.notify_restore_check.isChecked())
        
        self.accept()
    
    def reset_settings(self):
        """Сбрасывает настройки к значениям по умолчанию"""
        reply = QMessageBox.question(
            self, "Подтверждение",
            "Сбросить все настройки бекапа к значениям по умолчанию?",
            QMessageBox.Yes | QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            self.settings.reset_to_defaults()
            # Обновляем интерфейс
            self.auto_backup_check.setChecked(self.settings.get('auto_backup_enabled'))
            self.interval_spin.setValue(self.settings.get('auto_backup_interval_days'))
            self.backup_dir_edit.setText(self.settings.get('backup_dir'))
            self.max_auto_spin.setValue(self.settings.get('max_auto_backups'))
            self.max_normal_spin.setValue(self.settings.get('max_normal_backups'))
            self.max_full_spin.setValue(self.settings.get('max_full_backups'))
            
            self.notify_backup_check.setChecked(self.settings.get('notify_on_backup'))
            self.notify_restore_check.setChecked(self.settings.get('notify_on_restore'))
            
            # Обновляем списки папок
            self.normal_folders_list.clear()
            for folder in self.settings.get('normal_backup_folders', []):
                self.normal_folders_list.addItem(folder)
            
            self.full_folders_list.clear()
            for folder in self.settings.get('full_backup_folders', []):
                self.full_folders_list.addItem(folder)