# -*- coding: utf-8 -*-

"""
Диалог для управления справочником гуртов
"""

import logging
from datetime import datetime
from PySide6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QPushButton,
                               QTableWidget, QTableWidgetItem, QHeaderView,
                               QMessageBox, QLabel, QTextEdit,
                               QGroupBox, QAbstractItemView, QWidget)
from PySide6.QtCore import Qt

from gui.dialogs.edge_dialog import EdgeDialog


class EdgeManagerDialog(QDialog):
    """Диалог для управления справочником гуртов"""
    
    def __init__(self, db_manager, parent=None):
        super().__init__(parent)
        self.logger = logging.getLogger('CoinCollector.GUI.EdgeManagerDialog')
        self.db_manager = db_manager
        self.setWindowTitle("Справочник гуртов")
        self.setMinimumSize(800, 500)
        
        layout = QVBoxLayout()
        self.setLayout(layout)
        
        # Заголовок
        title_label = QLabel("⚙️ Справочник гуртов")
        title_label.setStyleSheet("font-weight: bold; font-size: 16px; padding: 8px; background-color: #4a6fa5; color: white; border-radius: 3px;")
        title_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(title_label)
        
        # Панель инструментов
        toolbar_layout = QHBoxLayout()
        
        self.add_btn = QPushButton("➕ Добавить")
        self.add_btn.clicked.connect(self.add_edge)
        self.add_btn.setMinimumHeight(30)
        toolbar_layout.addWidget(self.add_btn)
        
        self.edit_btn = QPushButton("✏️ Редактировать")
        self.edit_btn.clicked.connect(self.edit_edge)
        self.edit_btn.setMinimumHeight(30)
        toolbar_layout.addWidget(self.edit_btn)
        
        self.delete_btn = QPushButton("🗑️ Удалить")
        self.delete_btn.clicked.connect(self.delete_edge)
        self.delete_btn.setMinimumHeight(30)
        toolbar_layout.addWidget(self.delete_btn)
        
        toolbar_layout.addStretch()
        
        self.refresh_btn = QPushButton("🔄 Обновить")
        self.refresh_btn.clicked.connect(self.load_edges)
        self.refresh_btn.setMinimumHeight(30)
        toolbar_layout.addWidget(self.refresh_btn)
        
        layout.addLayout(toolbar_layout)
        
        # Таблица гуртов
        self.table = QTableWidget()
        self.table.setColumnCount(3)
        self.table.setHorizontalHeaderLabels(["ID", "Название", "Описание"])
        
        # Настройка ширины колонок
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeToContents)  # ID по содержимому
        header.setSectionResizeMode(1, QHeaderView.ResizeToContents)  # Название по содержимому
        header.setSectionResizeMode(2, QHeaderView.Stretch)  # Описание растягивается
        
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setAlternatingRowColors(True)
        self.table.itemSelectionChanged.connect(self.on_edge_selected)
        
        layout.addWidget(QLabel("Список гуртов:"))
        layout.addWidget(self.table)
        
        # Информация о выбранном гурте
        self.info_group = QGroupBox("Информация о гурте")
        info_layout = QVBoxLayout()
        
        self.info_text = QTextEdit()
        self.info_text.setReadOnly(True)
        self.info_text.setMaximumHeight(150)
        info_layout.addWidget(self.info_text)
        
        self.info_group.setLayout(info_layout)
        layout.addWidget(self.info_group)
        
        # Кнопка закрытия
        button_layout = QHBoxLayout()
        button_layout.addStretch()
        
        close_btn = QPushButton("❌ Закрыть")
        close_btn.clicked.connect(self.accept)
        close_btn.setMinimumHeight(35)
        button_layout.addWidget(close_btn)
        
        layout.addLayout(button_layout)
        
        # Загружаем список гуртов
        self.load_edges()
    
    def load_edges(self):
        """Загружает список гуртов в таблицу"""
        try:
            from database.models import Edge
            
            edges = self.db_manager.session.query(Edge).order_by(Edge.name).all()
            
            self.table.setRowCount(len(edges))
            self.table.setSortingEnabled(False)  # Отключаем сортировку на время заполнения
            
            for row, edge in enumerate(edges):
                # ID
                id_item = QTableWidgetItem(str(edge.id))
                id_item.setTextAlignment(Qt.AlignCenter)
                id_item.setData(Qt.UserRole, edge.id)
                self.table.setItem(row, 0, id_item)
                
                # Название
                name_item = QTableWidgetItem(edge.name)
                name_item.setData(Qt.UserRole, edge.id)
                self.table.setItem(row, 1, name_item)
                
                # Описание
                desc_item = QTableWidgetItem(edge.description or "")
                desc_item.setTextAlignment(Qt.AlignLeft | Qt.AlignTop)
                self.table.setItem(row, 2, desc_item)
            
            self.table.setSortingEnabled(True)  # Включаем сортировку обратно
            
            # Автоматически подгоняем ширину колонок
            self.table.resizeColumnsToContents()
            
            # Устанавливаем минимальную ширину для колонки "Название"
            if self.table.columnWidth(1) < 150:
                self.table.setColumnWidth(1, 150)
            
            # Выбираем первую строку, если есть
            if edges:
                self.table.selectRow(0)
            
        except Exception as e:
            self.logger.error(f"Ошибка при загрузке гуртов: {e}")
            QMessageBox.critical(self, "Ошибка", f"Не удалось загрузить список гуртов: {e}")
    
    def on_edge_selected(self):
        """Обработчик выбора гурта в таблице"""
        current_row = self.table.currentRow()
        if current_row < 0:
            self.info_text.clear()
            return
        
        try:
            from database.models import Edge
            from database.models import Coin
            
            edge_id = self.table.item(current_row, 0).data(Qt.UserRole)
            edge = self.db_manager.session.query(Edge).get(edge_id)
            
            if edge:
                # Считаем количество монет с этим типом гурта
                coin_count = self.db_manager.session.query(Coin).filter_by(edge_id=edge_id).count()
                
                # Формируем информацию о гурте
                info = []
                info.append(f"ID: {edge.id}")
                info.append(f"Название: {edge.name}")
                info.append("")
                info.append(f"Используется в монетах: {coin_count}")
                
                if edge.description:
                    info.append("")
                    info.append("Описание:")
                    info.append(edge.description)
                
                self.info_text.setText("\n".join(info))
            
        except Exception as e:
            self.logger.error(f"Ошибка при выборе гурта: {e}")
            self.info_text.setText(f"Ошибка загрузки информации: {e}")
    
    def add_edge(self):
        """Добавляет новый гурт"""
        try:
            dialog = EdgeDialog(self.db_manager, self)
            if dialog.exec():
                self.load_edges()
        except Exception as e:
            self.logger.error(f"Ошибка при добавлении гурта: {e}")
            QMessageBox.critical(self, "Ошибка", f"Не удалось открыть диалог добавления: {e}")
    
    def edit_edge(self):
        """Редактирует выбранный гурт"""
        current_row = self.table.currentRow()
        if current_row < 0:
            QMessageBox.warning(self, "Предупреждение", "Выберите гурт для редактирования")
            return
        
        try:
            edge_id = self.table.item(current_row, 0).data(Qt.UserRole)
            dialog = EdgeDialog(self.db_manager, self, edge_id)
            if dialog.exec():
                self.load_edges()
        except Exception as e:
            self.logger.error(f"Ошибка при редактировании гурта: {e}")
            QMessageBox.critical(self, "Ошибка", f"Не удалось открыть диалог редактирования: {e}")
    
    def delete_edge(self):
        """Удаляет выбранный гурт"""
        current_row = self.table.currentRow()
        if current_row < 0:
            QMessageBox.warning(self, "Предупреждение", "Выберите гурт для удаления")
            return
        
        try:
            edge_name = self.table.item(current_row, 1).text()
            edge_id = self.table.item(current_row, 0).data(Qt.UserRole)
            
            # Проверяем, используется ли гурт в монетах
            from database.models import Coin
            coin_count = self.db_manager.session.query(Coin).filter_by(edge_id=edge_id).count()
            
            if coin_count > 0:
                QMessageBox.warning(self, "Предупреждение", 
                    f"Нельзя удалить гурт '{edge_name}', так как он используется в {coin_count} монетах.")
                return
            
            reply = QMessageBox.question(
                self, "Подтверждение",
                f"Вы уверены, что хотите удалить гурт '{edge_name}'?",
                QMessageBox.Yes | QMessageBox.No
            )
            
            if reply == QMessageBox.Yes:
                from database.models import Edge
                edge = self.db_manager.session.query(Edge).get(edge_id)
                if edge:
                    self.db_manager.session.delete(edge)
                    self.db_manager.session.commit()
                    QMessageBox.information(self, "Успех", "Гурт удален")
                    self.load_edges()
        except Exception as e:
            self.logger.error(f"Ошибка при удалении гурта: {e}")
            QMessageBox.critical(self, "Ошибка", f"Не удалось удалить гурт: {e}")