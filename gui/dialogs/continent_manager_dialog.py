# -*- coding: utf-8 -*-

"""
Диалог для управления континентами и загрузки их карт
"""

import logging
import os
import shutil
from datetime import datetime
from pathlib import Path
from PySide6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QPushButton,
                               QTableWidget, QTableWidgetItem, QHeaderView,
                               QMessageBox, QLabel, QSplitter, QGroupBox,
                               QAbstractItemView, QWidget, QFormLayout,
                               QScrollArea, QApplication, QLineEdit, QTextEdit,
                               QFileDialog, QGridLayout, QFrame, QSizePolicy)
from PySide6.QtCore import Qt, Signal, QSettings, QTimer
from PySide6.QtGui import QPixmap, QFont, QResizeEvent

from database.models import Continent


class ImageLabel(QLabel):
    """Кастомный QLabel для изображений с автоматическим масштабированием"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.original_pixmap = None
        self.setAlignment(Qt.AlignCenter)
        self.setMinimumSize(200, 150)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.setStyleSheet("""
            background-color: #f8f9fa;
            border: 2px dashed #ccc;
            border-radius: 5px;
        """)
    
    def setPixmap(self, pixmap):
        """Сохраняет оригинальное изображение и масштабирует его"""
        self.original_pixmap = pixmap
        self.update_display()
    
    def update_display(self):
        """Обновляет отображение с текущим размером виджета"""
        if self.original_pixmap and not self.original_pixmap.isNull():
            scaled = self.original_pixmap.scaled(
                self.width() - 10, self.height() - 10,
                Qt.KeepAspectRatio,
                Qt.SmoothTransformation
            )
            super().setPixmap(scaled)
    
    def resizeEvent(self, event: QResizeEvent):
        super().resizeEvent(event)
        self.update_display()


class ContinentManagerDialog(QDialog):
    """
    Диалог для управления континентами и загрузки их карт
    """
    
    data_updated = Signal()
    
    # Список континентов
    CONTINENTS = ["Европа", "Азия", "Америка", "Африка", "Океания"]
    
    # Цвета для континентов
    CONTINENT_COLORS = {
        "Европа": "#4a6fa5",      # Синий
        "Азия": "#e67e22",         # Оранжевый
        "Америка": "#27ae60",      # Зелёный
        "Африка": "#f1c40f",       # Жёлтый
        "Океания": "#9b59b6",      # Фиолетовый
    }
    
    def __init__(self, db_manager, parent=None):
        super().__init__(parent)
        self.logger = logging.getLogger('CoinCollector.GUI.ContinentManagerDialog')
        self.db_manager = db_manager
        self.current_continent_id = None
        self.current_continent_name = None
        
        # Директория для карт континентов
        self.continent_maps_dir = Path("continent_maps")
        self.continent_maps_dir.mkdir(exist_ok=True)
        
        self.setWindowTitle("🌍 Управление континентами")
        self.setMinimumSize(1000, 700)
        
        self.init_ui()
        self.load_data()
        
        self.logger.info("ContinentManagerDialog инициализирован")
    
    def init_ui(self):
        """Инициализация интерфейса"""
        layout = QVBoxLayout()
        layout.setContentsMargins(3, 3, 3, 3)
        layout.setSpacing(3)
        self.setLayout(layout)
        
        # Заголовок
        title_label = QLabel("🌍 Управление континентами")
        title_label.setStyleSheet("""
            font-weight: bold;
            font-size: 16px;
            padding: 8px;
            background-color: #4a6fa5;
            color: white;
            border-radius: 3px;
        """)
        title_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(title_label)
        
        # Основной сплиттер
        splitter = QSplitter(Qt.Horizontal)
        splitter.setHandleWidth(3)
        
        # Левая панель - список континентов
        left_panel = self.create_continent_list_panel()
        splitter.addWidget(left_panel)
        
        # Правая панель - детальная информация о континенте
        right_panel = self.create_detail_panel()
        splitter.addWidget(right_panel)
        
        splitter.setSizes([300, 700])
        layout.addWidget(splitter)
        
        # Кнопка закрытия
        close_layout = QHBoxLayout()
        close_layout.addStretch()
        
        close_btn = QPushButton("❌ Закрыть")
        close_btn.clicked.connect(self.accept)
        close_btn.setMinimumHeight(35)
        close_btn.setMinimumWidth(100)
        close_btn.setStyleSheet("""
            QPushButton {
                background-color: #f44336;
                color: white;
                font-weight: bold;
                border-radius: 3px;
                padding: 5px 10px;
            }
            QPushButton:hover {
                background-color: #d32f2f;
            }
        """)
        close_layout.addWidget(close_btn)
        
        layout.addLayout(close_layout)
    
    def create_continent_list_panel(self):
        """Создает панель со списком континентов"""
        panel = QWidget()
        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(2)
        panel.setLayout(layout)
        
        # Заголовок
        title = QLabel("📋 Список континентов")
        title.setMaximumHeight(25)
        title.setStyleSheet("""
            font-weight: bold;
            font-size: 12px;
            padding: 3px;
            background-color: #4a6fa5;
            color: white;
            border-radius: 2px;
        """)
        title.setAlignment(Qt.AlignCenter)
        layout.addWidget(title)
        
        # Таблица континентов
        self.continent_table = QTableWidget()
        self.continent_table.setColumnCount(2)
        self.continent_table.setHorizontalHeaderLabels(["Континент", "Карта"])
        self.continent_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.continent_table.setAlternatingRowColors(True)
        self.continent_table.setSortingEnabled(True)
        
        # Настройка колонок
        header = self.continent_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.Stretch)
        header.setSectionResizeMode(1, QHeaderView.ResizeToContents)
        
        self.continent_table.itemSelectionChanged.connect(self.on_continent_selected)
        
        layout.addWidget(self.continent_table)
        
        return panel
    
    def create_detail_panel(self):
        """Создает панель с детальной информацией о континенте"""
        panel = QWidget()
        main_layout = QVBoxLayout()
        main_layout.setContentsMargins(5, 0, 5, 0)
        main_layout.setSpacing(10)
        panel.setLayout(main_layout)
        
        # Название континента
        self.continent_name_label = QLabel()
        self.continent_name_label.setMaximumHeight(40)
        self.continent_name_label.setStyleSheet("""
            font-weight: bold;
            font-size: 18px;
            color: #4a6fa5;
            padding: 8px;
            background-color: #f0f7ff;
            border: 1px solid #4a6fa5;
            border-radius: 5px;
        """)
        self.continent_name_label.setAlignment(Qt.AlignCenter)
        main_layout.addWidget(self.continent_name_label)
        
        # Карта континента
        map_group = QGroupBox("🗺️ Карта континента")
        map_group.setStyleSheet("""
            QGroupBox {
                font-weight: bold;
                font-size: 12px;
                margin-top: 5px;
                padding-top: 5px;
            }
        """)
        map_layout = QVBoxLayout()
        map_layout.setSpacing(5)
        map_layout.setContentsMargins(5, 5, 5, 5)
        
        self.continent_map_label = ImageLabel()
        self.continent_map_label.setMinimumHeight(300)
        map_layout.addWidget(self.continent_map_label)
        
        self.load_map_btn = QPushButton("📁 Загрузить карту континента")
        self.load_map_btn.clicked.connect(self.load_continent_map)
        self.load_map_btn.setMinimumHeight(35)
        map_layout.addWidget(self.load_map_btn)
        
        map_group.setLayout(map_layout)
        main_layout.addWidget(map_group)
        
        # Информация о континенте
        info_group = QGroupBox("ℹ️ Информация")
        info_layout = QFormLayout()
        info_layout.setSpacing(5)
        
        self.continent_description = QTextEdit()
        self.continent_description.setMaximumHeight(100)
        self.continent_description.setPlaceholderText("Описание континента (необязательно)")
        info_layout.addRow("Описание:", self.continent_description)
        
        info_group.setLayout(info_layout)
        main_layout.addWidget(info_group)
        
        # Кнопка сохранения
        self.save_btn = QPushButton("💾 Сохранить изменения")
        self.save_btn.clicked.connect(self.save_continent_changes)
        self.save_btn.setMinimumHeight(35)
        self.save_btn.setStyleSheet("background-color: #4CAF50; color: white; font-weight: bold;")
        main_layout.addWidget(self.save_btn)
        
        main_layout.addStretch()
        
        return panel
    
    def load_data(self):
        """Загружает данные о континентах"""
        try:
            # Получаем или создаем записи для всех континентов
            for continent_name in self.CONTINENTS:
                continent = self.db_manager.session.query(Continent).filter_by(name=continent_name).first()
                if not continent:
                    continent = Continent(name=continent_name)
                    self.db_manager.session.add(continent)
            
            self.db_manager.session.commit()
            
            # Получаем все континенты из БД
            continents = self.db_manager.session.query(Continent).all()
            
            # Заполняем таблицу
            self.continent_table.setRowCount(len(continents))
            
            for row, continent in enumerate(continents):
                # Название континента
                name_item = QTableWidgetItem(continent.name)
                name_item.setData(Qt.UserRole, continent.id)
                
                # Устанавливаем цвет в зависимости от континента
                color = self.CONTINENT_COLORS.get(continent.name, "#000000")
                name_item.setForeground(Qt.GlobalColor)  # Сброс цвета
                
                self.continent_table.setItem(row, 0, name_item)
                
                # Статус карты
                map_status = "✅ Есть" if continent.map_image_path and os.path.exists(continent.map_image_path) else "❌ Нет"
                map_item = QTableWidgetItem(map_status)
                map_item.setTextAlignment(Qt.AlignCenter)
                self.continent_table.setItem(row, 1, map_item)
            
            # Выбираем первый континент
            if continents:
                self.continent_table.selectRow(0)
            
        except Exception as e:
            self.logger.error(f"Ошибка при загрузке данных: {e}")
    
    def on_continent_selected(self):
        """Обработчик выбора континента"""
        current_row = self.continent_table.currentRow()
        if current_row < 0:
            return
        
        continent_id = self.continent_table.item(current_row, 0).data(Qt.UserRole)
        continent = self.db_manager.session.query(Continent).get(continent_id)
        
        if not continent:
            return
        
        self.current_continent_id = continent.id
        self.current_continent_name = continent.name
        
        # Обновляем заголовок
        self.continent_name_label.setText(continent.name)
        
        # Устанавливаем цвет в зависимости от континента
        color = self.CONTINENT_COLORS.get(continent.name, "#4a6fa5")
        self.continent_name_label.setStyleSheet(f"""
            font-weight: bold;
            font-size: 18px;
            color: {color};
            padding: 8px;
            background-color: #f0f7ff;
            border: 1px solid {color};
            border-radius: 5px;
        """)
        
        # Загружаем карту
        self.continent_map_label.clear()
        if continent.map_image_path and os.path.exists(continent.map_image_path):
            pixmap = QPixmap(continent.map_image_path)
            if not pixmap.isNull():
                self.continent_map_label.setPixmap(pixmap)
            else:
                self.continent_map_label.setText("🖼️")
                self.continent_map_label.setStyleSheet("font-size: 48px; color: #999;")
        else:
            self.continent_map_label.setText("🗺️")
            self.continent_map_label.setStyleSheet("font-size: 48px; color: #999;")
        
        # Загружаем описание
        self.continent_description.setText(continent.description or "")
    
    def load_continent_map(self):
        """Загружает карту для выбранного континента"""
        if not self.current_continent_id:
            QMessageBox.warning(self, "Предупреждение", "Выберите континент")
            return
        
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Выберите карту континента",
            "",
            "Изображения (*.png *.jpg *.jpeg *.bmp *.gif);;Все файлы (*.*)"
        )
        
        if file_path:
            # Формируем имя файла для сохранения
            continent_name = self.current_continent_name.lower()
            dest_filename = f"continent_{continent_name}.png"
            dest_path = self.continent_maps_dir / dest_filename
            
            try:
                # Загружаем и сохраняем изображение
                pixmap = QPixmap(file_path)
                if not pixmap.isNull():
                    pixmap.save(str(dest_path))
                    
                    # Отображаем
                    self.continent_map_label.setPixmap(pixmap)
                    
                    self.logger.info(f"Загружена карта для {self.current_continent_name}: {dest_path}")
                    
                    # Обновляем статус в таблице
                    current_row = self.continent_table.currentRow()
                    if current_row >= 0:
                        self.continent_table.setItem(current_row, 1, QTableWidgetItem("✅ Есть"))
                    
                else:
                    QMessageBox.warning(self, "Ошибка", "Не удалось загрузить изображение")
                    
            except Exception as e:
                self.logger.error(f"Ошибка при сохранении карты: {e}")
                QMessageBox.critical(self, "Ошибка", f"Не удалось сохранить карту: {e}")
    
    def save_continent_changes(self):
        """Сохраняет изменения для континента"""
        if not self.current_continent_id:
            return
        
        try:
            continent = self.db_manager.session.query(Continent).get(self.current_continent_id)
            if not continent:
                return
            
            # Сохраняем описание
            continent.description = self.continent_description.toPlainText() or None
            
            # Сохраняем путь к карте, если она была загружена
            continent_name = continent.name.lower()
            map_path = self.continent_maps_dir / f"continent_{continent_name}.png"
            if map_path.exists():
                continent.map_image_path = str(map_path)
            
            continent.updated_at = datetime.now()
            self.db_manager.session.commit()
            
            QMessageBox.information(self, "Успех", "Изменения сохранены")
            self.logger.info(f"Сохранены изменения для континента {continent.name}")
            
        except Exception as e:
            self.logger.error(f"Ошибка при сохранении: {e}")
            QMessageBox.critical(self, "Ошибка", f"Не удалось сохранить изменения: {e}")