# ===== gui/widgets/notebook/note_list.py =====
# НОВЫЙ ФАЙЛ

# -*- coding: utf-8 -*-

"""
Список заметок с фильтрацией и группировкой
"""

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QListWidget, QListWidgetItem,
    QLabel, QLineEdit, QComboBox, QPushButton, QMenu
)
from PySide6.QtCore import Qt, Signal, QPoint
from PySide6.QtGui import QColor, QAction

from database.models import NotebookNote, NotebookCategory


class NoteListWidget(QWidget):
    """Виджет списка заметок с фильтрацией"""
    
    note_selected = Signal(int)  # Сигнал при выборе заметки (id)
    
    def __init__(self, db_manager, parent=None):
        super().__init__(parent)
        self.db_manager = db_manager
        self.current_filter = 'active'  # 'active', 'archived', 'trash'
        self.current_category_id = None
        self.search_text = ""
        
        self.init_ui()
    
    def init_ui(self):
        """Инициализация интерфейса"""
        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(3)
        self.setLayout(layout)
        
        # Панель фильтров
        filter_panel = self._create_filter_panel()
        layout.addWidget(filter_panel)
        
        # Список заметок
        self.note_list = QListWidget()
        self.note_list.setAlternatingRowColors(True)
        self.note_list.itemClicked.connect(self._on_item_clicked)
        self.note_list.setContextMenuPolicy(Qt.CustomContextMenu)
        self.note_list.customContextMenuRequested.connect(self._show_context_menu)
        layout.addWidget(self.note_list)
        
        # Статус
        self.status_label = QLabel("Заметок: 0")
        self.status_label.setStyleSheet("color: #666; font-size: 10px; padding: 2px;")
        layout.addWidget(self.status_label)
    
    def _create_filter_panel(self):
        """Создаёт панель фильтрации"""
        panel = QWidget()
        panel.setStyleSheet("""
            QWidget {
                background-color: #f5f5f5;
                border-radius: 3px;
                padding: 3px;
            }
        """)
        layout = QHBoxLayout()
        layout.setContentsMargins(5, 3, 5, 3)
        panel.setLayout(layout)
        
        # Фильтр по статусу
        layout.addWidget(QLabel("Статус:"))
        self.status_combo = QComboBox()
        self.status_combo.addItem("📌 Активные", "active")
        self.status_combo.addItem("📦 Архив", "archived")
        self.status_combo.addItem("🗑️ Корзина", "trash")
        self.status_combo.currentIndexChanged.connect(self._on_filter_changed)
        layout.addWidget(self.status_combo)
        
        # Фильтр по категории
        layout.addWidget(QLabel("Категория:"))
        self.category_combo = QComboBox()
        self.category_combo.addItem("📁 Все", None)
        self.category_combo.currentIndexChanged.connect(self._on_category_changed)
        layout.addWidget(self.category_combo)
        
        layout.addStretch()
        
        # Поиск
        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText("🔍 Поиск...")
        self.search_edit.setMinimumWidth(150)
        self.search_edit.textChanged.connect(self._on_search_changed)
        layout.addWidget(self.search_edit)
        
        return panel
    
    def load_categories(self):
        """Загружает категории в комбобокс"""
        categories = self.db_manager.session.query(NotebookCategory).order_by(
            NotebookCategory.sort_order
        ).all()
        
        self.category_combo.blockSignals(True)
        current_id = self.category_combo.currentData()
        
        self.category_combo.clear()
        self.category_combo.addItem("📁 Все", None)
        
        for cat in categories:
            self.category_combo.addItem(f"{cat.icon} {cat.name}", cat.id)
        
        if current_id:
            idx = self.category_combo.findData(current_id)
            if idx >= 0:
                self.category_combo.setCurrentIndex(idx)
        
        self.category_combo.blockSignals(False)
    
# ===== gui/widgets/notebook/note_list.py =====
# В МЕТОДЕ load_notes, ЗАМЕНИТЬ создание item (для отображения без HTML тегов)

    def load_notes(self):
        """Загружает заметки в список"""
        query = self.db_manager.session.query(NotebookNote)
        
        # Фильтр по статусу
        if self.current_filter == 'active':
            query = query.filter(
                NotebookNote.is_archived == False,
                NotebookNote.is_trashed == False
            )
        elif self.current_filter == 'archived':
            query = query.filter(NotebookNote.is_archived == True)
        elif self.current_filter == 'trash':
            query = query.filter(NotebookNote.is_trashed == True)
        
        # Фильтр по категории
        if self.current_category_id:
            query = query.filter(NotebookNote.category_id == self.current_category_id)
        
        # Поиск
        if self.search_text:
            query = query.filter(
                (NotebookNote.title.contains(self.search_text)) |
                (NotebookNote.content.contains(self.search_text))
            )
        
        # Сортировка: сначала закреплённые, потом по дате
        notes = query.order_by(
            NotebookNote.is_pinned.desc(),
            NotebookNote.updated_at.desc()
        ).all()
        
        self.note_list.clear()
        
        for note in notes:
            # Иконка типа
            type_icons = {'note': '📝', 'task': '☑', 'checklist': '📋'}
            icon = type_icons.get(note.note_type, '📝')
            
            # Заголовок
            title = note.title
            if note.is_pinned:
                title = f"📌 {title}"
            
            # Количество невыполненных задач
            if note.tasks:
                pending = sum(1 for t in note.tasks if not t.is_checked)
                if pending > 0:
                    title = f"{title} ({pending})"
            
            # Для списка удаляем HTML теги из заголовка (если есть)
            import re
            clean_title = re.sub(r'<[^>]+>', '', title)
            
            item = QListWidgetItem(f"{icon} {clean_title}")
            item.setData(Qt.UserRole, note.id)
            
            # Цвет для закреплённых
            if note.is_pinned:
                item.setBackground(QColor(255, 248, 225))
            
            # Цвет для заметок с напоминанием
            if note.remind_at and not note.remind_sent:
                item.setForeground(QColor(231, 76, 60))
            
            self.note_list.addItem(item)
        
        self.status_label.setText(f"Заметок: {len(notes)}")

    def _on_filter_changed(self):
        """Обработчик изменения фильтра статуса"""
        self.current_filter = self.status_combo.currentData()
        self.load_notes()
    
    def _on_category_changed(self):
        """Обработчик изменения фильтра категории"""
        self.current_category_id = self.category_combo.currentData()
        self.load_notes()
    
    def _on_search_changed(self, text):
        """Обработчик поиска"""
        self.search_text = text.strip().lower()
        self.load_notes()
    
    def _on_item_clicked(self, item):
        """Обработчик выбора заметки"""
        note_id = item.data(Qt.UserRole)
        self.note_selected.emit(note_id)
    
    def _show_context_menu(self, position: QPoint):
        """Контекстное меню для заметки"""
        item = self.note_list.itemAt(position)
        if not item:
            return
        
        note_id = item.data(Qt.UserRole)
        note = self.db_manager.session.query(NotebookNote).get(note_id)
        if not note:
            return
        
        menu = QMenu(self)
        
        # Пункты меню
        if note.is_pinned:
            pin_action = QAction("📌 Открепить", self)
            pin_action.triggered.connect(lambda: self._toggle_pin(note))
        else:
            pin_action = QAction("📍 Закрепить", self)
            pin_action.triggered.connect(lambda: self._toggle_pin(note))
        menu.addAction(pin_action)
        
        menu.addSeparator()
        
        if note.is_archived:
            unarchive_action = QAction("📂 Восстановить из архива", self)
            unarchive_action.triggered.connect(lambda: self._toggle_archive(note))
            menu.addAction(unarchive_action)
        else:
            archive_action = QAction("📦 В архив", self)
            archive_action.triggered.connect(lambda: self._toggle_archive(note))
            menu.addAction(archive_action)
        
        if not note.is_trashed:
            trash_action = QAction("🗑️ В корзину", self)
            trash_action.triggered.connect(lambda: self._move_to_trash(note))
            menu.addAction(trash_action)
        else:
            restore_action = QAction("🔄 Восстановить", self)
            restore_action.triggered.connect(lambda: self._restore_from_trash(note))
            menu.addAction(restore_action)
            
            menu.addSeparator()
            
            delete_action = QAction("💀 Удалить навсегда", self)
            delete_action.triggered.connect(lambda: self._delete_permanently(note))
            menu.addAction(delete_action)
        
        menu.exec(self.note_list.mapToGlobal(position))
    
    def _toggle_pin(self, note):
        """Закрепить/открепить"""
        note.is_pinned = not note.is_pinned
        note.updated_at = datetime.now()
        self.db_manager.session.commit()
        self.load_notes()
    
    def _toggle_archive(self, note):
        """Архивировать/восстановить"""
        note.is_archived = not note.is_archived
        if note.is_archived:
            note.is_pinned = False
        note.updated_at = datetime.now()
        self.db_manager.session.commit()
        self.load_notes()
    
    def _move_to_trash(self, note):
        """Переместить в корзину"""
        from PySide6.QtWidgets import QMessageBox
        reply = QMessageBox.question(self, "Подтверждение",
                                     f"Переместить '{note.title}' в корзину?",
                                     QMessageBox.Yes | QMessageBox.No)
        if reply == QMessageBox.Yes:
            note.is_trashed = True
            note.is_archived = False
            note.is_pinned = False
            note.deleted_at = datetime.now()
            self.db_manager.session.commit()
            self.load_notes()
    
    def _restore_from_trash(self, note):
        """Восстановить из корзины"""
        note.is_trashed = False
        note.deleted_at = None
        self.db_manager.session.commit()
        self.load_notes()
    
    def _delete_permanently(self, note):
        """Удалить навсегда"""
        from PySide6.QtWidgets import QMessageBox
        reply = QMessageBox.question(self, "Подтверждение",
                                     f"Удалить '{note.title}' навсегда?\nЭто действие нельзя отменить!",
                                     QMessageBox.Yes | QMessageBox.No)
        if reply == QMessageBox.Yes:
            self.db_manager.session.delete(note)
            self.db_manager.session.commit()
            self.load_notes()
    
    def refresh(self):
        """Обновляет список заметок"""
        self.load_categories()
        self.load_notes()