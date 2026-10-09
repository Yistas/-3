# ===== gui/dialogs/gdrive_sync_dialog.py =====
# ПОЛНОСТЬЮ ЗАМЕНИТЬ ФАЙЛ

# -*- coding: utf-8 -*-

"""
Диалог управления синхронизацией с Google Drive
"""

import logging
import json
from pathlib import Path
from PySide6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QPushButton,
                               QLabel, QGroupBox, QCheckBox, QProgressBar,
                               QMessageBox, QFrame, QGridLayout, QApplication)
from PySide6.QtCore import Qt, QThread, Signal, QTimer
from PySide6.QtGui import QFont

# ===== ИМПОРТ paths =====
from utils.paths import paths


# gui/dialogs/gdrive_sync_dialog.py

class SyncThread(QThread):
    """Поток для синхронизации"""
    progress = Signal(str, int, int)  # message, current, total
    finished = Signal(dict)
    
    def __init__(self, gdrive_sync, sync_config):
        super().__init__()
        self.gdrive_sync = gdrive_sync
        self.sync_config = sync_config
        self._is_running = True
    
    def run(self):
        result = {'uploaded': 0, 'downloaded': 0, 'skipped': 0, 'errors': 0}
        
        # 1. СИНХРОНИЗАЦИЯ КОНФИГУРАЦИОННЫХ ФАЙЛОВ (всегда)
        self.progress.emit("Синхронизация конфигурационных файлов...", 0, 5)
        file_result = self.gdrive_sync.sync_all_files()
        result['uploaded'] += file_result['uploaded']
        result['downloaded'] += file_result['downloaded']
        result['skipped'] += file_result['skipped']
        result['errors'] += file_result['errors']
        
        if not self._is_running:
            self.finished.emit(result)
            return
        
        # 2. Синхронизация иконок
        if self.sync_config.get('sync_icons', False) and self._is_running:
            self.progress.emit("Синхронизация иконок...", 1, 5)
            folder_result = self.gdrive_sync.sync_folder("custom_icons")
            result['uploaded'] += folder_result['uploaded']
            result['downloaded'] += folder_result['downloaded']
            result['skipped'] += folder_result['skipped']
            result['errors'] += folder_result['errors']
        
        # 3. Синхронизация изображений стран
        if self.sync_config.get('sync_images', False) and self._is_running:
            self.progress.emit("Синхронизация изображений стран...", 2, 5)
            folder_result = self.gdrive_sync.sync_folder("custom_images")
            result['uploaded'] += folder_result['uploaded']
            result['downloaded'] += folder_result['downloaded']
            result['skipped'] += folder_result['skipped']
            result['errors'] += folder_result['errors']
        
        # 4. Синхронизация фото монет
        if self.sync_config.get('sync_coin_images', False) and self._is_running:
            self.progress.emit("Синхронизация фото монет...", 3, 5)
            folder_result = self.gdrive_sync.sync_folder("coin_images")
            result['uploaded'] += folder_result['uploaded']
            result['downloaded'] += folder_result['downloaded']
            result['skipped'] += folder_result['skipped']
            result['errors'] += folder_result['errors']
        
        # 5. Синхронизация погодовки
        if self.sync_config.get('sync_yearly', False) and self._is_running:
            self.progress.emit("Синхронизация таблиц погодовки...", 4, 5)
            folder_result = self.gdrive_sync.sync_folder("yearly_tables")
            result['uploaded'] += folder_result['uploaded']
            result['downloaded'] += folder_result['downloaded']
            result['skipped'] += folder_result['skipped']
            result['errors'] += folder_result['errors']
        
        self.progress.emit("Готово!", 5, 5)
        self.finished.emit(result)
    
    def stop(self):
        self._is_running = False

class GDriveSyncDialog(QDialog):
    """Диалог управления синхронизацией с Google Drive"""
    
    def __init__(self, gdrive_sync, parent=None):
        super().__init__(parent)
        self.gdrive_sync = gdrive_sync
        self.sync_thread = None
        self.logger = logging.getLogger('CoinCollector.GDriveSyncDialog')
        
        # ===== ИСПРАВЛЕНО: используем paths =====
        self.SETTINGS_FILE = paths.get_data_dir() / "gdrive_sync_settings.json"
        
        self.setWindowTitle("☁️ Синхронизация с Google Drive")
        self.setMinimumWidth(550)
        self.setMinimumHeight(650)
        self.setModal(True)
        
        self.init_ui()
        self.load_settings()
        self.update_status()
    
    def init_ui(self):
        """Инициализация интерфейса"""
        layout = QVBoxLayout()
        layout.setSpacing(10)
        layout.setContentsMargins(15, 15, 15, 15)
        self.setLayout(layout)
        
        # Заголовок
        title = QLabel("☁️ Синхронизация с Google Drive")
        title.setStyleSheet("""
            font-weight: bold;
            font-size: 16px;
            padding: 10px;
            background-color: #4a6fa5;
            color: white;
            border-radius: 5px;
        """)
        title.setAlignment(Qt.AlignCenter)
        layout.addWidget(title)
        
        # === ГЛАВНЫЙ ВКЛЮЧАТЕЛЬ ===
        enable_group = QGroupBox("🔘 Включить синхронизацию")
        enable_layout = QVBoxLayout()
        
        self.enable_sync_check = QCheckBox("✅ Включить автоматическую синхронизацию с Google Drive")
        self.enable_sync_check.setChecked(True)
        self.enable_sync_check.toggled.connect(self.on_enable_toggled)
        self.enable_sync_check.setStyleSheet("font-weight: bold; font-size: 12px;")
        enable_layout.addWidget(self.enable_sync_check)
        
        enable_layout.addWidget(QLabel("   При выключении синхронизация не будет запускаться при старте программы"))
        enable_group.setLayout(enable_layout)
        layout.addWidget(enable_group)
        
        # Статус (виден только когда синхронизация включена)
        self.status_group = QGroupBox("📊 Статус")
        status_layout = QGridLayout()
        
        status_layout.addWidget(QLabel("Статус:"), 0, 0)
        self.status_label = QLabel("⏳ Проверка...")
        self.status_label.setStyleSheet("font-weight: bold;")
        status_layout.addWidget(self.status_label, 0, 1)
        
        status_layout.addWidget(QLabel("Аккаунт:"), 1, 0)
        self.account_label = QLabel("—")
        status_layout.addWidget(self.account_label, 1, 1)
        
        status_layout.addWidget(QLabel("Папка в облаке:"), 2, 0)
        self.folder_label = QLabel("CoinCollector")
        status_layout.addWidget(self.folder_label, 2, 1)
        
        status_layout.addWidget(QLabel("Локальная папка:"), 3, 0)
        self.local_label = QLabel(str(paths.get_data_dir().absolute()))
        status_layout.addWidget(self.local_label, 3, 1)
        
        self.status_group.setLayout(status_layout)
        layout.addWidget(self.status_group)
        
        # Настройки синхронизации
        self.settings_group = QGroupBox("⚙️ Настройки автоматической синхронизации")
        settings_layout = QVBoxLayout()
        
        self.auto_sync_core = QCheckBox("🔄 База данных и настройки")
        self.auto_sync_core.setChecked(True)
        self.auto_sync_core.setEnabled(True)
        settings_layout.addWidget(self.auto_sync_core)
        settings_layout.addWidget(QLabel("   coins.db, settings.json, window_settings.json, backup_settings.json"))
        settings_layout.addSpacing(10)
        
        self.auto_sync_icons = QCheckBox("🖼️ Иконки стран и папок")
        self.auto_sync_icons.setChecked(False)
        settings_layout.addWidget(self.auto_sync_icons)
        
        self.auto_sync_images = QCheckBox("🏳️ Изображения стран (флаги, гербы)")
        self.auto_sync_images.setChecked(False)
        settings_layout.addWidget(self.auto_sync_images)
        
        self.auto_sync_coin_images = QCheckBox("🪙 Фотографии монет")
        self.auto_sync_coin_images.setChecked(False)
        settings_layout.addWidget(self.auto_sync_coin_images)
        
        self.auto_sync_yearly = QCheckBox("📅 Таблицы погодовки (.xlsx)")
        self.auto_sync_yearly.setChecked(False)
        settings_layout.addWidget(self.auto_sync_yearly)
        
        self.settings_group.setLayout(settings_layout)
        layout.addWidget(self.settings_group)
        
        # Кнопки ручной синхронизации
        manual_group = QGroupBox("🔄 Ручная синхронизация")
        manual_layout = QGridLayout()
        manual_layout.setSpacing(8)
        
        sync_core_btn = QPushButton("📁 БД и настройки")
        sync_core_btn.clicked.connect(lambda: self.start_sync({'sync_core': True}))
        manual_layout.addWidget(sync_core_btn, 0, 0)
        
        sync_icons_btn = QPushButton("🎨 Иконки")
        sync_icons_btn.clicked.connect(lambda: self.start_sync({'sync_icons': True}))
        manual_layout.addWidget(sync_icons_btn, 0, 1)
        
        sync_images_btn = QPushButton("🏳️ Изображения стран")
        sync_images_btn.clicked.connect(lambda: self.start_sync({'sync_images': True}))
        manual_layout.addWidget(sync_images_btn, 1, 0)
        
        sync_coin_images_btn = QPushButton("🪙 Фото монет")
        sync_coin_images_btn.clicked.connect(lambda: self.start_sync({'sync_coin_images': True}))
        manual_layout.addWidget(sync_coin_images_btn, 1, 1)
        
        sync_yearly_btn = QPushButton("📅 Погодовка")
        sync_yearly_btn.clicked.connect(lambda: self.start_sync({'sync_yearly': True}))
        manual_layout.addWidget(sync_yearly_btn, 2, 0)
        
        sync_all_btn = QPushButton("🔄 Синхронизировать всё")
        sync_all_btn.clicked.connect(lambda: self.start_sync({
            'sync_core': True,
            'sync_icons': True,
            'sync_images': True,
            'sync_coin_images': True,
            'sync_yearly': True
        }))
        sync_all_btn.setStyleSheet("background-color: #4a6fa5; color: white; font-weight: bold;")
        manual_layout.addWidget(sync_all_btn, 2, 1)
        
        manual_group.setLayout(manual_layout)
        layout.addWidget(manual_group)
        
        # Прогресс бар
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        layout.addWidget(self.progress_bar)
        
        # Статус синхронизации
        self.sync_status_label = QLabel("")
        self.sync_status_label.setStyleSheet("color: #666;")
        self.sync_status_label.setWordWrap(True)
        layout.addWidget(self.sync_status_label)
        
        # Кнопки
        button_layout = QHBoxLayout()
        button_layout.addStretch()
        
        save_btn = QPushButton("💾 Сохранить настройки")
        save_btn.clicked.connect(self.save_settings)
        save_btn.setMinimumHeight(35)
        save_btn.setStyleSheet("background-color: #4CAF50; color: white; font-weight: bold;")
        button_layout.addWidget(save_btn)
        
        close_btn = QPushButton("❌ Закрыть")
        close_btn.clicked.connect(self.accept)
        close_btn.setMinimumHeight(35)
        button_layout.addWidget(close_btn)
        
        layout.addLayout(button_layout)
    
    def on_enable_toggled(self, checked):
        """Обработчик переключения главного выключателя"""
        self.status_group.setEnabled(checked)
        self.settings_group.setEnabled(checked)
        
        for child in self.findChildren(QPushButton):
            btn_text = child.text()
            if btn_text not in ["❌ Закрыть", "💾 Сохранить настройки"]:
                child.setEnabled(checked)
    
    def load_settings(self):
        """Загружает сохранённые настройки"""
        if self.SETTINGS_FILE.exists():
            try:
                with open(self.SETTINGS_FILE, 'r', encoding='utf-8') as f:
                    settings = json.load(f)
                    enabled = settings.get('sync_enabled', True)
                    self.enable_sync_check.setChecked(enabled)
                    self.auto_sync_core.setChecked(settings.get('auto_sync_core', True))
                    self.auto_sync_icons.setChecked(settings.get('auto_sync_icons', False))
                    self.auto_sync_images.setChecked(settings.get('auto_sync_images', False))
                    self.auto_sync_coin_images.setChecked(settings.get('auto_sync_coin_images', False))
                    self.auto_sync_yearly.setChecked(settings.get('auto_sync_yearly', False))
                    
                    # Применяем состояние включения
                    self.on_enable_toggled(enabled)
            except Exception as e:
                self.logger.error(f"Ошибка загрузки настроек: {e}")
    
    def save_settings(self):
        """Сохраняет настройки"""
        settings = {
            'sync_enabled': self.enable_sync_check.isChecked(),
            'auto_sync_core': self.auto_sync_core.isChecked(),
            'auto_sync_icons': self.auto_sync_icons.isChecked(),
            'auto_sync_images': self.auto_sync_images.isChecked(),
            'auto_sync_coin_images': self.auto_sync_coin_images.isChecked(),
            'auto_sync_yearly': self.auto_sync_yearly.isChecked(),
        }
        
        self.SETTINGS_FILE.parent.mkdir(parents=True, exist_ok=True)
        
        try:
            with open(self.SETTINGS_FILE, 'w', encoding='utf-8') as f:
                json.dump(settings, f, ensure_ascii=False, indent=2)
            QMessageBox.information(self, "Успех", "Настройки сохранены")
        except Exception as e:
            self.logger.error(f"Ошибка сохранения настроек: {e}")
            QMessageBox.critical(self, "Ошибка", f"Не удалось保存ить настройки: {e}")
    
    def update_status(self):
        """Обновляет статус подключения"""
        if not self.enable_sync_check.isChecked():
            self.status_label.setText("🔴 Синхронизация отключена")
            self.account_label.setText("—")
            return
        
        if not self.gdrive_sync:
            self.status_label.setText("❌ Google Drive не инициализирован")
            self.account_label.setText("—")
            return
        
        if not self.gdrive_sync.is_available():
            self.status_label.setText("⚠️ Не настроен (нет credentials.json)")
            self.account_label.setText("—")
            self.folder_label.setText("CoinCollector (будет создана)")
            return
        
        try:
            # Получаем статус
            status = self.gdrive_sync.get_status()
            self.status_label.setText("✅ Готов к синхронизации")
            self.account_label.setText("Сервисный аккаунт")
            self.folder_label.setText(status.get('cloud_folder', 'CoinCollector'))
            self.local_label.setText(str(paths.get_data_dir().absolute()))
        except Exception as e:
            self.logger.error(f"Ошибка получения статуса: {e}")
            self.status_label.setText("⚠️ Ошибка подключения")
            self.account_label.setText("—")
    
    def start_sync(self, sync_config):
        """Запускает синхронизацию"""
        if not self.gdrive_sync or not self.gdrive_sync.is_available():
            QMessageBox.warning(
                self, 
                "Синхронизация недоступна",
                "Google Drive не настроен.\n\n"
                "Положите файл credentials.json в папку data/\n"
                "и перезапустите программу для авторизации."
            )
            return
        
        # Блокируем кнопки
        for child in self.findChildren(QPushButton):
            btn_text = child.text()
            if btn_text not in ["❌ Закрыть", "💾 Сохранить настройки"]:
                child.setEnabled(False)
        
        self.progress_bar.setVisible(True)
        self.progress_bar.setRange(0, 5)
        self.progress_bar.setValue(0)
        self.sync_status_label.setText("⏳ Синхронизация...")
        
        # Запускаем поток
        self.sync_thread = SyncThread(self.gdrive_sync, sync_config)
        self.sync_thread.progress.connect(self.on_sync_progress)
        self.sync_thread.finished.connect(self.on_sync_finished)
        self.sync_thread.start()
    
    def on_sync_progress(self, message, current, total):
        """Обновляет прогресс синхронизации"""
        self.progress_bar.setValue(current)
        self.sync_status_label.setText(message)
        QApplication.processEvents()  # <-- ДОЛЖНО РАБОТАТЬ
    
    def on_sync_finished(self, result):
        """Завершение синхронизации"""
        self.progress_bar.setVisible(False)
        
        # Разблокируем кнопки
        for child in self.findChildren(QPushButton):
            child.setEnabled(True)
        
        # Показываем результат
        msg = f"📤 Загружено: {result['uploaded']}\n"
        msg += f"📥 Скачано: {result['downloaded']}\n"
        msg += f"⏭️ Пропущено: {result['skipped']}\n"
        if result['errors'] > 0:
            msg += f"❌ Ошибок: {result['errors']}"
        
        self.sync_status_label.setText(msg)
        
        if result['errors'] == 0:
            QMessageBox.information(self, "Синхронизация завершена", msg)
        else:
            QMessageBox.warning(self, "Синхронизация завершена с ошибками", msg)
        
        # Обновляем статус
        self.update_status()
        
        # Очищаем поток
        self.sync_thread = None
    
    def closeEvent(self, event):
        """Обработчик закрытия"""
        if self.sync_thread and self.sync_thread.isRunning():
            self.sync_thread.stop()
            self.sync_thread.wait(2000)
        event.accept()


# Импорт для QApplication (для processEvents)
from PySide6.QtWidgets import QApplication