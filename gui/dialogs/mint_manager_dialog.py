# -*- coding: utf-8 -*-

"""
Диалог управления справочником монетных дворов
"""

from PySide6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QPushButton,
                               QTableWidget, QTableWidgetItem, QHeaderView,
                               QMessageBox, QLabel, QSplitter, QTextEdit,
                               QGroupBox, QAbstractItemView, QWidget)
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont

from gui.dialogs.mint_dialog import MintDialog


class MintManagerDialog(QDialog):
    """Диалог для управления справочником монетных дворов"""
    
    def __init__(self, db_manager, parent=None):
        super().__init__(parent)
        self.db_manager = db_manager
        self.setWindowTitle("Справочник монетных дворов")
        self.setMinimumSize(900, 600)
        
        layout = QVBoxLayout()
        self.setLayout(layout)
        
        # Заголовок
        title_label = QLabel("🏭 Справочник монетных дворов")
        title_label.setStyleSheet("font-weight: bold; font-size: 16px; padding: 8px; background-color: #4a6fa5; color: white; border-radius: 3px;")
        title_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(title_label)
        
        # Панель инструментов
        toolbar_layout = QHBoxLayout()
        
        add_btn = QPushButton("➕ Добавить")
        add_btn.clicked.connect(self.add_mint)
        add_btn.setMinimumHeight(30)
        toolbar_layout.addWidget(add_btn)
        
        edit_btn = QPushButton("✏️ Редактировать")
        edit_btn.clicked.connect(self.edit_mint)
        edit_btn.setMinimumHeight(30)
        toolbar_layout.addWidget(edit_btn)
        
        delete_btn = QPushButton("🗑️ Удалить")
        delete_btn.clicked.connect(self.delete_mint)
        delete_btn.setMinimumHeight(30)
        toolbar_layout.addWidget(delete_btn)
        
        toolbar_layout.addStretch()
        
        refresh_btn = QPushButton("🔄 Обновить")
        refresh_btn.clicked.connect(self.load_mints)
        refresh_btn.setMinimumHeight(30)
        toolbar_layout.addWidget(refresh_btn)
        
        layout.addLayout(toolbar_layout)
        
        # Создаем сплиттер для таблицы и деталей
        splitter = QSplitter(Qt.Horizontal)
        
        # Левая панель - таблица монетных дворов
        left_panel = QWidget()
        left_layout = QVBoxLayout()
        left_panel.setLayout(left_layout)
        
        # Таблица
        self.table = QTableWidget()
        self.table.setColumnCount(6)
        self.table.setHorizontalHeaderLabels(["ID", "Название", "Краткое", "Знак", "Страна", "Город"])
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setAlternatingRowColors(True)
        self.table.itemSelectionChanged.connect(self.on_mint_selected)
        
        left_layout.addWidget(QLabel("Список монетных дворов:"))
        left_layout.addWidget(self.table)
        
        splitter.addWidget(left_panel)
        
        # Правая панель - детальная информация
        right_panel = QWidget()
        right_layout = QVBoxLayout()
        right_panel.setLayout(right_layout)
        
        # Информация о выбранном монетном дворе
        self.info_group = QGroupBox("Информация о монетном дворе")
        info_layout = QVBoxLayout()
        
        self.info_text = QTextEdit()
        self.info_text.setReadOnly(True)
        self.info_text.setFont(QFont("Courier New", 10))
        info_layout.addWidget(self.info_text)
        
        self.info_group.setLayout(info_layout)
        right_layout.addWidget(self.info_group)
        
        splitter.addWidget(right_panel)
        
        # Устанавливаем соотношение размеров (2:1)
        splitter.setSizes([600, 300])
        
        layout.addWidget(splitter)
        
        # Кнопка закрытия
        button_layout = QHBoxLayout()
        button_layout.addStretch()
        
        close_btn = QPushButton("❌ Закрыть")
        close_btn.clicked.connect(self.accept)
        close_btn.setMinimumHeight(35)
        button_layout.addWidget(close_btn)
        
        layout.addLayout(button_layout)
        
        # Загружаем список монетных дворов
        self.load_mints()
    
    def load_mints(self):
        """Загружает список монетных дворов в таблицу"""
        try:
            mints = self.db_manager.get_all_mints()
            
            self.table.setRowCount(len(mints))
            
            for row, mint in enumerate(mints):
                # ID
                id_item = QTableWidgetItem(str(mint.id))
                id_item.setTextAlignment(Qt.AlignCenter)
                self.table.setItem(row, 0, id_item)
                
                # Название
                name_item = QTableWidgetItem(mint.name)
                self.table.setItem(row, 1, name_item)
                
                # Краткое название
                short_name_item = QTableWidgetItem(mint.short_name or "")
                short_name_item.setTextAlignment(Qt.AlignCenter)
                self.table.setItem(row, 2, short_name_item)
                
                # Знак
                mark_item = QTableWidgetItem(mint.mark or "")
                mark_item.setTextAlignment(Qt.AlignCenter)
                self.table.setItem(row, 3, mark_item)
                
                # Страна
                country_name = mint.country.name if mint.country else ""
                country_item = QTableWidgetItem(country_name)
                self.table.setItem(row, 4, country_item)
                
                # Город
                city_item = QTableWidgetItem(mint.city or "")
                self.table.setItem(row, 5, city_item)
            
            # Выбираем первую строку, если есть
            if mints:
                self.table.selectRow(0)
            
        except Exception as e:
            QMessageBox.critical(self, "Ошибка", f"Не удалось загрузить список монетных дворов: {e}")
    
    def on_mint_selected(self):
        """Обработчик выбора монетного двора в таблице"""
        current_row = self.table.currentRow()
        if current_row < 0:
            self.info_text.clear()
            return
        
        try:
            mint_id = int(self.table.item(current_row, 0).text())
            mint = self.db_manager.get_mint(mint_id)
            
            if mint:
                # Формируем информацию о монетном дворе
                info = []
                info.append(f"ID: {mint.id}")
                info.append(f"Название: {mint.name}")
                if mint.short_name:
                    info.append(f"Краткое название: {mint.short_name}")
                if mint.mark:
                    info.append(f"Знак на монетах: {mint.mark}")
                if mint.country:
                    info.append(f"Страна: {mint.country.name}")
                if mint.city:
                    info.append(f"Город: {mint.city}")
                if mint.founded_year:
                    info.append(f"Год основания: {mint.founded_year}")
                if mint.closed_year:
                    info.append(f"Год закрытия: {mint.closed_year}")
                if mint.website:
                    info.append(f"Веб-сайт: {mint.website}")
                
                if mint.description:
                    info.append("")
                    info.append("Описание:")
                    info.append(mint.description)
                
                self.info_text.setText("\n".join(info))
            
        except Exception as e:
            self.info_text.setText(f"Ошибка загрузки информации: {e}")
    
    def add_mint(self):
        """Добавляет новый монетный двор"""
        dialog = MintDialog(self.db_manager, self)
        if dialog.exec():
            self.load_mints()
    
    def edit_mint(self):
        """Редактирует выбранный монетный двор"""
        current_row = self.table.currentRow()
        if current_row < 0:
            QMessageBox.warning(self, "Предупреждение", "Выберите монетный двор для редактирования")
            return
        
        mint_id = int(self.table.item(current_row, 0).text())
        dialog = MintDialog(self.db_manager, self, mint_id)
        if dialog.exec():
            self.load_mints()
    
    def delete_mint(self):
        """Удаляет выбранный монетный двор"""
        current_row = self.table.currentRow()
        if current_row < 0:
            QMessageBox.warning(self, "Предупреждение", "Выберите монетный двор для удаления")
            return
        
        mint_name = self.table.item(current_row, 1).text()
        mint_id = int(self.table.item(current_row, 0).text())
        
        reply = QMessageBox.question(
            self, "Подтверждение",
            f"Вы уверены, что хотите удалить монетный двор '{mint_name}'?\n\n"
            "Если монетный двор используется в монетах, удаление будет невозможно.",
            QMessageBox.Yes | QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            try:
                success, message = self.db_manager.delete_mint(mint_id)
                if success:
                    QMessageBox.information(self, "Успех", message)
                    self.load_mints()
                else:
                    QMessageBox.warning(self, "Предупреждение", message)
            except Exception as e:
                QMessageBox.critical(self, "Ошибка", f"Не удалось удалить монетный двор: {e}")