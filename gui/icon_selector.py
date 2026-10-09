# -*- coding: utf-8 -*-

"""
Диалог для выбора иконок для элементов дерева
"""

import os
from pathlib import Path
from PySide6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel, 
                               QListWidget, QListWidgetItem, QPushButton,
                               QTabWidget, QWidget, QFileDialog, QMessageBox,
                               QSplitter, QScrollArea, QGroupBox)
from PySide6.QtCore import Qt, QSize
from PySide6.QtGui import QIcon, QPixmap, QFont
from utils.paths import paths
# Удаляем проблемный импорт:
# from gui.widgets.country_tree import CountryTreeWidget

class IconSelectorDialog(QDialog):
    """Диалог для выбора иконки для элемента дерева"""
    
    def __init__(self, parent=None, current_icon=None, for_folder=False):
        super().__init__(parent)
        self.selected_icon = None
        self.selected_icon_type = None  # 'emoji' или 'custom'
        self.current_icon = current_icon
        self.for_folder = for_folder  # True для папок, False для стран
        
        # ===== ИСПРАВЛЕНО: иконки в data/custom_icons/ =====
        from utils.paths import paths
        self.custom_icons_dir = paths.get_data_dir() / "custom_icons"
        self.custom_icons_dir.mkdir(parents=True, exist_ok=True)
        
        self.setWindowTitle("Выбор иконки")
        self.setMinimumWidth(600)
        self.setMinimumHeight(500)
        
        self.init_ui()

    def init_ui(self):
        """Инициализация интерфейса"""
        layout = QVBoxLayout()
        self.setLayout(layout)
        
        # Заголовок с пояснением
        if self.for_folder:
            title_label = QLabel("Выберите иконку для папки/континента:")
        else:
            title_label = QLabel("Выберите иконку для страны:")
        title_label.setStyleSheet("font-weight: bold; font-size: 14px; padding: 5px;")
        layout.addWidget(title_label)
        
        # Текущая иконка (если есть)
        if self.current_icon:
            current_layout = QHBoxLayout()
            current_layout.addWidget(QLabel("Текущая иконка:"))
            
            current_icon_label = QLabel()
            if isinstance(self.current_icon, str) and (self.current_icon.startswith(('🇷', '🇺', '📁', '⭐')) or len(self.current_icon) in [1, 2]):
                # Это emoji
                current_icon_label.setText(self.current_icon)
                current_icon_label.setFont(QFont("Segoe UI Emoji", 24))
            else:
                # Это путь к файлу
                if os.path.exists(str(self.current_icon)):
                    pixmap = QPixmap(str(self.current_icon))
                    if not pixmap.isNull():
                        pixmap = pixmap.scaled(32, 32, Qt.KeepAspectRatio, Qt.SmoothTransformation)
                        current_icon_label.setPixmap(pixmap)
                    else:
                        current_icon_label.setText("❌")
                else:
                    current_icon_label.setText("❌")
            
            current_layout.addWidget(current_icon_label)
            current_layout.addStretch()
            layout.addLayout(current_layout)
        
        # Создаем вкладки
        tabs = QTabWidget()
        
        # Вкладка с emoji
        emoji_tab = self.create_emoji_tab()
        tabs.addTab(emoji_tab, "😊 Emoji")
        
        # Вкладка с пользовательскими иконками
        custom_tab = self.create_custom_tab()
        tabs.addTab(custom_tab, "🖼️ Свои иконки")
        
        layout.addWidget(tabs)
        
        # Кнопки
        button_layout = QHBoxLayout()
        
        ok_btn = QPushButton("✅ OK")
        ok_btn.clicked.connect(self.accept)
        ok_btn.setMinimumHeight(35)
        button_layout.addWidget(ok_btn)
        
        cancel_btn = QPushButton("❌ Отмена")
        cancel_btn.clicked.connect(self.reject)
        cancel_btn.setMinimumHeight(35)
        button_layout.addWidget(cancel_btn)
        
        layout.addLayout(button_layout)    
    
    def create_emoji_tab(self):
        """Создает вкладку с emoji"""
        widget = QWidget()
        layout = QVBoxLayout()
        widget.setLayout(layout)
        
        # Информация
        info_label = QLabel("Выберите emoji из списка:")
        info_label.setStyleSheet("color: gray;")
        layout.addWidget(info_label)
        
        # Список emoji
        self.emoji_list = QListWidget()
        self.emoji_list.setIconSize(QSize(32, 32))
        self.emoji_list.setGridSize(QSize(50, 50))
        self.emoji_list.setViewMode(QListWidget.IconMode)
        self.emoji_list.setResizeMode(QListWidget.Adjust)
        self.emoji_list.itemClicked.connect(self.on_emoji_selected)
        
        # Добавляем emoji
        emojis = [
            # Флаги
            "🇷🇺", "🇺🇸", "🇬🇧", "🇩🇪", "🇫🇷", "🇮🇹", "🇪🇸", "🇨🇳", "🇯🇵", "🇨🇦",
            "🇦🇺", "🇧🇷", "🇮🇳", "🇲🇽", "🇰🇷", "🇳🇱", "🇧🇪", "🇨🇭", "🇦🇹", "🇸🇪",
            "🇳🇴", "🇩🇰", "🇫🇮", "🇵🇱", "🇨🇿", "🇭🇺", "🇬🇷", "🇵🇹", "🇮🇪", "🇳🇿",
            
            # Папки и символы
            "📁", "📂", "🗂️", "📌", "📍", "⭐", "🌟", "💫", "✨", "🔥",
            "💎", "👑", "🏆", "🥇", "🥈", "🥉", "🌍", "🌎", "🌏", "🌐",
            "🗺️", "🧭", "⚜️", "🔱", "♔", "♕", "♚", "♛", "🏳️", "🏴"
        ]
        
        for emoji in emojis:
            item = QListWidgetItem(emoji)
            item.setData(Qt.UserRole, emoji)
            item.setToolTip(emoji)
            item.setTextAlignment(Qt.AlignCenter)
            item.setFont(QFont("Segoe UI Emoji", 18))
            self.emoji_list.addItem(item)
        
        layout.addWidget(self.emoji_list)
        
        return widget
    
    def create_custom_tab(self):
        """Создает вкладку с пользовательскими иконками"""
        widget = QWidget()
        layout = QVBoxLayout()
        widget.setLayout(layout)
        
        # Кнопка загрузки иконки
        upload_layout = QHBoxLayout()
        
        self.upload_btn = QPushButton("📁 Загрузить свою иконку")
        self.upload_btn.clicked.connect(self.upload_custom_icon)
        self.upload_btn.setMinimumHeight(40)
        upload_layout.addWidget(self.upload_btn)
        
        upload_layout.addStretch()
        layout.addLayout(upload_layout)
        
        # Информация
        info_label = QLabel("Или выберите из ранее загруженных:")
        info_label.setStyleSheet("color: gray;")
        layout.addWidget(info_label)
        
        # Список пользовательских иконок
        self.custom_list = QListWidget()
        self.custom_list.setIconSize(QSize(48, 48))
        self.custom_list.setGridSize(QSize(70, 70))
        self.custom_list.setViewMode(QListWidget.IconMode)
        self.custom_list.setResizeMode(QListWidget.Adjust)
        self.custom_list.itemClicked.connect(self.on_custom_icon_selected)
        
        # Загружаем существующие иконки
        self.load_custom_icons()
        
        layout.addWidget(self.custom_list)
        
        # Кнопка удаления
        delete_btn = QPushButton("🗑️ Удалить выбранную иконку")
        delete_btn.clicked.connect(self.delete_custom_icon)
        layout.addWidget(delete_btn)
        
        return widget
    
    def load_custom_icons(self):
        """Загружает пользовательские иконки из папки"""
        self.custom_list.clear()
        
        if self.custom_icons_dir.exists():
            for icon_file in sorted(self.custom_icons_dir.glob("*.*")):
                if icon_file.suffix.lower() in ['.png', '.jpg', '.jpeg', '.ico', '.svg', '.bmp']:
                    try:
                        pixmap = QPixmap(str(icon_file))
                        if not pixmap.isNull():
                            icon = QIcon(pixmap)
                            item = QListWidgetItem(icon, "")
                            item.setData(Qt.UserRole, str(icon_file))
                            item.setToolTip(icon_file.name)
                            item.setFlags(item.flags() | Qt.ItemIsSelectable)
                            self.custom_list.addItem(item)
                    except Exception as e:
                        print(f"Ошибка загрузки иконки {icon_file}: {e}")
    
    def upload_custom_icon(self):
        """Загружает пользовательскую иконку из файла"""
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Выберите иконку", "",
            "Изображения (*.png *.jpg *.jpeg *.ico *.svg *.bmp);;Все файлы (*.*)"
        )
        
        if file_path:
            # Копируем файл в папку custom_icons
            import shutil
            from datetime import datetime
            
            dest_filename = f"custom_{datetime.now().strftime('%Y%m%d_%H%M%S')}{Path(file_path).suffix}"
            dest_path = self.custom_icons_dir / dest_filename
            
            try:
                shutil.copy2(file_path, dest_path)
                self.load_custom_icons()  # Перезагружаем список
                
                # Выбираем новую иконку
                for i in range(self.custom_list.count()):
                    item = self.custom_list.item(i)
                    if item.data(Qt.UserRole) == str(dest_path):
                        self.custom_list.setCurrentItem(item)
                        self.selected_icon = str(dest_path)
                        self.selected_icon_type = 'custom'
                        break
                        
                QMessageBox.information(self, "Успех", "Иконка успешно загружена")
                
            except Exception as e:
                QMessageBox.critical(self, "Ошибка", f"Не удалось загрузить иконку:\n{e}")
    
    def delete_custom_icon(self):
        """Удаляет выбранную пользовательскую иконку"""
        current = self.custom_list.currentItem()
        if not current:
            QMessageBox.warning(self, "Предупреждение", "Выберите иконку для удаления")
            return
        
        icon_path = current.data(Qt.UserRole)
        
        reply = QMessageBox.question(
            self, "Подтверждение",
            f"Удалить иконку '{Path(icon_path).name}'?\n"
            "Это действие нельзя отменить.",
            QMessageBox.Yes | QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            try:
                if os.path.exists(icon_path):
                    os.remove(icon_path)
                self.load_custom_icons()  # Перезагружаем список
                
                if self.selected_icon == icon_path:
                    self.selected_icon = None
                    self.selected_icon_type = None
                    
                QMessageBox.information(self, "Успех", "Иконка удалена")
                
            except Exception as e:
                QMessageBox.critical(self, "Ошибка", f"Не удалось удалить иконку:\n{e}")
    
    def on_emoji_selected(self, item):
        """Обработчик выбора emoji"""
        self.selected_icon = item.data(Qt.UserRole)
        self.selected_icon_type = 'emoji'
        
        # Для отладки
        print(f"Выбран emoji: {self.selected_icon}")
    
    def on_custom_icon_selected(self, item):
        """Обработчик выбора пользовательской иконки"""
        self.selected_icon = item.data(Qt.UserRole)
        self.selected_icon_type = 'custom'
        
        # Для отладки
        print(f"Выбрана пользовательская иконка: {self.selected_icon}")
    
    def get_selected_icon(self):
        """Возвращает выбранную иконку и её тип"""
        if self.selected_icon_type == 'emoji':
            return self.selected_icon, 'emoji'
        elif self.selected_icon_type == 'custom':
            return self.selected_icon, 'custom'
        return None, None