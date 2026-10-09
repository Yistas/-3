# ===== gui/widgets/notebook/category_manager.py =====
# НОВЫЙ ФАЙЛ

# -*- coding: utf-8 -*-

"""
Диалог управления категориями заметок
"""

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QPushButton, QTableWidget,
    QTableWidgetItem, QHeaderView, QMessageBox, QInputDialog,
    QColorDialog, QAbstractItemView
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor

from database.models import NotebookCategory


class CategoryManagerDialog(QDialog):
    """Диалог управления категориями"""
    
    categories_changed = Signal()
    
    def __init__(self, db_manager, parent=None):
        super().__init__(parent)
        self.db_manager = db_manager
        
        self.setWindowTitle("Управление категориями")
        self.setMinimumSize(500, 400)
        
        self.init_ui()
        self.load_categories()
    
    def init_ui(self):
        """Инициализация интерфейса"""
        layout = QVBoxLayout()
        self.setLayout(layout)
        
        # Заголовок
        title = QLabel("📁 Управление категориями заметок")
        title.setStyleSheet("""
            font-weight: bold;
            font-size: 14px;
            padding: 5px;
            background-color: #4a6fa5;
            color: white;
            border-radius: 3px;
        """)
        title.setAlignment(Qt.AlignCenter)
        layout.addWidget(title)
        
        # Таблица категорий
        self.table = QTableWidget()
        self.table.setColumnCount(4)
        self.table.setHorizontalHeaderLabels(["Иконка", "Название", "Цвет", ""])
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setAlternatingRowColors(True)
        
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.Stretch)
        header.setSectionResizeMode(2, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(3, QHeaderView.ResizeToContents)
        
        layout.addWidget(self.table)
        
        # Панель кнопок
        button_layout = QHBoxLayout()
        
        add_btn = QPushButton("➕ Добавить")
        add_btn.clicked.connect(self.add_category)
        button_layout.addWidget(add_btn)
        
        edit_btn = QPushButton("✏️ Редактировать")
        edit_btn.clicked.connect(self.edit_category)
        button_layout.addWidget(edit_btn)
        
        delete_btn = QPushButton("🗑️ Удалить")
        delete_btn.clicked.connect(self.delete_category)
        button_layout.addWidget(delete_btn)
        
        button_layout.addStretch()
        
        close_btn = QPushButton("❌ Закрыть")
        close_btn.clicked.connect(self.accept)
        button_layout.addWidget(close_btn)
        
        layout.addLayout(button_layout)
    
    def load_categories(self):
        """Загружает категории в таблицу"""
        categories = self.db_manager.session.query(NotebookCategory).order_by(
            NotebookCategory.sort_order
        ).all()
        
        self.table.setRowCount(len(categories))
        self.table.setSortingEnabled(False)
        
        for row, cat in enumerate(categories):
            # Иконка
            icon_item = QTableWidgetItem(cat.icon or "📁")
            icon_item.setTextAlignment(Qt.AlignCenter)
            self.table.setItem(row, 0, icon_item)
            
            # Название
            name_item = QTableWidgetItem(cat.name)
            name_item.setData(Qt.UserRole, cat.id)
            self.table.setItem(row, 1, name_item)
            
            # Цвет
            color_item = QTableWidgetItem("  ")
            color_item.setBackground(QColor(cat.color or "#4a6fa5"))
            color_item.setTextAlignment(Qt.AlignCenter)
            self.table.setItem(row, 2, color_item)
            
            # Кнопка перемещения вверх/вниз
            move_widget = QWidget()
            move_layout = QHBoxLayout()
            move_layout.setContentsMargins(0, 0, 0, 0)
            move_layout.setSpacing(2)
            move_widget.setLayout(move_layout)
            
            up_btn = QPushButton("▲")
            up_btn.setFixedSize(25, 22)
            up_btn.clicked.connect(lambda checked, r=row: self.move_up(r))
            move_layout.addWidget(up_btn)
            
            down_btn = QPushButton("▼")
            down_btn.setFixedSize(25, 22)
            down_btn.clicked.connect(lambda checked, r=row: self.move_down(r))
            move_layout.addWidget(down_btn)
            
            self.table.setCellWidget(row, 3, move_widget)
        
        self.table.setSortingEnabled(True)
        self.table.resizeColumnsToContents()
    
    def add_category(self):
        """Добавляет новую категорию"""
        name, ok = QInputDialog.getText(self, "Новая категория", "Введите название:")
        if not ok or not name.strip():
            return
        
        icon, ok = QInputDialog.getText(self, "Иконка категории", 
                                        "Введите иконку (эмодзи):", text="📁")
        if not ok:
            icon = "📁"
        
        color = QColorDialog.getColor(QColor("#4a6fa5"), self, "Выберите цвет")
        if not color.isValid():
            color = QColor("#4a6fa5")
        
        category = NotebookCategory(
            name=name.strip(),
            icon=icon[:2],
            color=color.name(),
            sort_order=self.db_manager.session.query(NotebookCategory).count()
        )
        
        self.db_manager.session.add(category)
        self.db_manager.session.commit()
        
        self.load_categories()
        self.categories_changed.emit()
    
    def edit_category(self):
        """Редактирует выбранную категорию"""
        current_row = self.table.currentRow()
        if current_row < 0:
            QMessageBox.warning(self, "Предупреждение", "Выберите категорию")
            return
        
        cat_id = self.table.item(current_row, 1).data(Qt.UserRole)
        category = self.db_manager.session.query(NotebookCategory).get(cat_id)
        
        if not category:
            return
        
        # Редактируем название
        name, ok = QInputDialog.getText(self, "Редактирование", 
                                        "Название:", text=category.name)
        if ok and name.strip():
            category.name = name.strip()
        
        # Редактируем иконку
        icon, ok = QInputDialog.getText(self, "Иконка категории", 
                                        "Иконка (эмодзи):", text=category.icon or "📁")
        if ok:
            category.icon = icon[:2]
        
        # Редактируем цвет
        color = QColorDialog.getColor(QColor(category.color or "#4a6fa5"), self, "Выберите цвет")
        if color.isValid():
            category.color = color.name()
        
        self.db_manager.session.commit()
        self.load_categories()
        self.categories_changed.emit()
    
    def delete_category(self):
        """Удаляет выбранную категорию"""
        current_row = self.table.currentRow()
        if current_row < 0:
            QMessageBox.warning(self, "Предупреждение", "Выберите категорию")
            return
        
        cat_id = self.table.item(current_row, 1).data(Qt.UserRole)
        category = self.db_manager.session.query(NotebookCategory).get(cat_id)
        
        if not category:
            return
        
        # Проверяем, есть ли заметки в этой категории
        notes_count = len(category.notes) if category.notes else 0
        
        if notes_count > 0:
            reply = QMessageBox.question(
                self, "Подтверждение",
                f"В категории '{category.name}' есть {notes_count} заметок.\n"
                f"При удалении категории заметки останутся без категории.\n\n"
                f"Удалить категорию?",
                QMessageBox.Yes | QMessageBox.No
            )
            if reply != QMessageBox.Yes:
                return
            
            # Снимаем категорию с заметок
            for note in category.notes:
                note.category_id = None
        else:
            reply = QMessageBox.question(
                self, "Подтверждение",
                f"Удалить категорию '{category.name}'?",
                QMessageBox.Yes | QMessageBox.No
            )
            if reply != QMessageBox.Yes:
                return
        
        self.db_manager.session.delete(category)
        self.db_manager.session.commit()
        
        self.load_categories()
        self.categories_changed.emit()
    
    def move_up(self, row):
        """Перемещает категорию вверх"""
        if row <= 0:
            return
        
        categories = self.db_manager.session.query(NotebookCategory).order_by(
            NotebookCategory.sort_order
        ).all()
        
        if row >= len(categories):
            return
        
        cat1 = categories[row]
        cat2 = categories[row - 1]
        
        cat1.sort_order, cat2.sort_order = cat2.sort_order, cat1.sort_order
        self.db_manager.session.commit()
        
        self.load_categories()
        self.table.selectRow(row - 1)
        self.categories_changed.emit()
    
    def move_down(self, row):
        """Перемещает категорию вниз"""
        categories = self.db_manager.session.query(NotebookCategory).order_by(
            NotebookCategory.sort_order
        ).all()
        
        if row >= len(categories) - 1:
            return
        
        cat1 = categories[row]
        cat2 = categories[row + 1]
        
        cat1.sort_order, cat2.sort_order = cat2.sort_order, cat1.sort_order
        self.db_manager.session.commit()
        
        self.load_categories()
        self.table.selectRow(row + 1)
        self.categories_changed.emit()