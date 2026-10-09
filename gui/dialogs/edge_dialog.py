# -*- coding: utf-8 -*-

"""
Диалог для добавления и редактирования гурта
"""

import logging
from datetime import datetime
from PySide6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QFormLayout,
                               QPushButton, QLineEdit, QTextEdit,
                               QLabel, QGroupBox, QMessageBox, QScrollArea,
                               QWidget)
from PySide6.QtCore import Qt


class EdgeDialog(QDialog):
    """Диалог для добавления/редактирования гурта"""
    
    def __init__(self, db_manager, parent=None, edge_id=None):
        super().__init__(parent)
        self.logger = logging.getLogger('CoinCollector.GUI.EdgeDialog')
        self.db_manager = db_manager
        self.edge_id = edge_id
        self.edge = None
        
        self.setWindowTitle("Добавление гурта" if not edge_id else "Редактирование гурта")
        self.setMinimumWidth(500)
        self.setMinimumHeight(300)
        
        self.init_ui()
        
        if edge_id:
            self.load_edge_data()
    
    def init_ui(self):
        """Инициализация интерфейса"""
        layout = QVBoxLayout()
        self.setLayout(layout)
        
        # Создаем область с прокруткой
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.NoFrame)
        
        scroll_widget = QWidget()
        scroll_layout = QVBoxLayout()
        scroll_widget.setLayout(scroll_layout)
        
        # === Группа: Основная информация ===
        main_group = QGroupBox("Информация о гурте")
        main_form = QFormLayout()
        
        # Название гурта (обязательное)
        self.name_edit = QLineEdit()
        self.name_edit.setPlaceholderText("например: Рубчатый, Гладкий, Узорчатый")
        self.name_edit.setMinimumHeight(30)
        main_form.addRow("Название*:", self.name_edit)
        
        main_group.setLayout(main_form)
        scroll_layout.addWidget(main_group)
        
        # === Группа: Описание ===
        desc_group = QGroupBox("Описание и примечания")
        desc_layout = QVBoxLayout()
        
        self.description_edit = QTextEdit()
        self.description_edit.setMaximumHeight(150)
        self.description_edit.setMinimumHeight(80)
        self.description_edit.setPlaceholderText("Описание типа гурта...")
        desc_layout.addWidget(self.description_edit)
        
        desc_group.setLayout(desc_layout)
        scroll_layout.addWidget(desc_group)
        
        # Добавляем прокрутку
        scroll.setWidget(scroll_widget)
        layout.addWidget(scroll)
        
        # Информационное сообщение
        info_label = QLabel("* - обязательные поля")
        info_label.setStyleSheet("color: gray; font-size: 10px;")
        layout.addWidget(info_label)
        
        # Кнопки
        button_layout = QHBoxLayout()
        
        save_btn = QPushButton("💾 Сохранить")
        save_btn.clicked.connect(self.save_edge)
        save_btn.setMinimumHeight(35)
        save_btn.setStyleSheet("background-color: #4CAF50; color: white; font-weight: bold;")
        button_layout.addWidget(save_btn)
        
        cancel_btn = QPushButton("❌ Отмена")
        cancel_btn.clicked.connect(self.reject)
        cancel_btn.setMinimumHeight(35)
        button_layout.addWidget(cancel_btn)
        
        layout.addLayout(button_layout)
    
    def collect_data(self):
        """Собирает данные из формы"""
        name = self.name_edit.text().strip()
        
        # Проверка обязательных полей
        if not name:
            QMessageBox.warning(self, "Предупреждение", "Введите название гурта")
            return None
        
        data = {
            'name': name,
            'description': self.description_edit.toPlainText().strip() or None,
        }
        
        return data
    
    def save_edge(self):
        """Сохраняет гурт"""
        data = self.collect_data()
        if not data:
            return
        
        try:
            from database.models import Edge
            
            if self.edge_id:
                # Обновление существующего гурта
                edge = self.db_manager.session.query(Edge).get(self.edge_id)
                if edge:
                    for key, value in data.items():
                        setattr(edge, key, value)
                    edge.updated_at = datetime.now()
                    self.db_manager.session.commit()
                    QMessageBox.information(self, "Успех", "Гурт успешно обновлен")
            else:
                # Добавление нового гурта
                edge = Edge(**data)
                self.db_manager.session.add(edge)
                self.db_manager.session.commit()
                QMessageBox.information(self, "Успех", f"Гурт добавлен с ID {edge.id}")
            
            self.accept()
            
        except Exception as e:
            self.logger.error(f"Ошибка при сохранении гурта: {e}")
            self.db_manager.session.rollback()
            QMessageBox.critical(self, "Ошибка", f"Не удалось сохранить гурт: {e}")
    
    def load_edge_data(self):
        """Загружает данные гурта для редактирования"""
        try:
            from database.models import Edge
            self.edge = self.db_manager.session.query(Edge).get(self.edge_id)
            if not self.edge:
                return
            
            self.name_edit.setText(self.edge.name or "")
            self.description_edit.setText(self.edge.description or "")
            
        except Exception as e:
            self.logger.error(f"Ошибка при загрузке данных гурта: {e}")
            QMessageBox.critical(self, "Ошибка", f"Не удалось загрузить данные гурта: {e}")