# -*- coding: utf-8 -*-

"""
Диалог для управления континентами
"""

import logging
import os
import re
from datetime import datetime
from pathlib import Path
from PySide6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QPushButton,
                               QTableWidget, QTableWidgetItem, QHeaderView,
                               QMessageBox, QLabel, QSplitter, QGroupBox,
                               QAbstractItemView, QWidget, QFormLayout,
                               QScrollArea, QApplication, QLineEdit, QTextEdit,
                               QFileDialog, QGridLayout, QFrame, QSizePolicy)
from PySide6.QtCore import Qt, Signal, QSettings, QTimer, QUrl
from PySide6.QtGui import QPixmap, QFont, QResizeEvent, QColor, QBrush
from PySide6.QtNetwork import QNetworkAccessManager, QNetworkRequest, QNetworkReply

from database.models import Continent


class ImageLabel(QLabel):
    """Кастомный QLabel для изображений с автоматическим масштабированием"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.original_pixmap = None
        self.setAlignment(Qt.AlignCenter)
        self.setMinimumSize(40, 40)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.setStyleSheet("""
            background-color: #f8f9fa;
            border: 1px solid #dee2e6;
            border-radius: 2px;
        """)
    
    def setPixmap(self, pixmap):
        self.original_pixmap = pixmap
        self.update_display()
    
    def update_display(self):
        if self.original_pixmap and not self.original_pixmap.isNull():
            scaled = self.original_pixmap.scaled(
                self.width() - 4, self.height() - 4,
                Qt.KeepAspectRatio,
                Qt.SmoothTransformation
            )
            super().setPixmap(scaled)
    
    def resizeEvent(self, event: QResizeEvent):
        super().resizeEvent(event)
        self.update_display()


class ContinentReferenceDialog(QDialog):
    """Диалог для управления континентами"""
    
    data_updated = Signal()
    
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
        self.logger = logging.getLogger('CoinCollector.GUI.ContinentReferenceDialog')
        self.db_manager = db_manager
        self.current_continent_id = None
        
        # Директория для карт континентов
        self.continent_maps_dir = Path("continent_maps")
        self.continent_maps_dir.mkdir(exist_ok=True)
        
        # Загружаем настройки
        self.settings = QSettings('CoinCollector', 'ContinentReference')
        
        self.setWindowTitle("🌍 Справочник континентов")
        self.setMinimumSize(900, 700)
        
        self.init_ui()
        self.load_column_widths()
        
        # Подключаем сигнал выбора в таблице
        self.continent_table.itemSelectionChanged.connect(self.on_continent_selected)
        
        # Загружаем континенты
        QTimer.singleShot(100, self.load_continents)
        
        self.logger.info("ContinentReferenceDialog инициализирован")
    
    def init_ui(self):
        """Инициализация интерфейса"""
        layout = QVBoxLayout()
        layout.setContentsMargins(2, 2, 2, 2)
        layout.setSpacing(2)
        self.setLayout(layout)
        
        # Панель инструментов
        toolbar = self.create_toolbar()
        layout.addWidget(toolbar)
        
        # Основной сплиттер
        splitter = QSplitter(Qt.Horizontal)
        splitter.setHandleWidth(2)
        
        # Левая панель - список континентов
        left_panel = self.create_continent_list_panel()
        splitter.addWidget(left_panel)
        
        # Правая панель с информацией
        right_panel = self.create_detail_panel()
        splitter.addWidget(right_panel)
        
        splitter.setSizes([270, 630])
        layout.addWidget(splitter)
        
        # Кнопка закрытия
        close_layout = QHBoxLayout()
        close_layout.addStretch()
        
        close_btn = QPushButton("❌ Закрыть")
        close_btn.clicked.connect(self.accept)
        close_btn.setMinimumHeight(30)
        close_btn.setMinimumWidth(100)
        close_layout.addWidget(close_btn)
        
        layout.addLayout(close_layout)
    
    def create_toolbar(self):
        """Создает панель инструментов"""
        toolbar = QWidget()
        toolbar.setMaximumHeight(40)
        
        layout = QHBoxLayout()
        layout.setContentsMargins(2, 2, 2, 2)
        toolbar.setLayout(layout)
        
        self.save_btn = QPushButton("💾 Сохранить")
        self.save_btn.clicked.connect(self.save_continent_changes)
        self.save_btn.setEnabled(False)
        layout.addWidget(self.save_btn)
        
        layout.addStretch()
        
        self.refresh_btn = QPushButton("🔄")
        self.refresh_btn.setMaximumWidth(30)
        self.refresh_btn.clicked.connect(self.load_continents)
        layout.addWidget(self.refresh_btn)
        
        return toolbar
    
    def create_continent_list_panel(self):
        """Создает панель со списком континентов"""
        panel = QWidget()
        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        panel.setLayout(layout)
        
        # Заголовок
        title = QLabel("📋 Список континентов")
        title.setStyleSheet("font-weight: bold; font-size: 12px; padding: 2px; background-color: #4a6fa5; color: white; border-radius: 2px;")
        title.setAlignment(Qt.AlignCenter)
        layout.addWidget(title)
        
        # Таблица
        self.continent_table = QTableWidget()
        self.continent_table.setColumnCount(2)
        self.continent_table.setHorizontalHeaderLabels(["Континент", "Карта"])
        self.continent_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.continent_table.setAlternatingRowColors(True)
        self.continent_table.setSortingEnabled(True)
        
        # Уменьшаем высоту строк
        self.continent_table.verticalHeader().setDefaultSectionSize(22)
        self.continent_table.verticalHeader().setVisible(False)
        
        header = self.continent_table.horizontalHeader()
        header.setStretchLastSection(False)
        header.setSectionResizeMode(0, QHeaderView.Stretch)
        header.setSectionResizeMode(1, QHeaderView.ResizeToContents)
        header.setMinimumHeight(22)
        header.sectionResized.connect(self.save_column_widths)
        
        layout.addWidget(self.continent_table)
        
        return panel
    
    def create_detail_panel(self):
        """Создает панель с информацией о континенте"""
        panel = QWidget()
        layout = QVBoxLayout()
        layout.setContentsMargins(5, 0, 5, 0)
        panel.setLayout(layout)
        
        # Название континента
        self.info_name = QLabel()
        self.info_name.setStyleSheet("font-weight: bold; font-size: 16px; color: #4a6fa5;")
        self.info_name.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.info_name)
        
        # Карта континента
        map_group = QGroupBox("🗺️ Карта континента")
        map_layout = QVBoxLayout()
        
        self.map_label = ImageLabel()
        self.map_label.setMinimumHeight(200)
        map_layout.addWidget(self.map_label)
        
        self.load_map_btn = QPushButton("📁 Загрузить карту")
        self.load_map_btn.clicked.connect(self.load_continent_map)
        map_layout.addWidget(self.load_map_btn)
        
        map_group.setLayout(map_layout)
        layout.addWidget(map_group)
        
        # Описание
        info_group = QGroupBox("📋 Описание")
        form_layout = QFormLayout()
        
        self.info_description = QTextEdit()
        self.info_description.setMaximumHeight(100)
        form_layout.addRow("Описание:", self.info_description)
        
        info_group.setLayout(form_layout)
        layout.addWidget(info_group)
        
        return panel
    
    def save_column_widths(self):
        """Сохраняет ширину колонок"""
        for i in range(self.continent_table.columnCount()):
            self.settings.setValue(f'column_width_{i}', self.continent_table.columnWidth(i))
    
    def load_column_widths(self):
        """Загружает ширину колонок"""
        for i in range(self.continent_table.columnCount()):
            width = self.settings.value(f'column_width_{i}', type=int)
            if width:
                self.continent_table.setColumnWidth(i, width)
    
    def get_image_path(self, continent_id):
        """Возвращает путь к карте континента"""
        return self.continent_maps_dir / f"continent_{continent_id}.png"
    
    def load_continent_map(self):
        """Загружает карту континента"""
        if not self.current_continent_id:
            QMessageBox.warning(self, "Предупреждение", "Сначала выберите континент")
            return
        
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Выберите карту континента",
            "",
            "Изображения (*.png *.jpg *.jpeg *.bmp *.gif);;Все файлы (*.*)"
        )
        
        if file_path:
            dest_path = self.get_image_path(self.current_continent_id)
            
            try:
                pixmap = QPixmap(file_path)
                if not pixmap.isNull():
                    pixmap.save(str(dest_path))
                    self.map_label.setPixmap(pixmap)
                    self.logger.info(f"Загружена карта: {dest_path}")
                    
                    # Обновляем статус в таблице
                    current_row = self.continent_table.currentRow()
                    if current_row >= 0:
                        self.continent_table.setItem(current_row, 1, QTableWidgetItem("✅ Есть"))
            except Exception as e:
                self.logger.error(f"Ошибка при сохранении: {e}")
    
    def load_continents(self):
        """Загружает список континентов"""
        try:
            # Список стандартных континентов
            standard_continents = ["Европа", "Азия", "Америка", "Африка", "Океания"]
            
            # Получаем все континенты из БД
            continents = self.db_manager.session.query(Continent).all()
            
            # Если нет континентов, создаем стандартные
            if not continents:
                for name in standard_continents:
                    continent = Continent(name=name)
                    self.db_manager.session.add(continent)
                self.db_manager.session.commit()
                continents = self.db_manager.session.query(Continent).all()
            
            self.continent_table.setSortingEnabled(False)
            self.continent_table.setRowCount(len(continents))
            
            for row, continent in enumerate(continents):
                # Название континента
                name_item = QTableWidgetItem(continent.name)
                name_item.setData(Qt.UserRole, continent.id)
                
                # Устанавливаем цвет текста
                color_hex = self.CONTINENT_COLORS.get(continent.name, "#000000")
                name_item.setForeground(QBrush(QColor(color_hex)))
                
                self.continent_table.setItem(row, 0, name_item)
                
                # Статус карты
                map_path = self.get_image_path(continent.id)
                map_status = "✅ Есть" if map_path.exists() else "❌ Нет"
                map_item = QTableWidgetItem(map_status)
                map_item.setTextAlignment(Qt.AlignCenter)
                self.continent_table.setItem(row, 1, map_item)
            
            self.continent_table.setSortingEnabled(True)
            
            if continents:
                self.continent_table.selectRow(0)
            
        except Exception as e:
            self.logger.error(f"Ошибка при загрузке континентов: {e}")
    
    def on_continent_selected(self):
        """Обработчик выбора континента"""
        current_row = self.continent_table.currentRow()
        if current_row < 0:
            return
        
        item = self.continent_table.item(current_row, 0)
        if not item:
            return
        
        continent_id = item.data(Qt.UserRole)
        if not continent_id:
            return
        
        self.current_continent_id = continent_id
        self.save_btn.setEnabled(True)
        
        self.load_continent_details(continent_id)
    
    def load_continent_details(self, continent_id):
        """Загружает детали континента"""
        try:
            continent = self.db_manager.session.query(Continent).get(continent_id)
            if not continent:
                return
            
            self.info_name.setText(continent.name)
            
            # Устанавливаем цвет названия
            color_hex = self.CONTINENT_COLORS.get(continent.name, "#4a6fa5")
            self.info_name.setStyleSheet(f"font-weight: bold; font-size: 16px; color: {color_hex};")
            
            # Загружаем карту
            map_path = self.get_image_path(continent_id)
            if map_path.exists():
                pixmap = QPixmap(str(map_path))
                self.map_label.setPixmap(pixmap)
            else:
                self.map_label.setText("🗺️")
                self.map_label.setStyleSheet("font-size: 48px; color: #999;")
            
            # Загружаем описание
            self.info_description.setText(continent.description or "")
            
        except Exception as e:
            self.logger.error(f"Ошибка при загрузке деталей: {e}")
    
    def save_continent_changes(self):
        """Сохраняет изменения"""
        if not self.current_continent_id:
            return
        
        try:
            continent = self.db_manager.session.query(Continent).get(self.current_continent_id)
            if not continent:
                return
            
            # Сохраняем описание
            continent.description = self.info_description.toPlainText() or None
            
            # Сохраняем путь к карте
            map_path = self.get_image_path(self.current_continent_id)
            if map_path.exists():
                continent.map_image_path = str(map_path)
            
            continent.updated_at = datetime.now()
            self.db_manager.session.commit()
            
            QMessageBox.information(self, "Успех", "Изменения сохранены")
            
        except Exception as e:
            self.logger.error(f"Ошибка при сохранении: {e}")